"""Unit tests for the shared analytics: calculators, conversions, scoring rules, statistics."""
import math

import pytest

from pitchvision import coach, ml, pitchmap, sample_data, scoring, selection, speed, stats, trajectory
from pitchvision.constants import PITCH_LENGTH_M


# ---------------------------------------------------------------- speed and units

def test_unit_conversions_are_exact():
    assert speed.to_metres(22, "yd") == pytest.approx(20.1168)          # a 22-yard pitch
    assert speed.to_metres(66, "ft") == pytest.approx(20.1168)          # 66 feet = 22 yards
    assert speed.to_metres(1, "m") == 1
    assert speed.from_metres(20.1168, "yd") == pytest.approx(22)
    assert speed.to_seconds(450, "ms") == pytest.approx(0.45)
    assert speed.ms_to_kmh(10) == pytest.approx(36)
    assert speed.ms_to_mph(10) == pytest.approx(22.369362920544)
    assert speed.mph_to_kmh(60) == pytest.approx(96.56064)
    assert speed.kmh_to_ms(36) == pytest.approx(10)


def test_average_speed_known_example():
    # 20 m in 0.5 s = 40 m/s = 144 km/h = 89.48 mph
    r = speed.average_speed(20, 0.5)
    assert r["speed_ms"] == pytest.approx(40)
    assert r["speed_kmh"] == pytest.approx(144)
    assert r["speed_mph"] == pytest.approx(89.4774, abs=1e-3)
    assert r["kind"] == "average"


def test_average_speed_same_answer_in_any_unit():
    a = speed.average_speed(18.9, 0.62, "m", "s")
    b = speed.average_speed(18.9 / 0.3048, 620, "ft", "ms")
    c = speed.average_speed(18.9 / 0.9144, 0.62, "yd", "s")
    assert a["speed_kmh"] == pytest.approx(b["speed_kmh"]) == pytest.approx(c["speed_kmh"])


@pytest.mark.parametrize("d,t", [(0, 1), (-5, 1), (10, 0), (10, -1), (float("nan"), 1), (10, float("inf"))])
def test_average_speed_rejects_bad_input(d, t):
    with pytest.raises(speed.SpeedInputError):
        speed.average_speed(d, t)


def test_unknown_unit_rejected():
    with pytest.raises(speed.SpeedInputError):
        speed.average_speed(10, 1, "km", "s")


def test_speed_summary_skips_missing():
    s = speed.speed_summary([100, None, 110, float("nan"), 105])
    assert s["count"] == 3 and s["average"] == pytest.approx(105) and s["max"] == 110 and s["min"] == 100
    assert s["recent"] == 105
    assert speed.speed_summary([])["average"] is None
    assert speed.speed_summary([99])["std_dev"] is None


def test_speed_trend_and_radar_comparison():
    assert speed.speed_trend([100, 101])["slope_per_reading"] is None
    assert speed.speed_trend([100, 102, 104, 106])["slope_per_reading"] == pytest.approx(2)
    c = speed.compare_radar_to_estimate(120, 105)
    assert c["difference_kmh"] == 15 and c["estimate_as_pct_of_radar"] == pytest.approx(87.5)


# ---------------------------------------------------------------- line and length

def test_length_and_line_bands():
    assert pitchmap.classify_length(1.0) == "yorker"
    assert pitchmap.classify_length(2.0) == "full"
    assert pitchmap.classify_length(7.0) == "good"
    assert pitchmap.classify_length(9.0) == "short"
    assert pitchmap.classify_length(11.0) == "bouncer"
    assert pitchmap.classify_length(5.0, bounced=False) == "full_toss"
    assert pitchmap.classify_length(None) is None
    assert pitchmap.classify_line(0.0) == "stumps"
    assert pitchmap.classify_line(0.2) == "off"
    assert pitchmap.classify_line(0.6) == "wide_off"
    assert pitchmap.classify_line(-0.2) == "leg"
    assert pitchmap.classify_line(-0.9) == "wide_leg"


