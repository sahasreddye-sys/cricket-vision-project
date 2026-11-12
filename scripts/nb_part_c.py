"""Notebooks 09-12: team and match analytics, machine learning, AI coach, full pipeline."""
from nb_common import closing, header

NB09 = header(
    "09 · Team and Match Analytics",
    "Scorecards, run rates, partnerships, bowling economy, player comparisons and an explained team selection, all from ball-by-ball data.",
) + [
    ("md", "## 1. Load the matches\n\nThe scoring engine follows the Laws of Cricket: an over is six legal balls, wides and no-balls are "
           "not legal balls, byes and leg-byes are not charged to the bowler, and a bowler is credited only with the wickets that are his."),
    ("code", '''from pitchvision import scoring, stats, selection

balls = pd.read_csv(DATA / "balls.csv")
matches = pd.read_csv(DATA / "matches.csv")
players = pd.read_csv(DATA / "players.csv")
ours = set(players["name"])
matches[["match_id", "date", "opponent", "batted_first", "our_score", "their_score", "result"]]'''),
    ("md", "## 2. A scorecard\n\nWe score match 1, first innings, ball by ball."),
    ("code", '''def innings(match_id, number):
    rows = balls[(balls["match_id"] == match_id) & (balls["innings"] == number)].to_dict("records")
    return scoring.score_innings([scoring.flat_to_ball(r) for r in rows], max_overs=20)

card = innings(1, 1)
print(f"{card['total']}/{card['wickets']} in {card['overs']} overs, run rate {card['run_rate']:.2f}")
print("Extras:", card["extras"])
pd.DataFrame(card["batting"])[["player", "runs", "balls", "fours", "sixes", "strike_rate", "how_out", "bowler"]].round(1)'''),
    ("code", '''# The scorecard must add up. Every run is either off a bat or an extra, and every run is either charged to a bowler or is a bye / leg-bye.
bat_runs = sum(b["runs"] for b in card["batting"])
bowl_runs = sum(b["runs"] for b in card["bowling"])
assert bat_runs + card["extras"]["total"] == card["total"]
assert bowl_runs + card["extras"]["byes"] + card["extras"]["leg_byes"] + card["extras"]["penalty"] == card["total"]
assert sum(b["legal_balls"] for b in card["bowling"]) == card["legal_balls"]
print("Batters' runs + extras = total, and bowlers' runs + byes + leg-byes = total.")
pd.DataFrame(card["bowling"])[["player", "overs", "maidens", "runs", "wickets", "wides", "no_balls", "economy"]].round(2)'''),
    ("md", "## 3. Run rate and required run rate\n\nThe run rate is runs divided by overs bowled, where overs are legal balls divided by six. "
           "The required rate is the runs still needed divided by the overs left."),
    ("code", '''o = pd.DataFrame(card["over_by_over"])
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
axes[0].bar(o["over"], o["runs"], color=[RED if w else INK for w in o["wickets"]])
axes[0].set_xlabel("over"); axes[0].set_ylabel("runs"); axes[0].set_title("Runs in each over (red: a wicket fell)")
axes[1].plot(o["over"], o["total"], marker="o", color=INK); axes[1].set_xlabel("over"); axes[1].set_ylabel("score"); axes[1].set_title("Score by over")
plt.show()

chase = innings(1, 2); target = card["total"] + 1
second = pd.DataFrame(chase["over_by_over"])
second["balls_left"] = 120 - second["over"] * 6
second["required_rate"] = [scoring.required_run_rate(target, t, b) for t, b in zip(second["total"], second["balls_left"])]
second["current_rate"] = second["total"] / second["over"]
fig, ax = plt.subplots()
ax.plot(second["over"], second["required_rate"], color=RED, label="required rate"); ax.plot(second["over"], second["current_rate"], color=INK, label="current rate")
ax.set_xlabel("over"); ax.set_ylabel("runs per over"); ax.set_title(f"The chase of {target}: required against current rate"); ax.legend(); plt.show()
print(scoring.match_result(card, chase, "Northfield", "Us") if card["batting"][0]["player"].startswith("Northfield") else "")'''),
    ("md", "## 4. Partnerships"),
    ("code", '''p = pd.DataFrame(card["partnerships"])
p["pair"] = p["contrib"].apply(lambda c: " & ".join(f"{x['player'].split()[-1]} {x['runs']}" for x in c))
fig, ax = plt.subplots(figsize=(10, 4))
ax.barh([f"Wkt {w}" for w in p["wicket"]][::-1], p["runs"][::-1], color=INK)
for i, (r, t) in enumerate(zip(p["runs"][::-1], p["pair"][::-1])): ax.text(r + 0.5, i, t, va="center", fontsize=9)
ax.set_xlabel("partnership runs (includes extras while together)"); ax.set_title("Partnerships, first innings of match 1 (SYNTHETIC)"); plt.show()'''),
    ("md", "## 5. Every match, every player"),
    ("code", '''lines = scoring.lines_from_balls(balls.to_dict("records"))
bat = [r for r in lines["batting"] if r["player"] in ours]
bowl = [r for r in lines["bowling"] if r["player"] in ours]
batting = pd.DataFrame(stats.career_batting(bat)).set_index("player")
bowling = pd.DataFrame(stats.career_bowling(bowl)).set_index("player")

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
b = batting.sort_values("runs").tail(8); axes[0].barh(b.index, b["runs"], color=INK); axes[0].set_title("Runs (SYNTHETIC)")
e = bowling[bowling["legal_balls"] >= 30].sort_values("economy", ascending=False); axes[1].barh(e.index, e["economy"], color=GREEN)
axes[1].axvline(bowling["runs"].sum() * 6 / bowling["legal_balls"].sum(), color=RED, ls="--", label="team economy"); axes[1].legend()
axes[1].set_title("Economy rate, 30+ balls bowled (lower is better)"); plt.show()
bowling[["overs", "runs", "wickets", "average", "economy", "strike_rate", "best"]].sort_values("wickets", ascending=False).round(2)'''),
    ("md", "## 6. Comparing two players"),
    ("code", '''a, b = "Arun Mehta", "Farhan Ali"
cmp = pd.DataFrame({a: batting.loc[a, ["innings", "runs", "average", "strike_rate", "highest", "fours", "sixes"]],
                    b: batting.loc[b, ["innings", "runs", "average", "strike_rate", "highest", "fours", "sixes"]]})
display(cmp)
print(f"{b} also bowls: {bowling.loc[b, 'wickets']} wickets at an economy of {bowling.loc[b, 'economy']:.2f}.")
print("With this few innings, differences of a few runs in the average are within chance.")'''),
    ("md", "## 7. Team selection\n\nThe selection assistant never produces a rating. It picks the keeper, then the bowling attack, then "
           "the best remaining batters, and writes the figure behind each choice. Minimum samples keep one good innings from deciding a place."),
    ("code", '''squad = []
for _, pl in players.iterrows():
    squad.append({"id": pl["name"], "name": pl["name"], "role": pl["role"], "bowl_style": pl["bowl_style"] if isinstance(pl["bowl_style"], str) else None,
                  "bat": batting.loc[pl["name"]].to_dict() if pl["name"] in batting.index else None,
                  "bowl": bowling.loc[pl["name"]].to_dict() if pl["name"] in bowling.index else None})
available = [p for p in squad if p["name"] not in ("Noah Reid", "Omar Aziz")]        # two players unavailable
pick = selection.select_xi(available, match_overs=20)
for r in pick["reasons"]:
    print(f"- {r['player']} ({r['role']}): {r['reason']}")
print("\\nLeft out:", [x["player"] for x in pick["left_out"]])
a = pick["analysis"]
print(f"\\nBatting depth {a['batting_depth']}, bowling options {a['bowling_options']} ({len(a['pace_options'])} pace, {len(a['spin_options'])} spin), overs covered {a['overs_covered']} of 20")
for w in a["warnings"]: print("Warning:", w)
print("\\nAssumptions:"); [print(" -", x) for x in pick["assumptions"]]'''),
    ("code", '''# Compare the suggested side with an alternative that swaps one bowler for a batter.
names = [p["name"] for p in pick["xi"]]
alt = [p for p in available if p["name"] in names]
bench = [p for p in available if p["name"] not in names]
alt[-1] = bench[0]
cmp = selection.compare_xis([p for p in available if p["name"] in names], alt)
pd.DataFrame(cmp["differences"]).T
matches_summary = pd.DataFrame({"match": matches["match_id"], "result": matches["result"], "ours": matches["our_score"], "theirs": matches["their_score"]})
matches_summary.to_csv(EXPORTS / "match_results.csv", index=False)
bowling.round(2).to_csv(EXPORTS / "bowling_by_player.csv")'''),
] + closing(
    "- The scoring engine's scorecards add up in two ways: batters' runs plus extras equal the total, and bowlers' runs plus byes and leg-byes equal the total.\n"
    "- Partnerships, over-by-over runs and the chase can all be rebuilt from the balls.\n"
    "- The selection assistant lists the number behind every pick and warns when the side lacks a keeper, a spinner or five bowlers.",
    "Selection from season statistics is a starting point. With six or seven innings each, many players cannot be separated by their numbers, and the coach's knowledge of form, fitness and the opposition should decide.",
    "- Averages and economy rates over a few matches are noisy.\n- Selection looks only at batting and bowling records, not fielding, fitness or the opposition.\n"
    "- Partnership runs include extras, so they can differ from the sum of the two batters' scores.\n- The synthetic matches are generated, so none of these players' numbers are real.",
    "The Match Center's scorecards, partnerships, over strips and chase panel come from `scoring.score_innings`, the same function used here. "
    "The Team Hub's Selection assistant calls `selection.select_xi` and `compare_xis` through `POST /api/team/select` and `/api/team/compare`.",
)

