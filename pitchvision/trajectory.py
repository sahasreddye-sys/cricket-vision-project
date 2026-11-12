"""Ball-flight geometry: calibration, bounce detection, swing/seam deviation and
an EDUCATIONAL DRS / LBW simulation.

THIS IS NOT HAWK-EYE.
Professional ball tracking uses six or more synchronised, calibrated high-speed
cameras and triangulates the ball in 3-D to a few millimetres. One uncalibrated
phone camera cannot recover depth, so everything here is an estimate with
stated assumptions and an uncertainty range. Results are for coaching and for
learning how the LBW law works. They are not umpiring decisions.

Coordinates: see constants.py (x lateral, + = off side; y metres from the
striker's stumps toward the bowler; z height).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

from .constants import (BALL_RADIUS_M, GRAVITY, PITCH_LENGTH_M, POPPING_CREASE_M, STUMP_HEIGHT_M,
                        WICKET_HALF_WIDTH_M)

# ------------------------------------------------------------------ calibration

def fit_homography(image_pts: Sequence[Sequence[float]], pitch_pts: Sequence[Sequence[float]]) -> np.ndarray:
    """3x3 homography H mapping image pixels to pitch GROUND-PLANE metres (x, y).

    Needs at least four point pairs, no three collinear (e.g. the four corners
    formed by the two popping creases and the return creases). Uses the direct
    linear transform. Valid ONLY for points on the ground: a ball in the air
    projects to the wrong ground position, which is why only the bounce point
    (which is on the ground) can be located this way with one camera.
    """
    src, dst = np.asarray(image_pts, float), np.asarray(pitch_pts, float)
    if src.shape[0] < 4 or src.shape != dst.shape or src.shape[1] != 2:
        raise ValueError("Calibration needs at least four matching (image, pitch) point pairs.")
    rows = []
    for (u, v), (x, y) in zip(src, dst):
        rows.append([-u, -v, -1, 0, 0, 0, u * x, v * x, x])
        rows.append([0, 0, 0, -u, -v, -1, u * y, v * y, y])
    _, s, vt = np.linalg.svd(np.asarray(rows))
    if s[-2] < 1e-9:
        raise ValueError("Calibration points are degenerate (three or more in a line). Pick the four pitch corners.")
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


def image_to_pitch(h: np.ndarray, u: float, v: float) -> tuple[float, float]:
    """Map an image point that lies ON THE GROUND to pitch metres."""
    p = h @ np.array([u, v, 1.0])
    return float(p[0] / p[2]), float(p[1] / p[2])


def standard_calibration_targets() -> list[dict]:
    """The four ground points the user is asked to click, with their pitch coordinates."""
    hw = 1.32  # return crease half-width
    far = PITCH_LENGTH_M - POPPING_CREASE_M
    return [
        {"label": "Striker's popping crease, off side end", "x": hw, "y": POPPING_CREASE_M},
        {"label": "Striker's popping crease, leg side end", "x": -hw, "y": POPPING_CREASE_M},
        {"label": "Bowler's popping crease, leg side end", "x": -hw, "y": far},
        {"label": "Bowler's popping crease, off side end", "x": hw, "y": far},
    ]


# ------------------------------------------------------------------ bounce detection

def detect_bounce(points: Sequence[dict], min_each_side: int = 3) -> dict:
    """Find the bounce in an image-space track.

    `points`: [{t, x, y}] in pixels, image y growing DOWNWARD. Before the bounce
    the ball descends (y increases); after it, the ball rises (y decreases). We
    fit one straight line to y(t) on each side of every candidate split and keep
    the split with the smallest total squared error, then require the vertical
    velocity to actually change sign.
    """
    pts = [p for p in points if p.get("observed", True)]
    n = len(pts)
    if n < 2 * min_each_side:
        return {"found": False, "reason": f"Only {n} observed points; at least {2 * min_each_side} are needed."}
    t = np.array([p["t"] for p in pts], float)
    y = np.array([p["y"] for p in pts], float)
    best = None
    for k in range(min_each_side, n - min_each_side + 1):
        a = np.polyfit(t[:k], y[:k], 1)
        b = np.polyfit(t[k - 1:], y[k - 1:], 1)
        err = float(np.sum((np.polyval(a, t[:k]) - y[:k]) ** 2) + np.sum((np.polyval(b, t[k - 1:]) - y[k - 1:]) ** 2))
        if best is None or err < best[0]:
            best = (err, k - 1, a[0], b[0])
    err, idx, v_before, v_after = best
    if not (v_before > 0 and v_after < 0):
        return {"found": False, "reason": "No reversal of vertical direction was found in the tracked points "
                                          "(the bounce may be outside the tracked frames, or the ball was a full toss)."}
    one_line = np.polyfit(t, y, 1)
    err_single = float(np.sum((np.polyval(one_line, t) - y) ** 2))
    # How much better two lines explain the track than one line: 0 = no better, 1 = perfect.
    confidence = max(0.0, min(1.0, 1.0 - err / err_single)) if err_single > 0 else 0.0
    return {"found": True, "index": int(idx), "t": float(t[idx]), "x": float(pts[idx]["x"]), "y": float(y[idx]),
            "frame": pts[idx].get("frame"), "confidence": confidence,
            "v_before": float(v_before), "v_after": float(v_after)}


# ------------------------------------------------------------------ swing and seam

def lateral_movement(points: Sequence[dict], bounce_index: Optional[int] = None, units: str = "px",
                     min_points: int = 5, sigma_threshold: float = 3.0) -> dict:
    """Lateral movement in the air (swing) and off the pitch (seam).

    `points`: [{t, x}] where x is the lateral coordinate (pixels, or metres if
    calibrated). Method:

    Swing  Fit a straight line to x(t) over the first half of the pre-bounce
           flight (the 'initial direction'), extend it to the last pre-bounce
           point, and measure how far the ball actually was from that line.
    Seam   Fit straight lines to x(t) before and after the bounce and compare
           their slopes (lateral velocity).
    Noise  The scatter of the points about a smooth (quadratic) fit. A movement
           is only REPORTED as real if it is larger than `sigma_threshold`
           times its own standard error. Otherwise it is 'within tracking noise'.
    """
    pts = [p for p in points if p.get("observed", True)]
    t = np.array([p["t"] for p in pts], float)
    x = np.array([p["x"] for p in pts], float)
    n = len(pts)
    result = {"units": units, "points": n, "swing": None, "seam": None, "noise": None,
              "calibrated": units == "m"}
    pre_end = bounce_index + 1 if bounce_index is not None else n
    tp, xp = t[:pre_end], x[:pre_end]
    if len(tp) < min_points:
        result["swing"] = {"status": "insufficient", "reason": f"{len(tp)} pre-bounce points; {min_points} needed."}
    else:
        quad = np.polyfit(tp, xp, 2)
        noise = float(np.sqrt(np.sum((np.polyval(quad, tp) - xp) ** 2) / max(len(tp) - 3, 1)))
        result["noise"] = noise
        half = max(3, len(tp) // 2)
        line = np.polyfit(tp[:half], xp[:half], 1)
        expected = float(np.polyval(line, tp[-1]))
        actual = float(np.polyval(quad, tp[-1]))          # smoothed position, not one noisy point
        deviation = actual - expected
        # Standard error of extrapolating a line fitted on `half` points out to tp[-1].
        tm = tp[:half].mean()
        sxx = float(np.sum((tp[:half] - tm) ** 2)) or 1e-12
        se = noise * math.sqrt(1.0 / half + (tp[-1] - tm) ** 2 / sxx + 1.0 / len(tp))
        z = abs(deviation) / se if se > 0 else float("inf")
        result["swing"] = {
            "status": "measured",
            "deviation": deviation, "std_error": se, "z": z,
            "significant": bool(z >= sigma_threshold),
            "direction": None if z < sigma_threshold else ("positive_x" if deviation > 0 else "negative_x"),
            "label": "Lateral movement in the air detected" if z >= sigma_threshold else "Within tracking noise",
        }
    if bounce_index is None:
        result["seam"] = {"status": "insufficient", "reason": "No bounce point was identified."}
    else:
        ta, xa = t[bounce_index:], x[bounce_index:]
        if len(ta) < 3 or len(tp) < 3:
            result["seam"] = {"status": "insufficient",
                              "reason": f"{len(ta)} points after the bounce; at least 3 are needed on each side."}
        else:
            k = min(len(tp), max(3, len(tp) // 2))        # last part of the pre-bounce flight
            (s1, _), cov1 = _linefit(tp[-k:], xp[-k:])
            (s2, _), cov2 = _linefit(ta, xa)
            change = s2 - s1
            se = math.sqrt(cov1 + cov2)
            z = abs(change) / se if se > 0 else float("inf")
            result["seam"] = {
                "status": "measured", "velocity_before": s1, "velocity_after": s2, "change": change,
                "std_error": se, "z": z, "significant": bool(z >= sigma_threshold),
                "label": "Change of direction off the pitch detected" if z >= sigma_threshold
                else "Within tracking noise",
            }
    if units != "m":
        result["warning"] = ("Values are in image pixels from one camera. They describe movement across the "
                             "IMAGE, which mixes true sideways movement with perspective. Use them to compare "
                             "deliveries filmed from the same fixed camera position, not as centimetres of swing.")
    return result


def _linefit(t: np.ndarray, x: np.ndarray):
    """Least-squares line and the variance of its slope."""
    coef = np.polyfit(t, x, 1)
    resid = x - np.polyval(coef, t)
    dof = max(len(t) - 2, 1)
    s2 = float(np.sum(resid ** 2) / dof)
    sxx = float(np.sum((t - t.mean()) ** 2)) or 1e-12
    return coef, s2 / sxx


def smooth_track(values: Sequence[float], window: int = 5) -> list[float]:
    """Centred moving average that shrinks at the ends. Used to suppress pixel jitter."""
    v = np.asarray(values, float)
    out = []
    half = window // 2
    for i in range(len(v)):
        lo, hi = max(0, i - half), min(len(v), i + half + 1)
        out.append(float(np.nanmean(v[lo:hi])))
    return out


# ------------------------------------------------------------------ DRS simulation

def _project(pitch, impact, speed_ms):
    """Project the ball from the impact point to the plane of the stumps (y = 0).

    Model: constant horizontal speed along the pitch after the bounce, a straight
    lateral line, and gravity acting on height (no air drag, no spin after impact).
    """
    (xp, yp, zp), (xi, yi, zi) = pitch, impact
    dy = yp - yi
    t1 = dy / speed_ms                     # pitch -> impact
    t2 = yp / speed_ms                     # pitch -> stumps
    vz0 = (zi - zp + 0.5 * GRAVITY * t1 ** 2) / t1
    z_stumps = zp + vz0 * t2 - 0.5 * GRAVITY * t2 ** 2
    x_stumps = xp + (xi - xp) / dy * yp
    return x_stumps, z_stumps, vz0


def _hits(x, z):
    return (np.abs(x) <= WICKET_HALF_WIDTH_M + BALL_RADIUS_M) & (z >= 0) & (z <= STUMP_HEIGHT_M + BALL_RADIUS_M)


def simulate_drs(pitch_x: Optional[float], pitch_y: Optional[float],
                 impact_x: Optional[float], impact_y: Optional[float], impact_z: Optional[float],
                 speed_kmh: float = 100.0, position_sigma_m: float = 0.03, speed_sigma_pct: float = 10.0,
                 no_ball: bool = False, shot_offered: bool = True, hit_bat_first: bool = False,
                 source: str = "manual", n_sim: int = 4000, seed: int = 7) -> dict:
    """Educational LBW simulation.

    Inputs are in metres on the shared pitch coordinate system. `speed_kmh` is
    the ball's speed along the pitch AFTER the bounce. `position_sigma_m` is how
    uncertain each entered position is (one standard deviation); use about 0.03
    for careful manual entry and 0.08 or more for positions taken from video.

    Decision rule: the trajectory is simulated `n_sim` times with the inputs
    varied inside their uncertainty. If at least 80% of the simulated balls hit
    the stumps the prediction is HITTING; at most 20%, MISSING; in between,
    INCONCLUSIVE.
    """
    assumptions = [
        "Positions are in metres relative to middle stump (x), the striker's stumps (y) and the ground (z).",
        "After the bounce the ball keeps a constant speed along the pitch and a straight line sideways.",
        "Height follows gravity only: no air drag, no further swing, no spin effect after impact.",
        f"Each entered position is uncertain by about {position_sigma_m * 100:.0f} cm and the speed by "
        f"about {speed_sigma_pct:.0f}% (one standard deviation).",
        "The centre of the ball is used for the pitching and impact tests; the ball's radius is added only "
        "when testing contact with the stumps.",
        "Single-camera input cannot measure depth, so the impact height and distance are estimates.",
    ]
    limitations = [
        "Not an official DRS and not Hawk-Eye: no multi-camera triangulation, no calibrated high-speed cameras.",
        "Camera perspective, lens distortion and motion blur shift where the ball appears to be.",
        "The ball is often hidden by the batter or bowler (occlusion) near pitching and impact.",
        "Extrapolating from a short post-bounce path magnifies small input errors at the stumps.",
    ]
    base = {"assumptions": assumptions, "limitations": limitations, "source": source,
            "educational_only": True}

    missing = [n for n, v in (("pitching point", pitch_x), ("pitching point", pitch_y),
                              ("impact point", impact_x), ("impact point", impact_y),
                              ("impact height", impact_z)) if v is None]
    if missing:
        return {**base, "decision": "inconclusive", "reason": f"Missing {missing[0]}; enter it manually or "
                "track more of the delivery.", "conditions": [], "projection": None}
    if not (0 <= impact_y < pitch_y <= PITCH_LENGTH_M):
        return {**base, "decision": "inconclusive", "conditions": [], "projection": None,
                "reason": "The impact must be between the pitching point and the stumps "
                          "(0 <= impact distance < pitching distance)."}
    if speed_kmh <= 0:
        return {**base, "decision": "inconclusive", "conditions": [], "projection": None,
                "reason": "Ball speed must be greater than zero."}

    speed = speed_kmh / 3.6
    travel = math.hypot(pitch_y - impact_y, impact_x - pitch_x)
    x0, z0, _ = _project((pitch_x, pitch_y, 0.0), (impact_x, impact_y, impact_z), speed)

    rng = np.random.default_rng(seed)
    s = position_sigma_m
    px = rng.normal(pitch_x, s, n_sim)
    py = rng.normal(pitch_y, s, n_sim)
    ix = rng.normal(impact_x, s, n_sim)
    iy = rng.normal(impact_y, s, n_sim)
    iz = np.clip(rng.normal(impact_z, s, n_sim), 0.0, None)
    sp = np.clip(rng.normal(speed, speed * speed_sigma_pct / 100.0, n_sim), 5.0, None)
    ok = (py - iy) > 0.05
    xs, zs, _ = _project((px[ok], py[ok], 0.0), (ix[ok], iy[ok], iz[ok]), sp[ok])
    p_hit = float(np.mean(_hits(xs, zs))) if xs.size else 0.0
    proj = {
        "x": float(x0), "z": float(z0),
        "x_low": float(np.percentile(xs, 2.5)), "x_high": float(np.percentile(xs, 97.5)),
        "z_low": float(np.percentile(zs, 2.5)), "z_high": float(np.percentile(zs, 97.5)),
        "x_sigma": float(np.std(xs)), "z_sigma": float(np.std(zs)),
        "hit_probability": p_hit,
        "would_hit_point_estimate": bool(_hits(np.array([x0]), np.array([z0]))[0]),
    }
    # Path for drawing: observed part (pitch -> impact) and predicted part (impact -> stumps).
    path = []
    for i in range(25):
        y = pitch_y * (1 - i / 24)
        t = (pitch_y - y) / speed
        t1 = (pitch_y - impact_y) / speed
        vz0 = (impact_z + 0.5 * GRAVITY * t1 ** 2) / t1
        path.append({"x": pitch_x + (impact_x - pitch_x) / (pitch_y - impact_y) * (pitch_y - y), "y": y,
                     "z": max(vz0 * t - 0.5 * GRAVITY * t ** 2, 0.0),
                     "predicted": bool(y < impact_y)})

    in_line = lambda x: abs(x) <= WICKET_HALF_WIDTH_M
    pitched = "in line" if in_line(pitch_x) else ("outside off" if pitch_x > 0 else "outside leg")
    impact = "in line" if in_line(impact_x) else ("outside off" if impact_x > 0 else "outside leg")
    impact_ok = impact == "in line" or (impact == "outside off" and not shot_offered)
    conditions = [
        {"law": "Law 36.1.1", "name": "Legal delivery", "pass": not no_ball,
         "detail": "Not a no-ball." if not no_ball else "No-ball: the batter cannot be out LBW."},
        {"law": "Law 36.1.2", "name": "Pitching", "pass": pitched != "outside leg",
         "detail": f"Pitched {pitched}." + (" A ball pitching outside leg stump cannot be LBW." if pitched == "outside leg" else "")},
        {"law": "Law 36.1.3", "name": "Bat", "pass": not hit_bat_first,
         "detail": "Ball did not touch the bat first." if not hit_bat_first else "Ball hit the bat first: not out LBW."},
        {"law": "Law 36.1.4", "name": "Impact", "pass": impact_ok,
         "detail": f"Impact {impact}." + ("" if impact_ok else (
             " Outside off with a shot offered: not out." if impact == "outside off" else " Impact outside leg: not out."))
             + (" No shot offered, so impact outside off still counts." if impact == "outside off" and not shot_offered else "")},
    ]

    if travel < 0.40:
        decision, reason = "inconclusive", (f"Only {travel * 100:.0f} cm between pitching and impact. Under "
                                            "40 cm there is too little post-bounce travel to judge the direction.")
    elif p_hit >= 0.80:
        decision, reason = "hitting", f"{p_hit * 100:.0f}% of simulated trajectories hit the stumps."
    elif p_hit <= 0.20:
        decision, reason = "missing", f"Only {p_hit * 100:.0f}% of simulated trajectories hit the stumps."
    else:
        decision, reason = "inconclusive", (f"{p_hit * 100:.0f}% of simulated trajectories hit the stumps. "
                                            "The result changes within the input uncertainty.")
    conditions.append({"law": "Law 36.1.5", "name": "Wickets", "pass": decision == "hitting" if decision != "inconclusive" else None,
                       "detail": {"hitting": "Predicted to hit the stumps.", "missing": "Predicted to miss the stumps.",
                                  "inconclusive": "Cannot be determined from this data."}[decision]})
    law_fail = [c for c in conditions[:4] if not c["pass"]]
    if law_fail:
        lbw = "not_out"
    elif decision == "hitting":
        lbw = "out"
    elif decision == "missing":
        lbw = "not_out"
    else:
        lbw = "inconclusive"
    return {**base, "decision": decision, "reason": reason, "lbw": lbw, "conditions": conditions,
            "projection": proj, "path": path, "pitched": pitched, "impact": impact,
            "inputs": {"pitch_x": pitch_x, "pitch_y": pitch_y, "impact_x": impact_x, "impact_y": impact_y,
                       "impact_z": impact_z, "speed_kmh": speed_kmh, "position_sigma_m": position_sigma_m,
                       "speed_sigma_pct": speed_sigma_pct, "no_ball": no_ball, "shot_offered": shot_offered,
                       "hit_bat_first": hit_bat_first},
            "post_bounce_travel_m": travel}


def flight_path(release_height: float, speed_kmh: float, pitch_y: float, release_y: float = PITCH_LENGTH_M - POPPING_CREASE_M,
                steps: int = 30) -> list[dict]:
    """Drag-free projectile from release to the pitching point (for teaching the physics).

    Solves for the launch angle that makes a ball released at `release_height`
    with speed `speed_kmh` land `pitch_y` metres from the striker's stumps.
    """
    v = speed_kmh / 3.6
    d = release_y - pitch_y
    if d <= 0 or v <= 0:
        raise ValueError("The pitching point must be in front of the release point and speed must be positive.")
    # y(t) = d = v cos(a) t ; z = h + v sin(a) t - g t^2 / 2 = 0. Solve for a by bisection (downward angles).
    def height_at_d(a):
        t = d / (v * math.cos(a))
        return release_height + v * math.sin(a) * t - 0.5 * GRAVITY * t * t
    lo, hi = -math.radians(60), math.radians(30)
    if height_at_d(lo) > 0 or height_at_d(hi) < 0:
        raise ValueError("No drag-free trajectory reaches that length at that speed.")
    for _ in range(60):
        mid = (lo + hi) / 2
        if height_at_d(mid) > 0:
            hi = mid
        else:
            lo = mid
    a = (lo + hi) / 2
    t_total = d / (v * math.cos(a))
    return [{"t": t_total * i / steps, "y": release_y - v * math.cos(a) * t_total * i / steps,
             "z": max(release_height + v * math.sin(a) * (t_total * i / steps) - 0.5 * GRAVITY * (t_total * i / steps) ** 2, 0.0)}
            for i in range(steps + 1)]
