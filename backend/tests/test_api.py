"""API tests: accounts, database operations, scoring, video uploads, DRS, coach."""
import io
import os

import pytest

from pitchvision import tracking

H = None


@pytest.fixture(scope="module", autouse=True)
def _headers(auth):
    global H
    H = auth


def test_health_and_docs(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert "/api/drs/simulate" in client.get("/openapi.json").json()["paths"]


def test_auth_rules(client):
    assert client.get("/api/players").status_code == 401
    assert client.get("/api/auth/status").json()["has_users"] is True
    assert client.get("/api/auth/me", headers=H).json()["role"] == "admin"            # first account is the admin
    assert client.post("/api/auth/register", json={"email": "coach@example.com", "name": "x", "password": "longenough1"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "p@example.com", "name": "P", "password": "short"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "coach@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "COACH@example.com", "password": "longenough1"}).status_code == 200
    r = client.post("/api/auth/register", json={"email": "player@example.com", "name": "Pat", "password": "longenough1"})
    ph = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["user"]["role"] == "player"
    assert client.post("/api/players", json={"name": "Nope"}, headers=ph).status_code == 403
    assert client.get("/api/players", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_app_starts_empty(client):
    o = client.get("/api/overview", headers=H).json()
    assert o["counts"]["players"] == 0 and o["counts"]["matches_played"] == 0
    assert o["top_batters"] == [] and o["insights"] == [] and o["fastest"] is None
    assert client.get("/api/stats/tables", headers=H).json() == {"batting": [], "bowling": [], "fielding": []}
    assert all(b["rows"] == [] for b in client.get("/api/stats/leaderboards", headers=H).json()["boards"])


def _player(client, name, role="batter", style=None, side="us"):
    r = client.post("/api/players", json={"name": name, "role": role, "bowl_style": style, "side": side}, headers=H)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_players_crud_and_validation(client):
    pid = _player(client, "Temp Player")
    assert client.post("/api/players", json={"name": "temp player"}, headers=H).status_code == 409
    assert client.post("/api/players", json={"name": ""}, headers=H).status_code == 422
    assert client.post("/api/players", json={"name": "X", "role": "captain"}, headers=H).status_code == 422
    r = client.put(f"/api/players/{pid}", json={"name": "Temp Renamed", "role": "bowler", "bowl_style": "spin_off"}, headers=H)
    assert r.json()["name"] == "Temp Renamed"
    assert client.delete(f"/api/players/{pid}", headers=H).status_code == 204
    assert client.get(f"/api/players/{pid}/profile", headers=H).status_code == 404


def test_speed_calculator_and_history(client):
    r = client.post("/api/speed/calculate", json={"distance": 22, "time": 500, "distance_unit": "yd", "time_unit": "ms"})
    assert r.json()["speed_kmh"] == pytest.approx(20.1168 / 0.5 * 3.6) and r.json()["kind"] == "average"
    assert client.post("/api/speed/calculate", json={"distance": 0, "time": 1}).status_code == 422
    assert client.post("/api/speed/calculate", json={"distance": 10, "time": 1, "distance_unit": "km"}).status_code == 422
    pid = _player(client, "Quick Bowler", "bowler", "pace_fast")
    for t in (0.66, 0.64, 0.63):
        r = client.post("/api/speed/readings", json={"player_id": pid, "date": "2025-05-01", "distance": 18.9, "time": t}, headers=H)
        assert r.status_code == 201
    assert client.post("/api/speed/readings", json={"player_id": pid, "date": "2025-05-01", "source": "radar", "kmh": 121.5}, headers=H).status_code == 201
    assert client.post("/api/speed/readings", json={"player_id": pid, "date": "2025-05-01", "source": "radar"}, headers=H).status_code == 422
    assert client.post("/api/speed/readings", json={"player_id": pid, "date": "2025-05-01", "distance": 18.9}, headers=H).status_code == 422
    assert client.post("/api/speed/readings", json={"player_id": pid, "date": "2025-05-01", "distance": 18.9, "time": 0.1}, headers=H).status_code == 422
    assert client.post("/api/speed/readings", json={"player_id": 99999, "date": "2025-05-01", "distance": 18.9, "time": 0.6}, headers=H).status_code == 404
    h = client.get(f"/api/speed/history?player_id={pid}", headers=H).json()
    assert h["average_speed"]["count"] == 3 and h["radar"]["count"] == 1
    assert h["average_speed"]["max"] == pytest.approx(18.9 / 0.63 * 3.6)
    assert h["comparison"]["mean_difference_kmh"] > 0          # radar (release) reads higher than the average speed
    rid = h["readings"][0]["id"]
    assert client.delete(f"/api/speed/readings/{rid}", headers=H).status_code == 204
    assert client.get(f"/api/speed/history?player_id={pid}", headers=H).json()["average_speed"]["count"] == 2


def test_line_and_length_session(client):
    pid = _player(client, "Line Bowler", "bowler", "pace_medium")
    s = client.post("/api/bowling/sessions", json={"player_id": pid, "date": "2025-05-02", "name": "Nets"}, headers=H).json()
    sid = s["id"]
    for x, y in [(0.2, 7.0), (0.25, 6.6), (0.9, 3.0), (0.0, 1.0)]:
        r = client.post(f"/api/bowling/sessions/{sid}/deliveries", json={"x": x, "y": y}, headers=H)
        assert r.status_code == 201
    a = r.json()
    assert a["accuracy"]["total"] == 4 and a["accuracy"]["hits"] == 2 and a["accuracy"]["hit_pct"] == 50
    assert {d["length"] for d in a["deliveries"]} == {"good", "full", "yorker"}
    assert client.post(f"/api/bowling/sessions/{sid}/deliveries", json={"x": 5, "y": 7}, headers=H).status_code == 422
    did = a["deliveries"][-1]["id"]
    assert client.delete(f"/api/bowling/deliveries/{did}", headers=H).json()["accuracy"]["total"] == 3
    r = client.put(f"/api/bowling/sessions/{sid}", json={"player_id": pid, "date": "2025-05-02", "target_x": 0.9, "target_y": 3.0}, headers=H)
    assert r.json()["accuracy"]["hits"] == 1                    # moving the target changes what counts as a hit
    s2 = client.post("/api/bowling/sessions", json={"player_id": pid, "date": "2025-05-09"}, headers=H).json()["id"]
    client.post(f"/api/bowling/sessions/{s2}/deliveries", json={"x": 0.9, "y": 3.0}, headers=H)
    cmp = client.get(f"/api/bowling/compare?a={sid}&b={s2}", headers=H).json()
    assert cmp["b"]["hit_pct"] == 100 and cmp["change"]["hit_pct"] > 0
    assert len(client.get(f"/api/bowling/accuracy-trend?player_id={pid}", headers=H).json()) == 2
    assert client.get("/api/bowling/sessions/99999", headers=H).status_code == 404
    g = client.get("/api/pitch/geometry").json()
    assert g["length"] == 20.12 and [b["name"] for b in g["length_bands"]][:3] == ["yorker", "full", "good"]


def test_live_scoring_follows_the_laws(client):
    a, b, c = _player(client, "Opener One"), _player(client, "Opener Two"), _player(client, "Number Three")
    x = _player(client, "Their Bowler", "bowler", "pace_medium", side="Rivals")
    mid = client.post("/api/matches", json={"date": "2025-06-01", "opponent": "Rivals", "overs": 2, "format": "T2"}, headers=H).json()["id"]
    iid = client.post(f"/api/matches/{mid}/innings", json={"batting_side": "us"}, headers=H).json()["innings_id"]
    ball = lambda **kw: client.post(f"/api/innings/{iid}/balls", json={"striker_id": a, "non_striker_id": b, "bowler_id": x, **kw}, headers=H)
    r = ball(runs_bat=1)
    assert r.status_code == 201 and r.json()["next"]["striker"] == b and r.json()["next"]["striker_name"] == "Opener Two"
    assert ball(wides=1, runs_bat=2).status_code == 422                         # runs off the bat on a wide
    assert ball(no_balls=1, wicket_kind="bowled").status_code == 422           # bowled off a no-ball
    assert ball(striker_id=a, non_striker_id=a).status_code == 422
    r = client.post(f"/api/innings/{iid}/balls", json={"striker_id": b, "non_striker_id": a, "bowler_id": x, "wides": 1}, headers=H)
    assert r.json()["total"] == 2 and r.json()["legal_balls"] == 1
    r = client.post(f"/api/innings/{iid}/balls", json={"striker_id": b, "non_striker_id": a, "bowler_id": x, "wicket_kind": "bowled",
                                                       "x": 0.0, "y": 5.5}, headers=H)
    card = r.json()
    assert card["wickets"] == 1 and card["bowling"][0]["wickets"] == 1 and card["next"]["striker"] is None
    assert card["fall_of_wickets"][0]["name"] == "Opener Two"
    r = client.post(f"/api/innings/{iid}/balls", json={"striker_id": c, "non_striker_id": a, "bowler_id": x, "runs_bat": 4,
                                                       "shot_angle": 70, "shot_type": "drive"}, headers=H)
    assert r.json()["total"] == 6 and r.json()["overs"] == "0.3"
    undone = client.delete(f"/api/innings/{iid}/balls/last", headers=H).json()
    assert undone["total"] == 2 and undone["overs"] == "0.2"
    for _ in range(10):
        r = client.post(f"/api/innings/{iid}/balls", json={"striker_id": c, "non_striker_id": a, "bowler_id": x, "runs_bat": 0}, headers=H)
    assert r.json()["complete"] and r.json()["overs"] == "2.0"
    assert client.post(f"/api/innings/{iid}/balls", json={"striker_id": c, "non_striker_id": a, "bowler_id": x}, headers=H).status_code == 409
    # second innings by scorecard entry
    assert client.post(f"/api/matches/{mid}/innings", json={"batting_side": "us"}, headers=H).status_code == 409
    i2 = client.post(f"/api/matches/{mid}/innings", json={"batting_side": "them"}, headers=H).json()["innings_id"]
    opp = _player(client, "Their Batter", side="Rivals")
    bad = {"batting": [{"player_id": opp, "runs": 3, "balls": 5, "fours": 1}], "bowling": []}
    assert client.put(f"/api/innings/{i2}/lines", json=bad, headers=H).status_code == 422       # a four needs 4 runs
    assert client.put(f"/api/innings/{i2}/lines", json={"batting": [], "bowling": [{"player_id": a, "overs": "1.7", "runs": 1, "wickets": 0}]}, headers=H).status_code == 422
    ok = {"batting": [{"player_id": opp, "runs": 1, "balls": 12, "out": False}],
          "bowling": [{"player_id": a, "overs": "2.0", "runs": 1, "wickets": 0, "maidens": 1}]}
    assert client.put(f"/api/innings/{i2}/lines", json=ok, headers=H).status_code == 200
    client.put(f"/api/matches/{mid}", json={"date": "2025-06-01", "opponent": "Rivals", "overs": 2, "format": "T2",
                                            "status": "completed", "outcome": "won", "season": "2025"}, headers=H)
    d = client.get(f"/api/matches/{mid}", headers=H).json()
    assert [c_["total"] for c_ in d["cards"]] == [2, 1] and d["computed_result"] == "Us won by 1 run"
    assert d["cards"][0]["source"] == "ball_by_ball" and d["cards"][1]["source"] == "scorecard"
    t = client.get("/api/stats/tables?season=2025", headers=H).json()
    one = next(r for r in t["batting"] if r["name"] == "Opener One")
    assert one["runs"] == 1 and one["average"] is None                      # not out: no average
    two = next(r for r in t["batting"] if r["name"] == "Opener Two")
    assert two["ducks"] == 1 and two["average"] == 0
    assert next(r for r in t["bowling"] if r["name"] == "Opener One")["economy"] == pytest.approx(0.5)
    assert client.get("/api/stats/tables?season=1999", headers=H).json()["batting"] == []
    prof = client.get(f"/api/players/{a}/profile", headers=H).json()
    assert prof["batting"]["runs"] == 1 and prof["bowling"]["overs"] == "2.0"
    assert client.delete(f"/api/players/{a}", headers=H).status_code == 409       # has recorded balls


def test_csv_import(client):
    mid = client.post("/api/matches", json={"date": "2025-06-08", "opponent": "CSV Club", "overs": 20}, headers=H).json()["id"]
    iid = client.post(f"/api/matches/{mid}/innings", json={"batting_side": "them"}, headers=H).json()["innings_id"]
    good = "striker,non_striker,bowler,runs_bat,wides,shot_angle,wicket_kind\nAl,Bo,Line Bowler,4,0,70,\nAl,Bo,Line Bowler,0,1,,\nAl,Bo,Line Bowler,0,0,,bowled\n"
    bad = "striker,non_striker,bowler,runs_bat,wides\nAl,Bo,Line Bowler,2,1\n"
    up = lambda text: client.post(f"/api/innings/{iid}/import-csv", files={"file": ("b.csv", text, "text/csv")}, headers=H)
    assert up("a,b\n1,2\n").status_code == 422
    assert up(bad).status_code == 422
    assert up(good).json()["imported"] == 3
    assert up(good).status_code == 409
    d = client.get(f"/api/matches/{mid}", headers=H).json()
    assert d["cards"][0]["total"] == 5 and d["cards"][0]["wickets"] == 1
    teams = client.get("/api/opposition/teams", headers=H).json()
    al = next(p for t in teams if t["team"] == "CSV Club" for p in t["players"] if p["name"] == "Al")
    assert al["balls_faced"] == 2
    assert client.get(f"/api/stats/wagon?player_id={al['id']}", headers=H).json()["total_runs"] == 4
    assert client.get(f"/api/opposition/report?player_id={al['id']}", headers=H).json()["enough_data"] is False


def test_fielding_setups_goals_training(client):
    pid = _player(client, "Field Er")
    for kind, n in (("catch", 3), ("drop", 1), ("clean_stop", 4)):
        assert client.post("/api/fielding/events", json={"player_id": pid, "date": "2025-06-01", "kind": kind, "count": n}, headers=H).status_code == 201
    assert client.post("/api/fielding/events", json={"player_id": pid, "date": "2025-06-01", "kind": "juggle"}, headers=H).status_code == 422
    row = next(r for r in client.get("/api/stats/tables", headers=H).json()["fielding"] if r["player"] == pid)
    assert row["catch_pct"] == 75 and row["ground_pct"] == 100
    pos = client.get("/api/fielding/positions").json()
    s = client.post("/api/fielding/setups", json={"name": "Powerplay", "style": "attacking", "positions": pos[:9]}, headers=H)
    assert s.status_code == 201 and len(client.get("/api/fielding/setups", headers=H).json()) == 1
    assert client.post("/api/fielding/setups", json={"name": "Too many", "positions": pos[:10]}, headers=H).status_code == 422
    assert client.delete(f"/api/fielding/setups/{s.json()['id']}", headers=H).status_code == 204
    assert client.get(f"/api/fielding/recommend?batter_id={pid}", headers=H).json()["enough_data"] is False
    assert client.post("/api/training", json={"player_id": pid, "date": "2025-06-02", "kind": "fielding", "duration_min": 45}, headers=H).status_code == 201
    assert client.post("/api/training", json={"player_id": pid, "date": "2025-06-02", "kind": "fielding", "duration_min": 0}, headers=H).status_code == 422
    assert client.post("/api/goals", json={"player_id": pid, "title": "Catch 80%", "metric": "catch_pct"}, headers=H).status_code == 422
    g = client.post("/api/goals", json={"player_id": pid, "title": "Catch 70%", "metric": "catch_pct", "target_value": 70}, headers=H).json()
    p = client.get(f"/api/progress?player_id={pid}", headers=H).json()
    assert p["goals"][0]["current_value"] == 75 and p["goals"][0]["met"] is True
    assert p["weekly"][0]["minutes"] == 45 and p["monthly"][0]["period"] == "2025-06"
    assert client.patch(f"/api/goals/{g['id']}", json={"status": "achieved"}, headers=H).json()["achieved_at"]
    assert any("Goal achieved" in m["title"] for m in client.get(f"/api/progress?player_id={pid}", headers=H).json()["milestones"])


def test_players_edit_only_their_own_records(client):
    pid = _player(client, "Own Profile")
    other = _player(client, "Someone Else")
    r = client.post("/api/auth/register", json={"email": "own@example.com", "name": "Own", "password": "longenough1"})
    ph, uid = {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["id"]
    body = {"date": "2025-06-03", "distance": 18.9, "time": 0.7}
    assert client.post("/api/speed/readings", json={"player_id": pid, **body}, headers=ph).status_code == 403
    assert client.patch(f"/api/users/{uid}", json={"player_id": pid}, headers=H).json()["player_id"] == pid
    assert client.post("/api/speed/readings", json={"player_id": pid, **body}, headers=ph).status_code == 201
    assert client.post("/api/speed/readings", json={"player_id": other, **body}, headers=ph).status_code == 403
    assert client.patch(f"/api/users/{uid}", json={"role": "coach"}, headers=ph).status_code == 403


def test_drs_endpoint(client):
    r = client.post("/api/drs/simulate", json={"pitch_x": 0, "pitch_y": 6, "impact_x": 0, "impact_y": 2, "impact_z": 0.3,
                                               "speed_kmh": 110, "save": True, "label": "Test review"}, headers=H).json()
    assert r["decision"] == "hitting" and r["lbw"] == "out" and r["educational_only"] and len(r["conditions"]) == 5
    assert client.post("/api/drs/simulate", json={"pitch_x": 0, "pitch_y": 6}, headers=H).json()["decision"] == "inconclusive"
    assert client.post("/api/drs/simulate", json={"pitch_x": 9, "pitch_y": 6}, headers=H).status_code == 422
    revs = client.get("/api/drs/reviews", headers=H).json()
    assert revs[0]["label"] == "Test review"
    assert client.delete(f"/api/drs/reviews/{revs[0]['id']}", headers=H).status_code == 204


def test_video_upload_validation(client, tmpdir_session):
    post = lambda url, name, data, **form: client.post(url, files={"file": (name, data, "video/mp4")}, data=form, headers=H)
    assert post("/api/video/track", "notes.txt", b"hello").status_code == 415                  # wrong type
    assert post("/api/video/track", "empty.mp4", b"").status_code == 422                       # empty file
    assert post("/api/video/track", "broken.mp4", os.urandom(4000)).status_code == 422         # corrupted video
    assert post("/api/video/pose", "broken.mov", b"not a real video" * 100).status_code == 422
    assert post("/api/video/track", "big.mp4", b"0" * (6 * 1024 * 1024)).status_code == 413   # over the 5 MB test limit
    assert os.listdir(os.environ["PITCHVISION_UPLOAD_DIR"]) == []                              # nothing left behind


def test_ball_tracking_upload(client, tmpdir_session):
    path = os.path.join(tmpdir_session, "synthetic.mp4")
    truth = tracking.write_synthetic_ball_video(path)
    with open(path, "rb") as f:
        r = client.post("/api/video/track", files={"file": ("ball.mp4", f, "video/mp4")}, data={"colour": "red", "label": "synthetic"}, headers=H)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["status"] == "ok" and res["observed_count"] >= 25 and res["confidence_label"] in ("high", "medium")
    assert res["bounce"]["found"] and abs(res["bounce"]["frame"] - truth["bounce_frame"]) <= 2
    assert all("observed" in p for p in res["points"])
    assert res["movement"]["swing"]["significant"] is False and res["calibrated"] is False
    # a clip with nothing moving -> insufficient tracking data, not an error
    import cv2, numpy as np
    still = os.path.join(tmpdir_session, "still.mp4")
    w = cv2.VideoWriter(still, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 180))
    for _ in range(20):
        w.write(np.full((180, 320, 3), 90, np.uint8))
    w.release()
    with open(still, "rb") as f:
        r = client.post("/api/video/track", files={"file": ("still.mp4", f, "video/mp4")}, headers=H)
    assert r.status_code == 200 and r.json()["result"]["status"] == "insufficient" and r.json()["result"]["reason"]
    # calibration maps the bounce point to pitch metres
    corners = [[600, 330], [40, 330], [40, 200], [600, 200]]
    import json
    with open(path, "rb") as f:
        r = client.post("/api/video/track", files={"file": ("ball.mp4", f, "video/mp4")}, data={"colour": "red", "calibration": json.dumps(corners)}, headers=H)
    assert r.json()["result"]["calibrated"] is True and "x" in r.json()["result"]["pitching"]
    ids = [v["id"] for v in client.get("/api/video/analyses?kind=tracking", headers=H).json()]
    assert len(ids) == 3
    cmp = client.get(f"/api/video/compare?a={ids[0]}&b={ids[2]}", headers=H).json()
    assert cmp["kind"] == "tracking" and len(cmp["rows"]) == 4


def test_pose_upload_without_a_person(client, tmpdir_session):
    with open(os.path.join(tmpdir_session, "still.mp4"), "rb") as f:
        r = client.post("/api/video/pose", files={"file": ("still.mp4", f, "video/mp4")}, data={"mode": "bowling"}, headers=H)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["status"] == "insufficient" and "disclaimer" in res and res["observations"] == []


def test_sample_data_round_trip(client):
    assert client.post("/api/sample-data", headers=H).json()["matches"] == 8
    assert client.post("/api/sample-data", headers=H).status_code == 409
    team = client.get("/api/team", headers=H).json()
    assert team["has_sample_data"] and "2025" in team["seasons"]
    o = client.get("/api/overview", headers=H).json()
    assert o["counts"]["matches_played"] >= 8 and o["top_batters"] and o["fastest"]
    lb = client.get("/api/stats/leaderboards?season=2025&format=T20", headers=H).json()
    assert all(b["rows"] for b in lb["boards"] if b["key"] in ("runs", "wickets", "economy", "speed", "accuracy", "catches"))
    players = client.get("/api/players?side=us", headers=H).json()
    sample = [p for p in players if p["is_sample"]]
    sel = client.post("/api/team/select", json={"available": [p["id"] for p in sample], "overs": 20}, headers=H).json()
    assert len(sel["xi"]) == 11 and all(r["reason"] for r in sel["reasons"]) and sel["analysis"]["keepers"]
    ids = [p["id"] for p in sample]
    assert "batting_depth" in client.post("/api/team/compare", json={"a": ids[:11], "b": ids[3:14]}, headers=H).json()["differences"]
    q = client.post("/api/coach/ask", json={"question": "Which of our bowlers has the best economy?"}, headers=H).json()
    assert q["engine"] == "rules" and q["evidence"]
    imran = next(p["id"] for p in sample if p["name"] == "Imran Khan")
    q = client.post("/api/coach/ask", json={"question": "How has my bowling speed changed this season?", "player_id": imran}, headers=H).json()
    assert q["intent"] == "speed trend" and q["about_player"] == "Imran Khan"
    recs = client.get("/api/coach/recommendations", headers=H).json()
    assert recs["players"] and all(r["evidence"] for p in recs["players"] for r in p["recommendations"])
    opp = client.get("/api/opposition/teams", headers=H).json()
    batter = max((p for t in opp for p in t["players"]), key=lambda p: p["balls_faced"])
    rep = client.get(f"/api/opposition/report?player_id={batter['id']}", headers=H).json()
    assert rep["enough_data"] and rep["findings"]
    rec = client.get(f"/api/fielding/recommend?batter_id={batter['id']}&style=defensive", headers=H).json()
    assert rec["enough_data"] and len(rec["positions"]) == 9
    model = client.get("/api/ml/dot-ball-model", headers=H).json()
    assert model["status"] == "ok" and "model" not in model
    prof = client.get(f"/api/players/{imran}/profile", headers=H).json()
    assert prof["bowling"]["wickets"] > 0 and prof["speed_summary"]["count"] > 0 and prof["accuracy"]["total"] > 0
    assert client.get(f"/api/stats/compare?a={ids[0]}&b={ids[1]}", headers=H).json()["players"][0]["batting"]
    assert client.delete("/api/sample-data", headers=H).json()["cleared"] is True
    assert client.get("/api/team", headers=H).json()["has_sample_data"] is False
    assert not [p for p in client.get("/api/players", headers=H).json() if p["is_sample"]]
