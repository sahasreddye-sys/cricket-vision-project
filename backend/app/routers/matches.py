"""Match Center and Team Hub: matches, live scoring, scorecards, statistics, selection, scouting."""
from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitchvision import scoring, selection, stats

from .. import services
from ..auth import coach_only, current_user
from ..models import Ball, BattingLine, BowlingLine, Innings, Match, Player, User, get_db

router = APIRouter()


# ------------------------------------------------------------------ matches

class MatchIn(BaseModel):
    date: dt.date
    opponent: str = Field(min_length=1, max_length=120)
    venue: str = Field(default="", max_length=120)
    format: str = Field(default="T20", max_length=20)
    overs: int = Field(default=20, ge=1, le=100)
    season: str = Field(default="", max_length=20)
    status: Literal["scheduled", "live", "completed"] = "scheduled"
    result: str = Field(default="", max_length=200)
    outcome: Optional[Literal["won", "lost", "tied", "no_result"]] = None
    notes: str = ""


def match_out(m: Match, cards: Optional[list] = None) -> dict:
    out = {"id": m.id, "date": m.date.isoformat(), "opponent": m.opponent, "venue": m.venue, "format": m.format,
           "overs": m.overs, "season": m.season, "status": m.status, "result": m.result, "outcome": m.outcome,
           "notes": m.notes, "is_sample": m.is_sample}
    if cards is not None:
        out["innings"] = [{"innings_id": c["innings_id"], "number": c["number"], "batting_side": c["batting_side"],
                           "total": c["total"], "wickets": c["wickets"], "overs": c["overs"], "source": c["source"]}
                          for c in cards]
    return out


def _match(db: Session, mid: int) -> Match:
    m = db.get(Match, mid)
    if not m:
        raise HTTPException(404, "Match not found.")
    return m


@router.get("/matches", tags=["matches"])
def list_matches(season: Optional[str] = None, format: Optional[str] = None, db: Session = Depends(get_db),
                 _: User = Depends(current_user)):
    ms = services.load_matches(db, season, format)
    return [match_out(m, services.match_cards(m)) for m in sorted(ms, key=lambda m: m.date, reverse=True)]


