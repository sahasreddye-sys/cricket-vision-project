"""Machine-learning helpers (scikit-learn) with honest evaluation.

Rules followed here
-------------------
* Every model is compared with a naive BASELINE. A model that does not beat the
  baseline has learned nothing useful and the result says so.
* Scores come from cross-validation or a held-out test set, never from the data
  the model was trained on.
* With small samples the function refuses to report a score.
* Scores obtained on SYNTHETIC data only show that the code works. They say
  nothing about how well the model would predict real cricket.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

import numpy as np

MIN_ROWS_CLASSIFIER = 150
MIN_ROWS_REGRESSION = 40


def _balls_frame(balls: Iterable[dict]):
    import pandas as pd
    df = pd.DataFrame(list(balls))
    for col in ("x", "y", "runs_bat", "wides", "no_balls"):
        if col not in df:
            df[col] = np.nan
    return df


def delivery_features(balls: Iterable[dict]):
    """Clean ball records and engineer features for the dot-ball model.

    Cleaning: wides and no-balls are dropped (the batter could not score
    normally), rows without a pitching point are dropped, missing bowl_type
    becomes 'unknown'.
    Features: x, y, |x| (distance from the stumps line), is_spin, over number.
    Target: 1 if the ball was a dot ball or took a wicket, else 0.
    """
    df = _balls_frame(balls)
    n_raw = len(df)
    df = df[(df["wides"].fillna(0) == 0) & (df["no_balls"].fillna(0) == 0)]
    df = df.dropna(subset=["x", "y"]).copy()
    df["bowl_type"] = df.get("bowl_type", "unknown")
    df["bowl_type"] = df["bowl_type"].fillna("unknown")
    df["abs_x"] = df["x"].abs()
    df["is_spin"] = (df["bowl_type"] == "spin").astype(int)
    df["over"] = df.get("over", 0)
    df["over"] = df["over"].fillna(0)
    wk = df.get("wicket_kind")
    took_wicket = wk.notna() if wk is not None else False
    df["target"] = ((df["runs_bat"].fillna(0) == 0) | took_wicket).astype(int)
    features = ["x", "y", "abs_x", "is_spin", "over"]
    return df, features, {"rows_in": n_raw, "rows_used": len(df), "dropped": n_raw - len(df)}


def train_dot_ball_model(balls: Iterable[dict], seed: int = 0, synthetic: bool = False) -> dict:
    """Predict whether a delivery will be a dot ball / wicket from where it pitched.

    Returns cross-validated accuracy and ROC-AUC for logistic regression and a
    random forest, the majority-class baseline, and permutation feature importance.
    """
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    df, features, cleaning = delivery_features(balls)
    if len(df) < MIN_ROWS_CLASSIFIER or df["target"].nunique() < 2:
        return {"status": "insufficient", "cleaning": cleaning,
                "reason": f"{len(df)} usable deliveries with pitching points; at least {MIN_ROWS_CLASSIFIER} "
                          "(with both outcomes present) are needed to evaluate a model."}
    X, y = df[features].to_numpy(float), df["target"].to_numpy(int)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    models = {
        "baseline (always predict the most common outcome)": DummyClassifier(strategy="most_frequent"),
        "logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
        "random forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=5, random_state=seed),
    }
    results = []
    for name, m in models.items():
        s = cross_validate(m, X, y, cv=cv, scoring=["accuracy", "roc_auc"])
        results.append({"model": name,
                        "accuracy_mean": float(s["test_accuracy"].mean()), "accuracy_std": float(s["test_accuracy"].std()),
                        "roc_auc_mean": float(s["test_roc_auc"].mean()), "roc_auc_std": float(s["test_roc_auc"].std())})
    base = results[0]["accuracy_mean"]
    best = max(results[1:], key=lambda r: r["roc_auc_mean"])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=seed, stratify=y)
    rf = models["random forest"].fit(Xtr, ytr)
    imp = permutation_importance(rf, Xte, yte, n_repeats=15, random_state=seed, scoring="roc_auc")
    importance = sorted(({"feature": f, "importance": float(m), "std": float(s)}
                         for f, m, s in zip(features, imp.importances_mean, imp.importances_std)),
                        key=lambda r: -r["importance"])
    beats = best["roc_auc_mean"] - 2 * best["roc_auc_std"] > 0.5 and best["accuracy_mean"] >= base - 0.01
    return {
        "status": "ok", "cleaning": cleaning, "rows": int(len(df)), "features": features,
        "positive_rate": float(y.mean()), "results": results, "best_model": best["model"],
        "feature_importance": importance,
        "beats_baseline": bool(beats),
        "conclusion": ("The model ranks deliveries better than chance (ROC-AUC above 0.5 by more than two standard "
                       "deviations)." if beats else
                       "The model does not clearly beat the baseline. Do not use it for decisions."),
        "caveat": ("Trained and tested on SYNTHETIC data: these scores only show the pipeline works." if synthetic else
                   "Scores are cross-validated on this team's own data and will be noisy with small samples. "
                   "They do not transfer to other teams, levels or conditions."),
        "model": rf, "X_columns": features,
    }


def explain_delivery(model_result: dict, x: float, y: float, bowl_type: str = "pace", over: int = 0) -> dict:
    """Predicted dot-ball probability for one delivery, with the inputs spelled out."""
    if model_result.get("status") != "ok":
        return {"status": "insufficient", "reason": model_result.get("reason")}
    row = np.array([[x, y, abs(x), 1 if bowl_type == "spin" else 0, over]], float)
    p = float(model_result["model"].predict_proba(row)[0, 1])
    return {"status": "ok", "probability_dot_or_wicket": p, "base_rate": model_result["positive_rate"],
            "difference_from_base_rate": p - model_result["positive_rate"],
            "inputs": {"x": x, "y": y, "bowl_type": bowl_type, "over": over},
            "explanation": f"For a {bowl_type} delivery pitching {y:.1f} m from the stumps and {abs(x) * 100:.0f} cm "
                           f"{'outside off' if x > 0 else 'toward leg' if x < 0 else 'on middle'}, the model estimates a "
                           f"{p * 100:.0f}% chance of a dot ball or wicket, against {model_result['positive_rate'] * 100:.0f}% "
                           "for all recorded deliveries."}


def batting_forecast(lines: Iterable[dict], seed: int = 0) -> dict:
    """Can a batter's next score be predicted from their previous scores?

    Features for each innings: the mean of the batter's previous 3 scores and
    their career mean before that innings. Baseline: predict the career mean.
    Evaluated with time-ordered cross-validation (no future data in training).
    """
    import pandas as pd
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import TimeSeriesSplit

    df = pd.DataFrame(list(lines))
    if df.empty or "runs" not in df:
        return {"status": "insufficient", "reason": "No batting innings supplied."}
    df = df.dropna(subset=["runs"]).copy()
    order = [c for c in ("date", "match_id") if c in df]
    df = df.sort_values(order) if order else df
    rows = []
    for player, g in df.groupby("player", sort=False):
        runs = g["runs"].astype(float).tolist()
        for i in range(3, len(runs)):
            rows.append({"player": player, "idx": i, "last3": float(np.mean(runs[i - 3:i])),
                         "career": float(np.mean(runs[:i])), "target": runs[i]})
    data = pd.DataFrame(rows)
    if len(data) < MIN_ROWS_REGRESSION:
        return {"status": "insufficient",
                "reason": f"Only {len(data)} innings have three earlier innings to learn from; at least "
                          f"{MIN_ROWS_REGRESSION} are needed."}
    data = data.sort_values("idx").reset_index(drop=True)
    X, y = data[["last3", "career"]].to_numpy(float), data["target"].to_numpy(float)
    mae_model, mae_base = [], []
    for tr, te in TimeSeriesSplit(n_splits=4).split(X):
        m = Ridge(alpha=1.0).fit(X[tr], y[tr])
        mae_model.append(float(np.mean(np.abs(m.predict(X[te]) - y[te]))))
        mae_base.append(float(np.mean(np.abs(X[te][:, 1] - y[te]))))
    mm, mb = float(np.mean(mae_model)), float(np.mean(mae_base))
    return {"status": "ok", "rows": int(len(data)), "mae_model": mm, "mae_baseline": mb,
            "beats_baseline": bool(mm < mb * 0.97),
            "conclusion": ("Recent form adds a little information beyond the career mean." if mm < mb * 0.97 else
                           "Recent form does NOT predict the next score better than the batter's career mean. "
                           "Individual cricket scores are highly variable; treat 'form' with caution."),
            "note": "Mean absolute error in runs, from time-ordered cross-validation."}


def performance_trend(values: list, min_points: int = 5) -> dict:
    """Linear trend with a 95% confidence interval for the slope.

    A trend is only called 'up' or 'down' if the interval excludes zero.
    """
    v = np.array([x for x in values if x is not None and not (isinstance(x, float) and math.isnan(x))], float)
    n = len(v)
    if n < min_points:
        return {"status": "insufficient", "n": int(n), "reason": f"{n} readings; at least {min_points} are needed."}
    t = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(t, v, 1)
    resid = v - (slope * t + intercept)
    se = math.sqrt(float(np.sum(resid ** 2)) / (n - 2) / float(np.sum((t - t.mean()) ** 2)))
    # t critical value for 95% two-sided, small-sample table (falls back to 1.96).
    tcrit = {3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
             12: 2.179, 15: 2.131, 20: 2.086, 30: 2.042}
    dof = n - 2
    key = max((k for k in tcrit if k <= dof), default=None)
    tc = tcrit[key] if key else 12.706 if dof == 1 else 4.303
    lo, hi = slope - tc * se, slope + tc * se
    direction = "up" if lo > 0 else "down" if hi < 0 else "no clear trend"
    return {"status": "ok", "n": int(n), "slope": float(slope), "ci_low": float(lo), "ci_high": float(hi),
            "direction": direction, "fitted": [float(slope * i + intercept) for i in range(n)]}


def cluster_deliveries(deliveries: Iterable[dict], k: int = 4, seed: int = 0) -> dict:
    """Group deliveries by where they pitch (k-means on x and y). Unsupervised: no accuracy claim."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    pts = np.array([[d["x"], d["y"]] for d in deliveries if d.get("x") is not None and d.get("y") is not None], float)
    if len(pts) < k * 5:
        return {"status": "insufficient", "reason": f"{len(pts)} deliveries; at least {k * 5} are needed for {k} groups."}
    sc = StandardScaler().fit(pts)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(sc.transform(pts))
    centres = sc.inverse_transform(km.cluster_centers_)
    from .pitchmap import classify_length, classify_line
    return {"status": "ok", "labels": km.labels_.tolist(),
            "clusters": [{"cluster": i, "x": float(c[0]), "y": float(c[1]), "count": int(np.sum(km.labels_ == i)),
                          "length": classify_length(float(c[1])), "line": classify_line(float(c[0]))}
                         for i, c in enumerate(centres)]}
