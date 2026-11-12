"""Pose estimation for bowling, batting and catching video (MediaPipe Pose Landmarker).

What this module CAN say: measurable 2-D joint angles and movement indicators
from the camera's point of view, and how they differ between two clips.

What it CANNOT say: whether an action is safe, whether it will cause injury, or
whether a bowling action is legal (elbow-extension testing needs calibrated 3-D
motion capture in an accredited lab). All angles are projections onto the image
plane, so they change with camera angle; compare clips filmed from the same spot.
"""
from __future__ import annotations

import base64
import math
import os
import urllib.request
from typing import Optional, Sequence

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from .tracking import VideoError, extract_frames, open_video

# MediaPipe's 33 landmark indices (the ones used here).
LM = {"nose": 0, "left_ear": 7, "right_ear": 8, "left_shoulder": 11, "right_shoulder": 12,
      "left_elbow": 13, "right_elbow": 14, "left_wrist": 15, "right_wrist": 16,
      "left_hip": 23, "right_hip": 24, "left_knee": 25, "right_knee": 26,
      "left_ankle": 27, "right_ankle": 28, "left_heel": 29, "right_heel": 30,
      "left_foot_index": 31, "right_foot_index": 32}
SKELETON = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
            (23, 25), (25, 27), (24, 26), (26, 28), (27, 31), (28, 32), (27, 29), (28, 30), (0, 11), (0, 12)]

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")
MODEL_PATH = os.environ.get("PITCHVISION_POSE_MODEL",
                            os.path.join(os.path.dirname(__file__), "models", "pose_landmarker_lite.task"))
MIN_VISIBILITY = 0.5
MIN_POSE_FRAMES = 5

DISCLAIMER = ("Angles are 2-D measurements from one camera and depend on where the camera stood. They are "
              "coaching observations only. They do not diagnose injury risk, medical safety, or whether a "
              "bowling action is legal.")


class PoseError(Exception):
    """Pose estimation could not run or found no person."""


# ------------------------------------------------------------------ geometry

