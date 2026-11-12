"""SYNTHETIC sample data.

Everything produced here is computer-generated for demonstrations, notebooks and
tests. The players, matches and numbers are invented. It must never be shown as
a real team's performance; every table carries a `synthetic = True` marker.

The generator is deterministic for a given seed, so notebook outputs are
reproducible.
"""
from __future__ import annotations

import csv
import datetime as dt
import os

import numpy as np

from .pitchmap import classify_length
from .scoring import score_innings

TEAM = "Sample XI (synthetic)"
OPPONENTS = ["Northfield (synthetic)", "Riverside (synthetic)", "Hilltop (synthetic)", "Eastbrook (synthetic)"]

# name, role, bat skill 0-1, bowl skill 0-1, bowl style, typical speed km/h, catching skill
_SQUAD = [
    ("Arun Mehta", "batter", 0.80, 0.10, None, None, 0.80),
    ("Ben Carter", "batter", 0.72, 0.15, None, None, 0.70),
    ("Dev Patel", "wicket_keeper", 0.66, 0.00, None, None, 0.85),
    ("Ethan Brooks", "batter", 0.60, 0.20, "spin_off", 68, 0.65),
    ("Farhan Ali", "all_rounder", 0.62, 0.62, "pace_medium", 104, 0.75),
    ("George Hill", "all_rounder", 0.55, 0.58, "spin_leg", 70, 0.60),
    ("Harry Singh", "batter", 0.50, 0.10, None, None, 0.55),
    ("Imran Khan", "bowler", 0.30, 0.78, "pace_fast", 116, 0.70),
    ("Jack Wood", "bowler", 0.25, 0.70, "pace_medium", 108, 0.50),
    ("Kabir Rao", "bowler", 0.22, 0.72, "spin_off", 72, 0.65),
    ("Liam Shaw", "bowler", 0.18, 0.60, "pace_medium", 101, 0.45),
    ("Milan Das", "all_rounder", 0.45, 0.50, "pace_medium", 98, 0.60),
    ("Noah Reid", "batter", 0.42, 0.05, None, None, 0.50),
    ("Omar Aziz", "wicket_keeper", 0.40, 0.00, None, None, 0.70),
]
_SHOTS = {  # shot type -> (mean angle deg, spread)
    "drive": (25, 28), "cut": (100, 18), "pull": (265, 22), "flick": (300, 22), "sweep": (240, 20),
    "defence": (0, 60), "glance": (205, 15), "loft": (350, 30),
}


def players() -> list[dict]:
    return [{"name": n, "role": r, "bowl_style": s, "batting_hand": "right", "synthetic": True}
            for n, r, _, _, s, _, _ in _SQUAD]


