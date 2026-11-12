"""Fielding Lab, video analysis (pose + ball tracking), DRS Studio, AI Coach, progress tracking."""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitchvision import coach as coach_mod
from pitchvision import ml, pose, stats, tracking, trajectory

from .. import services
from ..auth import can_edit_player, coach_only, current_user
from ..config import settings
from ..models import DrsReview, FieldingEvent, FieldSetup, Goal, Match, Player, TrainingLog, User, VideoAnalysis, _now, get_db
from .core import goal_out, training_out

router = APIRouter()

# ------------------------------------------------------------------ fielding

FieldKind = Literal["catch", "drop", "run_out", "direct_hit", "missed_run_out", "stumping", "missed_stumping",
                    "clean_stop", "misfield"]


class FieldEventIn(BaseModel):
    player_id: int
    date: dt.date
    kind: FieldKind
    count: int = Field(default=1, ge=1, le=50)
    match_id: Optional[int] = None


@router.post("/fielding/events", tags=["fielding"], status_code=201)
def add_event(body: FieldEventIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Player, body.player_id):
        raise HTTPException(404, "Player not found.")
    if body.match_id and not db.get(Match, body.match_id):
        raise HTTPException(404, "Match not found.")
    can_edit_player(user, body.player_id)
    e = FieldingEvent(**body.model_dump())
    db.add(e)
    db.commit()
    return {"id": e.id}


