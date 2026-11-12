"""Cricket-ball detection and tracking from video with OpenCV.

Pipeline
--------
1. Background subtraction (MOG2) finds pixels that moved.
2. Moving blobs are filtered by size and roundness (circularity = 4*pi*area / perimeter^2).
   An optional HSV colour range (red, white or pink ball) raises the score of matching blobs.
3. A constant-velocity Kalman filter links detections frame to frame. Detections far
   from the filter's prediction are rejected. When the ball is not detected the filter
   COASTS for a few frames; those points are marked observed = False (predicted).

Every returned point says whether it was OBSERVED in the image or PREDICTED by the filter.

Limitations (single ordinary camera)
------------------------------------
* A ball at 100 km/h moves about 0.9 m between frames at 30 fps, and smears into a
  streak at normal shutter speeds. 120-240 fps and good light help a great deal.
* The ball is a few pixels wide in a wide shot and is hidden by the bowler and batter.
* Anything else that moves and is small and round (a bird, a bail, a shoe) can be detected.
* Pixel positions are not metres. See trajectory.fit_homography for ground-plane calibration.
"""
from __future__ import annotations

import math
import os
from typing import Optional

import numpy as np

try:  # OpenCV is required for video work but not for importing the rest of the package.
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


class VideoError(Exception):
    """The video is missing, unreadable, corrupted or too short."""


# OpenCV hue runs 0-179. Red wraps around 0, so it needs two ranges.
BALL_COLOURS = {
    "red": [((0, 90, 60), (10, 255, 255)), ((168, 90, 60), (179, 255, 255))],
    "pink": [((150, 60, 90), (175, 255, 255))],
    "white": [((0, 0, 190), (179, 55, 255))],
}

MIN_OBSERVED_POINTS = 6


def _require_cv2():
    if cv2 is None:
        raise VideoError("OpenCV is not installed. Run: pip install opencv-python-headless")


def open_video(path: str):
    """Open a video and return (capture, info). Raises VideoError with a clear reason."""
    _require_cv2()
    if not path or not os.path.exists(path):
        raise VideoError("Video file not found.")
    if os.path.getsize(path) == 0:
        raise VideoError("The video file is empty (0 bytes).")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        raise VideoError("The file could not be opened as a video. It may be corrupted or in an unsupported format "
                         "(use MP4/H.264, MOV, AVI or WebM).")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    info = {
        "fps": float(fps) if fps and fps > 0 and not math.isnan(fps) else 30.0,
        "fps_assumed": not (fps and fps > 0),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
    }
    ok, _ = cap.read()
    if not ok:
        cap.release()
        raise VideoError("The video opened but no frame could be decoded. The file is probably corrupted or truncated.")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    info["duration_s"] = info["frame_count"] / info["fps"] if info["frame_count"] else None
    return cap, info


def extract_frames(path: str, every: int = 1, max_frames: int = 600, resize_width: Optional[int] = None):
    """Yield (frame_index, time_seconds, BGR image) for every `every`-th frame."""
    cap, info = open_video(path)
    try:
        i = produced = 0
        while produced < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if i % every == 0:
                if resize_width and frame.shape[1] > resize_width:
                    s = resize_width / frame.shape[1]
                    frame = cv2.resize(frame, (resize_width, int(round(frame.shape[0] * s))))
                yield i, i / info["fps"], frame
                produced += 1
            i += 1
    finally:
        cap.release()


def detect_candidates(frame, fg_mask, colour: Optional[str] = None, min_radius: float = 1.5,
                      max_radius: float = 30.0) -> list[dict]:
    """Ball-like moving blobs in one frame, best first.

    score = circularity (0-1), plus up to 0.5 if the blob matches the ball colour.
    """
    mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    colour_mask = None
    if colour in BALL_COLOURS:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        colour_mask = np.zeros(mask.shape, np.uint8)
        for lo, hi in BALL_COLOURS[colour]:
            colour_mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 3:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(c)
        if not (min_radius <= r <= max_radius):
            continue
        per = cv2.arcLength(c, True)
        circ = min(1.0, 4 * math.pi * area / (per * per)) if per > 0 else 0.0
        fill = area / (math.pi * r * r)            # 1.0 for a perfect disc
        if circ < 0.45 or fill < 0.35:
            continue
        score = 0.5 * circ + 0.5 * min(fill, 1.0)
        if colour_mask is not None:
            x0, y0, w, h = cv2.boundingRect(c)
            patch = colour_mask[y0:y0 + h, x0:x0 + w]
            score += 0.5 * float(np.count_nonzero(patch)) / max(patch.size, 1)
        out.append({"x": float(cx), "y": float(cy), "r": float(r), "score": float(min(score, 1.5)),
                    "circularity": float(circ)})
    return sorted(out, key=lambda d: -d["score"])