@router.post("/matches", tags=["matches"], status_code=201)
def create_match(body: MatchIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    m = Match(**body.model_dump())
    if not m.season:
        m.season = str(m.date.year)
    db.add(m)
    db.commit()
    return match_out(m, [])


@router.put("/matches/{mid}", tags=["matches"])
def update_match(mid: int, body: MatchIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    m = _match(db, mid)
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.commit()
    return match_out(m, services.match_cards(m))


@router.delete("/matches/{mid}", tags=["matches"], status_code=204)
def delete_match(mid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    db.delete(_match(db, mid))
    db.commit()


def _named_card(card: dict, nm: dict) -> dict:
    n = lambda pid: nm.get(pid, "?") if pid is not None else None
    for b in card["batting"]:
        b["name"], b["bowler_name"], b["fielder_name"] = n(b["player"]), n(b.get("bowler")), n(b.get("fielder"))
    for b in card["bowling"]:
        b["name"] = n(b["player"])
    for f in card["fall_of_wickets"]:
        f["name"] = n(f["player"])
    for p in card["partnerships"]:
        p["names"] = [n(x) for x in p["batters"]]
        for c in p["contrib"]:
            c["name"] = n(c["player"])
    for o in card["over_by_over"]:
        o["bowler_name"] = n(o["bowler"])
    card["next"]["striker_name"], card["next"]["non_striker_name"] = n(card["next"]["striker"]), n(card["next"]["non_striker"])
    return card


@router.get("/matches/{mid}", tags=["matches"])
def match_detail(mid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    m = _match(db, mid)
    nm = services.names(db)
    cards = [_named_card(c, nm) for c in services.match_cards(m)]
    worm = []
    for c in cards:
        worm.append({"number": c["number"], "side": c["batting_side"],
                     "points": [{"over": o["over"], "total": o["total"], "runs": o["runs"], "wickets": o["wickets"]}
                                for o in c["over_by_over"] if not o.get("in_progress")]})
    summary = None
    if len(cards) == 2 and (cards[0]["total"] or cards[1]["total"]):
        us = m.innings[0].batting_side == "us"
        a, b = ("Us", m.opponent) if us else (m.opponent, "Us")
        cards[1]["complete"] = cards[1]["complete"] or m.status == "completed"
        summary = scoring.match_result(cards[0], cards[1], a, b)
    return {**match_out(m, cards), "cards": cards, "worm": worm, "computed_result": summary}


class InningsIn(BaseModel):
    batting_side: Literal["us", "them"]


@router.post("/matches/{mid}/innings", tags=["scoring"], status_code=201)
def add_innings(mid: int, body: InningsIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    m = _match(db, mid)
    if len(m.innings) >= 2:
        raise HTTPException(409, "This match already has two innings.")
    if m.innings and m.innings[0].batting_side == body.batting_side:
        raise HTTPException(409, "The second innings must be batted by the other side.")
    if m.innings:
        m.innings[0].closed = True
    inn = Innings(match_id=mid, number=len(m.innings) + 1, batting_side=body.batting_side)
    db.add(inn)
    if m.status == "scheduled":
        m.status = "live"
    db.commit()
    return {"innings_id": inn.id, "number": inn.number}


class BallIn(BaseModel):
    striker_id: int
    non_striker_id: Optional[int] = None
    bowler_id: int
    runs_bat: int = Field(default=0, ge=0, le=7)
    wides: int = Field(default=0, ge=0, le=7)
    no_balls: int = Field(default=0, ge=0, le=1)
    byes: int = Field(default=0, ge=0, le=7)
    leg_byes: int = Field(default=0, ge=0, le=7)
    penalty: int = Field(default=0, ge=0, le=10)
    wicket_kind: Optional[str] = None
    player_out_id: Optional[int] = None
    fielder_id: Optional[int] = None
    new_batter_on_strike: Optional[bool] = None
    bowl_type: Optional[Literal["pace", "spin"]] = None
    x: Optional[float] = Field(default=None, ge=-1.6, le=1.6)
    y: Optional[float] = Field(default=None, ge=-1.0, le=20.12)
    shot_type: Optional[str] = Field(default=None, max_length=20)
    shot_angle: Optional[float] = Field(default=None, ge=0, lt=360)


def _innings(db: Session, iid: int) -> Innings:
    inn = db.get(Innings, iid)
    if not inn:
        raise HTTPException(404, "Innings not found.")
    return inn


def _target(inn: Innings) -> Optional[int]:
    if inn.number != 2:
        return None
    first = inn.match.innings[0]
    return services.innings_card(first, inn.match)["total"] + 1


@router.post("/innings/{iid}/balls", tags=["scoring"], status_code=201)
def add_ball(iid: int, body: BallIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    """Record one ball. The ball is validated against the Laws before it is saved."""
    inn = _innings(db, iid)
    if inn.closed:
        raise HTTPException(409, "This innings is closed.")
    if body.striker_id == body.non_striker_id:
        raise HTTPException(422, "The striker and non-striker must be different players.")
    for pid in (body.striker_id, body.non_striker_id, body.bowler_id, body.player_out_id, body.fielder_id):
        if pid is not None and not db.get(Player, pid):
            raise HTTPException(404, f"Player {pid} not found.")
    ball = Ball(innings_id=iid, seq=len(inn.balls) + 1, **body.model_dump())
    if not ball.bowl_type:
        style = db.get(Player, body.bowler_id).bowl_style or ""
        ball.bowl_type = "spin" if style.startswith("spin") else "pace" if style.startswith("pace") else None
    existing = [services.engine_ball(b) for b in inn.balls]
    try:
        scoring.score_innings(existing + [services.engine_ball(ball)], max_overs=inn.match.overs, target=_target(inn))
    except scoring.ScoringError as e:
        raise HTTPException(422, str(e))
    db.add(ball)
    db.commit()
    db.refresh(inn)
    card = services.innings_card(inn, inn.match, _target(inn))
    if card["complete"]:
        inn.closed = True
        db.commit()
    return _named_card(card, services.names(db))


@router.delete("/innings/{iid}/balls/last", tags=["scoring"])
def undo_ball(iid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    inn = _innings(db, iid)
    if not inn.balls:
        raise HTTPException(409, "There is no ball to undo.")
    db.delete(inn.balls[-1])
    inn.closed = False
    db.commit()
    db.refresh(inn)
    return _named_card(services.innings_card(inn, inn.match, _target(inn)), services.names(db))


@router.post("/innings/{iid}/close", tags=["scoring"])
def close_innings(iid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    inn = _innings(db, iid)
    inn.closed = True
    db.commit()
    return {"closed": True}


class BatLineIn(BaseModel):
    player_id: int
    runs: int = Field(ge=0, le=500)
    balls: int = Field(ge=0, le=1000)
    fours: int = Field(default=0, ge=0)
    sixes: int = Field(default=0, ge=0)
    out: bool = True
    how_out: Optional[str] = None


class BowlLineIn(BaseModel):
    player_id: int
    overs: str = Field(description="overs.balls, e.g. 3.4")
    maidens: int = Field(default=0, ge=0)
    runs: int = Field(ge=0)
    wickets: int = Field(ge=0, le=10)
    wides: int = Field(default=0, ge=0)
    no_balls: int = Field(default=0, ge=0)


class LinesIn(BaseModel):
    batting: list[BatLineIn] = []
    bowling: list[BowlLineIn] = []


@router.put("/innings/{iid}/lines", tags=["scoring"])
def set_lines(iid: int, body: LinesIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    """Enter a finished scorecard for an innings that was not scored ball by ball."""
    inn = _innings(db, iid)
    if inn.balls:
        raise HTTPException(409, "This innings has ball-by-ball data; its scorecard is calculated from the balls.")
    for b in body.batting:
        if 4 * b.fours + 6 * b.sixes > b.runs:
            raise HTTPException(422, f"Boundaries add up to more than the {b.runs} runs entered for one batter.")
        if b.runs and not b.balls:
            raise HTTPException(422, "A batter with runs must have faced at least one ball.")
    inn.batting_lines.clear()
    inn.bowling_lines.clear()
    db.flush()
    for i, b in enumerate(body.batting):
        inn.batting_lines.append(BattingLine(position=i + 1, **b.model_dump()))
    for b in body.bowling:
        try:
            balls = scoring.overs_to_balls(b.overs)
        except (scoring.ScoringError, ValueError) as e:
            raise HTTPException(422, str(e))
        if b.maidens * 6 > balls:
            raise HTTPException(422, "A bowler cannot have more maidens than completed overs.")
        inn.bowling_lines.append(BowlingLine(player_id=b.player_id, legal_balls=balls, maidens=b.maidens, runs=b.runs,
                                             wickets=b.wickets, wides=b.wides, no_balls=b.no_balls))
    inn.closed = True
    db.commit()
    return {"saved": True}


@router.post("/innings/{iid}/import-csv", tags=["scoring"])
async def import_balls(iid: int, file: UploadFile = File(...), db: Session = Depends(get_db), _: User = Depends(coach_only)):
    """Import ball-by-ball data from CSV. Columns: striker, non_striker, bowler (player NAMES), runs_bat, wides,
    no_balls, byes, leg_byes, wicket_kind, player_out, x, y, shot_type, shot_angle, bowl_type."""
    inn = _innings(db, iid)
    if inn.balls:
        raise HTTPException(409, "This innings already has balls recorded.")
    try:
        text = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "The file is not a UTF-8 CSV.")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or not {"striker", "bowler"} <= set(rows[0]):
        raise HTTPException(422, "The CSV needs at least 'striker' and 'bowler' columns.")
    bat_side = "us" if inn.batting_side == "us" else inn.match.opponent
    bowl_side = inn.match.opponent if inn.batting_side == "us" else "us"
    cache: dict = {}

    def pid(name: Optional[str], side: str) -> Optional[int]:
        name = (name or "").strip()
        if not name:
            return None
        if (name, side) not in cache:
            p = db.scalar(select(Player).where(func.lower(Player.name) == name.lower(), Player.side == side))
            if not p:
                p = Player(name=name, side=side)
                db.add(p)
                db.flush()
            cache[(name, side)] = p.id
        return cache[(name, side)]

    num = lambda r, k: int(float(r[k])) if r.get(k) not in (None, "") else 0
    opt = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None
    balls = []
    for i, r in enumerate(rows):
        try:
            balls.append(Ball(innings_id=iid, seq=i + 1, striker_id=pid(r["striker"], bat_side),
                              non_striker_id=pid(r.get("non_striker"), bat_side), bowler_id=pid(r["bowler"], bowl_side),
                              runs_bat=num(r, "runs_bat"), wides=num(r, "wides"), no_balls=num(r, "no_balls"),
                              byes=num(r, "byes"), leg_byes=num(r, "leg_byes"),
                              wicket_kind=(r.get("wicket_kind") or None), player_out_id=pid(r.get("player_out"), bat_side),
                              bowl_type=(r.get("bowl_type") or None), x=opt(r, "x"), y=opt(r, "y"),
                              shot_type=(r.get("shot_type") or None), shot_angle=opt(r, "shot_angle")))
        except (ValueError, KeyError) as e:
            db.rollback()
            raise HTTPException(422, f"Row {i + 2}: {e}")
    try:
        scoring.score_innings([services.engine_ball(b) for b in balls])
    except scoring.ScoringError as e:
        db.rollback()
        raise HTTPException(422, f"The file breaks a scoring rule: {e}")
    db.add_all(balls)
    inn.closed = True
    db.commit()
    return {"imported": len(balls)}


# ------------------------------------------------------------------ statistics

@router.get("/stats/tables", tags=["stats"])
def tables(season: Optional[str] = None, format: Optional[str] = None, side: str = "us",
           db: Session = Depends(get_db), _: User = Depends(current_user)):
    t = services.career_tables(db, season, format, side)
    return {"batting": t["batting"], "bowling": t["bowling"], "fielding": t["fielding"]}


@router.get("/stats/leaderboards", tags=["stats"])
def leaderboards(season: Optional[str] = None, format: Optional[str] = None, db: Session = Depends(get_db),
                 _: User = Depends(current_user)):
    t = services.career_tables(db, season, format)
    nm = services.names(db)
    ours = {p.id for p in db.scalars(select(Player).where(Player.side == "us"))}

    def named(rows):
        return [{**r, "name": nm.get(r["player"], "?")} for r in rows]

    speeds = [{"player": pid, "max_kmh": max(r["kmh"] for r in rs)}
              for pid, rs in services.speeds_by_player(db).items() if rs and pid in ours]
    acc = [{"player": pid, "hit_pct": a["hit_pct"], "total": a["total"]}
           for pid, a in services.accuracy_by_player(db).items() if a["total"] and pid in ours]
    runs_seq: dict = {}
    for ln in sorted(t["batting_lines"], key=lambda l: (l["date"], l["match_id"])):
        if ln["player"] in ours:
            runs_seq.setdefault(ln["player"], []).append(ln["runs"])
    lb = stats.leaderboard
    boards = [
        {"key": "batting_average", "title": "Highest batting average", "unit": "", "digits": 1,
         "rule": "At least 3 dismissals.", "rows": named(lb([{**r, "outs": r["innings"] - r["not_outs"]} for r in t["batting"]],
                                                           "average", True, ("outs", 3)))},
        {"key": "strike_rate", "title": "Highest strike rate", "unit": "", "digits": 1, "rule": "At least 30 balls faced.",
         "rows": named(lb(t["batting"], "strike_rate", True, ("balls", 30)))},
        {"key": "runs", "title": "Most runs", "unit": "", "digits": 0, "rule": "", "rows": named(lb(t["batting"], "runs"))},
        {"key": "wickets", "title": "Most wickets", "unit": "", "digits": 0, "rule": "",
         "rows": named(lb([r for r in t["bowling"] if r["wickets"] > 0], "wickets"))},
        {"key": "economy", "title": "Best bowling economy", "unit": "rpo", "digits": 2, "rule": "At least 30 balls bowled.",
         "rows": named(lb(t["bowling"], "economy", False, ("legal_balls", 30)))},
        {"key": "speed", "title": "Fastest recorded speed", "unit": "km/h", "digits": 1,
         "rule": "Best single reading. Radar and stopwatch readings measure different things.",
         "rows": named(lb(speeds, "max_kmh"))},
        {"key": "accuracy", "title": "Most accurate bowling", "unit": "%", "digits": 0,
         "rule": "Share of practice deliveries in the target zone; at least 12 deliveries.",
         "rows": named(lb(acc, "hit_pct", True, ("total", 12)))},
        {"key": "catches", "title": "Most catches", "unit": "", "digits": 0, "rule": "",
         "rows": named(lb([r for r in t["fielding"] if r["catch"] > 0], "catch"))},
        {"key": "catch_pct", "title": "Best catch success", "unit": "%", "digits": 0, "rule": "At least 3 chances.",
         "rows": named(lb(t["fielding"], "catch_pct", True, ("catch_chances", 3)))},
        {"key": "improvement", "title": "Most improved batting", "unit": "runs/inns", "digits": 1,
         "rule": "Change in runs per innings from the earlier half to the later half of the player's innings; at least 4 innings.",
         "rows": named([{"rank": r["rank"], "player": r["player"], "value": r["change"]}
                        for r in stats.improvement(runs_seq) if r["change"] > 0][:10])},
    ]
    return {"season": season, "format": format, "boards": boards}


@router.get("/stats/wagon", tags=["stats"])
def wagon(player_id: int, match_id: Optional[int] = None, season: Optional[str] = None,
          db: Session = Depends(get_db), _: User = Depends(current_user)):
    balls = [b for b in services.collect(db, season)["balls"] if b["striker"] == player_id]
    if match_id:
        balls = [b for b in balls if b["match_id"] == match_id]
    matches = sorted({(b["match_id"], b["date"]) for b in services.collect(db, season)["balls"] if b["striker"] == player_id})
    return {**stats.wagon_wheel(balls), "matches": [{"match_id": m, "date": d} for m, d in matches]}


@router.get("/stats/splits", tags=["stats"])
def splits(player_id: int, season: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    balls = services.collect(db, season)["balls"]
    return {"batting": stats.batting_splits(balls, player_id), "bowling": stats.bowling_splits(balls, player_id)}


@router.get("/stats/compare", tags=["stats"])
def compare_players(a: int, b: int, season: Optional[str] = None, db: Session = Depends(get_db),
                    _: User = Depends(current_user)):
    t = services.career_tables(db, season, side="")
    pick = lambda rows, pid: next((r for r in rows if r["player"] == pid), None)
    nm = services.names(db)
    return {"players": [{"id": p, "name": nm.get(p, "?"), "batting": pick(t["batting"], p), "bowling": pick(t["bowling"], p),
                         "fielding": pick(t["fielding"], p)} for p in (a, b)]}


@router.get("/opposition/report", tags=["opposition"])
def opposition_report(player_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    p = db.get(Player, player_id)
    if not p:
        raise HTTPException(404, "Player not found.")
    rep = stats.scouting_report(services.collect(db)["balls"], player_id)
    rep["name"], rep["side"] = p.name, p.side
    return rep


@router.get("/opposition/teams", tags=["opposition"])
def opposition_teams(db: Session = Depends(get_db), _: User = Depends(current_user)):
    balls = services.collect(db)["balls"]
    faced: dict = {}
    for b in balls:
        faced[b["striker"]] = faced.get(b["striker"], 0) + (0 if b["wides"] else 1)
    teams: dict = {}
    for p in db.scalars(select(Player).where(Player.side != "us").order_by(Player.side, Player.name)):
        teams.setdefault(p.side, []).append({"id": p.id, "name": p.name, "balls_faced": faced.get(p.id, 0)})
    return [{"team": k, "players": v} for k, v in teams.items()]


# ------------------------------------------------------------------ selection

class SelectIn(BaseModel):
    available: list[int]
    overs: int = Field(default=20, ge=1, le=100)
    season: Optional[str] = None


def _squad(db: Session, ids: list[int], season: Optional[str]) -> list[dict]:
    t = services.career_tables(db, season)
    bat = {r["player"]: r for r in t["batting"]}
    bowl = {r["player"]: r for r in t["bowling"]}
    out = []
    for pid in ids:
        p = db.get(Player, pid)
        if p:
            out.append({"id": p.id, "name": p.name, "role": p.role, "bowl_style": p.bowl_style,
                        "bat": bat.get(pid), "bowl": bowl.get(pid)})
    return out


@router.post("/team/select", tags=["selection"])
def select_team(body: SelectIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return selection.select_xi(_squad(db, body.available, body.season), match_overs=body.overs)


class CompareIn(BaseModel):
    a: list[int]
    b: list[int]
    overs: int = Field(default=20, ge=1, le=100)
    season: Optional[str] = None


@router.post("/team/compare", tags=["selection"])
def compare_teams(body: CompareIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return selection.compare_xis(_squad(db, body.a, body.season), _squad(db, body.b, body.season), body.overs)