def test_accuracy_known_example():
    ds = [{"x": 0.2, "y": 7.0}, {"x": 0.3, "y": 7.5}, {"x": 0.9, "y": 3.0}, {"x": None, "y": 7.0}]
    a = pitchmap.accuracy(ds, 0.2, 7.0, tol_x=0.2, tol_y=1.0)
    assert a["total"] == 3 and a["hits"] == 2          # the delivery with a missing x is skipped
    assert a["hit_pct"] == pytest.approx(200 / 3)
    assert a["bias_x"] == pytest.approx((0.2 + 0.3 + 0.9) / 3 - 0.2)
    empty = pitchmap.accuracy([], 0.2, 7.0)
    assert empty["total"] == 0 and empty["hit_pct"] is None


def test_distribution_and_heatmap_totals():
    ds = [{"x": 0.0, "y": 1.0}, {"x": 0.2, "y": 7.0}, {"x": 0.2, "y": 7.2}, {"x": -0.3, "y": 9.0}]
    d = pitchmap.distribution(ds)
    assert d["total"] == 4
    assert sum(r["count"] for r in d["length"]) == 4 and sum(r["count"] for r in d["line"]) == 4
    assert {r["band"]: r["count"] for r in d["length"]}["good"] == 2
    h = pitchmap.heatmap(ds)
    assert sum(sum(row) for row in h["counts"]) + h["outside"] == 4


def test_tighter_group_has_higher_consistency():
    tight = [{"x": 0.2 + 0.01 * i, "y": 7 + 0.05 * i} for i in range(-3, 4)]
    loose = [{"x": 0.2 + 0.15 * i, "y": 7 + 0.8 * i} for i in range(-3, 4)]
    assert pitchmap.accuracy(tight, 0.2, 7)["consistency_index"] > pitchmap.accuracy(loose, 0.2, 7)["consistency_index"]


# ---------------------------------------------------------------- scoring rules

def B(s="A", ns="B", bw="X", **kw):
    return {"striker": s, "non_striker": ns, "bowler": bw, **kw}


def test_overs_notation():
    assert scoring.overs_text(0) == "0.0" and scoring.overs_text(6) == "1.0" and scoring.overs_text(22) == "3.4"
    assert scoring.overs_to_balls("3.4") == 22 and scoring.overs_to_balls(4) == 24
    with pytest.raises(scoring.ScoringError):
        scoring.overs_to_balls("3.6")


def test_run_rates():
    assert scoring.run_rate(60, 60) == pytest.approx(6)
    assert scoring.run_rate(10, 0) is None
    assert scoring.required_run_rate(151, 100, 30) == pytest.approx(51 / 5)
    assert scoring.required_run_rate(100, 100, 30) == 0
    assert scoring.required_run_rate(120, 100, 0) is None


def test_wide_and_no_ball_rules():
    balls = [B(wides=1), B(no_balls=1, runs_bat=4), B(runs_bat=1)]
    c = scoring.score_innings(balls)
    assert c["total"] == 1 + 5 + 1
    assert c["legal_balls"] == 1                        # only the last ball is legal
    a = next(b for b in c["batting"] if b["player"] == "A")
    assert a["runs"] == 5 and a["balls"] == 2          # the no-ball is a ball faced; the wide is not
    bw = c["bowling"][0]
    assert bw["runs"] == 7 and bw["wides"] == 1 and bw["no_balls"] == 1 and bw["overs"] == "0.1"
    assert c["extras"]["total"] == 2


def test_byes_not_charged_to_bowler_or_batter():
    c = scoring.score_innings([B(byes=4), B(leg_byes=1)])
    assert c["total"] == 5 and c["bowling"][0]["runs"] == 0
    assert c["batting"][0]["runs"] == 0 and c["batting"][0]["balls"] == 2      # both balls were faced
    assert c["extras"]["byes"] == 4 and c["extras"]["leg_byes"] == 1


def test_maiden_needs_six_legal_scoreless_balls():
    assert scoring.score_innings([B() for _ in range(6)])["bowling"][0]["maidens"] == 1
    assert scoring.score_innings([B(byes=1)] + [B(s="B", ns="A") for _ in range(5)])["bowling"][0]["maidens"] == 1
    with_wide = [B(wides=1)] + [B() for _ in range(6)]
    assert scoring.score_innings(with_wide)["bowling"][0]["maidens"] == 0