# ---------------------------------------------------------------------------------------------------------------

NB10 = header(
    "10 · Machine Learning and Cricket Predictions",
    "Clean the data, explore it, build features, train models, test them honestly, and explain a prediction. The question is whether the models beat a plain baseline.",
    "numpy, pandas, matplotlib, scikit-learn",
) + [
    ("md", "## 1. The rule for this notebook\n\nA model is only worth using if it beats a simple baseline on data it was not trained on. "
           "Every score below is measured with cross-validation or on a held-out test set, and each model is shown next to a baseline that "
           "always predicts the most common outcome.\n\nAll of the data is synthetic. A score here shows the code works. It tells you nothing "
           "about how well the same model would predict real cricket."),
    ("code", '''from pitchvision import ml
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, confusion_matrix, ConfusionMatrixDisplay
from sklearn.inspection import permutation_importance, PartialDependenceDisplay

balls = pd.read_csv(DATA / "balls.csv")
print(len(balls), "rows")'''),
    ("md", "## 2. Cleaning\n\nThe question: given where a delivery pitched, who bowled it and when, will the batter score off it?\n\n"
           "Wides and no-balls are removed because the batter did not get a normal chance to score. Rows with no pitching point are removed "
           "because the main features need one. We print how many rows each step removes."),
    ("code", '''df, features, cleaning = ml.delivery_features(balls.to_dict("records"))
print(cleaning)
print("Missing values left in the model columns:", int(df[features].isna().sum().sum()))
df[features + ["target"]].describe().round(2)'''),
    ("md", "## 3. Exploring the data\n\nThe target is 1 when the ball was a dot or took a wicket, and 0 when the batter scored."),
    ("code", '''print(f"Dot or wicket on {df['target'].mean() * 100:.0f}% of balls ({len(df)} balls)")
df["length"] = df["y"].apply(__import__("pitchvision.pitchmap", fromlist=["x"]).classify_length)
by_len = df.groupby("length")["target"].agg(["mean", "count"]).reindex(["yorker", "full", "good", "short", "bouncer"]).dropna()
by_type = df.groupby("bowl_type")["target"].agg(["mean", "count"])
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].bar(by_len.index, by_len["mean"] * 100, color=INK); axes[0].set_title("Dot or wicket (%) by length")
axes[1].bar(by_type.index, by_type["mean"] * 100, color=GREEN); axes[1].set_title("By bowling type")
axes[2].hist([df.loc[df.target == 1, "abs_x"], df.loc[df.target == 0, "abs_x"]], bins=12, label=["dot/wicket", "scored"], color=[INK, YELLOW])
axes[2].set_title("Distance from the stumps line (m)"); axes[2].legend(); plt.show()
print(by_len.round(2))'''),
    ("md", "## 4. Features\n\n| Feature | Meaning |\n|---|---|\n| x, y | where the ball pitched |\n| abs_x | how far from the stumps line, either side |\n"
           "| is_spin | 1 for a spinner |\n| over | the over number |\n\nabs_x is built from x because the distance from the stumps matters more than the side. "
           "A linear model cannot make that fold on its own."),
    ("code", '''X, y = df[features].to_numpy(float), df["target"].to_numpy(int)
print("Features:", features); print("Baseline accuracy (always predict the commoner outcome):", round(max(y.mean(), 1 - y.mean()), 3))'''),
    ("md", "## 5. Models and cross-validation\n\nFive-fold cross-validation splits the data into five parts, trains on four and tests on the fifth, "
           "and repeats so every part is tested once. The spread across folds says how stable the score is. ROC-AUC measures how well the model "
           "ranks balls: 0.5 is no better than guessing and 1.0 is perfect."),
    ("code", '''cv = StratifiedKFold(5, shuffle=True, random_state=0)
models = {"baseline": DummyClassifier(strategy="most_frequent"),
          "logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
          "random forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=5, random_state=0),
          "gradient boosting": GradientBoostingClassifier(random_state=0)}
rows = []
for name, m in models.items():
    auc = cross_val_score(m, X, y, cv=cv, scoring="roc_auc"); acc = cross_val_score(m, X, y, cv=cv, scoring="accuracy")
    rows.append({"model": name, "accuracy": acc.mean(), "accuracy sd": acc.std(), "ROC-AUC": auc.mean(), "ROC-AUC sd": auc.std()})
results = pd.DataFrame(rows).set_index("model").round(3); display(results)

fig, ax = plt.subplots()
ax.barh(results.index, results["ROC-AUC"], xerr=2 * results["ROC-AUC sd"], color=[RED, INK, GREEN, YELLOW])
ax.axvline(0.5, color="black", ls="--"); ax.set_xlim(0.4, 0.8); ax.set_xlabel("ROC-AUC, with a 2 standard deviation bar. The dashed line is chance.")
ax.set_title("Models against the baseline (SYNTHETIC data)"); plt.show()'''),
    ("md", "## 6. A held-out test set\n\nCross-validation chose between models, so a final check goes to data the choosing never touched."),
    ("code", '''Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=1, stratify=y)
best = RandomForestClassifier(n_estimators=200, min_samples_leaf=5, random_state=0).fit(Xtr, ytr)
proba = best.predict_proba(Xte)[:, 1]
print(f"Test ROC-AUC {roc_auc_score(yte, proba):.3f}, test accuracy {(best.predict(Xte) == yte).mean():.3f} on {len(yte)} balls")
ConfusionMatrixDisplay(confusion_matrix(yte, best.predict(Xte)), display_labels=["scored", "dot/wicket"]).plot(cmap="Greys"); plt.grid(False); plt.show()'''),
    ("md", "## 7. Feature importance\n\nPermutation importance shuffles one feature at a time on the test set and measures how much the score drops. "
           "A large drop means the model relies on that feature."),
    ("code", '''imp = permutation_importance(best, Xte, yte, n_repeats=20, random_state=0, scoring="roc_auc")
order = np.argsort(imp.importances_mean)
fig, ax = plt.subplots()
ax.barh(np.array(features)[order], imp.importances_mean[order], xerr=imp.importances_std[order], color=INK)
ax.set_xlabel("drop in ROC-AUC when the feature is shuffled"); ax.set_title("What the forest relies on"); plt.show()'''),
    ("md", "## 8. Explaining one prediction\n\nPartial dependence shows how the predicted chance changes as one feature moves with the others held at "
           "their typical values. For a single ball we can also print the inputs next to the prediction."),
    ("code", '''PartialDependenceDisplay.from_estimator(best, Xte, [features.index("y"), features.index("abs_x")], feature_names=features, line_kw={"color": INK})
plt.suptitle("Chance of a dot or wicket as the ball moves"); plt.tight_layout(); plt.show()

result = ml.train_dot_ball_model(balls.to_dict("records"), synthetic=True)
for case in [(0.15, 7.0, "pace"), (0.15, 1.0, "pace"), (0.9, 7.0, "pace"), (0.15, 5.0, "spin")]:
    e = ml.explain_delivery(result, case[0], case[1], case[2])
    print(e["explanation"])
print("\\n" + result["conclusion"]); print(result["caveat"])'''),
    ("md", "## 9. A second question: can a batter's next score be predicted?\n\nThe features are the average of the batter's last three scores and "
           "their career average before that innings. The baseline predicts the career average. The test uses time-ordered splits so the model never "
           "sees the future."),
    ("code", '''from pitchvision import scoring
lines = scoring.lines_from_balls(balls.to_dict("records"))
bat = pd.DataFrame([r for r in lines["batting"] if not r["player"].split()[0] in ("Northfield", "Riverside", "Hilltop", "Eastbrook")])
forecast = ml.batting_forecast(bat.to_dict("records"))
print(forecast.get("status"), "-", forecast.get("reason") or forecast["conclusion"])
if forecast["status"] == "ok":
    print(f"Model error {forecast['mae_model']:.2f} runs, career-average baseline {forecast['mae_baseline']:.2f} runs, over {forecast['rows']} innings")'''),
    ("md", "## 10. Trends\n\nA trend is called up or down only when the 95% range for its slope excludes zero."),
    ("code", '''speeds = pd.read_csv(DATA / "speeds.csv", parse_dates=["date"]); speeds = speeds[speeds["source"] == "stopwatch"].dropna(subset=["kmh"])
rows = []
for name, g in speeds.sort_values("date").groupby("player"):
    t = ml.performance_trend(g["kmh"].tolist(), min_points=5)
    if t["status"] == "ok": rows.append({"player": name, "readings": t["n"], "slope": t["slope"], "low": t["ci_low"], "high": t["ci_high"], "direction": t["direction"]})
trend = pd.DataFrame(rows).set_index("player").round(2); display(trend)
print(trend["direction"].value_counts().to_string())

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.errorbar(trend["slope"], range(len(trend)), xerr=[trend["slope"] - trend["low"], trend["high"] - trend["slope"]], fmt="o", color=INK, ecolor=INK)
ax.axvline(0, color=RED, ls="--"); ax.set_yticks(range(len(trend))); ax.set_yticklabels(trend.index)
ax.set_xlabel("change in speed per reading (km/h), with 95% range"); ax.set_title("Speed trends (SYNTHETIC). A range crossing zero is no clear trend."); plt.show()
results.to_csv(EXPORTS / "ml_model_scores.csv")'''),
    ("md", "## 11. Grouping deliveries without labels\n\nK-means groups deliveries by where they pitched. It has no right answer to be scored against, so the "
           "only claim is descriptive: these are the typical landing areas."),
    ("code", '''deliveries = pd.read_csv(DATA / "deliveries.csv").dropna(subset=["x", "y"])
cl = ml.cluster_deliveries(deliveries.to_dict("records"), k=4)
cdf = pd.DataFrame(cl["clusters"]); display(cdf.round(2))
fig, ax = plt.subplots(figsize=(4.8, 7))
ax.scatter(deliveries["x"], deliveries["y"], c=cl["labels"], cmap="viridis", s=8, alpha=0.6)
ax.scatter(cdf["x"], cdf["y"], marker="X", s=200, color=RED, edgecolor="white")
ax.set_xlabel("across (m)"); ax.set_ylabel("from the stumps (m)"); ax.set_title("Four typical landing areas (SYNTHETIC)"); plt.show()'''),
] + closing(
    "- Every model is shown next to a baseline, and every score comes from cross-validation or held-out data.\n"
    "- Where a ball pitched predicts whether it is scored off only a little better than chance, which is what the generator built in.\n"
    "- Recent form does not improve on a batter's career average in the forecast test, and most speed trends have a range that includes zero.",
    "On a school team's data the honest conclusion is usually that the models add little. That is a useful result: it says where not to spend effort.",
    "- Synthetic data means a score proves nothing about real cricket.\n- A season of a school team is a few thousand balls from a few players, which is small for machine learning.\n"
    "- Balls are not independent: the same batter and bowler appear again and again, so cross-validation scores are somewhat optimistic.\n"
    "- Features exclude what matters most: pace, swing, the batter's skill and the match situation.",
    "`GET /api/ml/dot-ball-model` trains the same model on the opposition's balls in the database and returns the scores, baseline and feature importance. "
    "`ml.performance_trend` supplies the trend wording in the Progress tracker.",
)