class BallKalman:
    """Constant-velocity Kalman filter over state [x, y, vx, vy] (pixels, pixels/frame)."""

    def __init__(self, x: float, y: float, process_noise: float = 4.0, measure_noise: float = 2.0):
        self.s = np.array([x, y, 0.0, 0.0])
        self.P = np.diag([25.0, 25.0, 400.0, 400.0])
        self.F = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], float)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], float)
        self.Q = np.eye(4) * process_noise
        self.R = np.eye(2) * measure_noise ** 2

    def predict(self):
        self.s = self.F @ self.s
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.s[:2].copy()

    def update(self, x: float, y: float):
        z = np.array([x, y])
        innov = z - self.H @ self.s
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.s = self.s + K @ innov
        self.P = (np.eye(4) - K @ self.H) @ self.P

    @property
    def position_sigma(self) -> float:
        return float(math.sqrt(max(self.P[0, 0] + self.P[1, 1], 0.0)))


def track_ball(path: str, colour: Optional[str] = None, max_frames: int = 600, resize_width: int = 960,
               gate_px: float = 120.0, max_coast: int = 4, warmup: int = 5) -> dict:
    """Track the ball through a video.

    Returns {status, points, info, confidence, ...}. `status` is "ok",
    "insufficient" (fewer than MIN_OBSERVED_POINTS observed positions) or raises
    VideoError for unreadable input.
    """
    _require_cv2()
    bg = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=28, detectShadows=False)
    tracks: list[dict] = []            # every track ever started
    active: Optional[dict] = None
    frames = 0
    cap0, info = open_video(path)          # raises VideoError early for bad input
    cap0.release()
    scale = 1.0
    for idx, t, frame in extract_frames(path, max_frames=max_frames, resize_width=resize_width):
        scale = frame.shape[1] / info["width"] if info["width"] else 1.0
        frames += 1
        fg = bg.apply(frame)
        if frames <= warmup:           # let the background model settle
            continue
        cands = detect_candidates(frame, fg, colour)
        if active is not None:
            pred = active["kf"].predict()
            near = [c for c in cands if math.hypot(c["x"] - pred[0], c["y"] - pred[1]) <= gate_px]
            if near:
                best = min(near, key=lambda c: math.hypot(c["x"] - pred[0], c["y"] - pred[1]) - 20 * c["score"])
                active["kf"].update(best["x"], best["y"])
                active["missed"] = 0
                active["points"].append({"frame": idx, "t": t, "x": best["x"], "y": best["y"], "r": best["r"],
                                         "observed": True, "confidence": min(best["score"], 1.0),
                                         "sigma_px": active["kf"].position_sigma})
            else:
                active["missed"] += 1
                if active["missed"] > max_coast:
                    # Drop the trailing predicted points: nothing was seen after them.
                    while active["points"] and not active["points"][-1]["observed"]:
                        active["points"].pop()
                    active = None
                else:
                    active["points"].append({"frame": idx, "t": t, "x": float(pred[0]), "y": float(pred[1]),
                                             "r": None, "observed": False, "confidence": 0.0,
                                             "sigma_px": active["kf"].position_sigma})
        if active is None and cands:
            c = cands[0]
            active = {"kf": BallKalman(c["x"], c["y"]), "missed": 0,
                      "points": [{"frame": idx, "t": t, "x": c["x"], "y": c["y"], "r": c["r"], "observed": True,
                                  "confidence": min(c["score"], 1.0), "sigma_px": 5.0}]}
            tracks.append(active)
    if frames == 0:
        raise VideoError("No frames could be read from the video.")
    for tr in tracks:
        while tr["points"] and not tr["points"][-1]["observed"]:
            tr["points"].pop()

    def quality(tr):
        obs = [p for p in tr["points"] if p["observed"]]
        if len(obs) < 2:
            return 0.0
        dist = math.hypot(obs[-1]["x"] - obs[0]["x"], obs[-1]["y"] - obs[0]["y"])
        return len(obs) * (1.0 + min(dist / 200.0, 3.0))       # long tracks that actually travel

    best = max(tracks, key=quality, default=None)
    points = best["points"] if best else []
    # Report positions in the ORIGINAL video's pixels.
    for p in points:
        p["x"] /= scale
        p["y"] /= scale
        if p["r"] is not None:
            p["r"] /= scale
        p["sigma_px"] /= scale
    observed = [p for p in points if p["observed"]]
    span = (points[-1]["frame"] - points[0]["frame"] + 1) if points else 0
    detect_rate = len(observed) / span if span else 0.0
    mean_score = float(np.mean([p["confidence"] for p in observed])) if observed else 0.0
    confidence = detect_rate * mean_score
    status = "ok" if len(observed) >= MIN_OBSERVED_POINTS else "insufficient"
    return {
        "status": status,
        "reason": None if status == "ok" else (
            f"Only {len(observed)} ball positions were detected; at least {MIN_OBSERVED_POINTS} are needed. "
            "Try a higher frame rate, a fixed camera, better light, or a ball colour that contrasts with the background."),
        "points": points,
        "observed_count": len(observed),
        "predicted_count": len(points) - len(observed),
        "frames_processed": frames,
        "detection_rate": detect_rate,
        "confidence": confidence,
        "confidence_label": "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low",
        "candidate_tracks": len(tracks),
        "info": info,
        "colour": colour,
    }


