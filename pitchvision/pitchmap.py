"""Line and length analysis on the shared pitch coordinate system.

See `constants.py` for the coordinate system: x = lateral metres from middle
stump (+ = off side), y = metres from the striker's stumps toward the bowler.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, Optional

from .constants import LENGTH_BANDS, LENGTH_ORDER, LINE_BANDS, LINE_ORDER, PITCH_LENGTH_M, PITCH_WIDTH_M


def classify_length(y: Optional[float], bounced: bool = True) -> Optional[str]:
    """Length band for a pitching point `y` metres from the striker's stumps."""
    if not bounced:
        return "full_toss"
    if y is None or (isinstance(y, float) and math.isnan(y)):
        return None
    if y < 0:
        return "full_toss"   # would have pitched behind the stumps: reached the batter on the full
    for name, lo, hi in LENGTH_BANDS:
        if lo <= y < hi:
            return name
    return None


def classify_line(x: Optional[float]) -> Optional[str]:
    """Line band for a lateral pitching position `x` (metres, + = off side)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    for name, lo, hi in LINE_BANDS:
        if lo <= x < hi:
            return name
    return "wide_off" if x > 0 else "wide_leg"


def _valid(deliveries: Iterable[dict]) -> list[dict]:
    """Keep deliveries that have both coordinates; missing data is skipped, not guessed."""
    out = []
    for d in deliveries:
        x, y = d.get("x"), d.get("y")
        if x is None or y is None:
            continue
        if isinstance(x, float) and math.isnan(x) or isinstance(y, float) and math.isnan(y):
            continue
        out.append(d)
    return out


def distribution(deliveries: Iterable[dict]) -> dict:
    """Counts and percentages of deliveries by length band and by line band."""
    ds = _valid(deliveries)
    n = len(ds)
    lengths = Counter(classify_length(d["y"], d.get("bounced", True)) for d in ds)
    lines = Counter(classify_line(d["x"]) for d in ds)

    def table(counter, order):
        return [{"band": b, "count": counter.get(b, 0),
                 "pct": (counter.get(b, 0) / n * 100.0) if n else 0.0} for b in order]

    return {"total": n, "length": table(lengths, LENGTH_ORDER), "line": table(lines, LINE_ORDER)}


def accuracy(deliveries: Iterable[dict], target_x: float, target_y: float,
             tol_x: float = 0.20, tol_y: float = 1.0) -> dict:
    """How closely deliveries group around a target line and length.

    hit_pct           share of deliveries inside the target box
                      (|x - target_x| <= tol_x and |y - target_y| <= tol_y)
    mean_error_m      mean straight-line distance from the target
    bias_x / bias_y   mean signed miss (systematic error: where the group is centred)
    spread_x / spread_y  standard deviation (consistency: how tight the group is)
    consistency_index 0-100. 100 * exp(-rms_radial_spread). It measures how tightly the
                      deliveries group around THEIR OWN centre, independent of the target.
                      It is a descriptive index, not a rating of the bowler.
    """
    ds = _valid(deliveries)
    n = len(ds)
    if n == 0:
        return {"total": 0, "hit_pct": None, "mean_error_m": None, "bias_x": None, "bias_y": None,
                "spread_x": None, "spread_y": None, "consistency_index": None, "hits": 0,
                "target": {"x": target_x, "y": target_y, "tol_x": tol_x, "tol_y": tol_y}}
    xs = [d["x"] for d in ds]
    ys = [d["y"] for d in ds]
    hits = sum(1 for x, y in zip(xs, ys) if abs(x - target_x) <= tol_x and abs(y - target_y) <= tol_y)
    mean_err = sum(math.hypot(x - target_x, y - target_y) for x, y in zip(xs, ys)) / n
    mx, my = sum(xs) / n, sum(ys) / n
    # Population SD: we are describing this set of deliveries, not estimating a wider population.
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    # Lateral spread matters far more per metre than length spread (the pitch is 3 m
    # wide but 20 m long), so scale each axis by its tolerance before combining.
    rms = math.sqrt((sx / tol_x) ** 2 + (sy / tol_y) ** 2)
    return {
        "total": n,
        "hits": hits,
        "hit_pct": hits / n * 100.0,
        "mean_error_m": mean_err,
        "bias_x": mx - target_x,
        "bias_y": my - target_y,
        "spread_x": sx,
        "spread_y": sy,
        "consistency_index": 100.0 * math.exp(-rms / 2.0) if n >= 2 else None,
        "target": {"x": target_x, "y": target_y, "tol_x": tol_x, "tol_y": tol_y},
    }


def heatmap(deliveries: Iterable[dict], x_bins: int = 7, y_bins: int = 12,
            x_range: tuple = (-1.05, 1.05), y_range: tuple = (0.0, 12.0)) -> dict:
    """2-D histogram of pitching points. Returns counts[y_bin][x_bin] and the bin edges."""
    ds = _valid(deliveries)
    counts = [[0] * x_bins for _ in range(y_bins)]
    xw = (x_range[1] - x_range[0]) / x_bins
    yw = (y_range[1] - y_range[0]) / y_bins
    outside = 0
    for d in ds:
        xi = int((d["x"] - x_range[0]) // xw)
        yi = int((d["y"] - y_range[0]) // yw)
        if 0 <= xi < x_bins and 0 <= yi < y_bins:
            counts[yi][xi] += 1
        else:
            outside += 1
    return {
        "counts": counts,
        "x_edges": [x_range[0] + i * xw for i in range(x_bins + 1)],
        "y_edges": [y_range[0] + i * yw for i in range(y_bins + 1)],
        "max": max((c for row in counts for c in row), default=0),
        "outside": outside,
        "total": len(ds),
    }


def compare_sessions(a: Iterable[dict], b: Iterable[dict], target_x: float, target_y: float,
                     tol_x: float = 0.20, tol_y: float = 1.0) -> dict:
    """Side-by-side accuracy for two sessions and the change from A to B."""
    ra = accuracy(a, target_x, target_y, tol_x, tol_y)
    rb = accuracy(b, target_x, target_y, tol_x, tol_y)

    def delta(key):
        if ra[key] is None or rb[key] is None:
            return None
        return rb[key] - ra[key]

    return {"a": ra, "b": rb,
            "change": {k: delta(k) for k in ("hit_pct", "mean_error_m", "spread_x", "spread_y", "consistency_index")}}


def in_pitch_bounds(x: float, y: float) -> bool:
    return abs(x) <= PITCH_WIDTH_M / 2 and 0 <= y <= PITCH_LENGTH_M