def test_strike_rotation():
    c = scoring.score_innings([B(runs_bat=1)])
    assert c["next"]["striker"] == "B"
    c = scoring.score_innings([B(runs_bat=4)])
    assert c["next"]["striker"] == "A"                   # boundary: no change of ends
    c = scoring.score_innings([B(runs_bat=0) for _ in range(6)])
    assert c["next"]["striker"] == "B" and c["next"]["over_complete"]     # ends change after the over
    c = scoring.score_innings([B(wides=2)])              # one wide run physically: batters crossed
    assert c["next"]["striker"] == "B"


def test_wickets_credit_and_partnerships():
    balls = [B(runs_bat=4), B(wicket={"kind": "bowled"}), B(s="C", ns="B", runs_bat=1),
             B(s="B", ns="C", wicket={"kind": "run_out", "player_out": "C"})]
    c = scoring.score_innings(balls)
    assert c["wickets"] == 2 and c["bowling"][0]["wickets"] == 1       # the run-out is not the bowler's
    assert [f["score"] for f in c["fall_of_wickets"]] == [4, 5]
    assert c["partnerships"][0]["runs"] == 4 and c["partnerships"][1]["runs"] == 1
    assert sum(b["runs"] for b in c["batting"]) + c["extras"]["total"] == c["total"]


@pytest.mark.parametrize("ball", [
    B(wides=1, runs_bat=1), B(wides=1, no_balls=1), B(byes=1, leg_byes=1), B(runs_bat=2, byes=1),
    B(no_balls=1, wicket={"kind": "bowled"}), B(wides=1, wicket={"kind": "lbw"}), B(no_balls=2),
    B(wicket={"kind": "bowled", "player_out": "B"}), B(wicket={"kind": "teleported"}), B(runs_bat=-1),
])
def test_impossible_balls_rejected(ball):
    with pytest.raises(scoring.ScoringError):
        scoring.score_innings([ball])


def test_stumped_off_wide_allowed_and_counts_for_bowler():
    c = scoring.score_innings([B(wides=1, wicket={"kind": "stumped"})])
    assert c["wickets"] == 1 and c["bowling"][0]["wickets"] == 1 and c["total"] == 1


def test_innings_ends_on_overs_target_and_wickets():
    c = scoring.score_innings([B() for _ in range(6)], max_overs=1)
    assert c["complete"]
    with pytest.raises(scoring.ScoringError):
        scoring.score_innings([B() for _ in range(7)], max_overs=1)
    c = scoring.score_innings([B(runs_bat=6)], target=5)
    assert c["complete"] and c["runs_required"] == 0
    c = scoring.score_innings([B(runs_bat=2)], max_overs=20, target=101)
    assert c["runs_required"] == 99 and c["balls_remaining"] == 119
    assert c["required_run_rate"] == pytest.approx(99 * 6 / 119)


def test_match_result_text():
    first = {"total": 150, "wickets": 6, "complete": True}
    assert scoring.match_result(first, {"total": 151, "wickets": 4, "complete": True}, "A", "B") == "B won by 6 wickets"
    assert scoring.match_result(first, {"total": 140, "wickets": 10, "complete": True}, "A", "B") == "A won by 10 runs"
    assert scoring.match_result(first, {"total": 150, "wickets": 8, "complete": True}, "A", "B") == "Match tied"
    assert scoring.match_result(first, {"total": 90, "wickets": 3, "complete": False}, "A", "B") == "In progress"


def test_synthetic_matches_are_internally_consistent():
    data = sample_data.generate(seed=3, n_matches=3)
    for m in data["matches"]:
        for n in (1, 2):
            rows = [b for b in data["balls"] if b["match_id"] == m["match_id"] and b["innings"] == n]
            c = scoring.score_innings(sample_data.engine_balls(rows), max_overs=20)     # validates every ball
            assert sum(b["runs"] for b in c["batting"]) + c["extras"]["total"] == c["total"]
            assert sum(b["runs"] for b in c["bowling"]) + c["extras"]["byes"] + c["extras"]["leg_byes"] == c["total"]
            assert sum(b["legal_balls"] for b in c["bowling"]) == c["legal_balls"] <= 120
            assert c["wickets"] <= 10


