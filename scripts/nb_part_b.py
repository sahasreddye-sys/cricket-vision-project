"""Notebooks 05-08: line and length, swing and seam, batting, fielding."""
from nb_common import closing, header

NB05 = header(
    "05 · Bowling Line and Length Analysis",
    "Plot where each delivery pitched, sort deliveries into line and length bands, and measure how accurate and how consistent a bowler was.",
) + [
    ("md", "## 1. The pitch coordinate system\n\nEvery delivery is stored as two numbers.\n\n"
           "`x` is how far across the pitch it landed, in metres from the line of middle stump. Positive means the off side. "
           "Left-handers are mirrored when the data is entered, so positive is always off.\n\n"
           "`y` is how far from the striker's stumps it landed, in metres. The stumps are at 0 and the bowler's stumps at 20.12.\n\n"
           "| Length | Pitches (m from the stumps) |\n|---|---|\n| Yorker | 0 to 2 |\n| Full | 2 to 6 |\n| Good | 6 to 8 |\n| Short | 8 to 10 |\n| Bouncer | over 10 |\n\n"
           "| Line | x (m) |\n|---|---|\n| Wide leg | below -0.45 |\n| Leg | -0.45 to -0.114 |\n| Stumps | within 0.114 of middle |\n| Off | 0.114 to 0.45 |\n| Wide off | above 0.45 |\n\n"
           "These bands are coaching conventions for pace bowling. A coach can change them in `pitchvision/constants.py`."),
    ("code", '''from pitchvision import pitchmap
from pitchvision.constants import LENGTH_BANDS, LINE_BANDS, PITCH_WIDTH_M, WICKET_HALF_WIDTH_M

def length_by_hand(y):
    """Length band from the distance to the stumps."""
    if y < 2: return "yorker"
    if y < 6: return "full"
    if y < 8: return "good"
    if y < 10: return "short"
    return "bouncer"

for y in [0.5, 1.99, 2.0, 5.9, 6.0, 7.99, 8.0, 9.5, 12.0]:
    assert length_by_hand(y) == pitchmap.classify_length(y)
print("Hand-written bands match pitchvision.pitchmap.classify_length")
print([pitchmap.classify_line(x) for x in (-0.9, -0.2, 0.0, 0.2, 0.6)])'''),
    ("md", "## 2. Load the deliveries\n\nEach row is one ball from a net session. A few rows have no `x`. Those balls were "
           "seen but not located, so they are counted and left out of every calculation."),
    ("code", '''deliveries = pd.read_csv(DATA / "deliveries.csv", parse_dates=["date"])
print(len(deliveries), "deliveries,", deliveries["x"].isna().sum(), "with no recorded line")
located = deliveries.dropna(subset=["x", "y"]).copy()
located["length"] = located["y"].apply(pitchmap.classify_length)
located["line"] = located["x"].apply(pitchmap.classify_line)
located.head()'''),
    ("md", "## 3. A pitch map for one bowler"),
    ("code", '''def draw_pitch(ax, y_max=13):
    ax.add_patch(plt.Rectangle((-PITCH_WIDTH_M / 2, 0), PITCH_WIDTH_M, y_max, color="#D8C98F", zorder=0))
    for name, lo, hi in LENGTH_BANDS:
        if lo < y_max:
            ax.axhline(min(hi, y_max), color=INK, lw=0.6, ls=":")
            ax.text(-PITCH_WIDTH_M / 2 - 0.08, (lo + min(hi, y_max)) / 2, name, ha="right", va="center", fontsize=9)
    ax.axhline(1.22, color="white", lw=2)                       # popping crease
    for s in (-WICKET_HALF_WIDTH_M, 0, WICKET_HALF_WIDTH_M):
        ax.plot(s, 0, "s", color=INK, ms=5)
    ax.set_xlim(-PITCH_WIDTH_M / 2 - 0.9, PITCH_WIDTH_M / 2 + 0.1); ax.set_ylim(-0.3, y_max)
    ax.set_xlabel("across (m): leg side  <-  ->  off side"); ax.set_ylabel("metres from the striker's stumps"); ax.grid(False)

bowler = "Imran Khan"
mine = located[located["player"] == bowler]
target = {"x": 0.2, "y": 7.0, "tol_x": 0.2, "tol_y": 1.0}

fig, ax = plt.subplots(figsize=(4.6, 8))
draw_pitch(ax)
ax.add_patch(plt.Rectangle((target["x"] - target["tol_x"], target["y"] - target["tol_y"]), 2 * target["tol_x"], 2 * target["tol_y"],
                           fill=False, ec=RED, lw=2, ls="--", label="target zone"))
ax.scatter(mine["x"], mine["y"], color=INK, s=22, edgecolor="white", linewidth=0.5, zorder=3)
ax.set_title(f"{bowler}: {len(mine)} deliveries (SYNTHETIC data)"); ax.legend(loc="upper right"); plt.show()'''),
    ("md", "## 4. Delivery distribution"),
    ("code", '''dist = pitchmap.distribution(mine.to_dict("records"))
length_table = pd.DataFrame(dist["length"]).set_index("band")
line_table = pd.DataFrame(dist["line"]).set_index("band")
assert length_table["count"].sum() == len(mine)                 # every located ball is in exactly one band

fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
axes[0].bar(length_table.index, length_table["pct"], color=INK); axes[0].set_title("By length (%)")
axes[1].bar(line_table.index, line_table["pct"], color=GREEN); axes[1].set_title("By line (%)")
plt.show()
length_table.round(1)'''),
    ("md", "## 5. Accuracy and consistency\n\nAccuracy is measured against a target the coach sets: a line, a length, and a tolerance for each.\n\n"
           "The hit rate is the share of deliveries inside the target box. The mean error is the average straight-line distance from "
           "the target. Bias is the average signed miss, which tells you where the group is centred. Spread is the standard deviation, "
           "which tells you how tight the group is.\n\n"
           "A bowler can be consistent and still inaccurate: a tight group in the wrong place has a small spread and a large bias. "
           "The fix for that is a different aim. A wide spread needs work on repeating the action."),
    ("code", '''def accuracy_by_hand(df, tx, ty, tol_x, tol_y):
    hits = ((df["x"] - tx).abs() <= tol_x) & ((df["y"] - ty).abs() <= tol_y)
    return {"hit_pct": hits.mean() * 100,
            "mean_error_m": np.hypot(df["x"] - tx, df["y"] - ty).mean(),
            "bias_x": df["x"].mean() - tx, "bias_y": df["y"].mean() - ty,
            "spread_x": df["x"].std(ddof=0), "spread_y": df["y"].std(ddof=0)}

hand = accuracy_by_hand(mine, **{"tx": 0.2, "ty": 7.0, "tol_x": 0.2, "tol_y": 1.0})
app = pitchmap.accuracy(mine.to_dict("records"), 0.2, 7.0, 0.2, 1.0)
for k, v in hand.items():
    assert abs(v - app[k]) < 1e-9, k
print(f"In the target zone: {app['hit_pct']:.0f}% ({app['hits']} of {app['total']})")
print(f"Average miss: {app['mean_error_m']:.2f} m")
print(f"Group centre: {app['bias_x'] * 100:+.0f} cm across, {app['bias_y']:+.2f} m in length, relative to the target")
print(f"Spread: {app['spread_x'] * 100:.0f} cm in line, {app['spread_y']:.2f} m in length")
print(f"Consistency index: {app['consistency_index']:.0f} / 100")'''),
    ("md", "## 6. Heatmap\n\nA heatmap counts deliveries in each cell of a grid laid over the pitch. It shows the pattern better than "
           "individual dots once there are many deliveries."),
    ("code", '''heat = pitchmap.heatmap(mine.to_dict("records"))
fig, ax = plt.subplots(figsize=(4.6, 7.2))
im = ax.imshow(heat["counts"], origin="lower", cmap="YlOrRd", aspect="auto",
               extent=[heat["x_edges"][0], heat["x_edges"][-1], heat["y_edges"][0], heat["y_edges"][-1]])
ax.axvline(-WICKET_HALF_WIDTH_M, color=INK, lw=0.8); ax.axvline(WICKET_HALF_WIDTH_M, color=INK, lw=0.8)
ax.set_xlabel("across (m)"); ax.set_ylabel("metres from the stumps"); ax.grid(False)
ax.set_title(f"{bowler}: where the ball pitched (SYNTHETIC data)"); plt.colorbar(im, label="deliveries"); plt.show()
print("Deliveries outside the grid:", heat["outside"])'''),
    ("md", "## 7. Comparing sessions"),
    ("code", '''rows = []
for session, g in mine.groupby("session_no"):
    a = pitchmap.accuracy(g.to_dict("records"), 0.2, 7.0)
    rows.append({"session": session, "date": g["date"].iloc[0].date(), "balls": a["total"], "hit %": a["hit_pct"],
                 "mean error (m)": a["mean_error_m"], "line spread (cm)": a["spread_x"] * 100, "length spread (m)": a["spread_y"]})
sessions = pd.DataFrame(rows).set_index("session"); display(sessions.round(2))

first, last = mine[mine["session_no"] == 1], mine[mine["session_no"] == mine["session_no"].max()]
cmp = pitchmap.compare_sessions(first.to_dict("records"), last.to_dict("records"), 0.2, 7.0)
print("Change from the first to the last session:", {k: round(v, 2) for k, v in cmp["change"].items()})

fig, ax = plt.subplots()
ax.plot(sessions.index, sessions["hit %"], marker="o", color=INK)
ax.set_xlabel("session"); ax.set_ylabel("deliveries in the target zone (%)"); ax.set_ylim(0, 100)
ax.set_title(f"{bowler}: accuracy by session (SYNTHETIC data)"); plt.show()'''),
    ("md", "## 8. Every bowler\n\nWith only 24 balls a session, a hit rate moves a lot by chance. The last column is a rough 95% "
           "range for the hit rate (the normal approximation, 1.96 standard errors either side)."),
    ("code", '''rows = []
for player, g in located.groupby("player"):
    t_y = 5.2 if g["bowl_type"].iloc[0] == "spin" else 7.0       # spinners aim fuller
    a = pitchmap.accuracy(g.to_dict("records"), 0.2, t_y)
    p = a["hit_pct"] / 100
    margin = 1.96 * np.sqrt(p * (1 - p) / a["total"]) * 100
    rows.append({"player": player, "balls": a["total"], "target length": t_y, "hit %": a["hit_pct"], "+/-": margin,
                 "line spread (cm)": a["spread_x"] * 100, "consistency": a["consistency_index"]})
table = pd.DataFrame(rows).set_index("player").sort_values("hit %", ascending=False).round(1)
table.to_csv(EXPORTS / "bowling_accuracy_by_player.csv")
table'''),
] + closing(
    "- Line and length bands are fixed thresholds on x and y; the hand-written rules match the shared module.\n"
    "- Accuracy splits into bias (where the group is centred) and spread (how tight it is), and the two call for different practice.\n"
    "- In the synthetic data the groups tighten across sessions because the generator shrinks the spread by 7% a session.",
    "Use the hit rate to track one bowler against one target over time. Compare bowlers only when they bowled at the same target, and read the range next to each hit rate before calling one bowler more accurate than another.",
    "- Pitching points are entered by eye or taken from single-camera tracking, so each has an error of several centimetres in line and more in length.\n"
    "- The bands suit pace bowling at adult pitch length. Junior pitches are shorter and the bands should be scaled.\n"
    "- A target box rewards landing the ball in an area. It says nothing about pace, movement or what the batter did.\n"
    "- All figures shown come from synthetic data.",
    "The Bowling Lab's Line and length tab stores each click on the pitch map as an (x, y) delivery and calls `pitchmap.distribution`, "
    "`accuracy`, `heatmap` and `compare_sessions` through `GET /api/bowling/sessions/{id}` and `/api/bowling/compare`. The band edges drawn "
    "on screen come from `GET /api/pitch/geometry`, which reads the same constants used here.",
)

