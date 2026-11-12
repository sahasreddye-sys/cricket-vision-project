"""Bowling Lab: speed calculator and readings, line-and-length sessions."""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pitchvision import pitchmap, speed
from pitchvision.constants import LENGTH_BANDS, LINE_BANDS, PITCH_LENGTH_M, PITCH_WIDTH_M, POPPING_CREASE_M, WICKET_WIDTH_M

from .. import services
from ..auth import can_edit_player, current_user
from ..models import BowlingSession, Delivery, Player, SpeedReading, User, get_db

router = APIRouter(tags=["bowling"])


class SpeedCalcIn(BaseModel):
    distance: float
    time: float
    distance_unit: Literal["m", "ft", "yd"] = "m"
    time_unit: Literal["s", "ms"] = "s"


@router.post("/speed/calculate")
def calculate(body: SpeedCalcIn):
    """Average ball speed over the measured distance (not a release speed)."""
    try:
        return speed.average_speed(body.distance, body.time, body.distance_unit, body.time_unit)
    except speed.SpeedInputError as e:
        raise HTTPException(422, str(e))


class ReadingIn(BaseModel):
    player_id: int
    date: dt.date
    source: Literal["stopwatch", "radar", "video"] = "stopwatch"
    distance: Optional[float] = Field(default=None, gt=0)
    time: Optional[float] = Field(default=None, gt=0)
    distance_unit: Literal["m", "ft", "yd"] = "m"
    time_unit: Literal["s", "ms"] = "s"
    kmh: Optional[float] = Field(default=None, gt=0, lt=200)
    note: str = Field(default="", max_length=200)


@router.post("/speed/readings", status_code=201)
def add_reading(body: ReadingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Player, body.player_id):
        raise HTTPException(404, "Player not found.")
    can_edit_player(user, body.player_id)
    if body.source == "radar":
        if body.kmh is None:
            raise HTTPException(422, "Enter the radar reading in km/h.")
        r = SpeedReading(player_id=body.player_id, date=body.date, source="radar", kmh=body.kmh, note=body.note)
    else:
        if body.distance is None or body.time is None:
            raise HTTPException(422, "Enter both the distance and the time.")
        try:
            calc = speed.average_speed(body.distance, body.time, body.distance_unit, body.time_unit)
        except speed.SpeedInputError as e:
            raise HTTPException(422, str(e))
        if calc["speed_kmh"] > 200:
            raise HTTPException(422, f"{calc['speed_kmh']:.0f} km/h is faster than any recorded delivery. Check the distance and time.")
        r = SpeedReading(player_id=body.player_id, date=body.date, source=body.source, distance_m=calc["distance_m"],
                         time_s=calc["time_s"], kmh=calc["speed_kmh"], note=body.note)
    db.add(r)
    db.commit()
    return {"id": r.id, "kmh": r.kmh}


