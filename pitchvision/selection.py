"""Explainable playing-XI analysis.

No composite "rating" is invented. Players are compared on named statistics
with stated qualification rules, and every pick carries the reason and the
numbers behind it. The coach's judgement always overrides.

Selection method
----------------
1. Wicket-keeper: the available keeper with the best batting average
   (qualified keepers first, then most runs, then any keeper).
2. Bowling attack: `bowlers_needed` players who bowl, ranked by bowling average
   (runs per wicket) among those who have bowled at least `min_balls`; then by
   economy; then unqualified bowlers. If the attack has no spinner (or no pace
   bowler) and one is available, the lowest-ranked pick is swapped for the best
   one of the missing type, so the attack has variety.
3. Batting: remaining places go to the best batting averages among players with
   at least `min_innings` innings; then runs per innings; then role order.
4. Batting order: specialist batters and the keeper by average, then
   all-rounders, then bowlers.
"""
from __future__ import annotations

from typing import Iterable, Optional

ROLES = ("batter", "all_rounder", "wicket_keeper", "bowler")
BOWLING_ROLES = ("bowler", "all_rounder")
RELIABLE_BAT_AVG = 15.0     # a batter averaging this or more counts toward "batting depth"


def _fmt(v, nd=1):
    return "no data" if v is None else f"{v:.{nd}f}"


def analyse_xi(xi: list[dict], match_overs: int = 20) -> dict:
    """Describe an XI. Each player: {id, name, role, bowl_style, bat: career row|None, bowl: career row|None}."""
    def avg(p):
        return (p.get("bat") or {}).get("average")

    depth = 0
    for p in xi:                      # count down the order until the first unreliable batter
        a = avg(p)
        if a is not None and a >= RELIABLE_BAT_AVG:
            depth += 1
        else:
            break
    reliable = [p["name"] for p in xi if avg(p) is not None and avg(p) >= RELIABLE_BAT_AVG]
    bowlers = [p for p in xi if p.get("role") in BOWLING_ROLES or (p.get("bowl") or {}).get("legal_balls")]
    pace = [p["name"] for p in bowlers if (p.get("bowl_style") or "").startswith("pace")]
    spin = [p["name"] for p in bowlers if (p.get("bowl_style") or "").startswith("spin")]
    per_bowler = match_overs // 5 if match_overs else None      # standard limited-overs cap
    overs_cover = len(bowlers) * per_bowler if per_bowler else None
    runs = [(p.get("bat") or {}).get("runs", 0) or 0 for p in xi]
    inns = [(p.get("bat") or {}).get("innings", 0) or 0 for p in xi]
    warnings = []
    if len(xi) != 11:
        warnings.append(f"This side has {len(xi)} players, not 11.")
    keepers = [p["name"] for p in xi if p.get("role") == "wicket_keeper"]
    if not keepers:
        warnings.append("No wicket-keeper in the side.")
    if len(bowlers) < 5:
        warnings.append(f"Only {len(bowlers)} bowling options; five are normally needed to bowl a full innings.")
    if overs_cover is not None and overs_cover < match_overs:
        warnings.append(f"{len(bowlers)} bowlers at {per_bowler} overs each cover {overs_cover} of {match_overs} overs.")
    if bowlers and not spin:
        warnings.append("No spin option.")
    if bowlers and not pace:
        warnings.append("No pace option.")
    no_data = [p["name"] for p in xi if not p.get("bat") and not p.get("bowl")]
    if no_data:
        warnings.append("No recorded statistics for: " + ", ".join(no_data) + ".")
    return {
        "size": len(xi),
        "batting_depth": depth,
        "reliable_batters": reliable,
        "batting_depth_rule": f"Consecutive players from the top of the order averaging {RELIABLE_BAT_AVG:.0f} or more.",
        "bowling_options": len(bowlers), "pace_options": pace, "spin_options": spin,
        "overs_per_bowler_cap": per_bowler, "overs_covered": overs_cover,
        "keepers": keepers,
        "runs_per_innings_sum": sum(r / i for r, i in zip(runs, inns) if i),
        "warnings": warnings,
    }


