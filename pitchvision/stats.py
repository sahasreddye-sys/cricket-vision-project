"""Batting, bowling and fielding statistics.

Everything works on plain lists of dicts so the same functions serve database
rows (backend) and `DataFrame.to_dict("records")` (notebooks).

Definitions (standard cricket statistics)
-----------------------------------------
Batting average   = runs / times out                 (undefined if never out)
Batting strike rate = runs / balls faced * 100
Bowling average   = runs conceded / wickets          (undefined with no wickets)
Economy rate      = runs conceded / overs            (overs = legal balls / 6)
Bowling strike rate = legal balls / wickets          (undefined with no wickets)
Catch success %   = catches / (catches + drops) * 100
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Optional

from .constants import BALLS_PER_OVER
from .pitchmap import classify_length, classify_line
from .scoring import overs_text

# ---------------------------------------------------------------- helpers

def safe_div(a: float, b: float) -> Optional[float]:
    """a / b, or None when b is zero or either value is missing."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _num(v, default=0):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    return v


# ---------------------------------------------------------------- batting

def career_batting(lines: Iterable[dict]) -> list[dict]:
    """Aggregate per-innings batting lines into one row per player.

    A line: {player, runs, balls, fours, sixes, out (bool), match_id, date?}
    Lines with a missing `runs` value are skipped (did not bat / not recorded).
    """
    agg: dict = {}
    for ln in lines:
        if ln.get("runs") is None:
            continue
        p = ln["player"]
        a = agg.setdefault(p, {"player": p, "innings": 0, "not_outs": 0, "runs": 0, "balls": 0,
                               "fours": 0, "sixes": 0, "highest": -1, "highest_not_out": False,
                               "fifties": 0, "hundreds": 0, "ducks": 0, "scores": []})
        runs, out = int(_num(ln["runs"])), bool(ln.get("out"))
        a["innings"] += 1
        a["not_outs"] += 0 if out else 1
        a["runs"] += runs
        a["balls"] += int(_num(ln.get("balls")))
        a["fours"] += int(_num(ln.get("fours")))
        a["sixes"] += int(_num(ln.get("sixes")))
        if runs > a["highest"] or (runs == a["highest"] and not out):
            a["highest"], a["highest_not_out"] = runs, not out
        if runs >= 100:
            a["hundreds"] += 1
        elif runs >= 50:
            a["fifties"] += 1
        if runs == 0 and out:
            a["ducks"] += 1
        a["scores"].append({"runs": runs, "out": out, "balls": int(_num(ln.get("balls"))),
                            "match_id": ln.get("match_id"), "date": ln.get("date")})
    out_rows = []
    for a in agg.values():
        dismissals = a["innings"] - a["not_outs"]
        a["average"] = safe_div(a["runs"], dismissals)
        a["strike_rate"] = None if a["balls"] == 0 else a["runs"] / a["balls"] * 100.0
        a["highest_text"] = f"{a['highest']}{'*' if a['highest_not_out'] else ''}"
        a["boundary_pct"] = None if a["runs"] == 0 else (4 * a["fours"] + 6 * a["sixes"]) / a["runs"] * 100.0
        out_rows.append(a)
    return sorted(out_rows, key=lambda r: -r["runs"])


# ---------------------------------------------------------------- bowling

def career_bowling(lines: Iterable[dict]) -> list[dict]:
    """Aggregate per-innings bowling lines into one row per player.

    A line: {player, legal_balls, runs, wickets, maidens, wides, no_balls, dots?}
    """
    agg: dict = {}
    for ln in lines:
        if ln.get("legal_balls") is None:
            continue
        p = ln["player"]
        a = agg.setdefault(p, {"player": p, "innings": 0, "legal_balls": 0, "runs": 0, "wickets": 0,
                               "maidens": 0, "wides": 0, "no_balls": 0, "dots": 0,
                               "best_wickets": -1, "best_runs": 0, "spells": []})
        balls, runs, wk = int(_num(ln["legal_balls"])), int(_num(ln.get("runs"))), int(_num(ln.get("wickets")))
        a["innings"] += 1
        a["legal_balls"] += balls
        a["runs"] += runs
        a["wickets"] += wk
        for k in ("maidens", "wides", "no_balls", "dots"):
            a[k] += int(_num(ln.get(k)))
        # Best figures: most wickets, then fewest runs.
        if wk > a["best_wickets"] or (wk == a["best_wickets"] and runs < a["best_runs"]):
            a["best_wickets"], a["best_runs"] = wk, runs
        a["spells"].append({"overs": overs_text(balls), "runs": runs, "wickets": wk,
                            "economy": safe_div(runs * BALLS_PER_OVER, balls),
                            "match_id": ln.get("match_id"), "date": ln.get("date")})
    rows = []
    for a in agg.values():
        a["overs"] = overs_text(a["legal_balls"])
        a["average"] = safe_div(a["runs"], a["wickets"])
        a["economy"] = safe_div(a["runs"] * BALLS_PER_OVER, a["legal_balls"])
        a["strike_rate"] = safe_div(a["legal_balls"], a["wickets"])
        a["best"] = f"{a['best_wickets']}/{a['best_runs']}" if a["best_wickets"] >= 0 else None
        a["dot_pct"] = safe_div(a["dots"] * 100.0, a["legal_balls"])
        rows.append(a)
    return sorted(rows, key=lambda r: (-r["wickets"], r["economy"] if r["economy"] is not None else 99))


