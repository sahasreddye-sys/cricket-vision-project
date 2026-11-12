"""Ball-by-ball innings engine that follows the Laws of Cricket.

A ball is a dict with these keys (all optional except striker and bowler):

    striker, non_striker, bowler   player identifiers (any hashable; names or ids)
    runs_bat    runs scored off the bat
    wides       total wides conceded on this ball (1 penalty + any runs run). 0 if not a wide.
    no_balls    1 if the ball was a no-ball, else 0 (the one-run penalty)
    byes, leg_byes, penalty        extras that are not charged to the bowler
    boundary    True if runs_bat was a boundary 4 or 6 (default: runs_bat in (4, 6))
    wicket      None or {"kind": ..., "player_out": id, "fielder": id}
    shot_angle, shot_type, x, y, bowl_type, ...   optional analysis fields, ignored here

Rules implemented
-----------------
* Law 17  An over is six LEGAL balls. Wides and no-balls do not count.
* Law 21  No-ball: one-run penalty charged to the bowler; runs off the bat go to the
          batter; the ball counts as a ball FACED by the batter but not as a legal ball.
* Law 22  Wide: all wides are charged to the bowler; not a ball faced; not a legal ball.
* Law 23  Byes and leg-byes go to the team total, not the batter, and not the bowler.
* Bowler's wickets: bowled, caught, lbw, stumped, hit wicket (and caught-and-bowled).
          Run-outs, retired out, obstructing the field, timed out are not the bowler's.
* A maiden over is a completed six-ball over with no runs charged to the bowler.
* Batters swap ends when an odd number of runs is physically run, and at the end
  of each over.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from .constants import BALLS_PER_OVER

BOWLER_WICKETS = {"bowled", "caught", "lbw", "stumped", "hit_wicket", "caught_and_bowled"}
NOT_A_WICKET = {"retired_hurt", "retired_not_out"}
ALL_DISMISSALS = BOWLER_WICKETS | {"run_out", "retired_out", "obstructing_the_field", "timed_out",
                                   "hit_the_ball_twice", "handled_the_ball"} | NOT_A_WICKET
# Dismissals that are possible on each kind of illegal delivery.
ALLOWED_ON_NO_BALL = {"run_out", "obstructing_the_field", "hit_the_ball_twice", "retired_hurt",
                      "retired_out", "retired_not_out"}
ALLOWED_ON_WIDE = {"run_out", "stumped", "hit_wicket", "obstructing_the_field", "retired_hurt",
                   "retired_out", "retired_not_out"}


class ScoringError(ValueError):
    """Raised when a ball breaks a scoring rule."""


def overs_text(legal_balls: int) -> str:
    """6 legal balls -> '1.0'; 7 -> '1.1'. The digit after the point is BALLS, not tenths."""
    return f"{legal_balls // BALLS_PER_OVER}.{legal_balls % BALLS_PER_OVER}"


def overs_to_balls(overs: float | str) -> int:
    """'3.4' (3 overs 4 balls) -> 22 balls. Rejects '.6' and above."""
    text = str(overs)
    whole, _, part = text.partition(".")
    balls = int(part) if part else 0
    if balls >= BALLS_PER_OVER:
        raise ScoringError(f"'{text}' is not a valid overs figure: the part after the point is balls (0-5).")
    return int(whole or 0) * BALLS_PER_OVER + balls


def run_rate(runs: int, legal_balls: int) -> Optional[float]:
    """Runs per over = runs / (legal balls / 6)."""
    if legal_balls <= 0:
        return None
    return runs * BALLS_PER_OVER / legal_balls


def required_run_rate(target: int, runs: int, balls_remaining: int) -> Optional[float]:
    """Runs per over needed to reach `target` from `runs` with `balls_remaining` legal balls."""
    needed = target - runs
    if needed <= 0:
        return 0.0
    if balls_remaining <= 0:
        return None
    return needed * BALLS_PER_OVER / balls_remaining


def _i(ball: dict, key: str) -> int:
    v = ball.get(key) or 0
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ScoringError(f"'{key}' must be a non-negative whole number, got {v!r}.")
    return v


def validate_ball(ball: dict) -> None:
    """Raise ScoringError if a ball is impossible under the Laws."""
    if ball.get("striker") is None or ball.get("bowler") is None:
        raise ScoringError("Every ball needs a striker and a bowler.")
    runs_bat, wides, nb = _i(ball, "runs_bat"), _i(ball, "wides"), _i(ball, "no_balls")
    byes, lb = _i(ball, "byes"), _i(ball, "leg_byes")
    _i(ball, "penalty")
    if nb > 1:
        raise ScoringError("A ball can carry at most one no-ball penalty.")
    if wides and nb:
        raise ScoringError("A ball cannot be both a wide and a no-ball (a no-ball takes precedence).")
    if wides and (runs_bat or byes or lb):
        raise ScoringError("On a wide, every run is scored as wides; there are no runs off the bat, byes or leg-byes.")
    if byes and lb:
        raise ScoringError("Runs on one ball are either byes or leg-byes, not both.")
    if runs_bat and (byes or lb):
        raise ScoringError("If the batter hit the ball the runs are off the bat, not byes or leg-byes.")
    w = ball.get("wicket")
    if w:
        kind = w.get("kind")
        if kind not in ALL_DISMISSALS:
            raise ScoringError(f"Unknown dismissal '{kind}'.")
        if nb and kind not in ALLOWED_ON_NO_BALL:
            raise ScoringError(f"A batter cannot be out {kind.replace('_', ' ')} off a no-ball.")
        if wides and kind not in ALLOWED_ON_WIDE:
            raise ScoringError(f"A batter cannot be out {kind.replace('_', ' ')} off a wide.")
        out = w.get("player_out", ball["striker"])
        if out not in (ball["striker"], ball.get("non_striker")):
            raise ScoringError("The player out must be the striker or the non-striker.")
        if kind in BOWLER_WICKETS and out != ball["striker"]:
            raise ScoringError(f"Only the striker can be out {kind.replace('_', ' ')}.")


def _new_batter(pid) -> dict:
    return {"player": pid, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dots": 0,
            "out": False, "how_out": None, "bowler": None, "fielder": None, "position": None}


def _new_bowler(pid) -> dict:
    return {"player": pid, "legal_balls": 0, "runs": 0, "wickets": 0, "maidens": 0,
            "wides": 0, "no_balls": 0, "dots": 0, "fours": 0, "sixes": 0}


def score_innings(balls: Iterable[dict], max_overs: Optional[int] = None, target: Optional[int] = None,
                  max_wickets: int = 10, validate: bool = True) -> dict:
    """Compute a full scorecard from a list of balls in the order they were bowled."""
    batters: dict[Any, dict] = {}
    bowlers: dict[Any, dict] = {}
    extras = {"wides": 0, "no_balls": 0, "byes": 0, "leg_byes": 0, "penalty": 0}
    total = wickets = legal = 0
    fall_of_wickets, partnerships, overs = [], [], []
    part = None                    # current partnership
    over_bowler_runs = 0           # runs charged to the bowler in the current over
    over_illegal = False           # a wide/no-ball in the over means it cannot be a maiden
    over_runs = over_wkts = 0
    current_over_balls: list[str] = []
    complete = False
    next_striker = next_non_striker = None

    def batter(pid):
        if pid not in batters:
            batters[pid] = _new_batter(pid)
            batters[pid]["position"] = len(batters)
        return batters[pid]

    def open_partnership(a, b):
        return {"wicket": wickets + 1, "batters": [a, b], "runs": 0, "balls": 0,
                "contrib": {a: 0, b: 0}, "unbroken": True}

    for n, ball in enumerate(balls):
        if complete:
            raise ScoringError(f"Ball {n + 1} was bowled after the innings had ended.")
        if validate:
            validate_ball(ball)
        s, ns, bw = ball["striker"], ball.get("non_striker"), ball["bowler"]
        runs_bat, wides, nb = ball.get("runs_bat") or 0, ball.get("wides") or 0, ball.get("no_balls") or 0
        byes, lb, pen = ball.get("byes") or 0, ball.get("leg_byes") or 0, ball.get("penalty") or 0
        is_legal = not wides and not nb
        ball_total = runs_bat + wides + nb + byes + lb + pen
        bowler_runs = runs_bat + wides + nb

        bs = batter(s)
        if ns is not None:
            batter(ns)
        if part is None or set(part["batters"]) != {s, ns}:
            if part is not None and part["unbroken"]:
                # Batters changed without a recorded wicket (e.g. retired hurt): close it.
                part["unbroken"] = False
                partnerships.append(part)
            part = open_partnership(s, ns)

        # --- batter
        if not wides:                       # a wide is not a ball faced
            bs["balls"] += 1
            if runs_bat == 0:
                bs["dots"] += 1
        bs["runs"] += runs_bat
        boundary = ball.get("boundary", runs_bat in (4, 6))
        if boundary and runs_bat == 4:
            bs["fours"] += 1
        if boundary and runs_bat == 6:
            bs["sixes"] += 1

        # --- bowler
        bo = bowlers.setdefault(bw, _new_bowler(bw))
        bo["runs"] += bowler_runs
        bo["wides"] += wides
        bo["no_balls"] += nb
        if is_legal:
            bo["legal_balls"] += 1
            if bowler_runs == 0:
                bo["dots"] += 1
        if boundary and runs_bat == 4:
            bo["fours"] += 1
        if boundary and runs_bat == 6:
            bo["sixes"] += 1

        # --- team
        total += ball_total
        extras["wides"] += wides
        extras["no_balls"] += nb
        extras["byes"] += byes
        extras["leg_byes"] += lb
        extras["penalty"] += pen
        part["runs"] += ball_total
        part["contrib"][s] = part["contrib"].get(s, 0) + runs_bat
        if is_legal:
            legal += 1
            part["balls"] += 1
        over_bowler_runs += bowler_runs
        over_runs += ball_total
        over_illegal = over_illegal or not is_legal

        # --- symbol for the over strip
        w = ball.get("wicket")
        real_wicket = bool(w) and w.get("kind") not in NOT_A_WICKET
        if real_wicket:
            sym = "W" if ball_total == 0 else f"{ball_total}W"
        elif wides:
            sym = "wd" if wides == 1 else f"{wides}wd"
        elif nb:
            sym = "nb" if ball_total == 1 else f"{ball_total}nb"
        elif byes:
            sym = f"{byes}b"
        elif lb:
            sym = f"{lb}lb"
        else:
            sym = "•" if runs_bat == 0 else str(runs_bat)
        current_over_balls.append(sym)

        # --- who is on strike next: odd runs physically run swap the batters
        ran = byes + lb + max(wides - 1, 0) + (0 if boundary else runs_bat)
        on_strike, off_strike = (ns, s) if ran % 2 == 1 else (s, ns)

        # --- wicket
        if w:
            out = w.get("player_out", s)
            kind = w["kind"]
            ob = batter(out)
            ob["how_out"] = kind
            ob["fielder"] = w.get("fielder")
            if kind in NOT_A_WICKET:
                ob["retired"] = True
            else:
                ob["out"] = True
                wickets += 1
                over_wkts += 1
                if kind in BOWLER_WICKETS:
                    bo["wickets"] += 1
                    ob["bowler"] = bw
                fall_of_wickets.append({"wicket": wickets, "score": total, "player": out,
                                        "over": overs_text(legal), "how_out": kind})
            part["unbroken"] = False
            partnerships.append(part)
            part = None
            # The incoming batter takes the place of the player who is out.
            if on_strike == out:
                on_strike = None
            else:
                off_strike = None
            if "new_batter_on_strike" in ball:      # explicit override from the scorer
                survivor = on_strike if on_strike is not None else off_strike
                on_strike, off_strike = (None, survivor) if ball["new_batter_on_strike"] else (survivor, None)

        # --- end of over
        if is_legal and legal % BALLS_PER_OVER == 0:
            if over_bowler_runs == 0 and not over_illegal:
                bo["maidens"] += 1
            overs.append({"over": legal // BALLS_PER_OVER, "bowler": bw, "runs": over_runs,
                          "wickets": over_wkts, "balls": current_over_balls, "total": total,
                          "total_wickets": wickets})
            over_bowler_runs = over_runs = over_wkts = 0
            over_illegal = False
            current_over_balls = []
            on_strike, off_strike = off_strike, on_strike   # ends change

        next_striker, next_non_striker = on_strike, off_strike

        if wickets >= max_wickets:
            complete = True
        if max_overs is not None and legal >= max_overs * BALLS_PER_OVER:
            complete = True
        if target is not None and total >= target:
            complete = True

    if current_over_balls:      # an over in progress
        overs.append({"over": legal // BALLS_PER_OVER + 1,
                      "bowler": next(reversed(bowlers)) if bowlers else None,
                      "runs": over_runs, "wickets": over_wkts, "balls": current_over_balls,
                      "total": total, "total_wickets": wickets, "in_progress": True})
    if part is not None:
        partnerships.append(part)

    batting = sorted(batters.values(), key=lambda b: b["position"])
    for b in batting:
        b["strike_rate"] = (b["runs"] / b["balls"] * 100.0) if b["balls"] else None
    bowling = list(bowlers.values())
    for b in bowling:
        b["overs"] = overs_text(b["legal_balls"])
        b["economy"] = run_rate(b["runs"], b["legal_balls"])
    for p in partnerships:
        p["contrib"] = [{"player": k, "runs": v} for k, v in p["contrib"].items()]
        p["run_rate"] = run_rate(p["runs"], p["balls"])

    extras_total = sum(extras.values())
    balls_left = (max_overs * BALLS_PER_OVER - legal) if max_overs is not None else None
    return {
        "total": total, "wickets": wickets, "legal_balls": legal, "overs": overs_text(legal),
        "run_rate": run_rate(total, legal),
        "extras": {**extras, "total": extras_total},
        "batting": batting, "bowling": bowling,
        "fall_of_wickets": fall_of_wickets, "partnerships": partnerships, "over_by_over": overs,
        "complete": complete,
        "target": target,
        "balls_remaining": balls_left,
        "runs_required": max(target - total, 0) if target is not None else None,
        "required_run_rate": required_run_rate(target, total, balls_left)
        if target is not None and balls_left is not None else None,
        "next": {"striker": next_striker, "non_striker": next_non_striker,
                 "over_complete": bool(legal) and legal % BALLS_PER_OVER == 0 and not current_over_balls},
    }


def match_result(first: dict, second: dict, team_a: str, team_b: str, max_wickets: int = 10) -> str:
    """Plain-language result. `first` is team_a's innings, `second` is team_b's chase."""
    if second["total"] > first["total"]:
        left = max_wickets - second["wickets"]
        return f"{team_b} won by {left} wicket{'s' if left != 1 else ''}"
    if not second["complete"]:
        return "In progress"
    if second["total"] == first["total"]:
        return "Match tied"
    margin = first["total"] - second["total"]
    return f"{team_a} won by {margin} run{'s' if margin != 1 else ''}"


def _clean(v):
    """None for missing values (None, NaN, empty string) so CSV/pandas rows can be used directly."""
    if v is None or v == "":
        return None
    try:
        if v != v:          # NaN is the only value not equal to itself
            return None
    except Exception:
        pass
    return v


def flat_to_ball(row: dict) -> dict:
    """Convert a flat record (as stored in balls.csv) to the engine's ball shape.

    Flat records keep the dismissal in `wicket_kind` / `player_out` / `fielder` columns.
    """
    ball = {k: _clean(row.get(k)) for k in ("striker", "non_striker", "bowler")}
    for k in ("runs_bat", "wides", "no_balls", "byes", "leg_byes", "penalty"):
        v = _clean(row.get(k))
        ball[k] = int(v) if v is not None else 0
    kind = _clean(row.get("wicket_kind"))
    if kind:
        ball["wicket"] = {"kind": kind, "player_out": _clean(row.get("player_out")) or ball["striker"],
                          "fielder": _clean(row.get("fielder"))}
    return ball


def lines_from_balls(rows: Iterable[dict], max_overs: Optional[int] = None) -> dict:
    """Per-innings batting and bowling lines from flat ball records.

    Rows are grouped by (match_id, innings) in the order given. Returns
    {"batting": [...], "bowling": [...], "innings": {(match_id, innings): scorecard}}.
    """
    groups: dict = {}
    meta: dict = {}
    for r in rows:
        key = (_clean(r.get("match_id")), _clean(r.get("innings")))
        groups.setdefault(key, []).append(flat_to_ball(r))
        meta.setdefault(key, {"match_id": key[0], "innings": key[1], "date": _clean(r.get("date")),
                              "batting_team": _clean(r.get("batting_team"))})
    batting, bowling, cards = [], [], {}
    for key, balls in groups.items():
        card = score_innings(balls, max_overs=max_overs)
        cards[key] = card
        for b in card["batting"]:
            batting.append({**meta[key], **b})
        for b in card["bowling"]:
            bowling.append({**meta[key], **b})
    return {"batting": batting, "bowling": bowling, "innings": cards}