def _simulate_innings(rng, batting, bowling, max_overs, match_id, innings_no, batting_team, target=None):
    """batting: [(name, bat_skill)], bowling: [(name, bowl_skill, style)]. Returns ball dicts."""
    balls = []
    order = list(batting)
    striker, non_striker = order[0][0], order[1][0]
    next_in = 2
    skill = dict((n, s) for n, s in order)
    over_no = 0
    bowler_overs = {b[0]: 0 for b in bowling}
    cap = max(1, max_overs // 5)
    last_bowler = None
    while over_no < max_overs:
        choices = [b for b in bowling if bowler_overs[b[0]] < cap and b[0] != last_bowler] or \
                  [b for b in bowling if b[0] != last_bowler]
        bw_name, bw_skill, bw_style = choices[int(rng.integers(len(choices)))] if over_no > 1 else choices[over_no % len(choices)]
        last_bowler = bw_name
        bowler_overs[bw_name] += 1
        spin = (bw_style or "").startswith("spin")
        legal = 0
        while legal < 6:
            bat = skill.get(striker, 0.3)
            # Where the ball pitches: better bowlers group tighter around a good length just outside off.
            sd_x, sd_y = 0.42 - 0.25 * bw_skill, 2.6 - 1.4 * bw_skill
            x = float(rng.normal(0.18, sd_x))
            y = float(np.clip(rng.normal(5.0 if spin else 6.8, sd_y), 0.2, 14))
            ball = {"match_id": match_id, "innings": innings_no, "batting_team": batting_team, "over": over_no,
                    "striker": striker, "non_striker": non_striker, "bowler": bw_name,
                    "bowl_type": "spin" if spin else "pace", "x": round(x, 3), "y": round(y, 3),
                    "runs_bat": 0, "wides": 0, "no_balls": 0, "byes": 0, "leg_byes": 0,
                    "wicket_kind": None, "player_out": None, "fielder": None,
                    "shot_type": None, "shot_angle": None, "synthetic": True}
            r = rng.random()
            if abs(x) > 0.85 or r < 0.02:
                ball["wides"] = 1
                ball["x"] = round(float(np.sign(x) * max(abs(x), 0.9)), 3)
            elif r < 0.03:
                ball["no_balls"] = 1
                ball["runs_bat"] = int(rng.choice([0, 1, 4], p=[0.5, 0.3, 0.2]))
            else:
                length = classify_length(y)
                good = length == "good" and 0.0 <= x <= 0.35
                # Chance of a wicket and of scoring depend on batter skill, bowler skill and where it pitched.
                p_w = 0.062 + 0.05 * bw_skill - 0.05 * bat + (0.02 if good else 0) + (0.015 if spin and bat < 0.5 else 0)
                if rng.random() < max(p_w, 0.006):
                    kind = str(rng.choice(["bowled", "caught", "lbw", "run_out", "stumped" if spin else "caught"],
                                          p=[0.25, 0.40, 0.15, 0.08, 0.12]))
                    ball["wicket_kind"] = kind
                    ball["player_out"] = striker
                    if kind in ("caught", "run_out", "stumped"):
                        ball["fielder"] = bowling[int(rng.integers(len(bowling)))][0]
                else:
                    attack = 0.20 + 0.45 * bat - (0.18 if good else 0) + (0.12 if length in ("short", "full") else 0) \
                        - (0.10 if spin and bat < 0.55 else 0)
                    if rng.random() < attack:
                        ball["runs_bat"] = int(rng.choice([1, 2, 3, 4, 6], p=[0.52, 0.17, 0.02, 0.23, 0.06]))
                    elif rng.random() < 0.04:
                        ball["leg_byes" if rng.random() < 0.6 else "byes"] = 1
                    if length == "short":
                        shot = str(rng.choice(["pull", "cut", "defence"], p=[0.45, 0.4, 0.15]))
                    elif length in ("full", "yorker"):
                        shot = str(rng.choice(["drive", "flick", "loft", "defence"], p=[0.5, 0.25, 0.1, 0.15]))
                    else:
                        shot = str(rng.choice(["defence", "drive", "glance", "cut", "sweep" if spin else "flick"],
                                              p=[0.4, 0.2, 0.12, 0.13, 0.15]))
                    ball["shot_type"] = shot
                    if ball["runs_bat"] > 0:
                        mu, sd = _SHOTS[shot]
                        ball["shot_angle"] = round(float(rng.normal(mu, sd)) % 360, 1)
            balls.append(ball)
            if not ball["wides"] and not ball["no_balls"]:
                legal += 1
            state = score_innings([_engine_ball(b) for b in balls], max_overs=max_overs, target=target)
            striker, non_striker = state["next"]["striker"], state["next"]["non_striker"]
            if state["complete"]:
                return balls
            if striker is None or non_striker is None:
                if next_in >= len(order):
                    return balls
                new = order[next_in][0]
                next_in += 1
                if striker is None:
                    striker = new
                else:
                    non_striker = new
        over_no += 1
    return balls


def _engine_ball(b: dict) -> dict:
    """Convert a flat record (wicket_kind/player_out columns) to the scoring engine's shape."""
    out = {k: b.get(k) for k in ("striker", "non_striker", "bowler", "runs_bat", "wides", "no_balls", "byes",
                                 "leg_byes", "penalty")}
    if b.get("wicket_kind"):
        out["wicket"] = {"kind": b["wicket_kind"], "player_out": b.get("player_out") or b["striker"],
                         "fielder": b.get("fielder")}
    return out


def engine_balls(rows: list[dict]) -> list[dict]:
    """Public helper: flat ball records -> scoring-engine balls."""
    return [_engine_ball(r) for r in rows]


def generate(seed: int = 42, n_matches: int = 8, overs: int = 20) -> dict:
    """Generate the full synthetic data set."""
    rng = np.random.default_rng(seed)
    squad = _SQUAD
    start = dt.date(2025, 4, 26)
    matches, balls = [], []
    for m in range(n_matches):
        mid = m + 1
        date = start + dt.timedelta(days=7 * m)
        opp = OPPONENTS[m % len(OPPONENTS)]
        avail = [squad[i] for i in sorted(rng.choice(len(squad), size=12, replace=False))]
        keepers = [p for p in avail if p[1] == "wicket_keeper"][:1]
        others = [p for p in avail if p not in keepers]
        xi = (keepers + others)[:11]
        xi.sort(key=lambda p: -p[2])
        our_bat = [(p[0], p[2]) for p in xi]
        our_bowl = [(p[0], p[3], p[4]) for p in xi if p[4]]
        opp_strength = float(rng.uniform(0.35, 0.6))
        opp_bat = [(f"{opp.split()[0]} batter {i + 1}", float(np.clip(opp_strength + 0.25 - 0.06 * i + rng.normal(0, 0.05), 0.1, 0.85)))
                   for i in range(11)]
        opp_bowl = [(f"{opp.split()[0]} bowler {i + 1}", float(np.clip(opp_strength + rng.normal(0.1, 0.08), 0.2, 0.8)),
                     "spin_off" if i in (2, 4) else "pace_medium") for i in range(5)]
        we_bat_first = bool(rng.random() < 0.5)
        if we_bat_first:
            first = _simulate_innings(rng, our_bat, opp_bowl, overs, mid, 1, TEAM)
            t = score_innings(engine_balls(first))["total"] + 1
            second = _simulate_innings(rng, opp_bat, our_bowl, overs, mid, 2, opp, target=t)
        else:
            first = _simulate_innings(rng, opp_bat, our_bowl, overs, mid, 1, opp)
            t = score_innings(engine_balls(first))["total"] + 1
            second = _simulate_innings(rng, our_bat, opp_bowl, overs, mid, 2, TEAM, target=t)
        s1, s2 = score_innings(engine_balls(first)), score_innings(engine_balls(second), target=t)
        our, their = (s1, s2) if we_bat_first else (s2, s1)
        if s2["total"] >= t:
            result = "won" if not we_bat_first else "lost"
        elif s2["total"] == t - 1:
            result = "tied"
        else:
            result = "won" if we_bat_first else "lost"
        matches.append({"match_id": mid, "date": date.isoformat(), "season": "2025", "format": f"T{overs}",
                        "overs": overs, "opponent": opp, "venue": "Home" if m % 2 == 0 else "Away",
                        "batted_first": TEAM if we_bat_first else opp,
                        "our_score": f"{our['total']}/{our['wickets']}", "our_overs": our["overs"],
                        "their_score": f"{their['total']}/{their['wickets']}", "their_overs": their["overs"],
                        "result": result, "synthetic": True})
        for b in first + second:
            b["date"] = date.isoformat()
            b["season"], b["format"] = "2025", f"T{overs}"
        balls += first + second
    # number balls within each innings
    counter = {}
    for b in balls:
        key = (b["match_id"], b["innings"])
        counter[key] = counter.get(key, 0) + 1
        b["ball_no"] = counter[key]

    # --- net-session deliveries (line & length practice), two sessions per bowler
    deliveries, speeds = [], []
    for name, role, _, bskill, style, kmh, _ in squad:
        if not style:
            continue
        spin = style.startswith("spin")
        for s in range(4):
            date = start + dt.timedelta(days=3 + 14 * s)
            improve = 1.0 - 0.07 * s                      # groups tighten slightly over the season
            n = 24
            xs = rng.normal(0.20, (0.40 - 0.24 * bskill) * improve, n)
            ys = rng.normal(5.2 if spin else 6.9, (2.5 - 1.3 * bskill) * improve, n)
            for i in range(n):
                deliveries.append({"player": name, "session": f"{name.split()[0]}-S{s + 1}", "session_no": s + 1,
                                   "date": date.isoformat(), "x": round(float(xs[i]), 3),
                                   "y": round(float(np.clip(ys[i], 0.1, 15)), 3), "bowl_type": "spin" if spin else "pace",
                                   "synthetic": True})
            # speed readings: stopwatch (average speed) and occasional radar (near release speed)
            for i in range(6):
                true_release = rng.normal(kmh + 0.6 * s, 2.5)
                t = 18.9 / (true_release * 0.88 / 3.6) + rng.normal(0, 0.012)     # average is ~88% of release
                speeds.append({"player": name, "date": date.isoformat(), "source": "stopwatch",
                               "distance_m": 18.9, "time_s": round(float(t), 3),
                               "kmh": round(18.9 / float(t) * 3.6, 1), "synthetic": True})
            speeds.append({"player": name, "date": date.isoformat(), "source": "radar", "distance_m": None,
                           "time_s": None, "kmh": round(float(rng.normal(kmh + 0.6 * s, 2.0)), 1), "synthetic": True})
    # a few missing values so the notebooks have to handle them
    for i in rng.choice(len(deliveries), size=6, replace=False):
        deliveries[int(i)]["x"] = None
    for i in rng.choice(len(speeds), size=3, replace=False):
        if speeds[int(i)]["source"] == "stopwatch":
            speeds[int(i)]["time_s"] = None
            speeds[int(i)]["kmh"] = None

    # --- fielding events
    fielding = []
    for name, _, _, _, _, _, catch in squad:
        for m in matches:
            for kind, rate, p_good in (("catch", 0.55, catch), ("clean_stop", 2.2, 0.55 + 0.4 * catch),
                                       ("run_out", 0.25, 0.35 + 0.3 * catch)):
                for _ in range(int(rng.poisson(rate))):
                    ok = rng.random() < p_good
                    k = {"catch": "catch" if ok else "drop", "clean_stop": "clean_stop" if ok else "misfield",
                         "run_out": ("direct_hit" if rng.random() < 0.4 else "run_out") if ok else "missed_run_out"}[kind]
                    fielding.append({"player": name, "match_id": m["match_id"], "date": m["date"], "kind": k,
                                     "count": 1, "synthetic": True})
    return {"team": TEAM, "players": players(), "matches": matches, "balls": balls,
            "deliveries": deliveries, "speeds": speeds, "fielding": fielding, "synthetic": True}


def write_csvs(folder: str, seed: int = 42) -> dict:
    """Write the synthetic data set to CSV files in `folder`. Returns {table: path}."""
    data = generate(seed)
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for table in ("players", "matches", "balls", "deliveries", "speeds", "fielding"):
        rows = data[table]
        cols = list(dict.fromkeys(k for r in rows for k in r))
        path = os.path.join(folder, f"{table}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        paths[table] = path
    return paths


def synthetic_track(seed: int = 0, n_pre: int = 16, n_post: int = 8, swing: float = 0.0, seam: float = 0.0,
                    noise: float = 1.2, fps: float = 120.0) -> list[dict]:
    """A SYNTHETIC image-space ball track (pixels) with optional swing and seam movement, plus pixel noise."""
    rng = np.random.default_rng(seed)
    pts = []
    for k in range(n_pre + n_post):
        t = k / fps
        if k < n_pre:
            u = k / (n_pre - 1)
            x = 300 + 40 * u + swing * u * u
            y = 80 + 260 * u ** 1.5
        else:
            j = (k - n_pre + 1) / n_post
            x = 300 + 40 + swing + (40 / n_pre * n_post + seam) * j
            y = 340 - 110 * j + 30 * j * j
        pts.append({"frame": k, "t": t, "x": float(x + rng.normal(0, noise)), "y": float(y + rng.normal(0, noise)),
                    "observed": True, "synthetic": True})
    return pts
