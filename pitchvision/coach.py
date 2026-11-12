"""AI cricket coach: evidence-backed recommendations and question answering.

The coach works entirely from data that is passed in (the team's stored
statistics). It never invents a number: if the data needed for an answer is not
there, it says so. Every recommendation carries the evidence that triggered it.

The rule-based coach is the default and needs no internet. An optional LLM
(`llm_answer`) can rephrase and combine the same facts in natural language; it
is given ONLY the retrieved facts and is told to use nothing else.

Context format (all keys optional)
----------------------------------
{
  "team": "name",
  "players": [{"id", "name", "role", "bowl_style"}],
  "batting":  [career_batting rows   + "name"],
  "bowling":  [career_bowling rows   + "name"],
  "fielding": [career_fielding rows  + "name"],
  "speeds":   {player_id: [{"date", "kmh", "source"}]},      # chronological
  "accuracy": {player_id: accuracy() result},
  "splits":   {player_id: batting_splits() result},
  "me": player_id or None,
}
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

MIN_BALLS_SPLIT = 12       # balls faced before a pace/spin split is interpreted
MIN_BALLS_BOWLED = 30      # balls bowled before economy is interpreted
MIN_CHANCES = 3            # catching chances before a catch % is interpreted


def _f(v, nd=1, none="no data"):
    return none if v is None else f"{v:.{nd}f}"


def _by_player(rows):
    return {r["player"]: r for r in rows or []}


def _name(ctx, pid):
    for p in ctx.get("players", []):
        if p["id"] == pid:
            return p["name"]
    return str(pid)


# ------------------------------------------------------------------ recommendations

def player_recommendations(ctx: dict, pid) -> list[dict]:
    """Training recommendations for one player. Each has area, recommendation, drill, evidence."""
    recs = []
    bat = _by_player(ctx.get("batting")).get(pid)
    bowl = _by_player(ctx.get("bowling")).get(pid)
    fld = _by_player(ctx.get("fielding")).get(pid)
    acc = (ctx.get("accuracy") or {}).get(pid)
    split = (ctx.get("splits") or {}).get(pid)
    speeds = [s["kmh"] for s in (ctx.get("speeds") or {}).get(pid, []) if s.get("kmh") is not None]

    def add(area, recommendation, drill, evidence, priority=2):
        recs.append({"area": area, "recommendation": recommendation, "drill": drill,
                     "evidence": evidence, "priority": priority})

    # --- bowling accuracy
    if acc and acc.get("total", 0) >= 12:
        if acc["hit_pct"] < 40:
            add("Bowling accuracy", "Targeted line-and-length practice.",
                "Place a mat or two cones on a good length outside off stump. Bowl sets of 12 and count hits; "
                "aim to beat your previous set.",
                f"{acc['hit_pct']:.0f}% of {acc['total']} recorded deliveries landed in the target zone (below 40%).", 1)
        if acc.get("spread_x") is not None and acc["spread_x"] > 0.30:
            add("Bowling line", "Tighten your line: the sideways spread of your deliveries is wide.",
                "Bowl to a single stump with a channel marked 20 cm either side; focus on a repeatable wrist and "
                "front-arm position.",
                f"Lateral spread {acc['spread_x'] * 100:.0f} cm (standard deviation) over {acc['total']} deliveries (above 30 cm).", 1)
        if acc.get("bias_y") is not None and abs(acc["bias_y"]) > 1.0:
            where = "shorter" if acc["bias_y"] > 0 else "fuller"
            add("Bowling length", f"Your group is centred {where} than your target; adjust your length.",
                "Mark the target length with a rope across the pitch and bowl 3 sets of 6 trying to land on it.",
                f"Average pitching point is {abs(acc['bias_y']):.1f} m {where} than the target length.", 2)
    # --- bowling economy / wides
    if bowl and bowl.get("legal_balls", 0) >= MIN_BALLS_BOWLED:
        extras = (bowl.get("wides", 0) + bowl.get("no_balls", 0))
        per_over = extras * 6 / bowl["legal_balls"]
        if per_over >= 1.0:
            add("Bowling discipline", "Cut down wides and no-balls.",
                "Run-up marker check for no-balls; bowl 2 overs at one stump with a wide line marked and count extras.",
                f"{bowl.get('wides', 0)} wides and {bowl.get('no_balls', 0)} no-balls in {bowl['overs']} overs "
                f"({per_over:.1f} per over, 1.0 or more).", 1)
        team_eco = _team_economy(ctx)
        if team_eco and bowl.get("economy") and bowl["economy"] > team_eco * 1.2:
            add("Bowling economy", "You concede more per over than the team rate; work on a stock ball you can land under pressure.",
                "Target bowling with a batter: 12 balls where anything outside the target zone counts as 4 runs.",
                f"Economy {bowl['economy']:.2f} against a team economy of {team_eco:.2f} ({bowl['overs']} overs bowled).", 2)
    # --- speed trend
    if len(speeds) >= 6:
        third = len(speeds) // 3
        early, late = sum(speeds[:third]) / third, sum(speeds[-third:]) / third
        if late < early - 3:
            add("Bowling speed", "Your recent average speeds are lower than earlier ones. Check workload and rhythm with your coach.",
                "Shorter, higher-quality spells; film the run-up and compare rhythm with an earlier session.",
                f"Average of the last {third} readings {late:.1f} km/h vs first {third} readings {early:.1f} km/h.", 3)
    # --- batting vs pace / spin
    if split:
        bt = split.get("bowl_type", {})
        pace, spin = bt.get("pace"), bt.get("spin")
        if pace and spin and pace["balls"] >= MIN_BALLS_SPLIT and spin["balls"] >= MIN_BALLS_SPLIT:
            if spin["strike_rate"] < pace["strike_rate"] * 0.75:
                add("Batting against spin", "You score much more slowly against spin than pace.",
                    "Throw-downs from a spinner's length: practise using your feet and the sweep; rotate strike drill "
                    "(score off 4 of every 6 balls).",
                    f"Strike rate {spin['strike_rate']:.0f} vs spin ({spin['balls']} balls) and {pace['strike_rate']:.0f} "
                    f"vs pace ({pace['balls']} balls).", 1)
            elif pace["strike_rate"] < spin["strike_rate"] * 0.75:
                add("Batting against pace", "You score much more slowly against pace than spin.",
                    "Bowling-machine or side-arm work at match pace; back-foot punch and leave drills.",
                    f"Strike rate {pace['strike_rate']:.0f} vs pace ({pace['balls']} balls) and {spin['strike_rate']:.0f} "
                    f"vs spin ({spin['balls']} balls).", 1)
        for kind, d in bt.items():
            if d["balls"] >= MIN_BALLS_SPLIT and d["dismissals"] >= 3 and d["average"] is not None and d["average"] < 10:
                add(f"Dismissals against {kind}", f"You are getting out often against {kind}.",
                    f"Net sessions against {kind} with a 'survive 30 balls' target before playing shots.",
                    f"{d['dismissals']} dismissals for {d['runs']} runs against {kind} (average {d['average']:.1f}).", 1)
        dot = (split.get("overall") or {}).get("dot_pct")
        if dot is not None and split["overall"]["balls"] >= 30 and dot > 60:
            add("Strike rotation", "A high share of the balls you face are dot balls.",
                "Soft-hands singles: tip-and-run in the nets, scoring a single off at least every other ball.",
                f"{dot:.0f}% dot balls from {split['overall']['balls']} balls faced (above 60%).", 2)
    if bat and bat.get("innings", 0) >= 4:
        low = sum(1 for s in bat["scores"] if s["out"] and s["runs"] < 10)
        if low / bat["innings"] >= 0.5:
            add("Starting an innings", "You are often out before reaching 10.",
                "First-20-balls routine in the nets: leave, defend, and only score in your strongest area.",
                f"Out for under 10 in {low} of {bat['innings']} innings.", 1)
    # --- fielding
    if fld:
        if fld["catch_chances"] >= MIN_CHANCES and fld["catch_pct"] < 60:
            add("Catching", "Catching practice: your catch success rate is low.",
                "20 catches a session split between high balls and flat catches; add reaction catches off a ramp or wall.",
                f"{fld['catch']} caught and {fld['drop']} dropped ({fld['catch_pct']:.0f}% of {fld['catch_chances']} chances, below 60%).", 1)
        if fld["ground_chances"] >= 5 and fld["ground_pct"] < 75:
            add("Ground fielding", "Clean pick-ups: too many misfields.",
                "Long-barrier and one-hand pick-up drill, 3 sets of 10, then pick-up-and-throw at one stump.",
                f"{fld['misfield']} misfields in {fld['ground_chances']} ground-fielding chances ({fld['ground_pct']:.0f}% clean, below 75%).", 2)
        if fld["run_out_chances"] >= MIN_CHANCES and fld["run_out_pct"] < 40:
            add("Throwing", "Work on throwing accuracy at the stumps.",
                "Underarm and overarm throws at a single stump from 10 m and 20 m; count hits out of 10.",
                f"{fld['run_outs_total']} run-outs from {fld['run_out_chances']} chances ({fld['run_out_pct']:.0f}%).", 2)
    recs.sort(key=lambda r: r["priority"])
    return recs


def _team_economy(ctx) -> Optional[float]:
    rows = ctx.get("bowling") or []
    balls = sum(r.get("legal_balls", 0) for r in rows)
    runs = sum(r.get("runs", 0) for r in rows)
    return runs * 6 / balls if balls else None


def team_insights(ctx: dict) -> list[dict]:
    """Team-level weaknesses and strengths, each with evidence."""
    out = []
    bat, bowl, fld = ctx.get("batting") or [], ctx.get("bowling") or [], ctx.get("fielding") or []
    name = lambda r: r.get("name") or _name(ctx, r["player"])
    if bowl:
        balls = sum(r["legal_balls"] for r in bowl)
        wides = sum(r.get("wides", 0) for r in bowl)
        nbs = sum(r.get("no_balls", 0) for r in bowl)
        if balls >= 60:
            per_over = (wides + nbs) * 6 / balls
            if per_over >= 0.8:
                out.append({"kind": "weakness", "title": "Extras conceded",
                            "detail": "The attack gives away too many wides and no-balls.",
                            "evidence": f"{wides} wides and {nbs} no-balls in {balls // 6}.{balls % 6} overs ({per_over:.1f} per over)."})
            eco = _team_economy(ctx)
            out.append({"kind": "fact", "title": "Team economy rate", "detail": f"{eco:.2f} runs per over.",
                        "evidence": f"{sum(r['runs'] for r in bowl)} runs from {balls // 6}.{balls % 6} overs."})
    if bat:
        outs = sum(r["innings"] - r["not_outs"] for r in bat)
        runs = sum(r["runs"] for r in bat)
        balls = sum(r["balls"] for r in bat)
        if outs:
            out.append({"kind": "fact", "title": "Runs per wicket (batting)", "detail": f"{runs / outs:.1f}.",
                        "evidence": f"{runs} runs for {outs} dismissals."})
        top = sorted(bat, key=lambda r: -r["runs"])[:3]
        if runs >= 100 and sum(r["runs"] for r in top) / runs > 0.65:
            out.append({"kind": "weakness", "title": "Run-scoring depends on a few batters",
                        "detail": "Most of the team's runs come from three players.",
                        "evidence": ", ".join(f"{name(r)} {r['runs']}" for r in top) + f" of {runs} team runs "
                                    f"({sum(r['runs'] for r in top) / runs * 100:.0f}%)."})
        if balls >= 120:
            dots_sr = runs / balls * 100
            if dots_sr < 70:
                out.append({"kind": "weakness", "title": "Slow scoring rate",
                            "detail": "The team's overall strike rate is low.",
                            "evidence": f"{runs} runs from {balls} balls (strike rate {dots_sr:.0f})."})
    if fld:
        c, d = sum(r["catch"] for r in fld), sum(r["drop"] for r in fld)
        if c + d >= 8:
            pct = c / (c + d) * 100
            out.append({"kind": "weakness" if pct < 65 else "strength", "title": "Catching",
                        "detail": f"The team holds {pct:.0f}% of its catches.",
                        "evidence": f"{c} caught, {d} dropped."})
    splits = ctx.get("splits") or {}
    tot = {"pace": [0, 0], "spin": [0, 0]}
    for sp in splits.values():
        for k in tot:
            d = (sp.get("bowl_type") or {}).get(k)
            if d:
                tot[k][0] += d["runs"]
                tot[k][1] += d["balls"]
    if tot["pace"][1] >= 60 and tot["spin"][1] >= 60:
        sr_p, sr_s = tot["pace"][0] / tot["pace"][1] * 100, tot["spin"][0] / tot["spin"][1] * 100
        if min(sr_p, sr_s) < 0.8 * max(sr_p, sr_s):
            weak = "spin" if sr_s < sr_p else "pace"
            out.append({"kind": "weakness", "title": f"Batting against {weak}",
                        "detail": f"The team scores more slowly against {weak}.",
                        "evidence": f"Team strike rate {sr_p:.0f} vs pace ({tot['pace'][1]} balls), {sr_s:.0f} vs spin ({tot['spin'][1]} balls)."})
    return out


# ------------------------------------------------------------------ question answering

def _best(rows, key, lowest=False, min_field=None, minimum=0):
    pool = [r for r in rows if r.get(key) is not None and (min_field is None or (r.get(min_field) or 0) >= minimum)]
    if not pool:
        return None, []
    pool.sort(key=lambda r: r[key], reverse=not lowest)
    return pool[0], pool[:5]


def retrieve_facts(question: str, ctx: dict) -> dict:
    """Pick the stored statistics relevant to a question. Returns {intent, facts, answer, evidence}."""
    q = question.lower()
    me = ctx.get("me")
    name = lambda r: r.get("name") or _name(ctx, r["player"])
    bat, bowl, fld = ctx.get("batting") or [], ctx.get("bowling") or [], ctx.get("fielding") or []
    has = lambda *words: any(w in q for w in words)
    # A player mentioned by name takes precedence over "me".
    subject = me
    for p in ctx.get("players", []):
        first = p["name"].split()[0].lower()
        if p["name"].lower() in q or re.search(rf"\b{re.escape(first)}\b", q):
            subject = p["id"]
            break
    personal = has(" i ", " my ", " me", "should i", "am i", "do i") or q.startswith(("i ", "my ", "what should i", "how has my", "how have i"))

    def ranked(rows, key, lowest, label, fmt, min_field=None, minimum=0, rule=""):
        best, top = _best(rows, key, lowest, min_field, minimum)
        if not best:
            return {"intent": label, "answer": f"There is not enough recorded data to answer that yet{(' (' + rule + ')') if rule else ''}.",
                    "evidence": [], "facts": []}
        return {"intent": label,
                "answer": f"{name(best)} has the {label}: {fmt(best)}." + (f" Ranked among players with {rule}." if rule else ""),
                "evidence": [f"{i + 1}. {name(r)}: {fmt(r)}" for i, r in enumerate(top)],
                "facts": [{"player": name(r), key: r[key]} for r in top]}

    if has("economy", "most economical"):
        return ranked(bowl, "economy", True, "best economy rate",
                      lambda r: f"{r['economy']:.2f} runs per over ({r['overs']} overs)", "legal_balls", MIN_BALLS_BOWLED,
                      f"at least {MIN_BALLS_BOWLED} balls bowled")
    if has("most wickets", "leading wicket", "top wicket"):
        return ranked(bowl, "wickets", False, "most wickets", lambda r: f"{r['wickets']} wickets at {_f(r['average'])}")
    if has("most runs", "top scorer", "leading run", "top run"):
        return ranked(bat, "runs", False, "most runs", lambda r: f"{r['runs']} runs in {r['innings']} innings")
    if has("best batting average", "highest average", "best average", "best batter", "best batsman"):
        return ranked(bat, "average", False, "highest batting average",
                      lambda r: f"{r['average']:.1f} ({r['runs']} runs, {r['innings'] - r['not_outs']} dismissals)",
                      "innings", 3, "at least 3 innings")
    if has("strike rate") and not personal:
        return ranked(bat, "strike_rate", False, "highest strike rate",
                      lambda r: f"{r['strike_rate']:.0f} ({r['runs']} runs from {r['balls']} balls)", "balls", 30,
                      "at least 30 balls faced")
    if has("fastest", "quickest") or (has("speed", "pace") and has("who", "which")):
        best = []
        for pid, rs in (ctx.get("speeds") or {}).items():
            vals = [s["kmh"] for s in rs if s.get("kmh") is not None]
            if vals:
                best.append((max(vals), _name(ctx, pid), len(vals)))
        best.sort(reverse=True)
        if not best:
            return {"intent": "fastest bowler", "answer": "No bowling speeds have been recorded yet.", "evidence": [], "facts": []}
        return {"intent": "fastest bowler",
                "answer": f"{best[0][1]} has the fastest recorded speed: {best[0][0]:.1f} km/h.",
                "evidence": [f"{i + 1}. {n}: {v:.1f} km/h (best of {c} readings)" for i, (v, n, c) in enumerate(best[:5])]
                + ["Distance/time readings are average speeds; radar readings are close to release speed."],
                "facts": [{"player": n, "max_kmh": v} for v, n, _ in best[:5]]}
    if has("spin", "pace") and has("who", "which", "best against", "performs best"):
        kind = "spin" if "spin" in q else "pace"
        rows = []
        for pid, sp in (ctx.get("splits") or {}).items():
            d = (sp.get("bowl_type") or {}).get(kind)
            if d and d["balls"] >= MIN_BALLS_SPLIT:
                rows.append({"player": pid, **d})
        if not rows:
            return {"intent": f"best against {kind}", "evidence": [], "facts": [],
                    "answer": f"No batter has faced {MIN_BALLS_SPLIT} or more recorded balls of {kind} yet, so this cannot be ranked."}
        rows.sort(key=lambda r: (-(r["average"] if r["average"] is not None else r["runs"]), -r["strike_rate"]))
        b = rows[0]
        return {"intent": f"best against {kind}",
                "answer": f"{_name(ctx, b['player'])} has the best record against {kind}: {b['runs']} runs from "
                          f"{b['balls']} balls (strike rate {b['strike_rate']:.0f}), {b['dismissals']} dismissal(s).",
                "evidence": [f"{i + 1}. {_name(ctx, r['player'])}: {r['runs']} runs, {r['balls']} balls, SR {r['strike_rate']:.0f}, "
                             f"average {_f(r['average'], 1, 'not out')}" for i, r in enumerate(rows[:5])]
                + [f"Ranked by average (runs per dismissal), then strike rate; minimum {MIN_BALLS_SPLIT} balls."],
                "facts": rows[:5]}
    if has("catch", "fielder", "fielding") and has("who", "which", "best"):
        return ranked(fld, "catch_pct", False, "best catch success rate",
                      lambda r: f"{r['catch_pct']:.0f}% ({r['catch']} of {r['catch_chances']})", "catch_chances", MIN_CHANCES,
                      f"at least {MIN_CHANCES} catching chances")
    if has("weakness", "weaknesses", "team") and has("weak", "problem", "improve", "biggest", "struggl"):
        ins = team_insights(ctx)
        weak = [i for i in ins if i["kind"] == "weakness"]
        if not ins:
            return {"intent": "team weaknesses", "answer": "There is not enough recorded match data to identify team weaknesses yet.",
                    "evidence": [], "facts": []}
        if not weak:
            return {"intent": "team weaknesses", "answer": "No clear weakness shows up in the recorded data against the thresholds used.",
                    "evidence": [f"{i['title']}: {i['detail']} {i['evidence']}" for i in ins], "facts": ins}
        return {"intent": "team weaknesses",
                "answer": "The recorded data points to: " + "; ".join(w["title"].lower() for w in weak) + ".",
                "evidence": [f"{w['title']}: {w['evidence']}" for w in weak], "facts": weak}
    if has("speed") and subject is not None:
        rs = [s for s in (ctx.get("speeds") or {}).get(subject, []) if s.get("kmh") is not None]
        who = "Your" if subject == me else f"{_name(ctx, subject)}'s"
        if len(rs) < 2:
            return {"intent": "speed trend", "answer": f"{who} speed trend needs at least two recorded readings; {len(rs)} found.",
                    "evidence": [], "facts": rs}
        vals = [s["kmh"] for s in rs]
        half = len(vals) // 2
        early, late = sum(vals[:half]) / half, sum(vals[-half:]) / half
        word = "risen" if late - early > 1 else "fallen" if early - late > 1 else "stayed about the same"
        return {"intent": "speed trend",
                "answer": f"{who} recorded speed has {word}: the first {half} readings average {early:.1f} km/h and the last "
                          f"{half} average {late:.1f} km/h (best {max(vals):.1f} km/h).",
                "evidence": [f"{len(vals)} readings from {rs[0].get('date', 'first')} to {rs[-1].get('date', 'latest')}.",
                             "These compare like with like only if the readings used the same method (stopwatch vs radar)."],
                "facts": rs}
    if has("improve", "focus", "practice", "practise", "work on", "train", "better"):
        if subject is None:
            return {"intent": "recommendations", "evidence": [], "facts": [],
                    "answer": "Choose a player (or sign in as one) so the coach can look at their recorded data."}
        recs = player_recommendations(ctx, subject)
        if has("bowl"):
            recs = [r for r in recs if "owling" in r["area"]] or recs
        if has("bat") and not has("bowl"):
            recs = [r for r in recs if "atting" in r["area"] or "innings" in r["area"] or "Strike" in r["area"] or "Dismissal" in r["area"]] or recs
        who = "you" if subject == me else _name(ctx, subject)
        if not recs:
            return {"intent": "recommendations", "evidence": [], "facts": [],
                    "answer": f"Nothing in the recorded data for {who} crosses a coaching threshold yet. Either there is too "
                              "little data, or the numbers are within the normal range. Record more sessions and matches."}
        return {"intent": "recommendations",
                "answer": f"Priorities for {who}: " + " ".join(f"({i + 1}) {r['area']}: {r['recommendation']}" for i, r in enumerate(recs[:3])),
                "evidence": [f"{r['area']}: {r['evidence']} Drill: {r['drill']}" for r in recs[:3]], "facts": recs}
    return {"intent": "unknown", "evidence": [], "facts": [],
            "answer": "I can answer questions about batting, bowling and fielding records, bowling speeds, who performs best "
                      "against pace or spin, team weaknesses, and what a player should practise. Try one of the suggested questions."}


SUGGESTED_QUESTIONS = [
    "What should I improve as a bowler?",
    "Which of our bowlers has the best economy?",
    "Who performs best against spin?",
    "What are our team's biggest weaknesses?",
    "Which areas should I focus on during practice?",
    "How has my bowling speed changed this season?",
    "Who has the most wickets?",
    "Who is our fastest bowler?",
]


def answer(question: str, ctx: dict, use_llm: bool = False) -> dict:
    """Answer a question from stored data. Falls back to the rule-based answer if the LLM is unavailable."""
    if not question or not question.strip():
        return {"answer": "Ask a question about your team's recorded data.", "evidence": [], "engine": "rules", "intent": "empty"}
    res = retrieve_facts(" " + question.strip() + " ", ctx)
    res["engine"] = "rules"
    if use_llm:
        try:
            text = llm_answer(question, res)
            if text:
                res["rule_answer"] = res["answer"]
                res["answer"], res["engine"] = text, "llm"
        except LLMUnavailable as e:
            res["llm_note"] = str(e)
    return res


# ------------------------------------------------------------------ optional LLM

class LLMUnavailable(Exception):
    pass


LLM_MODEL = os.environ.get("PITCHVISION_LLM_MODEL", "claude-opus-5-5")
LLM_SYSTEM = (
    "You are a cricket coach for a school team. Answer the player's or coach's question using ONLY the facts in the "
    "JSON block provided. Never state a number that is not in the facts. If the facts do not answer the question, say "
    "what data is missing. Be encouraging and specific, in at most 120 words. Do not give medical advice and do not "
    "judge whether a bowling action is legal."
)


def llm_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def llm_answer(question: str, retrieved: dict) -> Optional[str]:
    """Rephrase the retrieved facts with Claude. Raises LLMUnavailable if it cannot run."""
    try:
        import anthropic
    except Exception:
        raise LLMUnavailable("The 'anthropic' package is not installed (pip install anthropic).")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise LLMUnavailable("No ANTHROPIC_API_KEY is set; using the built-in rule-based coach.")
    facts = json.dumps({"rule_based_answer": retrieved.get("answer"), "evidence": retrieved.get("evidence"),
                        "facts": retrieved.get("facts")}, default=str)[:20000]
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=LLM_MODEL,
            max_tokens=2000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=LLM_SYSTEM,
            messages=[{"role": "user", "content": f"Question: {question}\n\nFacts (JSON):\n{facts}"}],
        )
    except anthropic.AuthenticationError:
        raise LLMUnavailable("The Anthropic API key was rejected.")
    except anthropic.RateLimitError:
        raise LLMUnavailable("The LLM is rate limited right now; showing the rule-based answer.")
    except anthropic.APIStatusError as e:
        raise LLMUnavailable(f"The LLM request failed ({e.status_code}); showing the rule-based answer.")
    except anthropic.APIConnectionError:
        raise LLMUnavailable("No network connection to the LLM; showing the rule-based answer.")
    if response.stop_reason == "refusal":
        raise LLMUnavailable("The LLM declined the request; showing the rule-based answer.")
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or None