# ---------------------------------------------------------------------------------------------------------------

NB11 = header(
    "11 · AI Cricket Coach",
    "A coach that answers questions and recommends practice from stored statistics. It works offline with rules, and can use a language model to phrase the answer.",
    "numpy, pandas, matplotlib (anthropic is optional)",
) + [
    ("md", "## 1. How it works\n\n1. Ingest: build a table of statistics for each player from the matches, sessions and readings.\n"
           "2. Retrieve: pick the figures that bear on the question.\n3. Answer: write the answer from those figures, with the evidence listed.\n"
           "4. Optionally rephrase the answer with a language model that is given only the retrieved figures.\n\n"
           "The rule-based path is the default. It needs no key and no internet, and every number in its answer can be traced to a row of data."),
    ("code", '''from pitchvision import coach, scoring, stats, pitchmap

balls = pd.read_csv(DATA / "balls.csv"); players = pd.read_csv(DATA / "players.csv")
speeds = pd.read_csv(DATA / "speeds.csv"); deliveries = pd.read_csv(DATA / "deliveries.csv"); fielding = pd.read_csv(DATA / "fielding.csv")
ours = set(players["name"])

lines = scoring.lines_from_balls(balls.to_dict("records"))
batting = [r for r in stats.career_batting([l for l in lines["batting"] if l["player"] in ours])]
bowling = [r for r in stats.career_bowling([l for l in lines["bowling"] if l["player"] in ours])]
for r in batting + bowling: r["name"] = r["player"]
fielding_rows = stats.career_fielding(fielding.to_dict("records"))

accuracy = {}
for name, g in deliveries.dropna(subset=["x", "y"]).groupby("player"):
    ty = 5.2 if g["bowl_type"].iloc[0] == "spin" else 7.0
    accuracy[name] = pitchmap.accuracy(g.to_dict("records"), 0.2, ty)
speed_history = {n: g.sort_values("date").dropna(subset=["kmh"])[["date", "kmh", "source"]].to_dict("records") for n, g in speeds.groupby("player")}
splits = {n: stats.batting_splits(balls.to_dict("records"), n) for n in ours}

ctx = {"players": [{"id": r["name"], "name": r["name"], "role": r["role"], "bowl_style": r["bowl_style"]} for _, r in players.iterrows()],
       "batting": batting, "bowling": bowling, "fielding": fielding_rows, "speeds": speed_history, "accuracy": accuracy, "splits": splits, "me": "Imran Khan"}
print("Statistics loaded for", len(ctx["players"]), "players (SYNTHETIC). 'me' is set to Imran Khan.")'''),
    ("md", "## 2. Summaries"),
    ("code", '''eco = pd.DataFrame(bowling).set_index("name")[["overs", "wickets", "economy", "average"]].round(2).sort_values("economy")
print("Team economy:", round(sum(b["runs"] for b in bowling) * 6 / sum(b["legal_balls"] for b in bowling), 2))
eco.head(6)'''),
    ("md", "## 3. Questions and answers\n\nEach answer states the data behind it. When the data is too thin the answer says so and names what to record."),
    ("code", '''for q in coach.SUGGESTED_QUESTIONS:
    r = coach.answer(q, ctx)
    print("Q:", q); print("A:", r["answer"])
    for e in r["evidence"][:3]: print("    ", e)
    print()'''),
    ("code", '''# Check one answer against the table by hand: the best economy among bowlers with at least 30 balls.
best = min((b for b in bowling if b["legal_balls"] >= 30), key=lambda b: b["economy"])
reply = coach.answer("Which of our bowlers has the best economy?", ctx)
assert best["name"] in reply["answer"] and f"{best['economy']:.2f}" in reply["answer"]
print("Verified against the table:", best["name"], round(best["economy"], 2))

# With no data the coach says so and invents nothing.
empty = {"players": [{"id": 1, "name": "Sam Lee", "role": "bowler"}], "me": 1}
for q in ["Which of our bowlers has the best economy?", "Who is our fastest bowler?", "What should I improve as a bowler?"]:
    print(q, "->", coach.answer(q, empty)["answer"])'''),
    ("md", "## 4. Recommendations with their evidence\n\nA recommendation fires when a recorded figure crosses a stated threshold. The figure and the threshold go in the output."),
    ("code", '''rows = []
for p in ctx["players"]:
    for rec in coach.player_recommendations(ctx, p["id"]):
        rows.append({"player": p["name"], "area": rec["area"], "recommendation": rec["recommendation"], "evidence": rec["evidence"], "drill": rec["drill"]})
recs = pd.DataFrame(rows)
print(len(recs), "recommendations for", recs["player"].nunique(), "players")
pd.set_option("display.max_colwidth", 140); recs.head(8)'''),
    ("code", '''print("Team-level insights")
for i in coach.team_insights(ctx):
    print(f"- {i['title']}: {i['detail']} ({i['evidence']})")
recs.to_csv(EXPORTS / "coaching_recommendations.csv", index=False)
print("\\nThresholds used:")
for name, value in [("balls in a pace/spin split", coach.MIN_BALLS_SPLIT), ("balls bowled before economy is read", coach.MIN_BALLS_BOWLED), ("catching chances before a catch % is read", coach.MIN_CHANCES)]:
    print(f" - {name}: {value}")'''),
    ("md", "## 5. Optional: phrasing with a language model\n\nIf an `ANTHROPIC_API_KEY` is set, the retrieved facts can be handed to Claude, which is told to use only those facts. "
           "Nothing else about the notebook changes. Without a key this cell prints the rule-based answer and carries on."),
    ("code", '''import os
print("Language model available:", coach.llm_available())
question = "What should I improve as a bowler?"
reply = coach.answer(question, ctx, use_llm=True)
print("Engine used:", reply["engine"])
print(reply["answer"])
if reply.get("llm_note"): print("Note:", reply["llm_note"])
# To switch it on:   os.environ["ANTHROPIC_API_KEY"] = "..."   (keep keys out of notebooks you share)'''),
    ("md", "## 6. Plotting the evidence"),
    ("code", '''acc = pd.DataFrame(accuracy).T[["hit_pct", "total"]].sort_values("hit_pct")
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.barh(acc.index, acc["hit_pct"], color=[RED if v < 40 else INK for v in acc["hit_pct"]])
ax.axvline(40, color=RED, ls="--", label="coaching threshold (40%)"); ax.legend()
ax.set_xlabel("practice deliveries in the target zone (%)"); ax.set_title("Bowling accuracy: bowlers below the line get a line-and-length recommendation (SYNTHETIC)"); plt.show()'''),
] + closing(
    "- The coach answers each question from the table of statistics and prints the rows it used.\n"
    "- With no data it says so, and the recommendation list stays empty.\n"
    "- Each recommendation carries its trigger figure, and the thresholds are constants anyone can read and change.",
    "A rule-based coach is easy to check: if an answer looks wrong, the evidence lines show why. A language model makes the prose smoother but adds nothing the rules did not already find.",
    "- The rules cover a short list of questions. Anything else gets a polite 'I can answer questions about...'.\n"
    "- Thresholds such as 40% in the target zone are coaching rules of thumb, not measured standards.\n"
    "- With synthetic data the recommendations show the mechanism, not real weaknesses.\n"
    "- A language model can still misread the facts it is given. Treat its wording as a draft and check the evidence list.",
    "The AI Coach page calls `POST /api/coach/ask` and `GET /api/coach/recommendations`, which build the same context from the database and call `coach.answer` and "
    "`coach.player_recommendations`. The language-model checkbox calls the same `coach.llm_answer` used above.",
)