# ---------------------------------------------------------------- fielding

FIELDING_EVENTS = ("catch", "drop", "run_out", "direct_hit", "missed_run_out", "stumping",
                   "missed_stumping", "clean_stop", "misfield")


def career_fielding(events: Iterable[dict]) -> list[dict]:
    """One row per player from fielding events {player, kind, count?}."""
    agg: dict = {}
    for e in events:
        kind = e.get("kind")
        if kind not in FIELDING_EVENTS:
            continue
        p = e["player"]
        a = agg.setdefault(p, {"player": p, **{k: 0 for k in FIELDING_EVENTS}})
        a[kind] += int(_num(e.get("count"), 1))
    rows = []
    for a in agg.values():
        # A direct hit is a run-out effected by a throw that hit the stumps.
        a["run_outs_total"] = a["run_out"] + a["direct_hit"]
        a["catch_chances"] = a["catch"] + a["drop"]
        a["catch_pct"] = safe_div(a["catch"] * 100.0, a["catch_chances"])
        a["run_out_chances"] = a["run_outs_total"] + a["missed_run_out"]
        a["run_out_pct"] = safe_div(a["run_outs_total"] * 100.0, a["run_out_chances"])
        a["ground_chances"] = a["clean_stop"] + a["misfield"]
        a["ground_pct"] = safe_div(a["clean_stop"] * 100.0, a["ground_chances"])
        a["opportunities"] = (a["catch_chances"] + a["run_out_chances"] + a["ground_chances"]
                              + a["stumping"] + a["missed_stumping"])
        a["dismissals"] = a["catch"] + a["run_outs_total"] + a["stumping"]
        rows.append(a)
    return sorted(rows, key=lambda r: -r["dismissals"])


# ---------------------------------------------------------------- ball-level splits

def _bat_split(balls: list[dict]) -> dict:
    """Runs, balls faced, dismissals, average and strike rate for a set of balls faced."""
    runs = sum(int(_num(b.get("runs_bat"))) for b in balls)
    faced = sum(1 for b in balls if not _num(b.get("wides")))
    outs = sum(1 for b in balls
               if b.get("wicket_kind") and b.get("wicket_kind") not in ("retired_hurt", "retired_not_out")
               and b.get("player_out", b.get("striker")) == b.get("striker"))
    dots = sum(1 for b in balls if not _num(b.get("wides")) and not _num(b.get("runs_bat")))
    return {"balls": faced, "runs": runs, "dismissals": outs,
            "average": safe_div(runs, outs), "strike_rate": safe_div(runs * 100.0, faced),
            "dot_pct": safe_div(dots * 100.0, faced)}


def batting_splits(balls: Iterable[dict], player) -> dict:
    """A batter's record against pace/spin, by length, by line and by shot type."""
    mine = [b for b in balls if b.get("striker") == player]
    groups = {"bowl_type": defaultdict(list), "length": defaultdict(list),
              "line": defaultdict(list), "shot_type": defaultdict(list)}
    for b in mine:
        if b.get("bowl_type"):
            groups["bowl_type"][b["bowl_type"]].append(b)
        if b.get("y") is not None:
            groups["length"][classify_length(b["y"], b.get("bounced", True))].append(b)
        if b.get("x") is not None:
            groups["line"][classify_line(b["x"])].append(b)
        if b.get("shot_type"):
            groups["shot_type"][b["shot_type"]].append(b)
    return {"overall": _bat_split(mine),
            **{g: {k: _bat_split(v) for k, v in d.items()} for g, d in groups.items()}}