def angle_between(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> Optional[float]:
    """Interior angle ABC in degrees (0-180) at joint B, from three (x, y) points.

    cos(theta) = (BA . BC) / (|BA| |BC|)
    """
    ba = np.array(a[:2], float) - np.array(b[:2], float)
    bc = np.array(c[:2], float) - np.array(b[:2], float)
    na, nc = np.linalg.norm(ba), np.linalg.norm(bc)
    if na < 1e-9 or nc < 1e-9:
        return None
    return float(math.degrees(math.acos(float(np.clip(np.dot(ba, bc) / (na * nc), -1.0, 1.0)))))


def line_tilt(p: Sequence[float], q: Sequence[float]) -> float:
    """Angle of the line PQ from horizontal, in degrees (-90..90). 0 = level."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    ang = math.degrees(math.atan2(dy, dx))
    if ang > 90:
        ang -= 180
    if ang < -90:
        ang += 180
    return float(ang)


def lean_from_vertical(top: Sequence[float], bottom: Sequence[float]) -> float:
    """Angle of the line bottom->top from vertical, degrees. 0 = upright. Signed: + leans toward +x."""
    dx, dy = top[0] - bottom[0], bottom[1] - top[1]      # image y grows downward
    return float(math.degrees(math.atan2(dx, dy)))


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def frame_metrics(lm: np.ndarray, aspect: float = 1.0) -> dict:
    """Measurable indicators from ONE frame's landmarks.

    `lm`: array (33, 3+) of normalised x, y (0-1, y down) and visibility in the
    last column. `aspect` = image width / height, so angles are measured in true
    pixel proportions. A metric is None when a joint it needs is not visible.
    """
    def pt(name):
        i = LM[name]
        vis = lm[i][-1] if lm.shape[1] > 3 else lm[i][2] if lm.shape[1] == 3 else 1.0
        if vis < MIN_VISIBILITY:
            return None
        return (float(lm[i][0]) * aspect, float(lm[i][1]))

    P = {k: pt(k) for k in LM}

    def ang(a, b, c):
        return angle_between(P[a], P[b], P[c]) if P[a] and P[b] and P[c] else None

    m = {
        "left_elbow_angle": ang("left_shoulder", "left_elbow", "left_wrist"),
        "right_elbow_angle": ang("right_shoulder", "right_elbow", "right_wrist"),
        "left_knee_angle": ang("left_hip", "left_knee", "left_ankle"),
        "right_knee_angle": ang("right_hip", "right_knee", "right_ankle"),
        "left_shoulder_angle": ang("left_elbow", "left_shoulder", "left_hip"),
        "right_shoulder_angle": ang("right_elbow", "right_shoulder", "right_hip"),
        "shoulder_tilt": None, "hip_tilt": None, "trunk_lean": None, "head_offset": None,
        "head_tilt": None, "stride_ratio": None, "stance_width_ratio": None,
        "hip_x": None, "hip_y": None, "left_wrist_y": None, "right_wrist_y": None,
        "left_wrist_x": None, "right_wrist_x": None, "wrist_gap_ratio": None, "hands_height": None,
    }
    ls, rs, lh, rh = P["left_shoulder"], P["right_shoulder"], P["left_hip"], P["right_hip"]
    la, ra = P["left_ankle"], P["right_ankle"]
    if ls and rs:
        m["shoulder_tilt"] = line_tilt(ls, rs)
    if lh and rh:
        m["hip_tilt"] = line_tilt(lh, rh)
        hip = _mid(lh, rh)
        m["hip_x"], m["hip_y"] = hip
    if ls and rs and lh and rh:
        sh, hip = _mid(ls, rs), _mid(lh, rh)
        m["trunk_lean"] = lean_from_vertical(sh, hip)
        torso = math.hypot(sh[0] - hip[0], sh[1] - hip[1])
        if la and ra and torso > 1e-6:
            base = _mid(la, ra)
            # Horizontal distance of the head from the middle of the feet, in torso lengths.
            if P["nose"]:
                m["head_offset"] = (P["nose"][0] - base[0]) / torso
            width = math.hypot(la[0] - ra[0], la[1] - ra[1])
            m["stride_ratio"] = width / torso
            sw = math.hypot(ls[0] - rs[0], ls[1] - rs[1])
            if sw > 1e-6:
                m["stance_width_ratio"] = abs(la[0] - ra[0]) / sw
        lw, rw = P["left_wrist"], P["right_wrist"]
        if lw and rw and torso > 1e-6:
            m["wrist_gap_ratio"] = math.hypot(lw[0] - rw[0], lw[1] - rw[1]) / torso
            # Hands relative to the hips: + = above hip height, in torso lengths.
            m["hands_height"] = (hip[1] - (lw[1] + rw[1]) / 2.0) / torso
    if P["left_ear"] and P["right_ear"]:
        m["head_tilt"] = line_tilt(P["left_ear"], P["right_ear"])
    for side in ("left", "right"):
        w = P[f"{side}_wrist"]
        if w:
            m[f"{side}_wrist_x"], m[f"{side}_wrist_y"] = w
    return m


# ------------------------------------------------------------------ MediaPipe

_landmarker = None


def ensure_model(download: bool = True) -> str:
    """Return the path of the pose model, downloading it once if needed."""
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100_000:
        return MODEL_PATH
    if not download:
        raise PoseError(f"Pose model not found at {MODEL_PATH}.")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception as e:  # pragma: no cover - network dependent
        raise PoseError(f"Could not download the MediaPipe pose model ({e}). Download it manually from "
                        f"{MODEL_URL} and save it to {MODEL_PATH}.")
    return MODEL_PATH


def _get_landmarker():
    global _landmarker
    if _landmarker is None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except Exception as e:
            raise PoseError(f"MediaPipe is not installed ({e}). Run: pip install mediapipe")
        opts = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=ensure_model()),
            running_mode=vision.RunningMode.IMAGE, num_poses=1,
            min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5)
        _landmarker = (vision.PoseLandmarker.create_from_options(opts), mp)
    return _landmarker


def detect_pose(frame_bgr) -> Optional[np.ndarray]:
    """Landmarks (33, 4) = x, y, z, visibility for the most prominent person, or None."""
    landmarker, mp = _get_landmarker()
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.pose_landmarks:
        return None
    return np.array([[p.x, p.y, p.z, p.visibility] for p in res.pose_landmarks[0]], float)


def draw_skeleton(frame_bgr, lm: np.ndarray, colour=(48, 194, 242)):
    """Draw visible landmarks and bones on a copy of the frame."""
    img = frame_bgr.copy()
    h, w = img.shape[:2]
    pts = [(int(p[0] * w), int(p[1] * h)) if p[-1] >= MIN_VISIBILITY else None for p in lm]
    for a, b in SKELETON:
        if pts[a] and pts[b]:
            cv2.line(img, pts[a], pts[b], (255, 255, 255), 4, cv2.LINE_AA)
            cv2.line(img, pts[a], pts[b], colour, 2, cv2.LINE_AA)
    for i in LM.values():
        if pts[i]:
            cv2.circle(img, pts[i], 5, (20, 20, 20), -1, cv2.LINE_AA)
            cv2.circle(img, pts[i], 3, (255, 255, 255), -1, cv2.LINE_AA)
    return img


def _jpeg_b64(img, max_width: int = 720) -> str:
    if img.shape[1] > max_width:
        s = max_width / img.shape[1]
        img = cv2.resize(img, (max_width, int(img.shape[0] * s)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode() if ok else ""


# ------------------------------------------------------------------ sequence analysis

def _series(frames: list[dict], key: str) -> list[float]:
    return [f["metrics"][key] for f in frames if f["metrics"].get(key) is not None]


def _stat(vals: list[float]) -> Optional[dict]:
    if not vals:
        return None
    a = np.array(vals, float)
    return {"mean": float(a.mean()), "min": float(a.min()), "max": float(a.max()),
            "std": float(a.std()), "n": int(len(a))}


def summarise_sequence(frames: list[dict], mode: str = "bowling", arm: Optional[str] = None) -> dict:
    """Turn per-frame metrics into the indicators and observations for one clip.

    `frames`: [{frame, t, metrics}] (frames where a person was found).
    `mode`: "bowling", "batting" or "catching".
    """
    if len(frames) < MIN_POSE_FRAMES:
        return {"status": "insufficient", "mode": mode,
                "reason": f"A person was found in only {len(frames)} frame(s); at least {MIN_POSE_FRAMES} are needed. "
                          "Film the whole body, side-on, in good light, with one person in shot.",
                "indicators": {}, "observations": [], "disclaimer": DISCLAIMER}
    ind: dict = {}
    obs: list[dict] = []
    key_frame = None

    def add(text, evidence, kind="note"):
        obs.append({"text": text, "evidence": evidence, "kind": kind})

    for k in ("trunk_lean", "shoulder_tilt", "hip_tilt", "head_offset", "head_tilt", "stride_ratio",
              "left_knee_angle", "right_knee_angle", "left_elbow_angle", "right_elbow_angle"):
        ind[k] = _stat(_series(frames, k))

    if mode == "bowling":
        # Bowling arm = the wrist that reaches the highest point (smallest image y).
        if arm not in ("left", "right"):
            lmin = min(_series(frames, "left_wrist_y"), default=9)
            rmin = min(_series(frames, "right_wrist_y"), default=9)
            arm = "left" if lmin < rmin else "right"
        front = "right" if arm == "left" else "left"
        cands = [f for f in frames if f["metrics"].get(f"{arm}_wrist_y") is not None]
        if cands:
            key_frame = min(cands, key=lambda f: f["metrics"][f"{arm}_wrist_y"])
        ind["bowling_arm"] = arm
        if key_frame:
            km = key_frame["metrics"]
            idx = frames.index(key_frame)
            ind["release_frame"] = key_frame["frame"]
            ind["release"] = {k: km.get(k) for k in ("trunk_lean", "shoulder_tilt", "head_offset", "stride_ratio",
                                                     f"{arm}_elbow_angle", f"{front}_knee_angle",
                                                     f"{front}_shoulder_angle")}
            ind["release"]["bowling_elbow_angle"] = km.get(f"{arm}_elbow_angle")
            ind["release"]["front_knee_angle"] = km.get(f"{front}_knee_angle")
            ind["release"]["front_arm_angle"] = km.get(f"{front}_shoulder_angle")
            # Run-up: horizontal hip speed before release, and how steady it is.
            pre = [f for f in frames[:idx + 1] if f["metrics"].get("hip_x") is not None]
            if len(pre) >= 4:
                v = [abs(b["metrics"]["hip_x"] - a["metrics"]["hip_x"]) / max(b["t"] - a["t"], 1e-6)
                     for a, b in zip(pre, pre[1:])]
                mean_v = float(np.mean(v))
                ind["runup"] = {"mean_speed": mean_v, "speed_cv": float(np.std(v) / mean_v) if mean_v > 1e-6 else None,
                                "frames": len(pre)}
            # Follow-through: how far the hips keep travelling after release, in torso-normalised image units.
            post = [f for f in frames[idx:] if f["metrics"].get("hip_x") is not None]
            if len(post) >= 3:
                ind["follow_through"] = {
                    "hip_travel": abs(post[-1]["metrics"]["hip_x"] - post[0]["metrics"]["hip_x"]),
                    "trunk_lean_change": (post[-1]["metrics"]["trunk_lean"] - post[0]["metrics"]["trunk_lean"])
                    if post[-1]["metrics"].get("trunk_lean") is not None and post[0]["metrics"].get("trunk_lean") is not None else None,
                    "frames": len(post)}
            r = ind["release"]
            if r.get("head_offset") is not None:
                if abs(r["head_offset"]) > 0.45:
                    add("Head is well outside the base of support at release; work on keeping the head over the front foot.",
                        f"Head offset {r['head_offset']:+.2f} torso lengths from the midpoint of the feet (|offset| > 0.45).", "focus")
                else:
                    add("Head stays over the base of support at release.",
                        f"Head offset {r['head_offset']:+.2f} torso lengths from the midpoint of the feet.", "strength")
            if r.get("trunk_lean") is not None and abs(r["trunk_lean"]) > 30:
                add("Marked trunk lean at release. Check whether this is intended; a taller position usually helps repeatability.",
                    f"Trunk lean {r['trunk_lean']:+.0f} deg from vertical at the release frame (|lean| > 30 deg).", "focus")
            if r.get("front_knee_angle") is not None:
                if r["front_knee_angle"] >= 160:
                    add("Front leg is braced (close to straight) at release.",
                        f"Front knee angle {r['front_knee_angle']:.0f} deg at the release frame.", "strength")
                elif r["front_knee_angle"] < 140:
                    add("Front knee is flexed at release. A firmer front leg can be explored with the coach.",
                        f"Front knee angle {r['front_knee_angle']:.0f} deg at the release frame (< 140 deg).", "focus")
            if r.get("front_arm_angle") is not None and r["front_arm_angle"] < 40:
                add("Front arm has already dropped by release; try keeping it up longer to stay tall through the crease.",
                    f"Front arm is {r['front_arm_angle']:.0f} deg from the trunk at release (< 40 deg).", "focus")
            if ind.get("runup") and ind["runup"]["speed_cv"] is not None:
                cv = ind["runup"]["speed_cv"]
                add("Run-up speed is steady into the crease." if cv < 0.35 else
                    "Run-up speed varies a lot frame to frame; rhythm drills may help.",
                    f"Coefficient of variation of hip speed {cv:.2f} over {ind['runup']['frames']} frames "
                    f"({'<' if cv < 0.35 else '>='} 0.35).", "strength" if cv < 0.35 else "focus")
            if r.get("stride_ratio") is not None:
                add("Delivery stride length recorded for comparison between deliveries.",
                    f"Feet {r['stride_ratio']:.2f} torso lengths apart at release.", "note")

    elif mode == "batting":
        # Stance = first fifth of the clip; shot = frame where the hands travel fastest.
        n0 = max(2, len(frames) // 5)
        stance = frames[:n0]
        ind["stance"] = {k: _stat(_series(stance, k)) for k in
                         ("head_offset", "trunk_lean", "stance_width_ratio", "left_knee_angle", "right_knee_angle", "head_tilt")}
        speeds = []
        for a, b in zip(frames, frames[1:]):
            pa = [a["metrics"].get("left_wrist_x"), a["metrics"].get("left_wrist_y")]
            pb = [b["metrics"].get("left_wrist_x"), b["metrics"].get("left_wrist_y")]
            if None in pa or None in pb:
                pa = [a["metrics"].get("right_wrist_x"), a["metrics"].get("right_wrist_y")]
                pb = [b["metrics"].get("right_wrist_x"), b["metrics"].get("right_wrist_y")]
            if None in pa or None in pb:
                speeds.append(0.0)
                continue
            speeds.append(math.hypot(pb[0] - pa[0], pb[1] - pa[1]) / max(b["t"] - a["t"], 1e-6))
        if speeds and max(speeds) > 0:
            i = int(np.argmax(speeds)) + 1
            key_frame = frames[i]
            ind["contact_frame"] = key_frame["frame"]
            ind["peak_hand_speed"] = float(max(speeds))
            hx0 = np.mean(_series(stance, "hip_x")) if _series(stance, "hip_x") else None
            hx1 = key_frame["metrics"].get("hip_x")
            if hx0 is not None and hx1 is not None:
                ind["weight_transfer"] = float(hx1 - hx0)
                add("Weight moves forward into the shot." if abs(hx1 - hx0) > 0.03 else
                    "Little movement of the hips between stance and the shot; check that the feet are moving.",
                    f"Hips moved {abs(hx1 - hx0):.3f} of the frame width from stance to the fastest-hands frame.",
                    "strength" if abs(hx1 - hx0) > 0.03 else "focus")
            ho = key_frame["metrics"].get("head_offset")
            if ho is not None:
                add("Head is over the base at the point of the shot." if abs(ho) <= 0.45 else
                    "Head is falling outside the base at the point of the shot; balance drills are worth trying.",
                    f"Head offset {ho:+.2f} torso lengths at the fastest-hands frame.",
                    "strength" if abs(ho) <= 0.45 else "focus")
            post = frames[i:]
            hh = _series(post, "hands_height")
            if hh:
                ind["follow_through"] = {"max_hands_height": float(max(hh)), "frames": len(post)}
                add("Full follow-through: hands finish high." if max(hh) > 0.9 else
                    "Hands finish low after the shot (a checked or defensive follow-through).",
                    f"Hands reached {max(hh):.2f} torso lengths above hip height after contact.", "note")
        st = ind["stance"]
        if st.get("head_tilt") and abs(st["head_tilt"]["mean"]) > 12:
            add("Head is tilted in the stance; level eyes make judging line easier.",
                f"Ear line {st['head_tilt']['mean']:+.0f} deg from level in the stance (|tilt| > 12 deg).", "focus")
        if st.get("stance_width_ratio"):
            w = st["stance_width_ratio"]["mean"]
            add("Stance width recorded." if 0.7 <= w <= 1.6 else
                ("Stance is narrow relative to the shoulders." if w < 0.7 else "Stance is wide relative to the shoulders."),
                f"Feet {w:.2f} shoulder widths apart in the stance.", "note" if 0.7 <= w <= 1.6 else "focus")

    else:  # catching
        gaps = _series(frames, "wrist_gap_ratio")
        if gaps:
            # The catch is taken when the hands are closest together.
            cands = [f for f in frames if f["metrics"].get("wrist_gap_ratio") is not None]
            key_frame = min(cands, key=lambda f: f["metrics"]["wrist_gap_ratio"])
            km = key_frame["metrics"]
            ind["hands_together_frame"] = key_frame["frame"]
            ind["catch"] = {k: km.get(k) for k in ("wrist_gap_ratio", "hands_height", "head_offset", "trunk_lean",
                                                   "left_knee_angle", "right_knee_angle")}
            add("Hands come together for the catch.",
                f"Smallest distance between the wrists: {km['wrist_gap_ratio']:.2f} torso lengths.", "note")
            if km.get("hands_height") is not None:
                where = "above the shoulders" if km["hands_height"] > 1.0 else "between waist and chest" if km["hands_height"] > 0 else "below the waist"
                add(f"Catch taken {where}.", f"Hands {km['hands_height']:+.2f} torso lengths relative to hip height.", "note")
            if km.get("head_offset") is not None:
                add("Balanced at the catch: head over the feet." if abs(km["head_offset"]) <= 0.45 else
                    "Off balance at the catch: head outside the feet. Work on getting the feet to the ball earlier.",
                    f"Head offset {km['head_offset']:+.2f} torso lengths at the hands-together frame.",
                    "strength" if abs(km["head_offset"]) <= 0.45 else "focus")
            knees = [km.get("left_knee_angle"), km.get("right_knee_angle")]
            knees = [k for k in knees if k is not None]
            if knees:
                add("Knees are flexed, giving a soft base." if min(knees) < 160 else
                    "Legs are nearly straight at the catch; a lower, flexed base absorbs the ball better.",
                    f"Smallest knee angle {min(knees):.0f} deg at the catch.", "strength" if min(knees) < 160 else "focus")
        else:
            add("Both wrists were not visible together, so hand placement could not be measured.",
                "No frame had both wrists above the visibility threshold.", "note")
        hx = _series(frames, "hip_x")
        hy = _series(frames, "hip_y")
        if len(hx) >= 2:
            ind["movement"] = {"hip_travel_x": float(max(hx) - min(hx)), "hip_travel_y": float(max(hy) - min(hy))}
            add("Movement to the ball recorded.",
                f"Hips travelled {ind['movement']['hip_travel_x']:.2f} of the frame width and "
                f"{ind['movement']['hip_travel_y']:.2f} of the frame height during the clip.", "note")

    return {"status": "ok", "mode": mode, "frames_with_pose": len(frames), "indicators": ind,
            "observations": obs, "key_frame": key_frame["frame"] if key_frame else None,
            "disclaimer": DISCLAIMER}


def analyse_video(path: str, mode: str = "bowling", arm: Optional[str] = None, sample_every: Optional[int] = None,
                  max_frames: int = 90, annotate: int = 6) -> dict:
    """Run pose estimation over a clip and return indicators, observations and annotated frames."""
    cap, info = open_video(path)
    cap.release()
    total = info["frame_count"] or max_frames
    every = sample_every or max(1, math.ceil(total / max_frames))
    frames, kept_images = [], {}
    processed = 0
    for idx, t, frame in extract_frames(path, every=every, max_frames=max_frames, resize_width=960):
        processed += 1
        lm = detect_pose(frame)
        if lm is None:
            continue
        aspect = frame.shape[1] / frame.shape[0]
        frames.append({"frame": idx, "t": t, "metrics": frame_metrics(lm, aspect),
                       "landmarks": [[round(float(p[0]), 4), round(float(p[1]), 4), round(float(p[3]), 2)] for p in lm]})
        kept_images[idx] = (frame, lm)
    if processed == 0:
        raise VideoError("No frames could be read from the video.")
    summary = summarise_sequence(frames, mode, arm)
    summary.update({"video": info, "frames_processed": processed, "sampled_every": every,
                    "pose_detection_rate": len(frames) / processed})
    # Annotated frames: the key frame plus evenly spaced others.
    chosen = []
    if summary.get("key_frame") is not None:
        chosen.append(summary["key_frame"])
    ids = list(kept_images)
    if ids:
        step = max(1, len(ids) // max(annotate - 1, 1))
        chosen += [i for i in ids[::step] if i not in chosen]
    summary["annotated_frames"] = [
        {"frame": i, "key": i == summary.get("key_frame"),
         "image": "data:image/jpeg;base64," + _jpeg_b64(draw_skeleton(*kept_images[i]))}
        for i in sorted(chosen[:annotate])]
    summary["series"] = [{"frame": f["frame"], "t": f["t"],
                          **{k: f["metrics"].get(k) for k in ("trunk_lean", "shoulder_tilt", "head_offset",
                                                              "left_knee_angle", "right_knee_angle",
                                                              "left_elbow_angle", "right_elbow_angle", "stride_ratio")}}
                         for f in frames]
    key = next((f for f in frames if f["frame"] == summary.get("key_frame")), None)
    summary["key_landmarks"] = key["landmarks"] if key else None
    return summary


def compare_analyses(a: dict, b: dict) -> dict:
    """Differences between two clips' key indicators (B minus A)."""
    def flat(s):
        out = {}
        ind = s.get("indicators", {})
        for group in ("release", "catch"):
            for k, v in (ind.get(group) or {}).items():
                if isinstance(v, (int, float)):
                    out[f"{group}.{k}"] = v
        for group in ("stance",):
            for k, v in (ind.get(group) or {}).items():
                if v:
                    out[f"{group}.{k}"] = v["mean"]
        for k in ("trunk_lean", "shoulder_tilt", "head_offset", "stride_ratio"):
            if ind.get(k):
                out[f"mean.{k}"] = ind[k]["mean"]
        if ind.get("runup") and ind["runup"].get("speed_cv") is not None:
            out["runup.speed_cv"] = ind["runup"]["speed_cv"]
        for k in ("weight_transfer", "peak_hand_speed"):
            if isinstance(ind.get(k), (int, float)):
                out[k] = ind[k]
        return out

    fa, fb = flat(a), flat(b)
    rows = [{"metric": k, "a": fa[k], "b": fb[k], "difference": fb[k] - fa[k]} for k in fa if k in fb]
    return {"rows": rows, "only_in_a": sorted(set(fa) - set(fb)), "only_in_b": sorted(set(fb) - set(fa)),
            "note": "Differences are meaningful only if both clips were filmed from the same camera position. "
                    "Differences of a few degrees are within pose-estimation error.",
            "disclaimer": DISCLAIMER}