def select_xi(squad: Iterable[dict], match_overs: int = 20, bowlers_needed: int = 5,
              min_innings: int = 3, min_balls: int = 60) -> dict:
    """Pick an XI from the available squad and explain every choice."""
    squad = [dict(p) for p in squad]
    if len(squad) < 11:
        return {"enough_players": False, "xi": [], "reasons": [], "left_out": [],
                "note": f"Only {len(squad)} players are available; 11 are needed.", "analysis": None}
    picked, reasons = [], []

    def take(p, reason):
        picked.append(p)
        reasons.append({"player": p["name"], "role": p.get("role"), "reason": reason})

    bat = lambda p: p.get("bat") or {}
    bowl = lambda p: p.get("bowl") or {}

    # 1. keeper
    keepers = [p for p in squad if p.get("role") == "wicket_keeper"]
    if keepers:
        k = max(keepers, key=lambda p: (bat(p).get("innings", 0) >= min_innings and bat(p).get("average") is not None,
                                        bat(p).get("average") or 0, bat(p).get("runs") or 0))
        only = " (only keeper available)" if len(keepers) == 1 else ""
        take(k, f"Wicket-keeper{only}. Batting average {_fmt(bat(k).get('average'))} from "
                f"{bat(k).get('innings', 0)} innings.")

    # 2. bowling attack
    pool = [p for p in squad if p not in picked and (p.get("role") in BOWLING_ROLES or bowl(p).get("legal_balls"))]

    def bowl_key(p):
        b = bowl(p)
        qualified = (b.get("legal_balls") or 0) >= min_balls
        return (0 if qualified and b.get("average") is not None else 1 if qualified else 2,
                b.get("average") if b.get("average") is not None else 1e9,
                b.get("economy") if b.get("economy") is not None else 1e9)

    pool.sort(key=bowl_key)
    attack = pool[:bowlers_needed]
    for kind in ("spin", "pace"):
        has = any((p.get("bowl_style") or "").startswith(kind) for p in attack)
        alt = next((p for p in pool[bowlers_needed:] if (p.get("bowl_style") or "").startswith(kind)), None)
        if attack and not has and alt:
            dropped = attack[-1]
            attack[-1] = alt
            alt["_variety"] = (f"Chosen ahead of {dropped['name']} so the attack has a {kind} option. ")
    for p in attack:
        b = bowl(p)
        if (b.get("legal_balls") or 0) >= min_balls:
            why = (f"Bowling average {_fmt(b.get('average'))}, economy {_fmt(b.get('economy'), 2)}, "
                   f"{b.get('wickets', 0)} wickets in {b.get('overs', '0.0')} overs.")
        elif b.get("legal_balls"):
            why = (f"Has bowled only {b.get('overs')} overs (fewer than {min_balls} balls), so figures are not yet "
                   f"reliable: {b.get('wickets', 0)} wickets, economy {_fmt(b.get('economy'), 2)}.")
        else:
            why = "No bowling recorded yet; selected on role only."
        take(p, p.pop("_variety", "") + f"{(p.get('bowl_style') or 'bowler').replace('_', ' ').capitalize()}. " + why)

    # 3. batting places
    rest = [p for p in squad if p not in picked]

    def bat_key(p):
        b = bat(p)
        qualified = (b.get("innings") or 0) >= min_innings
        rpi = (b.get("runs") or 0) / b["innings"] if b.get("innings") else -1
        return (0 if qualified and b.get("average") is not None else 1 if b.get("innings") else 2,
                -(b.get("average") or 0) if qualified else 0, -rpi, ROLES.index(p.get("role")) if p.get("role") in ROLES else 9)

    rest.sort(key=bat_key)
    for p in rest[:11 - len(picked)]:
        b = bat(p)
        if (b.get("innings") or 0) >= min_innings:
            why = (f"Batting average {_fmt(b.get('average'))}, strike rate {_fmt(b.get('strike_rate'), 0)}, "
                   f"{b.get('runs', 0)} runs in {b.get('innings')} innings.")
        elif b.get("innings"):
            why = (f"Only {b.get('innings')} innings (fewer than {min_innings}), so the average is not yet reliable: "
                   f"{b.get('runs', 0)} runs.")
        else:
            why = "No batting recorded yet; selected on role only."
        take(p, why)

    # 4. batting order
    def order_key(p):
        group = {"batter": 0, "wicket_keeper": 0, "all_rounder": 1, "bowler": 2}.get(p.get("role"), 1)
        return (group, -(bat(p).get("average") or 0), -(bat(p).get("runs") or 0))

    xi = sorted(picked, key=order_key)
    left_out = [{"player": p["name"], "role": p.get("role"),
                 "reason": f"Batting average {_fmt(bat(p).get('average'))}, bowling average {_fmt(bowl(p).get('average'))}; "
                           "ranked below the selected players on the rules above."}
                for p in squad if p not in picked]
    return {
        "enough_players": True,
        "xi": [{"id": p.get("id"), "name": p["name"], "role": p.get("role"), "bowl_style": p.get("bowl_style"),
                "position": i + 1} for i, p in enumerate(xi)],
        "reasons": reasons, "left_out": left_out,
        "analysis": analyse_xi(xi, match_overs),
        "assumptions": [
            f"Batting averages are ranked only for players with at least {min_innings} innings.",
            f"Bowling averages are ranked only for players who have bowled at least {min_balls} balls.",
            f"The attack needs {bowlers_needed} bowlers and, where available, both pace and spin.",
            "Statistics come from this team's recorded matches only; opposition strength, pitch, fitness and "
            "recent form outside the records are not considered.",
            "Small samples are noisy. Treat this as a starting point for the coach's decision.",
        ],
    }


def compare_xis(a: list[dict], b: list[dict], match_overs: int = 20) -> dict:
    """Analyse two alternative sides and list what changes between them."""
    ra, rb = analyse_xi(a, match_overs), analyse_xi(b, match_overs)
    names_a, names_b = {p["name"] for p in a}, {p["name"] for p in b}
    return {"a": ra, "b": rb, "only_in_a": sorted(names_a - names_b), "only_in_b": sorted(names_b - names_a),
            "differences": {k: {"a": ra[k], "b": rb[k]} for k in
                            ("batting_depth", "bowling_options", "overs_covered", "runs_per_innings_sum")}}