def bowling_splits(balls: Iterable[dict], player) -> dict:
    """A bowler's record by length and by line (runs conceded per ball, wickets)."""
    mine = [b for b in balls if b.get("bowler") == player]
    out = {"length": defaultdict(list), "line": defaultdict(list)}
    for b in mine:
        if b.get("y") is not None:
            out["length"][classify_length(b["y"], b.get("bounced", True))].append(b)
        if b.get("x") is not None:
            out["line"][classify_line(b["x"])].append(b)

    def summarise(bs):
        legal = sum(1 for b in bs if not _num(b.get("wides")) and not _num(b.get("no_balls")))
        runs = sum(int(_num(b.get("runs_bat"))) + int(_num(b.get("wides"))) + int(_num(b.get("no_balls"))) for b in bs)
        wk = sum(1 for b in bs if b.get("wicket_kind") in
                 ("bowled", "caught", "lbw", "stumped", "hit_wicket", "caught_and_bowled"))
        return {"balls": legal, "runs": runs, "wickets": wk,
                "economy": safe_div(runs * BALLS_PER_OVER, legal)}

    return {g: {k: summarise(v) for k, v in d.items()} for g, d in out.items()}


# ---------------------------------------------------------------- wagon wheel

# Zones for a handedness-normalised batter. Angle 0 deg = straight back past the
# bowler; angles increase CLOCKWISE seen from above, i.e. toward the OFF side.
WAGON_ZONES = ["long_off", "cover", "point", "third_man", "fine_leg", "square_leg", "midwicket", "long_on"]
OFF_SIDE_ZONES = {"long_off", "cover", "point", "third_man"}