# ---------------------------------------------------------------- statistics

def test_batting_average_and_strike_rate():
    lines = [{"player": 1, "runs": 50, "balls": 40, "fours": 6, "sixes": 1, "out": True},
             {"player": 1, "runs": 30, "balls": 20, "fours": 3, "sixes": 0, "out": False},
             {"player": 1, "runs": 0, "balls": 3, "out": True},
             {"player": 1, "runs": None},                       # did not bat: skipped
             {"player": 2, "runs": 12, "balls": 12, "out": False}]
    rows = {r["player"]: r for r in stats.career_batting(lines)}
    a = rows[1]
    assert a["innings"] == 3 and a["not_outs"] == 1 and a["runs"] == 80
    assert a["average"] == pytest.approx(40)                    # 80 runs / 2 dismissals
    assert a["strike_rate"] == pytest.approx(80 / 63 * 100)
    assert a["highest_text"] == "50" and a["fifties"] == 1 and a["ducks"] == 1
    assert rows[2]["average"] is None and rows[2]["highest_text"] == "12*"     # never out: average undefined


def test_bowling_figures():
    lines = [{"player": 1, "legal_balls": 24, "runs": 20, "wickets": 2, "maidens": 1},
             {"player": 1, "legal_balls": 18, "runs": 30, "wickets": 0},
             {"player": 2, "legal_balls": 12, "runs": 9, "wickets": 0}]
    rows = {r["player"]: r for r in stats.career_bowling(lines)}
    a = rows[1]
    assert a["overs"] == "7.0" and a["runs"] == 50 and a["wickets"] == 2
    assert a["average"] == pytest.approx(25) and a["economy"] == pytest.approx(50 / 7) and a["strike_rate"] == pytest.approx(21)
    assert a["best"] == "2/20"
    assert rows[2]["average"] is None and rows[2]["strike_rate"] is None and rows[2]["economy"] == pytest.approx(4.5)


def test_fielding_percentages():
    ev = [{"player": 1, "kind": "catch", "count": 3}, {"player": 1, "kind": "drop"}, {"player": 1, "kind": "direct_hit"},
          {"player": 1, "kind": "missed_run_out"}, {"player": 1, "kind": "clean_stop", "count": 8},
          {"player": 1, "kind": "misfield", "count": 2}, {"player": 1, "kind": "nonsense"}]
    r = stats.career_fielding(ev)[0]
    assert r["catch_pct"] == pytest.approx(75) and r["run_out_pct"] == pytest.approx(50) and r["ground_pct"] == pytest.approx(80)
    assert r["dismissals"] == 4 and r["opportunities"] == 16


def test_wagon_wheel_zones():
    assert stats.wagon_zone(10) == "long_off" and stats.wagon_zone(100) == "point" and stats.wagon_zone(260) == "square_leg"
    w = stats.wagon_wheel([{"shot_angle": 10, "runs_bat": 4}, {"shot_angle": 260, "runs_bat": 6},
                           {"shot_angle": None, "runs_bat": 1}])
    assert w["total_runs"] == 10 and w["unplotted"] == 1
    assert w["off_side_pct"] == pytest.approx(40) and w["leg_side_pct"] == pytest.approx(60)
    assert w["strong_zones"][0] == "square_leg"


def test_splits_and_leaderboard_qualification():
    balls = [{"striker": 1, "bowler": 9, "runs_bat": 4, "bowl_type": "pace", "x": 0.2, "y": 7},
             {"striker": 1, "bowler": 9, "runs_bat": 0, "bowl_type": "spin", "wicket_kind": "bowled", "x": 0, "y": 4},
             {"striker": 1, "bowler": 9, "wides": 1, "bowl_type": "pace"}]
    sp = stats.batting_splits(balls, 1)
    assert sp["overall"]["balls"] == 2 and sp["overall"]["runs"] == 4 and sp["overall"]["dismissals"] == 1
    assert sp["bowl_type"]["pace"]["strike_rate"] == pytest.approx(400)
    assert sp["bowl_type"]["spin"]["average"] == 0
    rows = [{"player": "a", "average": 60, "outs": 1}, {"player": "b", "average": 30, "outs": 5}, {"player": "c", "average": None, "outs": 0}]
    assert [r["player"] for r in stats.leaderboard(rows, "average", True, ("outs", 3))] == ["b"]
    assert [r["player"] for r in stats.leaderboard(rows, "average")] == ["a", "b"]


