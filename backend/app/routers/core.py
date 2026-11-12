"""Accounts, team settings, players, overview and sample-data import."""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pitchvision import coach as coach_mod
from pitchvision import sample_data, stats

from .. import services
from ..auth import admin_only, coach_only, current_user, hash_password, make_token, verify_password
from ..models import (Ball, BowlingSession, Delivery, FieldingEvent, Goal, Innings, Match, Player, SpeedReading, Team,
                      TrainingLog, User, VideoAnalysis, get_db)

router = APIRouter()

Role = Literal["batter", "bowler", "all_rounder", "wicket_keeper"]
BowlStyle = Optional[Literal["pace_fast", "pace_medium", "spin_off", "spin_leg"]]


# ------------------------------------------------------------------ auth

class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "player_id": u.player_id}


@router.get("/auth/status", tags=["auth"])
def auth_status(db: Session = Depends(get_db)):
    """Whether any account exists yet (the first account becomes the team admin)."""
    return {"has_users": db.scalar(select(func.count(User.id))) > 0}


@router.post("/auth/register", tags=["auth"])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    first = db.scalar(select(func.count(User.id))) == 0
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password),
             role="admin" if first else "player")
    db.add(u)
    db.commit()
    return {"token": make_token(u), "user": user_out(u)}


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"token": make_token(u), "user": user_out(u)}


@router.get("/auth/me", tags=["auth"])
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.get("/users", tags=["auth"])
def list_users(db: Session = Depends(get_db), _: User = Depends(coach_only)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.id))]


class UserPatch(BaseModel):
    role: Optional[Literal["admin", "coach", "player"]] = None
    player_id: Optional[int] = None
    unlink_player: bool = False