# ---------------------------------------------------------------------------------------------------------------

NB06 = header(
    "06 · Swing and Seam Analysis",
    "Measure sideways movement in the air and off the pitch from a tracked ball path, and tell real movement apart from tracking noise.",
) + [
    ("md", "## 1. The problem with noise\n\nA tracked ball position is never exact. Each point is off by a pixel or two. If we report "
           "every wobble as swing, every delivery will appear to swing. So each movement is compared with its own uncertainty, and it "
           "is reported as movement only when it is at least three times its standard error. Anything smaller is labelled "
           "\"within tracking noise\".\n\n"
           "Swing is measured as the gap between where the ball was just before it bounced and where its early direction was pointing. "
           "Seam is measured as the change in sideways speed across the bounce.\n\n"
           "The tracks here are synthetic pixel paths made by `sample_data.synthetic_track`. To use a real clip, track it in notebook 03 "
           "and pass `result[\"points\"]` to the same functions."),
    ("code", '''from pitchvision import trajectory, sample_data

straight = sample_data.synthetic_track(seed=1, noise=1.2)
swinging = sample_data.synthetic_track(seed=1, noise=1.2, swing=30)
seaming = sample_data.synthetic_track(seed=1, noise=1.2, seam=45)

fig, ax = plt.subplots()
for pts, label, colour in [(straight, "straight", INK), (swinging, "swing built in", RED), (seaming, "seam built in", GREEN)]:
    d = pd.DataFrame(pts); ax.plot(d["t"], d["x"], "o-", ms=3, color=colour, label=label)
ax.axvline(straight[15]["t"], color=INK, ls=":", label="bounce")
ax.set_xlabel("time (s)"); ax.set_ylabel("sideways position in the image (px)")
ax.set_title("Three SYNTHETIC deliveries"); ax.legend(); plt.show()'''),
    ("md", "## 2. Noise filtering\n\nA moving average replaces each point with the mean of itself and its neighbours. It removes jitter "
           "and keeps the shape. It also flattens sharp changes, which is why the bounce is found on the raw points and the filter is "
           "used only for drawing."),
    ("code", '''noisy = sample_data.synthetic_track(seed=3, noise=4.0, swing=30)
d = pd.DataFrame(noisy)
d["smoothed"] = trajectory.smooth_track(d["x"].tolist(), window=5)
by_hand = d["x"].rolling(5, center=True, min_periods=1).mean()
assert np.allclose(d["smoothed"], by_hand)                      # same as pandas' centred rolling mean

fig, ax = plt.subplots()
ax.plot(d["t"], d["x"], "o", ms=4, color=INK, alpha=0.45, label="tracked points (noisy)")
ax.plot(d["t"], d["smoothed"], color=RED, lw=2, label="5-point moving average")
ax.set_xlabel("time (s)"); ax.set_ylabel("sideways position (px)"); ax.legend(); plt.show()'''),
    ("md", "## 3. Swing, step by step\n\n1. Fit a straight line to the first half of the pre-bounce points. This is the initial direction.\n"
           "2. Extend that line to the moment of the bounce.\n3. Compare it with where the ball was (taken from a smooth curve through "
           "all the pre-bounce points, so one noisy point cannot decide the answer).\n4. Divide the gap by its standard error to get z."),
    ("code", '''def swing_by_hand(points, bounce_index):
    pre = points[: bounce_index + 1]
    t = np.array([p["t"] for p in pre]); x = np.array([p["x"] for p in pre])
    half = max(3, len(t) // 2)
    line = np.polyfit(t[:half], x[:half], 1)                    # initial direction
    curve = np.polyfit(t, x, 2)                                 # smooth path
    deviation = np.polyval(curve, t[-1]) - np.polyval(line, t[-1])
    return deviation, line, curve, t, x

for name, pts in [("straight", straight), ("swing built in", swinging)]:
    dev, line, curve, t, x = swing_by_hand(pts, 15)
    m = trajectory.lateral_movement(pts, 15)
    assert abs(dev - m["swing"]["deviation"]) < 1e-6
    print(f"{name:15s} deviation {dev:6.1f} px, standard error {m['swing']['std_error']:.1f}, z = {m['swing']['z']:.1f} -> {m['swing']['label']}")

dev, line, curve, t, x = swing_by_hand(swinging, 15)
fig, ax = plt.subplots()
ax.plot(t, x, "o", color=INK, label="tracked points")
ax.plot(t, np.polyval(line, t), "--", color=GREEN, label="initial direction, extended")
ax.plot(t, np.polyval(curve, t), color=RED, label="smooth path")
ax.annotate("", xy=(t[-1], np.polyval(curve, t[-1])), xytext=(t[-1], np.polyval(line, t[-1])), arrowprops=dict(arrowstyle="<->", color=INK))
ax.text(t[-1], (np.polyval(curve, t[-1]) + np.polyval(line, t[-1])) / 2, f"  {dev:.0f} px", va="center")
ax.set_xlabel("time (s)"); ax.set_ylabel("sideways position (px)"); ax.set_title("Measuring swing (SYNTHETIC track)"); ax.legend(); plt.show()'''),
    ("md", "## 4. Seam\n\nFit one straight line before the bounce and one after. Their slopes are the sideways speed before and after. "
           "The change between them, divided by its standard error, is tested the same way."),
    ("code", '''for name, pts in [("straight", straight), ("seam built in", seaming)]:
    s = trajectory.lateral_movement(pts, 15)["seam"]
    print(f"{name:14s} sideways speed {s['velocity_before']:7.0f} -> {s['velocity_after']:7.0f} px/s, change {s['change']:7.0f} "
          f"+/- {s['std_error']:.0f}, z = {s['z']:.1f} -> {s['label']}")

few = trajectory.lateral_movement(straight[:4])
print("\\nWith four points:", few["swing"]["status"], "/", few["seam"]["status"])'''),
    ("md", "## 5. Does the test behave?\n\nTwo checks on 300 synthetic deliveries each. First, deliveries with no movement built in: how "
           "often does the test wrongly report swing? Second, deliveries with more and more swing built in: how often is it found?"),
    ("code", '''def detection_rate(swing_px, n=300, noise=1.5):
    found = 0
    for seed in range(n):
        m = trajectory.lateral_movement(sample_data.synthetic_track(seed=seed, noise=noise, swing=swing_px), 15)
        found += bool(m["swing"]["significant"])
    return found / n * 100

levels = [0, 4, 8, 12, 16, 24, 32]
rates = [detection_rate(s) for s in levels]
power = pd.DataFrame({"swing built in (px)": levels, "reported as swing (%)": rates}); display(power.round(1))

fig, ax = plt.subplots()
ax.plot(levels, rates, marker="o", color=INK)
ax.set_xlabel("swing built into the synthetic delivery (px)"); ax.set_ylabel("deliveries reported as swinging (%)")
ax.set_title("False alarms at zero swing, detection as swing grows (noise 1.5 px)"); ax.set_ylim(-2, 102); plt.show()
print(f"False-alarm rate with no swing: {rates[0]:.1f}%")'''),
    ("md", "## 6. Comparing deliveries and sessions\n\nMovement from one fixed camera can be compared between deliveries. Below, two "
           "synthetic 'sessions' of ten deliveries each, the second with more swing built in."),
    ("code", '''rows = []
for session, base in [("A", 6), ("B", 22)]:
    for i in range(10):
        pts = sample_data.synthetic_track(seed=100 * (session == "B") + i, noise=1.5, swing=base + i % 4)
        b = trajectory.detect_bounce(pts)
        m = trajectory.lateral_movement(pts, b["index"] if b["found"] else None)
        rows.append({"session": session, "delivery": i + 1, "deviation_px": m["swing"]["deviation"], "z": m["swing"]["z"],
                     "reported": m["swing"]["label"]})
moves = pd.DataFrame(rows)
moves.to_csv(EXPORTS / "swing_by_delivery.csv", index=False)
summary = moves.groupby("session").agg(mean_deviation_px=("deviation_px", "mean"), reported_as_swing=("reported", lambda s: (s != "Within tracking noise").sum()))
display(summary.round(1))

fig, ax = plt.subplots()
for session, colour in [("A", INK), ("B", RED)]:
    g = moves[moves["session"] == session]
    ax.scatter(g["delivery"], g["deviation_px"], color=colour, label=f"session {session}")
ax.set_xlabel("delivery"); ax.set_ylabel("swing deviation (px)"); ax.legend(); ax.set_title("Swing by delivery (SYNTHETIC)"); plt.show()
print(trajectory.lateral_movement(straight, 15)["warning"])'''),
] + closing(
    "- Swing is the gap between the ball's actual position at the bounce and its initial line; seam is the change in sideways speed across the bounce.\n"
    "- With no movement built in, the test reports swing in only a small percentage of synthetic deliveries; it finds nearly all deliveries once the built-in swing is several times the noise.\n"
    "- With too few points the result is 'insufficient' and nothing is reported.",
    "The method answers a narrow question well: did this ball move sideways across the image by more than the tracking error? It is good for comparing a bowler's deliveries filmed from one fixed position.",
    "- Values are in image pixels. Sideways movement across the image mixes true swing with perspective, so they are not centimetres of swing.\n"
    "- A camera behind the bowler sees sideways movement best; a side-on camera barely sees it.\n"
    "- The three-standard-error threshold is strict, so small real movement is reported as noise.\n"
    "- Rates above come from synthetic tracks with evenly spread noise. Real tracking errors are not that tidy.",
    "The Bowling Lab's Swing and seam tab lists each tracked delivery with these labels and values. `POST /api/video/track` runs "
    "`trajectory.detect_bounce` and `trajectory.lateral_movement` on the tracked points, and `GET /api/video/compare` puts two deliveries side by side.",
)