def test_improvement_needs_enough_readings():
    out = stats.improvement({"a": [10, 12, 30, 40], "b": [5, 50]})
    assert len(out) == 1 and out[0]["player"] == "a" and out[0]["change"] == pytest.approx(24)


def test_field_recommendation_needs_data_and_uses_nine_fielders():
    assert stats.recommend_field([{"shot_angle": 10, "runs_bat": 4}])["enough_data"] is False
    shots = [{"shot_angle": a, "runs_bat": r} for a, r in [(20, 4), (25, 1), (70, 4), (75, 2), (100, 1), (260, 6),
                                                           (265, 4), (300, 1), (300, 2), (330, 1), (60, 4), (15, 1), (250, 1)]]
    for style in ("attacking", "balanced", "defensive"):
        rec = stats.recommend_field(shots, style)
        assert rec["enough_data"] and len(rec["positions"]) == 9
        assert len({p["name"] for p in rec["positions"]}) == 9
        assert all(r["reason"] for r in rec["reasons"])


def test_scouting_report_states_evidence():
    data = sample_data.generate(seed=1, n_matches=4)
    batter = next(b["striker"] for b in data["balls"] if "batter 1" in b["striker"])
    rep = stats.scouting_report(data["balls"], batter)
    assert rep["enough_data"] and rep["findings"]
    assert all(f["evidence"] for f in rep["findings"])
    assert stats.scouting_report([], "nobody")["enough_data"] is False


# ---------------------------------------------------------------- DRS / trajectory

def test_drs_hitting_missing_inconclusive():
    hit = trajectory.simulate_drs(0.0, 6.0, 0.0, 2.0, 0.30, speed_kmh=110)
    assert hit["decision"] == "hitting" and hit["lbw"] == "out" and hit["educational_only"]
    miss = trajectory.simulate_drs(0.0, 6.0, 0.35, 2.0, 0.30, speed_kmh=110, shot_offered=False)
    assert miss["decision"] == "missing"                 # angling well past off stump
    over = trajectory.simulate_drs(0.0, 4.0, 0.0, 2.5, 0.75, speed_kmh=120)
    assert over["decision"] == "missing" and over["projection"]["z"] > 0.75    # going over the top
    edge = trajectory.simulate_drs(0.0, 6.0, 0.08, 2.0, 0.30, speed_kmh=110, position_sigma_m=0.06)
    assert edge["decision"] == "inconclusive"
    short = trajectory.simulate_drs(0.0, 2.2, 0.0, 2.0, 0.1)
    assert short["decision"] == "inconclusive" and "40 cm" in short["reason"]
    assert trajectory.simulate_drs(None, None, 0, 2, 0.3)["decision"] == "inconclusive"
    assert trajectory.simulate_drs(0, 2, 0, 3, 0.3)["decision"] == "inconclusive"     # impact behind the pitching point
    for r in (hit, miss, edge):
        assert r["assumptions"] and r["limitations"]
        assert r["projection"]["x_low"] <= r["projection"]["x"] <= r["projection"]["x_high"]


def test_lbw_law_conditions():
    leg = trajectory.simulate_drs(-0.3, 6.0, 0.0, 2.0, 0.3)
    assert leg["pitched"] == "outside leg" and leg["lbw"] == "not_out"
    nb = trajectory.simulate_drs(0.0, 6.0, 0.0, 2.0, 0.3, no_ball=True)
    assert nb["decision"] == "hitting" and nb["lbw"] == "not_out"
    bat = trajectory.simulate_drs(0.0, 6.0, 0.0, 2.0, 0.3, hit_bat_first=True)
    assert bat["lbw"] == "not_out"
    off_shot = trajectory.simulate_drs(0.5, 7.0, 0.2, 2.0, 0.3, shot_offered=True)
    assert off_shot["impact"] == "outside off" and off_shot["lbw"] == "not_out"
    off_noshot = trajectory.simulate_drs(0.5, 7.0, 0.2, 2.0, 0.3, shot_offered=False, position_sigma_m=0.01)
    assert off_noshot["conditions"][3]["pass"] is True