@router.delete("/speed/readings/{rid}", status_code=204)
def delete_reading(rid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.get(SpeedReading, rid)
    if not r:
        raise HTTPException(404, "Reading not found.")
    can_edit_player(user, r.player_id)
    db.delete(r)
    db.commit()


@router.get("/speed/history")
def speed_history(player_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """A player's readings with separate summaries for average-speed and radar readings."""
    rows = services.speeds_by_player(db).get(player_id, [])
    avg_rows = [r for r in rows if r["source"] != "radar"]
    radar = [r for r in rows if r["source"] == "radar"]
    out = {"readings": rows,
           "average_speed": {**speed.speed_summary([r["kmh"] for r in avg_rows]),
                             "trend": speed.speed_trend([r["kmh"] for r in avg_rows])},
           "radar": {**speed.speed_summary([r["kmh"] for r in radar]),
                     "trend": speed.speed_trend([r["kmh"] for r in radar])},
           "comparison": None}
    # Compare radar and estimates taken on the same date.
    pairs = []
    for d in sorted({r["date"] for r in radar}):
        est = [r["kmh"] for r in avg_rows if r["date"] == d]
        rad = [r["kmh"] for r in radar if r["date"] == d]
        if est and rad:
            pairs.append({"date": d, **speed.compare_radar_to_estimate(sum(rad) / len(rad), sum(est) / len(est)),
                          "radar_n": len(rad), "estimate_n": len(est)})
    if pairs:
        out["comparison"] = {"by_date": pairs,
                             "mean_difference_kmh": sum(p["difference_kmh"] for p in pairs) / len(pairs),
                             "note": pairs[0]["note"]}
    return out


@router.get("/pitch/geometry")
def geometry():
    """Pitch dimensions and the band thresholds, so the frontend draws exactly what the analytics use."""
    return {"length": PITCH_LENGTH_M, "width": PITCH_WIDTH_M, "popping_crease": POPPING_CREASE_M,
            "wicket_width": WICKET_WIDTH_M,
            "length_bands": [{"name": n, "min": lo, "max": min(hi, PITCH_LENGTH_M)} for n, lo, hi in LENGTH_BANDS],
            "line_bands": [{"name": n, "min": max(lo, -PITCH_WIDTH_M / 2), "max": min(hi, PITCH_WIDTH_M / 2)}
                           for n, lo, hi in LINE_BANDS]}


class SessionIn(BaseModel):
    player_id: int
    date: dt.date
    name: str = Field(default="", max_length=120)
    target_x: float = Field(default=0.2, ge=-1.5, le=1.5)
    target_y: float = Field(default=7.0, ge=0, le=20.12)
    tol_x: float = Field(default=0.2, gt=0, le=1.5)
    tol_y: float = Field(default=1.0, gt=0, le=10)


def session_out(s: BowlingSession, nm: dict) -> dict:
    ds = services.session_deliveries(s)
    return {"id": s.id, "player_id": s.player_id, "player": nm.get(s.player_id, "?"), "date": s.date.isoformat(),
            "name": s.name, "target": {"x": s.target_x, "y": s.target_y, "tol_x": s.tol_x, "tol_y": s.tol_y},
            "count": len(ds), "is_sample": s.is_sample}


def _session(db: Session, sid: int) -> BowlingSession:
    s = db.scalar(select(BowlingSession).options(selectinload(BowlingSession.deliveries)).where(BowlingSession.id == sid))
    if not s:
        raise HTTPException(404, "Session not found.")
    return s


@router.get("/bowling/sessions")
def list_sessions(player_id: Optional[int] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(BowlingSession).options(selectinload(BowlingSession.deliveries)).order_by(BowlingSession.date.desc(), BowlingSession.id.desc())
    if player_id:
        q = q.where(BowlingSession.player_id == player_id)
    nm = services.names(db)
    return [session_out(s, nm) for s in db.scalars(q)]


@router.post("/bowling/sessions", status_code=201)
def create_session(body: SessionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Player, body.player_id):
        raise HTTPException(404, "Player not found.")
    can_edit_player(user, body.player_id)
    s = BowlingSession(**body.model_dump())
    db.add(s)
    db.commit()
    return session_out(_session(db, s.id), services.names(db))


@router.put("/bowling/sessions/{sid}")
def update_session(sid: int, body: SessionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = _session(db, sid)
    can_edit_player(user, s.player_id)
    for k, v in body.model_dump().items():
        if k != "player_id":
            setattr(s, k, v)
    db.commit()
    return session_analysis(sid, db, user)


@router.delete("/bowling/sessions/{sid}", status_code=204)
def delete_session(sid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = _session(db, sid)
    can_edit_player(user, s.player_id)
    db.delete(s)
    db.commit()


class DeliveryIn(BaseModel):
    x: float = Field(ge=-1.6, le=1.6, description="metres from middle stump, + = off side")
    y: float = Field(ge=-1.0, le=20.12, description="metres from the striker's stumps")
    bounced: bool = True


@router.post("/bowling/sessions/{sid}/deliveries", status_code=201)
def add_delivery(sid: int, body: DeliveryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = _session(db, sid)
    can_edit_player(user, s.player_id)
    d = Delivery(session_id=sid, **body.model_dump())
    db.add(d)
    db.commit()
    db.expire_all()
    return session_analysis(sid, db, user)


@router.delete("/bowling/deliveries/{did}")
def delete_delivery(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    d = db.get(Delivery, did)
    if not d:
        raise HTTPException(404, "Delivery not found.")
    s = _session(db, d.session_id)
    can_edit_player(user, s.player_id)
    db.delete(d)
    db.commit()
    db.expire_all()
    return session_analysis(s.id, db, user)


@router.get("/bowling/sessions/{sid}")
def session_analysis(sid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = _session(db, sid)
    ds = services.session_deliveries(s)
    return {**session_out(s, services.names(db)), "deliveries": ds,
            "distribution": pitchmap.distribution(ds),
            "accuracy": pitchmap.accuracy(ds, s.target_x, s.target_y, s.tol_x, s.tol_y),
            "heatmap": pitchmap.heatmap(ds)}


@router.get("/bowling/compare")
def compare(a: int, b: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Compare two sessions against session A's target."""
    sa, sb = _session(db, a), _session(db, b)
    nm = services.names(db)
    res = pitchmap.compare_sessions(services.session_deliveries(sa), services.session_deliveries(sb),
                                    sa.target_x, sa.target_y, sa.tol_x, sa.tol_y)
    return {"session_a": session_out(sa, nm), "session_b": session_out(sb, nm), **res,
            "note": "Both sessions are measured against session A's target."}


@router.get("/bowling/accuracy-trend")
def accuracy_trend(player_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    ss = db.scalars(select(BowlingSession).options(selectinload(BowlingSession.deliveries))
                    .where(BowlingSession.player_id == player_id).order_by(BowlingSession.date, BowlingSession.id)).all()
    out = []
    for s in ss:
        acc = pitchmap.accuracy(services.session_deliveries(s), s.target_x, s.target_y, s.tol_x, s.tol_y)
        if acc["total"]:
            out.append({"session_id": s.id, "date": s.date.isoformat(), "name": s.name, "hit_pct": acc["hit_pct"],
                        "mean_error_m": acc["mean_error_m"], "spread_x": acc["spread_x"], "spread_y": acc["spread_y"],
                        "total": acc["total"]})
    return out