def wagon_zone(angle_deg: float) -> str:
    return WAGON_ZONES[int((angle_deg % 360) // 45)]


def wagon_wheel(shots: Iterable[dict]) -> dict:
    """Scoring distribution by zone from shots {shot_angle (deg), runs_bat}.

    Shots without an angle are counted in `unplotted` and left out of the zones.
    """
    zones = {z: {"zone": z, "shots": 0, "runs": 0, "fours": 0, "sixes": 0} for z in WAGON_ZONES}
    total_runs = unplotted = 0
    plotted = []
    for s in shots:
        ang, runs = s.get("shot_angle"), int(_num(s.get("runs_bat")))
        if ang is None or (isinstance(ang, float) and math.isnan(ang)):
            unplotted += 1
            continue
        z = zones[wagon_zone(ang)]
        z["shots"] += 1
        z["runs"] += runs
        z["fours"] += 1 if runs == 4 else 0
        z["sixes"] += 1 if runs == 6 else 0
        total_runs += runs
        plotted.append({"angle": ang % 360, "runs": runs, "zone": z["zone"],
                        "shot_type": s.get("shot_type"), "match_id": s.get("match_id")})
    rows = list(zones.values())
    for z in rows:
        z["pct_of_runs"] = safe_div(z["runs"] * 100.0, total_runs) or 0.0
    off = sum(z["runs"] for z in rows if z["zone"] in OFF_SIDE_ZONES)
    scoring = [z for z in rows if z["runs"] > 0]
    return {"zones": rows, "shots": plotted, "total_runs": total_runs, "unplotted": unplotted,
            "off_side_pct": safe_div(off * 100.0, total_runs),
            "leg_side_pct": safe_div((total_runs - off) * 100.0, total_runs),
            "strong_zones": [z["zone"] for z in sorted(scoring, key=lambda z: -z["runs"])[:3]]}


# ---------------------------------------------------------------- leaderboards

def leaderboard(rows: list[dict], key: str, descending: bool = True, min_filter: Optional[tuple] = None,
                limit: int = 10) -> list[dict]:
    """Rank rows by `key`. Rows where the value is None are excluded.

    `min_filter=(field, minimum)` applies a qualification rule (for example at
    least 3 dismissals before a batting average is ranked) and is returned with
    the result so the table can state it.
    """
    pool = [r for r in rows if r.get(key) is not None]
    if min_filter:
        f, m = min_filter
        pool = [r for r in pool if _num(r.get(f)) >= m]
    pool.sort(key=lambda r: r[key], reverse=descending)
    return [{"rank": i + 1, "player": r["player"], "value": r[key]} for i, r in enumerate(pool[:limit])]


def improvement(scores_by_player: dict, higher_is_better: bool = True, min_each: int = 2) -> list[dict]:
    """Change between the earlier half and the later half of each player's readings.

    `scores_by_player` maps player -> chronological list of numbers (runs per
    innings, speeds, accuracy %, ...). Players need at least `min_each` readings
    in each half; otherwise no improvement figure is reported for them.
    """
    out = []
    for p, vals in scores_by_player.items():
        vals = [v for v in vals if v is not None]
        half = len(vals) // 2
        if half < min_each:
            continue
        early, late = vals[:half], vals[-half:]
        change = sum(late) / len(late) - sum(early) / len(early)
        out.append({"player": p, "early_mean": sum(early) / len(early), "late_mean": sum(late) / len(late),
                    "change": change, "improved": (change > 0) == higher_is_better and change != 0,
                    "n": len(vals)})
    out.sort(key=lambda r: r["change"], reverse=higher_is_better)
    for i, r in enumerate(out):
        r["rank"] = i + 1
    return out


# ---------------------------------------------------------------- opposition scouting

def scouting_report(balls: Iterable[dict], batter) -> dict:
    """Evidence-based scouting summary for one (opposition) batter.

    Every statement carries the numbers it is based on. Groups with fewer than
    `MIN_BALLS` balls are reported as 'not enough data' rather than interpreted.
    """
    MIN_BALLS = 6
    balls = list(balls)
    sp = batting_splits(balls, batter)
    mine = [b for b in balls if b.get("striker") == batter]
    ww = wagon_wheel(mine)
    dismissals = defaultdict(int)
    for b in mine:
        k = b.get("wicket_kind")
        if k and b.get("player_out", batter) == batter:
            dismissals[k] += 1
    findings = []

    def enough(d):
        return d and d["balls"] >= MIN_BALLS

    pace, spin = sp["bowl_type"].get("pace"), sp["bowl_type"].get("spin")
    if enough(pace) and enough(spin):
        slower = "spin" if spin["strike_rate"] < pace["strike_rate"] else "pace"
        findings.append({
            "finding": f"Scores more slowly against {slower}.",
            "evidence": f"Strike rate {pace['strike_rate']:.0f} vs pace ({pace['balls']} balls), "
                        f"{spin['strike_rate']:.0f} vs spin ({spin['balls']} balls)."})
    best_len = [(k, v) for k, v in sp["length"].items() if enough(v)]
    if best_len:
        k, v = min(best_len, key=lambda kv: (-(kv[1]["dismissals"] / kv[1]["balls"]), kv[1]["strike_rate"]))
        findings.append({
            "finding": f"Most effective length so far: {k.replace('_', ' ')}.",
            "evidence": f"{v['runs']} runs from {v['balls']} balls (SR {v['strike_rate']:.0f}), "
                        f"{v['dismissals']} dismissal(s)."})
    best_line = [(k, v) for k, v in sp["line"].items() if enough(v)]
    if best_line:
        k, v = min(best_line, key=lambda kv: (-(kv[1]["dismissals"] / kv[1]["balls"]), kv[1]["strike_rate"]))
        findings.append({
            "finding": f"Most effective line so far: {k.replace('_', ' ')}.",
            "evidence": f"{v['runs']} runs from {v['balls']} balls (SR {v['strike_rate']:.0f}), "
                        f"{v['dismissals']} dismissal(s)."})
    if ww["strong_zones"] and ww["total_runs"] >= 10:
        top = [z for z in ww["zones"] if z["zone"] in ww["strong_zones"]]
        top.sort(key=lambda z: -z["runs"])
        findings.append({
            "finding": "Main scoring areas: " + ", ".join(z["zone"].replace("_", " ") for z in top) + ".",
            "evidence": ", ".join(f"{z['zone'].replace('_', ' ')} {z['runs']} runs ({z['pct_of_runs']:.0f}%)" for z in top) + "."})
    if dismissals:
        k = max(dismissals, key=dismissals.get)
        findings.append({"finding": f"Most common dismissal: {k.replace('_', ' ')}.",
                         "evidence": ", ".join(f"{n} x {d.replace('_', ' ')}" for d, n in dismissals.items()) + "."})
    shots = [(k, v) for k, v in sp["shot_type"].items() if v["balls"] >= 3]
    if shots:
        k, v = max(shots, key=lambda kv: kv[1]["runs"])
        findings.append({"finding": f"Preferred scoring shot: {k.replace('_', ' ')}.",
                         "evidence": f"{v['runs']} runs from {v['balls']} balls played with this shot."})
    return {"batter": batter, "balls_recorded": sp["overall"]["balls"], "overall": sp["overall"],
            "splits": sp, "wagon_wheel": ww, "dismissals": dict(dismissals), "findings": findings,
            "enough_data": sp["overall"]["balls"] >= MIN_BALLS,
            "note": f"Groups with fewer than {MIN_BALLS} balls are not interpreted."}


# ---------------------------------------------------------------- field recommendations

# Named positions for a handedness-normalised batter: (angle deg, distance 0-1 of boundary radius).
FIELD_POSITIONS = {
    "long_off": (22, 0.92), "mid_off": (25, 0.45), "extra_cover": (55, 0.48), "deep_cover": (65, 0.92),
    "cover": (70, 0.42), "point": (100, 0.40), "deep_point": (105, 0.92), "gully": (125, 0.22),
    "slip": (160, 0.16), "third_man": (150, 0.90), "fine_leg": (205, 0.90), "short_fine_leg": (210, 0.35),
    "square_leg": (255, 0.42), "deep_square_leg": (255, 0.92), "midwicket": (295, 0.42),
    "deep_midwicket": (295, 0.92), "mid_on": (335, 0.45), "long_on": (338, 0.92),
}
_ZONE_FIELDERS = {  # (inner position, boundary position) for each wagon zone
    "long_off": ("mid_off", "long_off"), "cover": ("cover", "deep_cover"), "point": ("point", "deep_point"),
    "third_man": ("gully", "third_man"), "fine_leg": ("short_fine_leg", "fine_leg"),
    "square_leg": ("square_leg", "deep_square_leg"), "midwicket": ("midwicket", "deep_midwicket"),
    "long_on": ("mid_on", "long_on"),
}


def recommend_field(shots: Iterable[dict], style: str = "balanced", fielders: int = 9) -> dict:
    """Place `fielders` (excluding bowler and keeper) according to where a batter scores.

    Method (stated so the coach can disagree with it):
      1. Split the batter's recorded runs into the eight wagon-wheel zones.
      2. Give each zone a share of fielders proportional to its share of runs
         (largest-remainder rounding), with at least one fielder in every zone
         that has conceded a boundary.
      3. In each zone, a 'defensive' field puts the first fielder on the boundary,
         an 'attacking' field puts fielders in the ring first and adds a slip,
         'balanced' alternates.
    With fewer than 12 plotted scoring shots no recommendation is made.
    """
    ww = wagon_wheel(shots)
    scoring = sum(1 for s in ww["shots"] if s["runs"] > 0)
    if scoring < 12:
        return {"enough_data": False, "positions": [], "reasons": [],
                "note": f"Only {scoring} plotted scoring shots; at least 12 are needed before a field is suggested."}
    budget = fielders - (1 if style == "attacking" else 0)
    shares = {z["zone"]: z["runs"] / ww["total_runs"] * budget for z in ww["zones"]}
    alloc = {z: int(math.floor(s)) for z, s in shares.items()}
    for z in ww["zones"]:
        if (z["fours"] or z["sixes"]) and alloc[z["zone"]] == 0:
            alloc[z["zone"]] = 1
    while sum(alloc.values()) > budget:
        z = max((z for z in alloc if alloc[z] > 0), key=lambda z: alloc[z] - shares[z])
        alloc[z] -= 1
    remainders = sorted(shares, key=lambda z: shares[z] - alloc[z], reverse=True)
    i = 0
    while sum(alloc.values()) < budget:
        alloc[remainders[i % len(remainders)]] += 1
        i += 1
    positions, reasons = [], []
    if style == "attacking":
        positions.append("slip")
        reasons.append({"position": "slip", "reason": "Attacking field: one catcher behind the wicket."})
    for z in ww["zones"]:
        n = alloc[z["zone"]]
        if not n:
            continue
        inner, deep = _ZONE_FIELDERS[z["zone"]]
        order = {"defensive": [deep, inner], "attacking": [inner, deep], "balanced":
                 [deep, inner] if (z["fours"] + z["sixes"]) >= 2 else [inner, deep]}[style]
        for k in range(min(n, 2)):
            positions.append(order[k])
            reasons.append({"position": order[k],
                            "reason": f"{z['pct_of_runs']:.0f}% of runs ({z['runs']}) scored through "
                                      f"{z['zone'].replace('_', ' ')}; {z['fours']} fours, {z['sixes']} sixes there."})
    # If rounding left fielders over (a zone capped at two), cover the straight boundaries.
    for extra in ("mid_off", "mid_on", "cover", "midwicket", "point", "square_leg"):
        if len(positions) >= fielders:
            break
        if extra not in positions:
            positions.append(extra)
            reasons.append({"position": extra, "reason": "Ring fielder added to complete the field."})
    return {"enough_data": True, "style": style,
            "positions": [{"name": p, "angle": FIELD_POSITIONS[p][0], "distance": FIELD_POSITIONS[p][1]}
                          for p in positions[:fielders]],
            "reasons": reasons[:fielders], "based_on_shots": scoring, "total_runs": ww["total_runs"],
            "note": "Positions follow recorded scoring areas only. They do not account for the bowler, "
                    "pitch, match situation or fielding restrictions."}