@router.get("/fielding/events", tags=["fielding"])
def list_events(player_id: Optional[int] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(FieldingEvent).order_by(FieldingEvent.date.desc(), FieldingEvent.id.desc()).limit(200)
    if player_id:
        q = q.where(FieldingEvent.player_id == player_id)
    nm = services.names(db)
    return [{"id": e.id, "player_id": e.player_id, "player": nm.get(e.player_id, "?"), "date": e.date.isoformat(),
             "kind": e.kind, "count": e.count, "match_id": e.match_id} for e in db.scalars(q)]


@router.delete("/fielding/events/{eid}", tags=["fielding"], status_code=204)
def delete_event(eid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = db.get(FieldingEvent, eid)
    if not e:
        raise HTTPException(404, "Event not found.")
    can_edit_player(user, e.player_id)
    db.delete(e)
    db.commit()


@router.get("/fielding/positions", tags=["fielding"])
def positions():
    return [{"name": k, "angle": a, "distance": d} for k, (a, d) in stats.FIELD_POSITIONS.items()]


class FieldPos(BaseModel):
    name: str = Field(max_length=40)
    angle: float = Field(ge=0, lt=360)
    distance: float = Field(ge=0, le=1)


class SetupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    style: Literal["attacking", "balanced", "defensive"] = "balanced"
    positions: list[FieldPos] = Field(max_length=9)
    notes: str = ""


def setup_out(s: FieldSetup) -> dict:
    return {"id": s.id, "name": s.name, "style": s.style, "positions": s.positions, "notes": s.notes,
            "created_at": s.created_at.isoformat()}


@router.get("/fielding/setups", tags=["fielding"])
def list_setups(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [setup_out(s) for s in db.scalars(select(FieldSetup).order_by(FieldSetup.created_at.desc()))]


@router.post("/fielding/setups", tags=["fielding"], status_code=201)
def save_setup(body: SetupIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    s = FieldSetup(name=body.name.strip(), style=body.style, positions=[p.model_dump() for p in body.positions], notes=body.notes)
    db.add(s)
    db.commit()
    return setup_out(s)


@router.delete("/fielding/setups/{sid}", tags=["fielding"], status_code=204)
def delete_setup(sid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    s = db.get(FieldSetup, sid)
    if not s:
        raise HTTPException(404, "Field setup not found.")
    db.delete(s)
    db.commit()


@router.get("/fielding/recommend", tags=["fielding"])
def recommend(batter_id: int, style: Literal["attacking", "balanced", "defensive"] = "balanced",
              db: Session = Depends(get_db), _: User = Depends(current_user)):
    shots = [b for b in services.collect(db)["balls"] if b["striker"] == batter_id]
    return {**stats.recommend_field(shots, style), "wagon_wheel": stats.wagon_wheel(shots)}


# ------------------------------------------------------------------ video

ALLOWED_EXT = {".mp4", ".mov", ".avi", ".webm", ".m4v", ".mkv"}


async def _save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"Unsupported file type '{ext or 'none'}'. Upload one of: {', '.join(sorted(ALLOWED_EXT))}.")
    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")       # never trust the client's file name
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with open(path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                os.remove(path)
                raise HTTPException(413, f"The video is larger than {settings.max_upload_mb} MB. Trim it to the delivery itself.")
            out.write(chunk)
    if size == 0:
        os.remove(path)
        raise HTTPException(422, "The uploaded file is empty.")
    return path


def _analysis_out(v: VideoAnalysis, nm: dict, full: bool = True) -> dict:
    out = {"id": v.id, "kind": v.kind, "player_id": v.player_id, "player": nm.get(v.player_id) if v.player_id else None,
           "filename": v.filename, "label": v.label, "status": v.status, "created_at": v.created_at.isoformat()}
    if full:
        out["result"] = v.result
    return out


@router.post("/video/pose", tags=["video"])
async def video_pose(file: UploadFile = File(...), mode: Literal["bowling", "batting", "catching"] = Form("bowling"),
                     player_id: Optional[int] = Form(None), label: str = Form(""), arm: Optional[str] = Form(None),
                     db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Pose analysis of a bowling, batting or catching clip."""
    path = await _save_upload(file)
    try:
        result = pose.analyse_video(path, mode=mode, arm=arm if arm in ("left", "right") else None)
    except tracking.VideoError as e:
        raise HTTPException(422, str(e))
    except pose.PoseError as e:
        raise HTTPException(503, str(e))
    finally:
        if os.path.exists(path):
            os.remove(path)          # the video itself is not kept; only the measurements are
    v = VideoAnalysis(player_id=player_id, kind=mode, filename=(file.filename or "video")[:255], label=label[:120],
                      status=result["status"], result=result)
    db.add(v)
    db.commit()
    return _analysis_out(v, services.names(db))


@router.post("/video/track", tags=["video"])
async def video_track(file: UploadFile = File(...), colour: Optional[str] = Form(None),
                      calibration: Optional[str] = Form(None), player_id: Optional[int] = Form(None),
                      label: str = Form(""), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Track the ball. `calibration` (optional JSON): [[u, v], ...] image points for the four pitch corners,
    in the order returned by GET /video/calibration-targets."""
    path = await _save_upload(file)
    try:
        res = tracking.track_ball(path, colour=colour if colour in tracking.BALL_COLOURS else None)
    except tracking.VideoError as e:
        raise HTTPException(422, str(e))
    finally:
        if os.path.exists(path):
            os.remove(path)
    result = _interpret_track(res, calibration)
    v = VideoAnalysis(player_id=player_id, kind="tracking", filename=(file.filename or "video")[:255], label=label[:120],
                      status=result["status"], result=result)
    db.add(v)
    db.commit()
    return _analysis_out(v, services.names(db))


def _interpret_track(res: dict, calibration: Optional[str]) -> dict:
    pts = res["points"]
    out = {**res, "bounce": None, "movement": None, "pitching": None, "calibrated": False}
    if res["status"] != "ok":
        return out
    bounce = trajectory.detect_bounce(pts)
    out["bounce"] = bounce
    obs = [p for p in pts if p["observed"]]
    idx = bounce["index"] if bounce.get("found") else None
    out["movement"] = trajectory.lateral_movement(obs, idx, units="px")
    if calibration:
        try:
            img_pts = json.loads(calibration)
            targets = trajectory.standard_calibration_targets()
            h = trajectory.fit_homography(img_pts, [[t["x"], t["y"]] for t in targets])
            out["calibrated"] = True
            if bounce.get("found"):
                x, y = trajectory.image_to_pitch(h, bounce["x"], bounce["y"])
                from pitchvision import pitchmap
                plausible = pitchmap.in_pitch_bounds(x, y)
                out["pitching"] = {"x": x, "y": y, "plausible": plausible,
                                   "length": pitchmap.classify_length(y) if plausible else None,
                                   "line": pitchmap.classify_line(x) if plausible else None,
                                   "note": "Located by mapping the bounce point through the ground-plane calibration. "
                                           "Accuracy depends on how precisely the four pitch corners were marked." if plausible
                                   else "The mapped bounce point falls outside the pitch. Re-check the calibration points."}
        except (ValueError, json.JSONDecodeError) as e:
            out["calibration_error"] = str(e)
    return out


@router.get("/video/calibration-targets", tags=["video"])
def calibration_targets():
    return trajectory.standard_calibration_targets()


@router.get("/video/analyses", tags=["video"])
def list_analyses(kind: Optional[str] = None, player_id: Optional[int] = None, db: Session = Depends(get_db),
                  _: User = Depends(current_user)):
    q = select(VideoAnalysis).order_by(VideoAnalysis.created_at.desc()).limit(100)
    if kind:
        q = q.where(VideoAnalysis.kind == kind)
    if player_id:
        q = q.where(VideoAnalysis.player_id == player_id)
    nm = services.names(db)
    return [_analysis_out(v, nm, full=False) for v in db.scalars(q)]


@router.get("/video/analyses/{vid}", tags=["video"])
def get_analysis(vid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    v = db.get(VideoAnalysis, vid)
    if not v:
        raise HTTPException(404, "Analysis not found.")
    return _analysis_out(v, services.names(db))


@router.delete("/video/analyses/{vid}", tags=["video"], status_code=204)
def delete_analysis(vid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    v = db.get(VideoAnalysis, vid)
    if not v:
        raise HTTPException(404, "Analysis not found.")
    db.delete(v)
    db.commit()


@router.get("/video/compare", tags=["video"])
def compare_videos(a: int, b: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    va, vb = db.get(VideoAnalysis, a), db.get(VideoAnalysis, b)
    if not va or not vb:
        raise HTTPException(404, "Analysis not found.")
    if va.kind != vb.kind:
        raise HTTPException(422, "Choose two analyses of the same kind (for example two bowling clips).")
    if va.kind == "tracking":
        ma, mb = va.result.get("movement") or {}, vb.result.get("movement") or {}
        row = lambda key, sub: {"metric": f"{key} {sub}", "a": (ma.get(key) or {}).get(sub), "b": (mb.get(key) or {}).get(sub)}
        rows = [row("swing", "deviation"), row("swing", "z"), row("seam", "change"), row("seam", "z")]
        for r in rows:
            r["difference"] = r["b"] - r["a"] if r["a"] is not None and r["b"] is not None else None
        return {"kind": "tracking", "rows": rows,
                "labels": {"a": {k: (ma.get(k) or {}).get("label") for k in ("swing", "seam")},
                           "b": {k: (mb.get(k) or {}).get("label") for k in ("swing", "seam")}},
                "note": "Pixel values are comparable only when both clips come from the same fixed camera position."}
    return {"kind": va.kind, **pose.compare_analyses(va.result, vb.result)}


# ------------------------------------------------------------------ DRS

class DrsIn(BaseModel):
    pitch_x: Optional[float] = Field(default=None, ge=-1.6, le=1.6)
    pitch_y: Optional[float] = Field(default=None, ge=0, le=20.12)
    impact_x: Optional[float] = Field(default=None, ge=-1.6, le=1.6)
    impact_y: Optional[float] = Field(default=None, ge=0, le=20.12)
    impact_z: Optional[float] = Field(default=None, ge=0, le=2.5)
    speed_kmh: float = Field(default=100, gt=0, le=180)
    position_sigma_m: float = Field(default=0.03, ge=0.005, le=0.5)
    speed_sigma_pct: float = Field(default=10, ge=0, le=50)
    no_ball: bool = False
    shot_offered: bool = True
    hit_bat_first: bool = False
    source: Literal["manual", "video"] = "manual"
    label: str = Field(default="", max_length=120)
    save: bool = False


@router.post("/drs/simulate", tags=["drs"])
def drs(body: DrsIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Educational LBW simulation. Not an official DRS."""
    args = body.model_dump(exclude={"label", "save"})
    res = trajectory.simulate_drs(**args)
    if body.save:
        r = DrsReview(label=body.label, inputs=args, decision=res["decision"], lbw=res.get("lbw"))
        db.add(r)
        db.commit()
        res["saved_id"] = r.id
    return res


@router.get("/drs/reviews", tags=["drs"])
def drs_reviews(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": r.id, "label": r.label, "inputs": r.inputs, "decision": r.decision, "lbw": r.lbw,
             "created_at": r.created_at.isoformat()}
            for r in db.scalars(select(DrsReview).order_by(DrsReview.created_at.desc()).limit(50))]


@router.delete("/drs/reviews/{rid}", tags=["drs"], status_code=204)
def delete_review(rid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    r = db.get(DrsReview, rid)
    if not r:
        raise HTTPException(404, "Review not found.")
    db.delete(r)
    db.commit()


# ------------------------------------------------------------------ AI coach

class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    player_id: Optional[int] = None
    use_llm: bool = False


@router.post("/coach/ask", tags=["coach"])
def ask(body: AskIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    me = body.player_id or user.player_id
    ctx = services.coach_context(db, me)
    res = coach_mod.answer(body.question, ctx, use_llm=body.use_llm)
    res.pop("facts", None)
    res["about_player"] = next((p["name"] for p in ctx["players"] if p["id"] == me), None)
    return res


@router.get("/coach/suggestions", tags=["coach"])
def suggestions():
    return coach_mod.SUGGESTED_QUESTIONS


@router.get("/coach/recommendations", tags=["coach"])
def recommendations(player_id: Optional[int] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    ctx = services.coach_context(db, player_id)
    if player_id:
        return {"player_id": player_id, "recommendations": coach_mod.player_recommendations(ctx, player_id)}
    return {"team": coach_mod.team_insights(ctx),
            "players": [{"player_id": p["id"], "name": p["name"], "recommendations": recs}
                        for p in ctx["players"] if (recs := coach_mod.player_recommendations(ctx, p["id"]))]}


@router.get("/ml/dot-ball-model", tags=["ml"])
def dot_ball_model(db: Session = Depends(get_db), _: User = Depends(current_user)):
    balls = [b for b in services.collect(db)["balls"] if b["batting_side"] == "them"]
    res = ml.train_dot_ball_model(balls)
    res.pop("model", None)
    return res


# ------------------------------------------------------------------ progress

class TrainingIn(BaseModel):
    player_id: int
    date: dt.date
    kind: Literal["batting", "bowling", "fielding", "fitness", "match"]
    duration_min: int = Field(ge=1, le=600)
    intensity: int = Field(default=3, ge=1, le=5)
    notes: str = Field(default="", max_length=2000)


@router.post("/training", tags=["progress"], status_code=201)
def add_training(body: TrainingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Player, body.player_id):
        raise HTTPException(404, "Player not found.")
    can_edit_player(user, body.player_id)
    x = TrainingLog(**body.model_dump())
    db.add(x)
    db.commit()
    return training_out(x)


@router.delete("/training/{tid}", tags=["progress"], status_code=204)
def delete_training(tid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    x = db.get(TrainingLog, tid)
    if not x:
        raise HTTPException(404, "Training entry not found.")
    can_edit_player(user, x.player_id)
    db.delete(x)
    db.commit()


class GoalIn(BaseModel):
    player_id: int
    title: str = Field(min_length=1, max_length=200)
    metric: Optional[Literal["max_speed", "batting_average", "strike_rate", "wickets", "runs", "economy",
                             "catch_pct", "accuracy_pct"]] = None
    target_value: Optional[float] = None
    due_date: Optional[dt.date] = None


@router.post("/goals", tags=["progress"], status_code=201)
def add_goal(body: GoalIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Player, body.player_id):
        raise HTTPException(404, "Player not found.")
    can_edit_player(user, body.player_id)
    if body.metric and body.target_value is None:
        raise HTTPException(422, "Enter a target value for a measured goal.")
    g = Goal(**body.model_dump())
    db.add(g)
    db.commit()
    return goal_out(g)


class GoalPatch(BaseModel):
    status: Literal["open", "achieved", "dropped"]


@router.patch("/goals/{gid}", tags=["progress"])
def patch_goal(gid: int, body: GoalPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    g = db.get(Goal, gid)
    if not g:
        raise HTTPException(404, "Goal not found.")
    can_edit_player(user, g.player_id)
    g.status = body.status
    g.achieved_at = _now() if body.status == "achieved" else None
    db.commit()
    return goal_out(g)


@router.delete("/goals/{gid}", tags=["progress"], status_code=204)
def delete_goal(gid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    g = db.get(Goal, gid)
    if not g:
        raise HTTPException(404, "Goal not found.")
    can_edit_player(user, g.player_id)
    db.delete(g)
    db.commit()


def _goal_value(metric: str, pid: int, t: dict, speeds: dict, acc: dict) -> Optional[float]:
    pick = lambda rows: next((r for r in rows if r["player"] == pid), None) or {}
    if metric == "max_speed":
        return max((s["kmh"] for s in speeds.get(pid, [])), default=None)
    if metric == "accuracy_pct":
        return (acc.get(pid) or {}).get("hit_pct")
    if metric in ("batting_average", "strike_rate", "runs"):
        return pick(t["batting"]).get({"batting_average": "average"}.get(metric, metric))
    if metric in ("wickets", "economy"):
        return pick(t["bowling"]).get(metric)
    if metric == "catch_pct":
        return pick(t["fielding"]).get("catch_pct")
    return None


@router.get("/progress", tags=["progress"])
def progress(player_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Training load by week and month, goals with their current measured value, and milestones."""
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(404, "Player not found.")
    logs = list(db.scalars(select(TrainingLog).where(TrainingLog.player_id == player_id).order_by(TrainingLog.date)))
    weekly: dict = {}
    monthly: dict = {}
    for x in logs:
        wk = (x.date - dt.timedelta(days=x.date.weekday())).isoformat()
        for bucket, key in ((weekly, wk), (monthly, x.date.strftime("%Y-%m"))):
            b = bucket.setdefault(key, {"period": key, "sessions": 0, "minutes": 0, "batting": 0, "bowling": 0,
                                        "fielding": 0, "fitness": 0, "match": 0})
            b["sessions"] += 1
            b["minutes"] += x.duration_min
            b[x.kind] += x.duration_min
    t = services.career_tables(db)
    speeds = services.speeds_by_player(db)
    acc = services.accuracy_by_player(db)
    goals = []
    for g in db.scalars(select(Goal).where(Goal.player_id == player_id).order_by(Goal.created_at.desc())):
        row = goal_out(g)
        if g.metric:
            cur = _goal_value(g.metric, player_id, t, speeds, acc)
            row["current_value"] = cur
            lower_better = g.metric == "economy"
            row["met"] = None if cur is None or g.target_value is None else (
                cur <= g.target_value if lower_better else cur >= g.target_value)
        goals.append(row)
    bat = next((r for r in t["batting"] if r["player"] == player_id), None)
    bowl = next((r for r in t["bowling"] if r["player"] == player_id), None)
    milestones = []
    if bat:
        best = max(bat["scores"], key=lambda s: s["runs"])
        milestones.append({"title": f"Highest score: {bat['highest_text']}", "date": best.get("date")})
        for mark in (50, 100, 250, 500, 1000):
            total = 0
            for s in bat["scores"]:
                total += s["runs"]
                if total >= mark:
                    milestones.append({"title": f"{mark} runs for the team", "date": s.get("date")})
                    break
        first50 = next((s for s in bat["scores"] if s["runs"] >= 50), None)
        if first50:
            milestones.append({"title": "First score of 50 or more", "date": first50.get("date")})
    if bowl:
        total = 0
        for mark in (10, 25, 50):
            total = 0
            for s in bowl["spells"]:
                total += s["wickets"]
                if total >= mark:
                    milestones.append({"title": f"{mark} wickets for the team", "date": s.get("date")})
                    break
        if bowl["best_wickets"] > 0:
            milestones.append({"title": f"Best bowling: {bowl['best']}", "date": None})
    sp = speeds.get(player_id, [])
    if sp:
        top = max(sp, key=lambda s: s["kmh"])
        milestones.append({"title": f"Fastest recorded ball: {top['kmh']:.1f} km/h ({top['source']})", "date": top["date"]})
    for g in goals:
        if g["status"] == "achieved":
            milestones.append({"title": f"Goal achieved: {g['title']}", "date": (g["achieved_at"] or "")[:10]})
    milestones.sort(key=lambda m: m["date"] or "", reverse=True)
    return {"player": {"id": p.id, "name": p.name},
            "training": [training_out(x) for x in reversed(logs)],
            "weekly": sorted(weekly.values(), key=lambda b: b["period"])[-12:],
            "monthly": sorted(monthly.values(), key=lambda b: b["period"])[-12:],
            "goals": goals, "milestones": milestones,
            "batting_scores": bat["scores"] if bat else [], "bowling_spells": bowl["spells"] if bowl else [],
            "speeds": sp,
            "batting_trend": ml.performance_trend([s["runs"] for s in bat["scores"]]) if bat else None,
            "speed_trend": ml.performance_trend([s["kmh"] for s in sp]) if sp else None}
