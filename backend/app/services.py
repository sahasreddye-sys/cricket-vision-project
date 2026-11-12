"""Turn database rows into the plain dicts the shared `pitchvision` analytics expect."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pitchvision import pitchmap, scoring, stats

from .models import (Ball, BowlingSession, FieldingEvent, Innings, Match, Player, SpeedReading)


def names(db: Session) -> dict[int, str]:
    return {p.id: p.name for p in db.scalars(select(Player))}


def flat_ball(b: Ball, inn: Innings, match: Match) -> dict:
    return {"match_id": match.id, "innings": inn.number, "date": match.date.isoformat(), "season": match.season,
            "format": match.format, "batting_side": inn.batting_side,
            "striker": b.striker_id, "non_striker": b.non_striker_id, "bowler": b.bowler_id,
            "runs_bat": b.runs_bat, "wides": b.wides, "no_balls": b.no_balls, "byes": b.byes,
            "leg_byes": b.leg_byes, "penalty": b.penalty, "wicket_kind": b.wicket_kind,
            "player_out": b.player_out_id or (b.striker_id if b.wicket_kind else None), "fielder": b.fielder_id,
            "bowl_type": b.bowl_type, "x": b.x, "y": b.y, "shot_type": b.shot_type, "shot_angle": b.shot_angle,
            "seq": b.seq, "id": b.id}


def engine_ball(b: Ball) -> dict:
    out = {"striker": b.striker_id, "non_striker": b.non_striker_id, "bowler": b.bowler_id,
           "runs_bat": b.runs_bat, "wides": b.wides, "no_balls": b.no_balls, "byes": b.byes,
           "leg_byes": b.leg_byes, "penalty": b.penalty}
    if b.wicket_kind:
        out["wicket"] = {"kind": b.wicket_kind, "player_out": b.player_out_id or b.striker_id, "fielder": b.fielder_id}
    if b.new_batter_on_strike is not None:
        out["new_batter_on_strike"] = b.new_batter_on_strike
    return out


def innings_card(inn: Innings, match: Match, target: Optional[int] = None, validate: bool = False) -> dict:
    """Scorecard for one innings: from balls if scored ball by ball, else from the manual lines."""
    if inn.balls:
        card = scoring.score_innings([engine_ball(b) for b in inn.balls], max_overs=match.overs or None,
                                     target=target, validate=validate)
        card["source"] = "ball_by_ball"
    else:
        bat = [{"player": l.player_id, "runs": l.runs, "balls": l.balls, "fours": l.fours, "sixes": l.sixes,
                "out": l.out, "how_out": l.how_out, "position": l.position,
                "strike_rate": (l.runs / l.balls * 100) if l.balls else None}
               for l in sorted(inn.batting_lines, key=lambda l: l.position)]
        bowl = [{"player": l.player_id, "legal_balls": l.legal_balls, "runs": l.runs, "wickets": l.wickets,
                 "maidens": l.maidens, "wides": l.wides, "no_balls": l.no_balls, "dots": 0,
                 "overs": scoring.overs_text(l.legal_balls), "economy": scoring.run_rate(l.runs, l.legal_balls)}
                for l in inn.bowling_lines]
        legal = sum(b["legal_balls"] for b in bowl)
        bat_runs = sum(b["runs"] for b in bat)
        conceded = sum(b["runs"] for b in bowl)
        # Byes and leg-byes are not in bowlers' figures, so the total is at least both sums.
        total = max(bat_runs, conceded)
        card = {"total": total, "wickets": sum(1 for b in bat if b["out"]), "legal_balls": legal,
                "overs": scoring.overs_text(legal), "run_rate": scoring.run_rate(total, legal),
                "extras": {"total": max(total - bat_runs, 0)}, "batting": bat, "bowling": bowl,
                "fall_of_wickets": [], "partnerships": [], "over_by_over": [], "complete": inn.closed,
                "target": target, "next": {"striker": None, "non_striker": None, "over_complete": False},
                "source": "scorecard" if (bat or bowl) else "empty"}
    card.update({"innings_id": inn.id, "number": inn.number, "batting_side": inn.batting_side, "closed": inn.closed})
    if inn.closed:
        card["complete"] = True
    return card


def match_cards(match: Match) -> list[dict]:
    cards, target = [], None
    for inn in match.innings:
        card = innings_card(inn, match, target if inn.number == 2 else None)
        if inn.number == 1:
            target = card["total"] + 1
        cards.append(card)
    return cards


def load_matches(db: Session, season: Optional[str] = None, fmt: Optional[str] = None) -> list[Match]:
    q = select(Match).options(selectinload(Match.innings).selectinload(Innings.balls),
                              selectinload(Match.innings).selectinload(Innings.batting_lines),
                              selectinload(Match.innings).selectinload(Innings.bowling_lines)).order_by(Match.date, Match.id)
    if season:
        q = q.where(Match.season == season)
    if fmt:
        q = q.where(Match.format == fmt)
    return list(db.scalars(q))


def collect(db: Session, season: Optional[str] = None, fmt: Optional[str] = None) -> dict:
    """All per-innings batting/bowling lines and flat balls for the filtered matches."""
    bat_lines, bowl_lines, balls = [], [], []
    for m in load_matches(db, season, fmt):
        for card, inn in zip(match_cards(m), m.innings):
            meta = {"match_id": m.id, "date": m.date.isoformat()}
            for b in card["batting"]:
                bat_lines.append({**meta, "player": b["player"], "runs": b["runs"], "balls": b["balls"],
                                  "fours": b["fours"], "sixes": b["sixes"], "out": b["out"]})
            for b in card["bowling"]:
                bowl_lines.append({**meta, "player": b["player"], "legal_balls": b["legal_balls"], "runs": b["runs"],
                                   "wickets": b["wickets"], "maidens": b["maidens"], "wides": b["wides"],
                                   "no_balls": b["no_balls"], "dots": b.get("dots", 0)})
            balls += [flat_ball(b, inn, m) for b in inn.balls]
    return {"batting_lines": bat_lines, "bowling_lines": bowl_lines, "balls": balls}


def fielding_events(db: Session, season: Optional[str] = None) -> list[dict]:
    rows = db.scalars(select(FieldingEvent)).all()
    if season:
        # An event tied to a match takes that match's season; otherwise the year of its date.
        seasons = {m.id: m.season for m in db.scalars(select(Match))}
        rows = [r for r in rows if (seasons.get(r.match_id) if r.match_id in seasons else str(r.date.year)) == season]
    return [{"player": r.player_id, "kind": r.kind, "count": r.count, "date": r.date.isoformat()} for r in rows]


def career_tables(db: Session, season: Optional[str] = None, fmt: Optional[str] = None, side: str = "us") -> dict:
    data = collect(db, season, fmt)
    nm = names(db)
    ours = {p.id for p in db.scalars(select(Player).where(Player.side == side))} if side else set(nm)

    def tag(rows):
        return [{**r, "name": nm.get(r["player"], "?")} for r in rows if r["player"] in ours]

    return {"batting": tag(stats.career_batting(data["batting_lines"])),
            "bowling": tag(stats.career_bowling(data["bowling_lines"])),
            "fielding": tag(stats.career_fielding(fielding_events(db, season))),
            "balls": data["balls"], "batting_lines": data["batting_lines"]}


def speeds_by_player(db: Session) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in db.scalars(select(SpeedReading).order_by(SpeedReading.date, SpeedReading.id)):
        out.setdefault(r.player_id, []).append({"id": r.id, "date": r.date.isoformat(), "kmh": r.kmh, "source": r.source,
                                                "distance_m": r.distance_m, "time_s": r.time_s, "note": r.note})
    return out


def session_deliveries(s: BowlingSession) -> list[dict]:
    return [{"id": d.id, "x": d.x, "y": d.y, "bounced": d.bounced,
             "length": pitchmap.classify_length(d.y, d.bounced), "line": pitchmap.classify_line(d.x)} for d in s.deliveries]


def accuracy_by_player(db: Session) -> dict[int, dict]:
    """Accuracy over every recorded practice delivery, each measured against its own session's target."""
    out = {}
    sessions = db.scalars(select(BowlingSession).options(selectinload(BowlingSession.deliveries))).all()
    by_player: dict[int, list] = {}
    for s in sessions:
        by_player.setdefault(s.player_id, []).append(s)
    for pid, ss in by_player.items():
        # Express every delivery relative to its session target, then score against a (0, 0) target.
        rel = [{"x": d.x - s.target_x, "y": d.y - s.target_y} for s in ss for d in s.deliveries]
        tol_x = sum(s.tol_x for s in ss) / len(ss)
        tol_y = sum(s.tol_y for s in ss) / len(ss)
        out[pid] = pitchmap.accuracy(rel, 0.0, 0.0, tol_x, tol_y)
        out[pid]["sessions"] = len(ss)
    return out


def coach_context(db: Session, me: Optional[int] = None, season: Optional[str] = None) -> dict:
    t = career_tables(db, season)
    players = [{"id": p.id, "name": p.name, "role": p.role, "bowl_style": p.bowl_style}
               for p in db.scalars(select(Player).where(Player.side == "us"))]
    ids = {p["id"] for p in players}
    splits = {}
    for pid in ids:
        sp = stats.batting_splits(t["balls"], pid)
        if sp["overall"]["balls"]:
            splits[pid] = sp
    return {"players": players, "batting": t["batting"], "bowling": t["bowling"], "fielding": t["fielding"],
            "speeds": {k: v for k, v in speeds_by_player(db).items() if k in ids},
            "accuracy": accuracy_by_player(db), "splits": splits, "me": me}