@router.patch("/users/{uid}", tags=["auth"])
def patch_user(uid: int, body: UserPatch, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    if body.role:
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(400, "You cannot remove your own admin role.")
        u.role = body.role
    if body.unlink_player:
        u.player_id = None
    elif body.player_id is not None:
        if not db.get(Player, body.player_id):
            raise HTTPException(404, "Player not found.")
        u.player_id = body.player_id
    db.commit()
    return user_out(u)


# ------------------------------------------------------------------ team settings

class TeamIn(BaseModel):
    name: str = Field(max_length=120)
    season: str = Field(max_length=20)
    default_overs: int = Field(ge=1, le=100)
    speed_unit: Literal["kmh", "mph"] = "kmh"


def get_team(db: Session) -> Team:
    t = db.get(Team, 1)
    if not t:
        t = Team(id=1, name="", season=str(dt.date.today().year), default_overs=20)
        db.add(t)
        db.commit()
    return t


@router.get("/team", tags=["team"])
def read_team(db: Session = Depends(get_db), _: User = Depends(current_user)):
    t = get_team(db)
    seasons = sorted({s for s in db.scalars(select(Match.season).distinct()) if s})
    formats = sorted({f for f in db.scalars(select(Match.format).distinct()) if f})
    return {"name": t.name, "season": t.season, "default_overs": t.default_overs, "speed_unit": t.speed_unit,
            "seasons": seasons, "formats": formats,
            "has_sample_data": db.scalar(select(func.count(Player.id)).where(Player.is_sample)) > 0,
            "llm_available": coach_mod.llm_available()}


@router.put("/team", tags=["team"])
def update_team(body: TeamIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    t = get_team(db)
    t.name, t.season, t.default_overs, t.speed_unit = body.name.strip(), body.season.strip(), body.default_overs, body.speed_unit
    db.commit()
    return read_team(db)


# ------------------------------------------------------------------ players

class PlayerIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    side: str = Field(default="us", max_length=120)
    role: Role = "batter"
    batting_hand: Literal["right", "left"] = "right"
    bowl_style: BowlStyle = None
    active: bool = True
    notes: str = ""


def player_out(p: Player) -> dict:
    return {"id": p.id, "name": p.name, "side": p.side, "role": p.role, "batting_hand": p.batting_hand,
            "bowl_style": p.bowl_style, "active": p.active, "notes": p.notes, "is_sample": p.is_sample}


@router.get("/players", tags=["players"])
def list_players(side: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(Player).order_by(Player.side != "us", Player.name)
    if side == "opposition":
        q = q.where(Player.side != "us")
    elif side:
        q = q.where(Player.side == side)
    return [player_out(p) for p in db.scalars(q)]


@router.post("/players", tags=["players"], status_code=201)
def create_player(body: PlayerIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    side = body.side.strip() or "us"
    if db.scalar(select(Player).where(func.lower(Player.name) == body.name.strip().lower(), Player.side == side)):
        raise HTTPException(409, f"A player called {body.name.strip()} already exists in this team.")
    p = Player(**{**body.model_dump(), "name": body.name.strip(), "side": side})
    db.add(p)
    db.commit()
    return player_out(p)


@router.put("/players/{pid}", tags=["players"])
def update_player(pid: int, body: PlayerIn, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    p = db.get(Player, pid)
    if not p:
        raise HTTPException(404, "Player not found.")
    for k, v in body.model_dump().items():
        setattr(p, k, v.strip() if isinstance(v, str) and k in ("name", "side") else v)
    db.commit()
    return player_out(p)


@router.delete("/players/{pid}", tags=["players"], status_code=204)
def delete_player(pid: int, db: Session = Depends(get_db), _: User = Depends(coach_only)):
    p = db.get(Player, pid)
    if not p:
        raise HTTPException(404, "Player not found.")
    used = db.scalar(select(func.count(Ball.id)).where(
        (Ball.striker_id == pid) | (Ball.bowler_id == pid) | (Ball.non_striker_id == pid)))
    if used:
        raise HTTPException(409, f"{p.name} appears in {used} recorded balls. Mark the player inactive instead of deleting.")
    db.delete(p)
    db.commit()


@router.get("/players/{pid}/profile", tags=["players"])
def player_profile(pid: int, season: Optional[str] = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    p = db.get(Player, pid)
    if not p:
        raise HTTPException(404, "Player not found.")
    t = services.career_tables(db, season, side=p.side)
    pick = lambda rows: next((r for r in rows if r["player"] == pid), None)
    speeds = services.speeds_by_player(db).get(pid, [])
    from pitchvision import speed as speed_mod
    ctx = services.coach_context(db, pid, season) if p.side == "us" else None
    return {
        "player": player_out(p),
        "batting": pick(t["batting"]), "bowling": pick(t["bowling"]), "fielding": pick(t["fielding"]),
        "splits": stats.batting_splits(t["balls"], pid),
        "bowling_splits": stats.bowling_splits(t["balls"], pid),
        "wagon_wheel": stats.wagon_wheel([b for b in t["balls"] if b["striker"] == pid]),
        "speeds": speeds, "speed_summary": speed_mod.speed_summary([s["kmh"] for s in speeds]),
        "accuracy": services.accuracy_by_player(db).get(pid),
        "recommendations": coach_mod.player_recommendations(ctx, pid) if ctx else [],
        "goals": [goal_out(g) for g in db.scalars(select(Goal).where(Goal.player_id == pid).order_by(Goal.created_at.desc()))],
        "training": [training_out(x) for x in db.scalars(select(TrainingLog).where(TrainingLog.player_id == pid)
                                                         .order_by(TrainingLog.date.desc()).limit(50))],
    }


def goal_out(g: Goal) -> dict:
    return {"id": g.id, "player_id": g.player_id, "title": g.title, "metric": g.metric, "target_value": g.target_value,
            "due_date": g.due_date.isoformat() if g.due_date else None, "status": g.status,
            "created_at": g.created_at.isoformat(), "achieved_at": g.achieved_at.isoformat() if g.achieved_at else None}


def training_out(x: TrainingLog) -> dict:
    return {"id": x.id, "player_id": x.player_id, "date": x.date.isoformat(), "kind": x.kind,
            "duration_min": x.duration_min, "intensity": x.intensity, "notes": x.notes}


# ------------------------------------------------------------------ overview

@router.get("/overview", tags=["overview"])
def overview(db: Session = Depends(get_db), user: User = Depends(current_user)):
    team = get_team(db)
    today = dt.date.today()
    # Show the current season when it has matches; otherwise show everything recorded.
    scope = team.season if team.season and db.scalar(select(func.count(Match.id)).where(Match.season == team.season)) else None
    t = services.career_tables(db, scope)
    nm = services.names(db)
    matches = services.load_matches(db)
    done = [m for m in matches if m.status == "completed"]
    upcoming = [m for m in matches if m.status != "completed" and m.date >= today]
    recent = []
    for m in sorted(done, key=lambda m: m.date, reverse=True)[:5]:
        cards = services.match_cards(m)
        recent.append({"id": m.id, "date": m.date.isoformat(), "opponent": m.opponent, "result": m.result,
                       "outcome": m.outcome, "scores": [{"side": c["batting_side"], "total": c["total"],
                                                         "wickets": c["wickets"], "overs": c["overs"]} for c in cards]})
    sessions = []
    for s in db.scalars(select(BowlingSession).order_by(BowlingSession.date.desc()).limit(5)):
        sessions.append({"kind": "Bowling session", "date": s.date.isoformat(), "player": nm.get(s.player_id, "?"),
                         "detail": f"{len(s.deliveries)} deliveries" + (f" · {s.name}" if s.name else "")})
    for x in db.scalars(select(TrainingLog).order_by(TrainingLog.date.desc()).limit(5)):
        sessions.append({"kind": f"{x.kind.capitalize()} training", "date": x.date.isoformat(), "player": nm.get(x.player_id, "?"),
                         "detail": f"{x.duration_min} min"})
    for v in db.scalars(select(VideoAnalysis).order_by(VideoAnalysis.created_at.desc()).limit(5)):
        sessions.append({"kind": f"Video: {v.kind}", "date": v.created_at.date().isoformat(),
                         "player": nm.get(v.player_id, "") if v.player_id else "", "detail": v.label or v.filename})
    sessions.sort(key=lambda s: s["date"], reverse=True)
    ctx = services.coach_context(db, user.player_id, scope)
    speeds = services.speeds_by_player(db)
    fastest = max(((max(s["kmh"] for s in rs), pid) for pid, rs in speeds.items() if rs and pid in nm), default=None)
    counts = {
        "players": db.scalar(select(func.count(Player.id)).where(Player.side == "us", Player.active)),
        "matches_played": len(done), "won": sum(1 for m in done if m.outcome == "won"),
        "lost": sum(1 for m in done if m.outcome == "lost"),
        "speed_readings": db.scalar(select(func.count(SpeedReading.id))),
        "deliveries": db.scalar(select(func.count(Delivery.id))),
        "balls_scored": db.scalar(select(func.count(Ball.id))),
    }
    return {
        "team": {"name": team.name, "season": team.season},
        "stats_scope": f"{scope} season" if scope else "all recorded matches",
        "counts": counts,
        "top_batters": [{"player": r["player"], "name": r["name"], "runs": r["runs"], "average": r["average"],
                         "strike_rate": r["strike_rate"], "innings": r["innings"]} for r in t["batting"][:5]],
        "top_bowlers": [{"player": r["player"], "name": r["name"], "wickets": r["wickets"], "economy": r["economy"],
                         "overs": r["overs"]} for r in t["bowling"][:5]],
        "fastest": {"kmh": fastest[0], "name": nm[fastest[1]], "player": fastest[1]} if fastest else None,
        "recent_matches": recent,
        "upcoming": [{"id": m.id, "date": m.date.isoformat(), "opponent": m.opponent, "venue": m.venue,
                      "format": m.format, "status": m.status} for m in sorted(upcoming, key=lambda m: m.date)[:5]],
        "recent_sessions": sessions[:8],
        "insights": coach_mod.team_insights(ctx),
        "my_recommendations": coach_mod.player_recommendations(ctx, user.player_id)[:3] if user.player_id else [],
    }


# ------------------------------------------------------------------ sample data (synthetic)

@router.post("/sample-data", tags=["sample data"])
def load_sample(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """Load the SYNTHETIC demo data set. Every row is flagged so it can be removed again."""
    if db.scalar(select(func.count(Player.id)).where(Player.is_sample)):
        raise HTTPException(409, "Sample data is already loaded.")
    data = sample_data.generate()
    ids: dict[str, int] = {}

    def pid(name: str, side: str = "us", role: str = "batter", style=None) -> int:
        if name not in ids:
            p = Player(name=name, side=side, role=role, bowl_style=style, is_sample=True,
                       notes="Synthetic demo player. Not a real person.")
            db.add(p)
            db.flush()
            ids[name] = p.id
        return ids[name]

    for p in data["players"]:
        pid(p["name"], "us", p["role"], p["bowl_style"])
    for m in data["matches"]:
        match = Match(date=dt.date.fromisoformat(m["date"]), opponent=m["opponent"], venue=m["venue"], format=m["format"],
                      overs=m["overs"], season=m["season"], status="completed", outcome=m["result"], is_sample=True,
                      result=f"{'Won' if m['result'] == 'won' else 'Lost' if m['result'] == 'lost' else 'Tied'}: "
                             f"{m['our_score']} v {m['their_score']}")
        db.add(match)
        db.flush()
        for n in (1, 2):
            rows = [b for b in data["balls"] if b["match_id"] == m["match_id"] and b["innings"] == n]
            us_batting = rows[0]["batting_team"] == data["team"]
            inn = Innings(match_id=match.id, number=n, batting_side="us" if us_batting else "them", closed=True)
            db.add(inn)
            db.flush()
            bat_side, bowl_side = ("us", m["opponent"]) if us_batting else (m["opponent"], "us")
            for i, b in enumerate(rows):
                bowler_style = "spin_off" if b["bowl_type"] == "spin" else "pace_medium"
                db.add(Ball(innings_id=inn.id, seq=i + 1, striker_id=pid(b["striker"], bat_side),
                            non_striker_id=pid(b["non_striker"], bat_side) if b["non_striker"] else None,
                            bowler_id=pid(b["bowler"], bowl_side, "bowler", bowler_style),
                            runs_bat=b["runs_bat"], wides=b["wides"], no_balls=b["no_balls"], byes=b["byes"],
                            leg_byes=b["leg_byes"], wicket_kind=b["wicket_kind"],
                            player_out_id=pid(b["player_out"], bat_side) if b["player_out"] else None,
                            fielder_id=pid(b["fielder"], bowl_side) if b["fielder"] else None,
                            bowl_type=b["bowl_type"], x=b["x"], y=b["y"], shot_type=b["shot_type"], shot_angle=b["shot_angle"]))
    sessions: dict[str, BowlingSession] = {}
    for d in data["deliveries"]:
        if d["x"] is None:
            continue
        if d["session"] not in sessions:
            s = BowlingSession(player_id=pid(d["player"]), date=dt.date.fromisoformat(d["date"]),
                               name=f"Nets {d['session_no']} (synthetic)", target_x=0.2,
                               target_y=5.2 if d["bowl_type"] == "spin" else 7.0, is_sample=True)
            db.add(s)
            db.flush()
            sessions[d["session"]] = s
        db.add(Delivery(session_id=sessions[d["session"]].id, x=d["x"], y=d["y"]))
    for s in data["speeds"]:
        if s["kmh"] is None:
            continue
        db.add(SpeedReading(player_id=pid(s["player"]), date=dt.date.fromisoformat(s["date"]), source=s["source"],
                            distance_m=s["distance_m"], time_s=s["time_s"], kmh=s["kmh"], note="synthetic", is_sample=True))
    for f in data["fielding"]:
        db.add(FieldingEvent(player_id=pid(f["player"]), date=dt.date.fromisoformat(f["date"]), kind=f["kind"],
                             count=1, is_sample=True))
    t = get_team(db)
    if not t.season:
        t.season = "2025"
    db.commit()
    return {"loaded": True, "players": len(ids), "matches": len(data["matches"]), "balls": len(data["balls"]),
            "note": "Synthetic data loaded. It is labelled as sample data and can be removed in Settings."}


@router.delete("/sample-data", tags=["sample data"])
def clear_sample(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    for m in db.scalars(select(Match).where(Match.is_sample)).all():
        db.delete(m)                       # cascades to innings and balls
    db.flush()
    db.execute(delete(FieldingEvent).where(FieldingEvent.is_sample))
    db.execute(delete(SpeedReading).where(SpeedReading.is_sample))
    for s in db.scalars(select(BowlingSession).where(BowlingSession.is_sample)).all():
        db.delete(s)
    db.flush()
    removed = 0
    for p in db.scalars(select(Player).where(Player.is_sample)).all():
        used = db.scalar(select(func.count(Ball.id)).where((Ball.striker_id == p.id) | (Ball.bowler_id == p.id)))
        if not used:
            db.delete(p)
            removed += 1
    db.commit()
    return {"cleared": True, "players_removed": removed}