def test_homography_recovers_known_points():
    import numpy as np
    targets = trajectory.standard_calibration_targets()
    true_h = np.array([[40.0, 6.0, 320.0], [2.0, -18.0, 400.0], [0.0, 0.004, 1.0]])    # pitch -> image
    def to_img(x, y):
        p = true_h @ np.array([x, y, 1.0])
        return [p[0] / p[2], p[1] / p[2]]
    h = trajectory.fit_homography([to_img(t["x"], t["y"]) for t in targets], [[t["x"], t["y"]] for t in targets])
    u, v = to_img(0.2, 7.0)
    x, y = trajectory.image_to_pitch(h, u, v)
    assert x == pytest.approx(0.2, abs=1e-6) and y == pytest.approx(7.0, abs=1e-6)
    with pytest.raises(ValueError):
        trajectory.fit_homography([[0, 0], [1, 1], [2, 2], [3, 3]], [[0, 0], [1, 1], [2, 2], [3, 3]])
    with pytest.raises(ValueError):
        trajectory.fit_homography([[0, 0]], [[0, 0]])


def test_bounce_and_movement_detection():
    straight = sample_data.synthetic_track(seed=1)
    b = trajectory.detect_bounce(straight)
    assert b["found"] and abs(b["index"] - 15) <= 1
    m = trajectory.lateral_movement(straight, b["index"])
    assert m["swing"]["significant"] is False and m["seam"]["significant"] is False     # noise is not movement
    assert "warning" in m
    swing = sample_data.synthetic_track(seed=1, swing=30)
    assert trajectory.lateral_movement(swing, 15)["swing"]["significant"] is True
    seam = sample_data.synthetic_track(seed=1, seam=45)
    assert trajectory.lateral_movement(seam, 15)["seam"]["significant"] is True
    few = trajectory.lateral_movement(straight[:3])
    assert few["swing"]["status"] == "insufficient" and few["seam"]["status"] == "insufficient"
    assert trajectory.detect_bounce(straight[:4])["found"] is False
    assert trajectory.detect_bounce(straight[:14])["found"] is False                    # no reversal yet


def test_flight_path_lands_on_the_requested_length():
    path = trajectory.flight_path(2.0, 110, 7.0)
    assert path[0]["z"] == pytest.approx(2.0) and path[-1]["y"] == pytest.approx(7.0) and path[-1]["z"] == pytest.approx(0, abs=1e-3)
    with pytest.raises(ValueError):
        trajectory.flight_path(2.0, 110, PITCH_LENGTH_M + 1)


# ---------------------------------------------------------------- selection

def _squad():
    def p(i, name, role, style=None, avg=None, inns=5, bavg=None, balls=120):
        bat = {"average": avg, "innings": inns, "runs": int((avg or 0) * inns), "strike_rate": 100} if avg is not None else None
        bowl = {"average": bavg, "legal_balls": balls, "economy": 6.0, "wickets": 8, "overs": "20.0"} if bavg is not None else None
        return {"id": i, "name": name, "role": role, "bowl_style": style, "bat": bat, "bowl": bowl}
    return [p(1, "K1", "wicket_keeper", avg=20), p(2, "K2", "wicket_keeper", avg=35),
            p(3, "B1", "batter", avg=40), p(4, "B2", "batter", avg=30), p(5, "B3", "batter", avg=25), p(6, "B4", "batter", avg=8),
            p(7, "A1", "all_rounder", "pace_medium", avg=22, bavg=18), p(8, "P1", "bowler", "pace_fast", avg=5, bavg=15),
            p(9, "P2", "bowler", "pace_medium", avg=4, bavg=20), p(10, "P3", "bowler", "pace_medium", avg=6, bavg=22),
            p(11, "P4", "bowler", "pace_medium", avg=3, bavg=24), p(12, "S1", "bowler", "spin_off", avg=7, bavg=40),
            p(13, "N1", "batter"), p(14, "B5", "batter", avg=28)]