# ---------------------------------------------------------------------------------------------------------------

NB12 = header(
    "12 · Complete Cricket Analytics Pipeline",
    "One notebook from raw files to finished reports: read the data, clean it, score the matches, calculate player statistics, analyse bowling and batting, draw the charts, and write the results to CSV.",
) + [
    ("md", "## 1. Settings\n\nPoint `INPUT` at a folder with files in the same format as `notebooks/data/` (see `DATA_DICTIONARY.md`) and run the notebook from the top."),
    ("code", '''from pitchvision import scoring, stats, pitchmap, speed, coach, ml
import datetime as dt

INPUT = DATA                        # change to the folder holding your own CSV files
OUTPUT = EXPORTS / "pipeline"; OUTPUT.mkdir(exist_ok=True)
TEAM_SEASON = "2025"
print("Reading from", INPUT); print("Writing to", OUTPUT)'''),
    ("md", "## 2. Ingest and validate\n\nEach table is checked for the columns it needs and for impossible values before anything is calculated."),
    ("code", '''REQUIRED = {"players": ["name", "role"], "matches": ["match_id", "date", "opponent"],
            "balls": ["match_id", "innings", "striker", "bowler", "runs_bat", "wides", "no_balls"],
            "deliveries": ["player", "x", "y", "date"], "speeds": ["player", "date", "kmh"], "fielding": ["player", "kind", "count"]}
tables, problems = {}, []
for name, cols in REQUIRED.items():
    df = pd.read_csv(INPUT / f"{name}.csv")
    missing = [c for c in cols if c not in df]
    if missing: problems.append(f"{name}.csv is missing columns {missing}")
    tables[name] = df
    print(f"{name:11s} {len(df):6d} rows")
assert not problems, problems

balls = tables["balls"]
checks = {"negative runs": (balls["runs_bat"] < 0).sum(), "runs over 7 off the bat": (balls["runs_bat"] > 7).sum(),
          "wide and no-ball on one ball": ((balls["wides"] > 0) & (balls["no_balls"] > 0)).sum(),
          "pitching point off the pitch": ((balls["x"].abs() > 1.6) | (balls["y"] > 20.12) | (balls["y"] < -1)).sum(),
          "speeds above 200 km/h": (tables["speeds"]["kmh"] > 200).sum()}
print("\\nValidation:"); [print(f" - {k}: {v}") for k, v in checks.items()]'''),
    ("md", "## 3. Clean\n\nMissing values are counted and handled by rule, never guessed. Rows that cannot be used for a calculation are dropped from that calculation only."),
    ("code", '''clean_log = []
def log(step, before, after): clean_log.append({"step": step, "rows before": before, "rows after": after, "removed": before - after})

speeds = tables["speeds"].copy(); speeds["date"] = pd.to_datetime(speeds["date"])
n = len(speeds); speeds = speeds.dropna(subset=["kmh"]); speeds = speeds[(speeds["kmh"] > 0) & (speeds["kmh"] < 200)]; log("speed readings with a usable value", n, len(speeds))

deliveries = tables["deliveries"].copy(); n = len(deliveries)
deliveries = deliveries.dropna(subset=["x", "y"]); log("deliveries with a pitching point", n, len(deliveries))
deliveries["length"] = deliveries["y"].apply(pitchmap.classify_length); deliveries["line"] = deliveries["x"].apply(pitchmap.classify_line)

matches = tables["matches"].copy(); matches["date"] = pd.to_datetime(matches["date"])
players = tables["players"]; ours = set(players["name"])
pd.DataFrame(clean_log)'''),
    ("md", "## 4. Score every innings\n\nThe scoring engine checks each ball against the Laws. A file that breaks a rule stops here with the match, innings and ball number rather than producing wrong statistics."),
    ("code", '''try:
    lines = scoring.lines_from_balls(balls.to_dict("records"), max_overs=20)
except scoring.ScoringError as e:
    raise SystemExit(f"The ball-by-ball data breaks a scoring rule: {e}")
cards = lines["innings"]
innings_table = pd.DataFrame([{"match_id": k[0], "innings": k[1], "total": c["total"], "wickets": c["wickets"], "overs": c["overs"],
                               "run_rate": c["run_rate"], "extras": c["extras"]["total"]} for k, c in cards.items()])
print(len(innings_table), "innings scored without a rule being broken")
innings_table.head()'''),
    ("md", "## 5. Player statistics and feature engineering"),
    ("code", '''batting = pd.DataFrame(stats.career_batting([l for l in lines["batting"] if l["player"] in ours])).set_index("player")
bowling = pd.DataFrame(stats.career_bowling([l for l in lines["bowling"] if l["player"] in ours])).set_index("player")
fielding_t = pd.DataFrame(stats.career_fielding(tables["fielding"].to_dict("records"))).set_index("player")

# Derived features per player: how consistent, how boundary-heavy, how accurate in practice, how fast.
batting["median_score"] = [pd.Series([s["runs"] for s in sc]).median() for sc in batting["scores"]]
batting["score_sd"] = [pd.Series([s["runs"] for s in sc]).std(ddof=0) for sc in batting["scores"]]
bowling["dot_pct"] = bowling["dot_pct"].round(1)
practice = deliveries.groupby("player").apply(lambda g: pd.Series(pitchmap.accuracy(g.to_dict("records"), 0.2, 5.2 if g["bowl_type"].iloc[0] == "spin" else 7.0)))[["total", "hit_pct", "spread_x", "spread_y", "consistency_index"]]
spd = speeds[speeds["source"] != "radar"].groupby("player")["kmh"].agg(avg_kmh="mean", max_kmh="max", readings="count")
radar = speeds[speeds["source"] == "radar"].groupby("player")["kmh"].agg(radar_kmh="max")
profile = (players.set_index("name")[["role", "bowl_style"]]
           .join(batting[["innings", "runs", "average", "strike_rate", "highest", "boundary_pct", "median_score", "score_sd"]])
           .join(bowling[["overs", "wickets", "economy", "average", "dot_pct"]], rsuffix="_bowl")
           .join(fielding_t[["catch", "drop", "catch_pct", "run_outs_total"]])
           .join(practice[["hit_pct", "consistency_index"]]).join(spd).join(radar))
profile.round(1).head(8)'''),
    ("md", "## 6. Bowling analysis"),
    ("code", '''fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
b = bowling[bowling["legal_balls"] >= 30].sort_values("economy")
axes[0].barh(b.index, b["economy"], color=INK); axes[0].set_title("Economy (30+ balls)")
axes[1].scatter(practice["spread_x"] * 100, practice["hit_pct"], color=GREEN)
for n_, r in practice.iterrows(): axes[1].annotate(n_.split()[0], (r["spread_x"] * 100, r["hit_pct"]), fontsize=8, xytext=(3, 3), textcoords="offset points")
axes[1].set_xlabel("line spread (cm)"); axes[1].set_ylabel("in target zone (%)"); axes[1].set_title("Tighter line, more hits")
axes[2].scatter(spd["avg_kmh"], spd["max_kmh"], color=RED); axes[2].set_xlabel("average timed speed (km/h)"); axes[2].set_ylabel("fastest (km/h)"); axes[2].set_title("Speed")
plt.tight_layout(); plt.show()'''),
    ("md", "## 7. Batting analysis"),
    ("code", '''fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
b = batting.sort_values("runs").tail(8)
axes[0].barh(b.index, b["runs"], color=INK); axes[0].set_title("Runs")
axes[1].scatter(batting["strike_rate"], batting["average"].fillna(0), s=batting["runs"] / 2, color=GREEN, alpha=0.7)
for n_, r in batting.iterrows(): axes[1].annotate(n_.split()[0], (r["strike_rate"], r["average"] if pd.notna(r["average"]) else 0), fontsize=8)
axes[1].set_xlabel("strike rate"); axes[1].set_ylabel("average (0 where never out)"); axes[1].set_title("Average against strike rate; size is runs")
plt.show()

team_splits = {"pace": [0, 0], "spin": [0, 0]}
for n_ in ours:
    for k, d in stats.batting_splits(balls.to_dict("records"), n_)["bowl_type"].items():
        team_splits[k][0] += d["runs"]; team_splits[k][1] += d["balls"]
for k, (r, bl) in team_splits.items(): print(f"Team against {k}: {r} runs from {bl} balls, strike rate {r / bl * 100:.0f}")'''),
    ("md", "## 8. Reports\n\nA one-page report for each player: their figures, their coaching recommendations with the evidence, and the thresholds used."),
    ("code", '''ctx = {"players": [{"id": n, "name": n, "role": r["role"]} for n, r in players.set_index("name").iterrows()],
       "batting": [{**r, "name": r["player"]} for r in stats.career_batting([l for l in lines["batting"] if l["player"] in ours])],
       "bowling": [{**r, "name": r["player"]} for r in stats.career_bowling([l for l in lines["bowling"] if l["player"] in ours])],
       "fielding": stats.career_fielding(tables["fielding"].to_dict("records")),
       "accuracy": {n_: pitchmap.accuracy(g.to_dict("records"), 0.2, 7.0) for n_, g in deliveries.groupby("player")},
       "speeds": {n_: g.sort_values("date")[["date", "kmh"]].to_dict("records") for n_, g in speeds.groupby("player")},
       "splits": {n_: stats.batting_splits(balls.to_dict("records"), n_) for n_ in ours}}

def report(name):
    p = profile.loc[name]; out = [f"PLAYER REPORT: {name}", f"Role: {p['role']}", ""]
    if pd.notna(p["runs"]): out.append(f"Batting: {int(p['innings'])} innings, {int(p['runs'])} runs, average {p['average']:.1f}" if pd.notna(p["average"]) else f"Batting: {int(p['innings'])} innings, {int(p['runs'])} runs, never out")
    if pd.notna(p["overs"]): out.append(f"Bowling: {p['overs']} overs, {int(p['wickets'])} wickets, economy {p['economy']:.2f}")
    if pd.notna(p["catch_pct"]): out.append(f"Fielding: {int(p['catch'])} catches, {p['catch_pct']:.0f}% of chances")
    out.append(""); recs = coach.player_recommendations(ctx, name)
    out.append("Recommendations:" if recs else "No recommendation crosses a coaching threshold.")
    for r in recs: out += [f" - {r['area']}: {r['recommendation']}", f"     evidence: {r['evidence']}"]
    return "\\n".join(out)

print(report("Imran Khan"))
(OUTPUT / "player_reports.txt").write_text("\\n\\n".join(report(n) for n in profile.index))'''),
    ("md", "## 9. A model, honestly evaluated"),
    ("code", '''model = ml.train_dot_ball_model(balls[balls["batting_team"].str.contains("synthetic")].to_dict("records"), synthetic=True)
if model["status"] == "ok":
    print(pd.DataFrame(model["results"]).round(3).to_string(index=False)); print(model["conclusion"]); print(model["caveat"])
else:
    print(model["reason"])'''),
    ("md", "## 10. Export"),
    ("code", '''profile.round(3).to_csv(OUTPUT / "player_profiles.csv")
innings_table.round(3).to_csv(OUTPUT / "innings.csv", index=False)
pd.DataFrame(clean_log).to_csv(OUTPUT / "cleaning_log.csv", index=False)
deliveries.to_csv(OUTPUT / "deliveries_classified.csv", index=False)
(pd.DataFrame(ctx["batting"]).drop(columns=["scores"]).round(3)).to_csv(OUTPUT / "batting.csv", index=False)
(pd.DataFrame(ctx["bowling"]).drop(columns=["spells"]).round(3)).to_csv(OUTPUT / "bowling.csv", index=False)
for f in sorted(OUTPUT.iterdir()): print(f"{f.name:28s} {f.stat().st_size / 1024:7.1f} KB")
print("\\nRun finished", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))'''),
] + closing(
    "- Every table is checked before use, and the scoring engine stops the run if a ball breaks a rule.\n"
    "- Player profiles join batting, bowling, fielding, practice accuracy and speed into one table, and a plain-text report for each player lists its evidence.\n"
    "- The results are written to `notebooks/exports/pipeline/` as CSV files.",
    "The pipeline gives a team a repeatable way to refresh its statistics: replace the input files, run the notebook from the top and read the reports.",
    "- Column names must match the data dictionary. A file in another format needs a short mapping step before this one.\n"
    "- Cleaning drops unusable rows from each calculation but never invents values.\n- Statistics from a few matches are noisy; the reports show counts so this stays visible.\n"
    "- The sample files are synthetic.",
    "The application runs the same steps on a database instead of CSV files: `services.collect` plays the role of sections 2 to 4, and the Overview, Team Hub, "
    "Match Center and AI Coach call the shared `stats`, `scoring`, `pitchmap`, `coach` and `ml` functions used above.",
)

NOTEBOOKS = {
    "09_team_match_analytics.ipynb": NB09,
    "10_cricket_machine_learning.ipynb": NB10,
    "11_ai_cricket_coach.ipynb": NB11,
    "12_complete_cricket_analytics_pipeline.ipynb": NB12,
}