# ---------------------------------------------------------------------------------------------------------------

NB07 = header(
    "07 · Batting Performance Analytics",
    "Batting averages, strike rates, scoring patterns, records against pace and spin, and a wagon wheel, all from ball-by-ball data.",
) + [
    ("md", "## 1. Definitions\n\n"
           "$$\\text{batting average} = \\frac{\\text{runs}}{\\text{times out}}\\qquad\\text{strike rate} = \\frac{\\text{runs}}{\\text{balls faced}}\\times 100$$\n\n"
           "The average divides by dismissals, so a not-out innings adds runs without adding to the divisor. A batter who has never been "
           "out has no average. A wide is not a ball faced; a no-ball is."),
    ("code", '''from pitchvision import scoring, stats

balls = pd.read_csv(DATA / "balls.csv")
players = pd.read_csv(DATA / "players.csv")
ours = set(players["name"])
print(len(balls), "balls from", balls["match_id"].nunique(), "matches (SYNTHETIC)")
balls.head(3)'''),
    ("md", "## 2. From balls to innings\n\nThe scoring engine turns each innings' balls into a scorecard. We take the batting line for "
           "each of our players in each innings."),
    ("code", '''lines = scoring.lines_from_balls(balls.to_dict("records"))
batting = pd.DataFrame(lines["batting"])
batting = batting[batting["player"].isin(ours)]
batting[["match_id", "player", "runs", "balls", "fours", "sixes", "out", "how_out"]].head(8)'''),
    ("code", '''# Averages by hand with pandas.
g = batting.groupby("player")
table = pd.DataFrame({"innings": g.size(), "not_outs": g["out"].apply(lambda s: (~s).sum()), "runs": g["runs"].sum(),
                      "balls": g["balls"].sum(), "highest": g["runs"].max(), "fours": g["fours"].sum(), "sixes": g["sixes"].sum()})
table["dismissals"] = table["innings"] - table["not_outs"]
table["average"] = (table["runs"] / table["dismissals"]).where(table["dismissals"] > 0)     # undefined if never out
table["strike_rate"] = (table["runs"] / table["balls"] * 100).where(table["balls"] > 0)
table = table.sort_values("runs", ascending=False)

# The application uses stats.career_batting. The two must agree.
career = {r["player"]: r for r in stats.career_batting(lines["batting"])}
for name, row in table.iterrows():
    c = career[name]
    assert c["runs"] == row["runs"] and c["innings"] == row["innings"]
    assert (c["average"] is None and pd.isna(row["average"])) or abs(c["average"] - row["average"]) < 1e-9
table.round(1)'''),
    ("md", "## 3. How each innings went"),
    ("code", '''top = table.index[0]
scores = batting[batting["player"] == top]["runs"].tolist()
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
axes[0].bar(range(1, len(scores) + 1), scores, color=INK)
axes[0].axhline(np.mean(scores), color=RED, ls="--", label=f"runs per innings {np.mean(scores):.1f}")
axes[0].set_xlabel("innings"); axes[0].set_ylabel("runs"); axes[0].set_title(f"{top}: innings by innings (SYNTHETIC)"); axes[0].legend()
axes[1].hist(batting["runs"], bins=range(0, int(batting["runs"].max()) + 10, 5), color=GREEN)
axes[1].set_xlabel("runs in an innings"); axes[1].set_ylabel("innings"); axes[1].set_title("All our innings: most are short")
plt.show()
print(f"Median innings {batting['runs'].median():.0f} runs; mean {batting['runs'].mean():.1f}. The mean is pulled up by a few big scores.")'''),
    ("md", "## 4. How the runs were scored"),
    ("code", '''faced = balls[balls["striker"].isin(ours) & (balls["wides"] == 0)]
mix = faced.groupby("striker")["runs_bat"].value_counts(normalize=True).unstack(fill_value=0) * 100
mix = mix.reindex(table.index[:6])
mix.plot(kind="bar", stacked=True, figsize=(10, 4.2), colormap="YlGn", edgecolor="white")
plt.ylabel("share of balls faced (%)"); plt.title("Runs off each ball faced (SYNTHETIC)"); plt.legend(title="runs", bbox_to_anchor=(1, 1)); plt.xticks(rotation=30, ha="right"); plt.show()

boundary = (table["fours"] * 4 + table["sixes"] * 6) / table["runs"] * 100
print("Share of runs in boundaries:"); print(boundary.head(6).round(0).to_string())'''),
    ("md", "## 5. Against pace and spin, and by length\n\nA split is only interpreted when there are enough balls behind it. With a dozen "
           "balls, one boundary changes the strike rate by more than 30 points."),
    ("code", '''rows = []
for name in table.index[:8]:
    sp = stats.batting_splits(balls.to_dict("records"), name)
    for kind in ("pace", "spin"):
        d = sp["bowl_type"].get(kind)
        if d:
            rows.append({"player": name, "against": kind, "balls": d["balls"], "runs": d["runs"], "outs": d["dismissals"],
                         "strike_rate": d["strike_rate"], "average": d["average"]})
splits = pd.DataFrame(rows)
pivot = splits.pivot(index="player", columns="against", values="strike_rate").reindex(table.index[:8])
pivot.plot(kind="bar", color=[INK, GREEN], figsize=(10, 4)); plt.ylabel("strike rate"); plt.title("Strike rate against pace and spin (SYNTHETIC)")
plt.xticks(rotation=30, ha="right"); plt.show()
splits.round(1)'''),
    ("code", '''sp = stats.batting_splits(balls.to_dict("records"), top)
by_length = pd.DataFrame(sp["length"]).T.reindex(["yorker", "full", "good", "short", "bouncer"]).dropna(how="all")
print(top, "by length of delivery:")
display(by_length[["balls", "runs", "dismissals", "strike_rate", "dot_pct"]].astype(float).round(1))
by_shot = pd.DataFrame(sp["shot_type"]).T.sort_values("runs", ascending=False)
print(top, "by shot played:"); by_shot[["balls", "runs", "dismissals", "strike_rate"]].astype(float).round(1)'''),
    ("md", "## 6. Wagon wheel\n\nEach scoring shot has an angle. 0 degrees is straight back past the bowler, and angles grow clockwise "
           "toward the off side, so 90 is square on the off side and 270 square on the leg side. The ground is split into eight 45-degree zones."),
    ("code", '''shots = balls[(balls["striker"] == top) & balls["shot_angle"].notna()]
wheel = stats.wagon_wheel(shots.to_dict("records"))

fig = plt.figure(figsize=(6.5, 6.5)); ax = fig.add_subplot(projection="polar")
ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)          # 0 at the top, clockwise
reach = {1: 0.42, 2: 0.62, 3: 0.78, 4: 1.0, 6: 1.0}
for s in wheel["shots"]:
    ax.plot([np.radians(s["angle"])] * 2, [0, reach.get(s["runs"], 0.3)], color=YELLOW if s["runs"] == 6 else RED if s["runs"] == 4 else INK,
            lw=2 if s["runs"] >= 4 else 1, alpha=0.8)
ax.set_xticks(np.radians(np.arange(22.5, 360, 45)))
ax.set_xticklabels([f"{z['zone'].replace('_', ' ')}\\n{z['runs']}" for z in wheel["zones"]], fontsize=9)
ax.set_yticks([]); ax.set_ylim(0, 1.05); ax.set_title(f"{top}: {wheel['total_runs']} runs plotted (SYNTHETIC). Off side on the right.", pad=18)
plt.show()
print(f"Off side {wheel['off_side_pct']:.0f}%, leg side {wheel['leg_side_pct']:.0f}%. Strongest zones: {', '.join(wheel['strong_zones'])}")
print("Shots with no recorded direction:", wheel["unplotted"])
table.round(2).to_csv(EXPORTS / "batting_summary.csv")'''),
] + closing(
    "- Averages and strike rates built with pandas match `stats.career_batting` for every player.\n"
    "- Most innings are short and a few are long, so runs per innings sits above the median.\n"
    "- Splits by bowling type, length and shot come straight from the ball records, and each carries its ball count.",
    "An average over six or seven innings is a rough guide. One more not-out or one more duck moves it a long way. Look at the ball counts before reading anything into a split.",
    "- Averages mean little before about ten dismissals.\n- Strike rate ignores the match situation: a slow innings can be the right one.\n"
    "- Shot type and direction depend on the scorer's judgement.\n- Synthetic data: the patterns reflect how the generator works, not real batters.",
    "Team Hub player profiles and leaderboards use `stats.career_batting` on lines produced by the scoring engine. The Batting Lab's Shot "
    "selection tab calls `stats.batting_splits` through `GET /api/stats/splits`, and the Wagon wheel tab calls `stats.wagon_wheel` through `GET /api/stats/wagon`.",
)