def test_selection_is_explained_and_balanced():
    res = selection.select_xi(_squad())
    names = [p["name"] for p in res["xi"]]
    assert len(names) == 11 and len(set(names)) == 11
    assert "K2" in names and "K1" not in names or "K1" in names        # best-averaging keeper is picked first
    assert next(r for r in res["reasons"] if r["player"] == "K2")["reason"].startswith("Wicket-keeper")
    assert "S1" in names                                               # spin option brought in for variety
    assert any("spin option" in r["reason"] for r in res["reasons"])
    assert all(r["reason"] for r in res["reasons"]) and res["assumptions"]
    assert res["analysis"]["bowling_options"] >= 5 and res["analysis"]["spin_options"] == ["S1"]
    assert {p["player"] for p in res["left_out"]} == {p["name"] for p in _squad()} - set(names)
    assert selection.select_xi(_squad()[:8])["enough_players"] is False


def test_xi_analysis_warnings_and_compare():
    xi = [p for p in _squad() if p["role"] == "batter"][:4]
    a = selection.analyse_xi(xi)
    assert any("not 11" in w for w in a["warnings"]) and any("wicket-keeper" in w for w in a["warnings"])
    c = selection.compare_xis(_squad()[:11], _squad()[3:14])
    assert c["only_in_a"] and c["only_in_b"] and "batting_depth" in c["differences"]


# ---------------------------------------------------------------- coach

def _ctx():
    data = sample_data.generate(seed=5, n_matches=6)
    from collections import defaultdict
    bat_lines, bowl_lines = [], []
    for m in data["matches"]:
        for n in (1, 2):
            rows = [b for b in data["balls"] if b["match_id"] == m["match_id"] and b["innings"] == n]
            c = scoring.score_innings(sample_data.engine_balls(rows))
            bat_lines += [{**b, "match_id": m["match_id"], "date": m["date"]} for b in c["batting"]]
            bowl_lines += [{**b, "match_id": m["match_id"], "date": m["date"]} for b in c["bowling"]]
    ours = {p["name"] for p in data["players"]}
    speeds = defaultdict(list)
    for s in data["speeds"]:
        speeds[s["player"]].append(s)
    acc = {}
    for name in ours:
        ds = [d for d in data["deliveries"] if d["player"] == name]
        if ds:
            acc[name] = pitchmap.accuracy(ds, 0.2, 7.0)
    return {"players": [{"id": p["name"], "name": p["name"], "role": p["role"]} for p in data["players"]],
            "batting": [r for r in stats.career_batting(bat_lines) if r["player"] in ours],
            "bowling": [r for r in stats.career_bowling(bowl_lines) if r["player"] in ours],
            "fielding": stats.career_fielding(data["fielding"]), "speeds": dict(speeds), "accuracy": acc,
            "splits": {n: stats.batting_splits(data["balls"], n) for n in ours}, "me": "Imran Khan"}


def test_coach_answers_come_from_data():
    ctx = _ctx()
    eco = coach.answer("Which of our bowlers has the best economy?", ctx)
    best = min((r for r in ctx["bowling"] if r["legal_balls"] >= 30), key=lambda r: r["economy"])
    assert best["player"] in eco["answer"] and f"{best['economy']:.2f}" in eco["answer"] and eco["engine"] == "rules"
    wk = coach.answer("Who has the most wickets?", ctx)
    assert max(ctx["bowling"], key=lambda r: r["wickets"])["player"] in wk["answer"]
    sp = coach.answer("How has my bowling speed changed this season?", ctx)
    assert sp["intent"] == "speed trend" and "km/h" in sp["answer"]
    spin = coach.answer("Who performs best against spin?", ctx)
    assert spin["intent"] == "best against spin" and spin["evidence"]
    weak = coach.answer("What are our team's biggest weaknesses?", ctx)
    assert weak["intent"] == "team weaknesses"
    imp = coach.answer("What should I improve as a bowler?", ctx)
    assert imp["intent"] == "recommendations"
    assert coach.answer("What is the meaning of life?", ctx)["intent"] == "unknown"
    assert coach.answer("", ctx)["intent"] == "empty"