def pixel_speed_estimate(points: list[dict], metres_per_pixel: Optional[float]) -> dict:
    """Average image-plane speed of the tracked ball.

    Without a scale this is pixels per second only. With `metres_per_pixel`
    (valid only when the ball moves roughly parallel to the image plane, i.e. a
    side-on camera) it becomes an AVERAGE speed estimate, not a release speed.
    """
    obs = [p for p in points if p.get("observed", True)]
    if len(obs) < 2 or obs[-1]["t"] == obs[0]["t"]:
        return {"px_per_s": None, "kmh": None}
    dist = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(obs, obs[1:]))
    pps = dist / (obs[-1]["t"] - obs[0]["t"])
    return {"px_per_s": pps, "kmh": pps * metres_per_pixel * 3.6 if metres_per_pixel else None,
            "kind": "average", "requires": "side-on camera and a known scale"}


def write_synthetic_ball_video(path: str, fps: int = 120, width: int = 640, height: int = 360,
                               noise: float = 0.0, swing_px: float = 0.0, seed: int = 0,
                               frames_before_bounce: int = 22, frames_after_bounce: int = 12) -> dict:
    """Write a SYNTHETIC clip of a red dot flying, bouncing and rising. For demos and tests only.

    Returns the ground-truth positions so tracking accuracy can be measured.
    """
    _require_cv2()
    rng = np.random.default_rng(seed)
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not out.isOpened():
        raise VideoError("Could not create the synthetic video file.")
    bgimg = np.full((height, width, 3), (70, 120, 80), np.uint8)       # green ground
    cv2.rectangle(bgimg, (0, int(height * 0.62)), (width, height), (150, 185, 190), -1)   # pale pitch strip
    truth = []
    n = frames_before_bounce + frames_after_bounce
    lead = 8
    for f in range(n + lead + 4):
        img = bgimg.copy()
        if noise:
            img = np.clip(img.astype(np.int16) + rng.normal(0, noise, img.shape), 0, 255).astype(np.uint8)
        k = f - lead
        if 0 <= k < n:
            u = k / (n - 1)
            x = 40 + u * (width - 80) + swing_px * (min(k, frames_before_bounce) / frames_before_bounce) ** 2
            if k <= frames_before_bounce:
                y = 60 + (height * 0.62 - 60) * (k / frames_before_bounce) ** 1.6
            else:
                j = (k - frames_before_bounce) / frames_after_bounce
                y = height * 0.62 - 120 * j + 40 * j * j
            cv2.circle(img, (int(round(x)), int(round(y))), 5, (40, 40, 200), -1, lineType=cv2.LINE_AA)
            truth.append({"frame": f, "t": f / fps, "x": float(x), "y": float(y)})
        out.write(img)
    out.release()
    return {"path": path, "fps": fps, "truth": truth, "bounce_frame": lead + frames_before_bounce,
            "synthetic": True}