# ---------------------------------------------------------------------------------------------------------------

NB08 = header(
    "08 · Fielding Analytics",
    "Catching percentages, run-outs and ground fielding for each player, with a look at how far small samples can be trusted.",
) + [
    ("md", "## 1. What is recorded\n\nFielding is recorded as events, each naming a player and what happened. Recording the misses matters "
           "as much as the successes, because a percentage needs both.\n\n"
           "| Event | Meaning |\n|---|---|\n| catch / drop | a catch held or put down |\n| run_out / direct_hit / missed_run_out | a run-out "
           "effected (a direct hit is one made by a throw that hit the stumps), or a chance missed |\n| stumping / missed_stumping | wicket-keeper only |\n"
           "| clean_stop / misfield | ground fielding |\n\n"
           "$$\\text{catch \\%} = \\frac{\\text{catches}}{\\text{catches}+\\text{drops}}\\times 100\\qquad"
           "\\text{ground fielding \\%} = \\frac{\\text{clean stops}}{\\text{clean stops}+\\text{misfields}}\\times 100$$"),
    ("code", '''from pitchvision import stats

events = pd.read_csv(DATA / "fielding.csv", parse_dates=["date"])
print(len(events), "fielding events (SYNTHETIC)")
print(events["kind"].value_counts().to_string())

# Rows with a missing or unknown kind cannot be counted. Show how many there are, then drop them.
known = events[events["kind"].isin(stats.FIELDING_EVENTS)]
print("\\nRows dropped for an unknown event type:", len(events) - len(known))'''),
    ("md", "## 2. Player table"),
    ("code", '''counts = known.pivot_table(index="player", columns="kind", values="count", aggfunc="sum", fill_value=0)
for col in stats.FIELDING_EVENTS:
    if col not in counts: counts[col] = 0
by_hand = pd.DataFrame({
    "catches": counts["catch"], "dropped": counts["drop"],
    "catch_pct": (counts["catch"] / (counts["catch"] + counts["drop"]) * 100).where((counts["catch"] + counts["drop"]) > 0),
    "run_outs": counts["run_out"] + counts["direct_hit"], "direct_hits": counts["direct_hit"],
    "ground_pct": (counts["clean_stop"] / (counts["clean_stop"] + counts["misfield"]) * 100).where((counts["clean_stop"] + counts["misfield"]) > 0),
})

career = pd.DataFrame(stats.career_fielding(known.to_dict("records"))).set_index("player")
for name in by_hand.index:                                       # the shared module must give the same numbers
    assert career.loc[name, "catch"] == by_hand.loc[name, "catches"]
    assert abs(career.loc[name, "catch_pct"] - by_hand.loc[name, "catch_pct"]) < 1e-9
by_hand.sort_values("catches", ascending=False).round(1)'''),
    ("md", "## 3. Catching"),
    ("code", '''c = career.sort_values("catch_pct", ascending=True)
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(c.index, c["catch"], color=GREEN, label="caught")
ax.barh(c.index, c["drop"], left=c["catch"], color=RED, label="dropped")
for i, (name, row) in enumerate(c.iterrows()):
    ax.text(row["catch_chances"] + 0.15, i, f"{row['catch_pct']:.0f}%", va="center", fontsize=9)
ax.set_xlabel("catching chances"); ax.set_title("Catches held and dropped (SYNTHETIC)"); ax.legend(loc="lower right"); plt.show()'''),
    ("md", "## 4. How much can a catch percentage be trusted?\n\nA fielder who has held 3 of 4 has a 75% record, but four chances say very "
           "little. The Wilson interval gives a range the true rate plausibly lies in:\n\n"
           "$$\\frac{\\hat p + \\frac{z^2}{2n} \\pm z\\sqrt{\\frac{\\hat p(1-\\hat p)}{n} + \\frac{z^2}{4n^2}}}{1+\\frac{z^2}{n}},\\qquad z = 1.96$$\n\n"
           "Wide ranges that overlap mean the data cannot separate two fielders yet."),
    ("code", '''def wilson(successes, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half) * 100, (centre + half) * 100

print("3 of 4 held  ->", [round(v) for v in wilson(3, 4)], "%")
print("30 of 40 held ->", [round(v) for v in wilson(30, 40)], "%")

c = career[career["catch_chances"] > 0].sort_values("catch_pct")
lows, highs = zip(*[wilson(r["catch"], r["catch_chances"]) for _, r in c.iterrows()])
fig, ax = plt.subplots(figsize=(9, 5))
ax.hlines(range(len(c)), lows, highs, color=INK, lw=2)
ax.plot(c["catch_pct"], range(len(c)), "o", color=YELLOW, mec=INK, ms=8)
ax.set_yticks(range(len(c))); ax.set_yticklabels([f"{n} ({int(r['catch_chances'])})" for n, r in c.iterrows()])
ax.set_xlabel("catch success (%) with 95% range. Chances in brackets."); ax.set_xlim(0, 100)
ax.set_title("The ranges overlap: few fielders can be told apart yet (SYNTHETIC)"); plt.show()'''),
    ("md", "## 5. Run-outs and ground fielding"),
    ("code", '''r = career[career["run_out_chances"] > 0].sort_values("run_outs_total", ascending=False)
display(r[["run_out", "direct_hit", "missed_run_out", "run_outs_total", "run_out_pct"]].round(0).head(8))

g = career[career["ground_chances"] >= 5].sort_values("ground_pct")
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.barh(g.index, g["ground_pct"], color=INK)
ax.axvline(g["ground_pct"].mean(), color=RED, ls="--", label=f"squad mean {g['ground_pct'].mean():.0f}%")
ax.set_xlabel("clean stops as a share of ground-fielding chances (%)"); ax.set_xlim(0, 100); ax.legend()
ax.set_title("Ground fielding, players with 5 or more chances (SYNTHETIC)"); plt.show()'''),
    ("md", "## 6. The team by match"),
    ("code", '''by_match = known.pivot_table(index="match_id", columns="kind", values="count", aggfunc="sum", fill_value=0)
by_match["catch_pct"] = by_match["catch"] / (by_match["catch"] + by_match["drop"]) * 100
fig, ax = plt.subplots()
ax.plot(by_match.index, by_match["catch_pct"], marker="o", color=INK)
ax.set_xlabel("match"); ax.set_ylabel("team catch success (%)"); ax.set_ylim(0, 100); ax.set_title("Team catching by match (SYNTHETIC)"); plt.show()
team_c, team_d = int(counts["catch"].sum()), int(counts["drop"].sum())
print(f"Season: {team_c} caught, {team_d} dropped, {team_c / (team_c + team_d) * 100:.0f}% (95% range {wilson(team_c, team_c + team_d)[0]:.0f} to {wilson(team_c, team_c + team_d)[1]:.0f}%)")
career.drop(columns=["name"], errors="ignore").round(1).to_csv(EXPORTS / "fielding_summary.csv")'''),
] + closing(
    "- Catch, run-out and ground-fielding percentages built with pandas match `stats.career_fielding`.\n"
    "- With a handful of chances each, most fielders' 95% ranges overlap, so the table cannot rank them reliably.\n"
    "- The team's season figure rests on far more chances and has a much narrower range.",
    "Fielding percentages become useful at team level first. For individuals, use them to start a conversation and to pick who needs more catching practice, and keep recording so the ranges narrow.",
    "- A chance is a judgement call: was that a dropped catch or a half-chance?\n- The record does not capture difficulty. A slip catch and a skier both count as one.\n"
    "- Misses are under-recorded unless someone is assigned to note them.\n- All figures shown come from synthetic data.",
    "The Fielding Lab's Performance tracker saves each record through `POST /api/fielding/events` and shows this table from "
    "`stats.career_fielding`. Catching and fielding leaderboards in the Team Hub apply a minimum of three chances before ranking a catch percentage.",
)

NOTEBOOKS = {
    "05_bowling_accuracy_analysis.ipynb": NB05,
    "06_swing_seam_analysis.ipynb": NB06,
    "07_batting_analysis.ipynb": NB07,
    "08_fielding_analysis.ipynb": NB08,
}