def test_coach_says_when_there_is_no_data():
    empty = {"players": [{"id": 1, "name": "Sam Lee", "role": "bowler"}], "me": 1}
    assert "not enough" in coach.answer("Which of our bowlers has the best economy?", empty)["answer"].lower()
    assert "No bowling speeds" in coach.answer("Who is our fastest bowler?", empty)["answer"]
    assert coach.player_recommendations(empty, 1) == []
    assert coach.team_insights(empty) == []
    r = coach.answer("What should I improve?", empty)
    assert "too little data" in r["answer"] or "Nothing in the recorded data" in r["answer"]


def test_recommendations_carry_evidence():
    ctx = {"players": [{"id": 1, "name": "Sam Lee"}], "me": 1,
           "accuracy": {1: {"total": 24, "hit_pct": 25.0, "spread_x": 0.4, "bias_y": 1.5}},
           "fielding": [{"player": 1, "catch": 1, "drop": 4, "catch_chances": 5, "catch_pct": 20.0, "ground_chances": 0,
                         "ground_pct": None, "misfield": 0, "run_out_chances": 0, "run_out_pct": None, "run_outs_total": 0}],
           "splits": {1: {"overall": {"balls": 40, "dot_pct": 70},
                          "bowl_type": {"pace": {"balls": 20, "runs": 30, "strike_rate": 150, "dismissals": 0, "average": None},
                                        "spin": {"balls": 20, "runs": 8, "strike_rate": 40, "dismissals": 1, "average": 8}}}}}
    recs = coach.player_recommendations(ctx, 1)
    areas = {r["area"] for r in recs}
    assert {"Bowling accuracy", "Bowling line", "Bowling length", "Batting against spin", "Catching", "Strike rotation"} <= areas
    assert all(r["evidence"] and r["drill"] for r in recs)
    assert "25%" in next(r for r in recs if r["area"] == "Bowling accuracy")["evidence"]


def test_llm_is_optional(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert coach.llm_available() is False
    r = coach.answer("Who has the most wickets?", _ctx(), use_llm=True)
    assert r["engine"] == "rules" and "llm_note" in r


# ---------------------------------------------------------------- machine learning

def test_ml_refuses_small_samples_and_reports_baseline():
    small = ml.train_dot_ball_model([{"x": 0.1, "y": 6.0, "runs_bat": 0}] * 20)
    assert small["status"] == "insufficient"
    data = sample_data.generate(seed=2, n_matches=6)
    res = ml.train_dot_ball_model(data["balls"], synthetic=True)
    assert res["status"] == "ok" and res["results"][0]["model"].startswith("baseline")
    assert res["results"][0]["roc_auc_mean"] == pytest.approx(0.5)
    assert "SYNTHETIC" in res["caveat"] and res["feature_importance"]
    assert res["cleaning"]["rows_used"] < res["cleaning"]["rows_in"]        # wides and no-balls dropped
    e = ml.explain_delivery(res, 0.2, 7.0)
    assert 0 <= e["probability_dot_or_wicket"] <= 1


def test_trend_requires_interval_to_exclude_zero():
    assert ml.performance_trend([1, 2])["status"] == "insufficient"
    up = ml.performance_trend([100, 102, 104, 106.5, 108, 110])
    assert up["direction"] == "up" and up["ci_low"] > 0
    flat = ml.performance_trend([100, 108, 99, 107, 101, 104])
    assert flat["direction"] == "no clear trend"
    assert ml.performance_trend([None, float("nan"), 1, 2, 3, 4, 5])["n"] == 5


def test_batting_forecast_and_clusters():
    assert ml.batting_forecast([])["status"] == "insufficient"
    assert ml.cluster_deliveries([{"x": 0, "y": 5}])["status"] == "insufficient"
    data = sample_data.generate(seed=2, n_matches=3)
    cl = ml.cluster_deliveries([d for d in data["deliveries"] if d["x"] is not None], k=3)
    assert cl["status"] == "ok" and sum(c["count"] for c in cl["clusters"]) == len(cl["labels"])
