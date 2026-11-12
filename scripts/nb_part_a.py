"""Notebooks 01-04: bowling speed, bowling action, ball tracking, DRS."""
from nb_common import closing, header

NB01 = header(
    "01 · Bowling Speed Analysis",
    "Work out a bowler's speed from a distance and a time, convert between units, and study a season of speed readings.",
) + [
    ("md", "## 1. The formula\n\n"
           "$$\\text{average speed} = \\frac{\\text{distance}}{\\text{time}}$$\n\n"
           "If a ball covers 18.9 m (popping crease to the far stumps) in 0.62 s, its average speed is "
           "18.9 / 0.62 = 30.5 m/s.\n\n"
           "**This is an average speed, not a release speed.** A cricket ball slows down through the air and loses more "
           "speed when it bounces, so the average over the whole flight is lower than the speed as it left the hand. "
           "A radar gun reads close to release speed. The two numbers are different quantities and should not be mixed.\n\n"
           "### Unit conversions (exact)\n"
           "| From | To metres / seconds |\n|---|---|\n| 1 foot | 0.3048 m |\n| 1 yard | 0.9144 m |\n| 1 millisecond | 0.001 s |\n\n"
           "| Speed | Multiply m/s by |\n|---|---|\n| km/h | 3.6 |\n| mph | 3600 / 1609.344 = 2.23694 |"),
    ("code", '''# Write the calculation out by hand first, so every step is visible.
DISTANCE_TO_M = {"m": 1.0, "ft": 0.3048, "yd": 0.9144}
TIME_TO_S = {"s": 1.0, "ms": 0.001}

def speed_by_hand(distance, time, distance_unit="m", time_unit="s"):
    """Average speed in m/s, km/h and mph."""
    if distance <= 0 or time <= 0:
        raise ValueError("Distance and time must both be greater than zero.")
    metres = distance * DISTANCE_TO_M[distance_unit]
    seconds = time * TIME_TO_S[time_unit]
    ms = metres / seconds
    return {"m/s": ms, "km/h": ms * 3.6, "mph": ms * 3600 / 1609.344}

print(speed_by_hand(18.9, 0.62))
print(speed_by_hand(22, 500, "yd", "ms"))      # a full 22-yard pitch in half a second'''),
    ("code", '''# The application uses pitchvision.speed.average_speed. Check that it gives exactly the same answers.
from pitchvision import speed

for args in [(18.9, 0.62, "m", "s"), (22, 500, "yd", "ms"), (62, 0.7, "ft", "s")]:
    mine = speed_by_hand(*args)
    app = speed.average_speed(*args)
    assert abs(mine["km/h"] - app["speed_kmh"]) < 1e-9 and abs(mine["mph"] - app["speed_mph"]) < 1e-9
    print(f"{args}: {app['speed_kmh']:.2f} km/h = {app['speed_mph']:.2f} mph   (kind: {app['kind']})")

# Bad input is rejected with a clear message rather than giving a silly answer.
try:
    speed.average_speed(18.9, 0)
except speed.SpeedInputError as e:
    print("Rejected:", e)'''),
    ("md", "## 2. Load the speed readings\n\nEach row is one timed delivery. `source` says how it was measured: "
           "`stopwatch` rows have a distance and a time; `radar` rows only have the radar's km/h figure."),
    ("code", '''readings = pd.read_csv(DATA / "speeds.csv", parse_dates=["date"])
print(len(readings), "readings for", readings["player"].nunique(), "bowlers")
readings.head()'''),
    ("md", "### Missing data\n\nSome stopwatch rows have no time recorded. We cannot work out a speed for those, so they are "
           "counted and left out. We never fill in a guessed value."),
    ("code", '''stopwatch = readings[readings["source"] == "stopwatch"].copy()
missing = stopwatch["time_s"].isna().sum()
print(f"{missing} stopwatch readings have no time and are left out.")
stopwatch = stopwatch.dropna(subset=["time_s", "distance_m"])

# Recalculate every speed from distance and time, and compare with the km/h stored in the file.
stopwatch["kmh_calc"] = stopwatch["distance_m"] / stopwatch["time_s"] * 3.6
print("Largest difference from the stored value:", (stopwatch["kmh_calc"] - stopwatch["kmh"]).abs().max().round(2), "km/h (rounding)")
radar = readings[readings["source"] == "radar"].dropna(subset=["kmh"])'''),
    ("md", "## 3. Speed statistics per bowler\n\n"
           "The mean is the sum of the readings divided by how many there are. The standard deviation says how spread out "
           "they are, so a small value means the bowler's pace is consistent. The table also gives the fastest, slowest "
           "and latest reading."),
    ("code", '''summary = (stopwatch.sort_values("date").groupby("player")["kmh_calc"]
           .agg(readings="count", average="mean", fastest="max", slowest="min", spread="std", recent="last")
           .round(1).sort_values("average", ascending=False))
summary'''),
    ("code", '''# Same figures from the shared module (this is what the Bowling Lab shows).
name = summary.index[0]
vals = stopwatch[stopwatch["player"] == name].sort_values("date")["kmh_calc"].tolist()
s = speed.speed_summary(vals)
print(name, {k: round(v, 1) if isinstance(v, float) else v for k, v in s.items()})
assert abs(s["average"] - summary.loc[name, "average"]) < 0.06'''),
    ("md", "## 4. Speed distributions"),
    ("code", '''pace = summary.head(5).index
fig, ax = plt.subplots()
ax.boxplot([stopwatch.loc[stopwatch["player"] == p, "kmh_calc"] for p in pace])
ax.set_xticklabels([p.split()[0] for p in pace])      # works on old and new matplotlib
ax.set_ylabel("Average ball speed (km/h)")
ax.set_title("Spread of timed deliveries (SYNTHETIC data)")
plt.show()

fig, ax = plt.subplots()
ax.hist(stopwatch.loc[stopwatch["player"] == name, "kmh_calc"], bins=10, color=INK)
ax.set_xlabel("Average ball speed (km/h)"); ax.set_ylabel("Deliveries")
ax.set_title(f"{name}: distribution of timed speeds (SYNTHETIC data)")
plt.show()'''),
    ("md", "## 5. Speed over the season"),
    ("code", '''by_session = stopwatch.groupby(["player", "date"])["kmh_calc"].mean().reset_index()
fig, ax = plt.subplots()
for p, colour in zip(pace[:3], [INK, GREEN, RED]):
    d = by_session[by_session["player"] == p]
    ax.plot(d["date"], d["kmh_calc"], marker="o", color=colour, label=p)
ax.set_ylabel("Session average (km/h)"); ax.set_title("Session-by-session speed (SYNTHETIC data)"); ax.legend()
fig.autofmt_xdate(); plt.show()

trend = speed.speed_trend(vals)
print(f"{name}: change from the first third to the last third of readings = {trend['change_first_to_last_third']:+.1f} km/h")'''),
    ("md", "## 6. Radar against stopwatch\n\nWhere a bowler has both kinds of reading on the same day we can compare them. "
           "We expect the radar figure to be **higher**, because it is taken near release and the stopwatch figure is an "
           "average over the whole flight."),
    ("code", '''sw_day = stopwatch.groupby(["player", "date"])["kmh_calc"].mean().rename("stopwatch_kmh")
rd_day = radar.groupby(["player", "date"])["kmh"].mean().rename("radar_kmh")
both = pd.concat([sw_day, rd_day], axis=1).dropna()
both["difference"] = both["radar_kmh"] - both["stopwatch_kmh"]
both["stopwatch as % of radar"] = both["stopwatch_kmh"] / both["radar_kmh"] * 100
print("Days with both kinds of reading:", len(both))
print("Radar reads higher by", round(both["difference"].mean(), 1), "km/h on average")
print("Timed (average) speed is", round(both["stopwatch as % of radar"].mean(), 1), "% of the radar speed")

fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.scatter(both["radar_kmh"], both["stopwatch_kmh"], color=INK)
lims = [both.min().min() - 3, both[["radar_kmh", "stopwatch_kmh"]].max().max() + 3]
ax.plot(lims, lims, "--", color=RED, label="equal")
ax.set_xlabel("Radar (near release), km/h"); ax.set_ylabel("Distance / time (average), km/h")
ax.set_title("Timed speed sits below radar speed (SYNTHETIC data)"); ax.legend(); plt.show()

summary.to_csv(EXPORTS / "bowling_speed_summary.csv")
print("Saved", EXPORTS / "bowling_speed_summary.csv")'''),
] + closing(
    "- Average speed is distance divided by time; the unit conversions are exact constants.\n"
    "- The hand calculation and `pitchvision.speed` agree to nine decimal places.\n"
    "- In the synthetic data the timed speed is about 88% of the radar speed, because that is how the sample was generated.",
    "A timed speed is useful for tracking **one bowler against themselves** using the same method each time. "
    "It is not comparable with a radar reading or with speeds quoted on television.",
    "- A hand-held stopwatch has a reaction-time error of about 0.1-0.2 s, which is large next to a 0.6 s flight. "
    "Timing from high-frame-rate video is far better.\n- The measured distance must be the real distance the ball travelled.\n"
    "- The ratio between average and release speed varies with length and pitch; do not use a fixed factor to 'convert' one into the other.\n"
    "- All figures shown come from synthetic data.",
    "The Bowling Lab's speed calculator calls `pitchvision.speed.average_speed` through `POST /api/speed/calculate`; the history, "
    "average, fastest, slowest and most recent figures come from `speed_summary`; the radar comparison uses "
    "`compare_radar_to_estimate`. The browser's live calculator uses the same constants and is tested against the same known values.",
)

# ---------------------------------------------------------------------------------------------------------------

NB02 = header(
    "02 · Bowling Action Analysis",
    "Load a video, pull out frames, find body landmarks with MediaPipe, and turn them into joint angles and movement indicators.",
    "numpy, matplotlib, opencv-python-headless, mediapipe",
) + [
    ("md", "## 1. What pose estimation can and cannot tell you\n\n"
           "MediaPipe Pose finds 33 body landmarks (shoulders, elbows, hips, knees, ankles...) in each frame. From them "
           "we can measure **2-D angles as the camera sees them**.\n\n"
           "It **cannot** diagnose an injury, say whether an action is medically safe, or decide whether a bowling action "
           "is legal. Testing elbow extension needs calibrated 3-D motion capture in an accredited laboratory. Angles here "
           "change with the camera position, so only compare clips filmed from the same spot."),
    ("md", "## 2. Use your own video\n\nPut a clip in the project folder and set `VIDEO_PATH` below (in Colab, upload it "
           "with the file browser on the left, or run `from google.colab import files; files.upload()`). Film side-on with "
           "the whole body in shot. If `VIDEO_PATH` stays `None`, the notebook runs on **synthetic landmarks** instead so "
           "every calculation can still be followed."),
    ("code", '''VIDEO_PATH = None          # e.g. "my_bowling_clip.mp4"
MODE = "bowling"            # "bowling", "batting" or "catching"

from pitchvision import pose, tracking
import cv2
print("OpenCV", cv2.__version__)'''),
    ("md", "## 3. Joint angles\n\nThe angle at joint **B** between points **A** and **C** comes from the dot product:\n\n"
           "$$\\cos\\theta = \\frac{\\vec{BA}\\cdot\\vec{BC}}{|\\vec{BA}|\\,|\\vec{BC}|}$$\n\n"
           "For the elbow, A is the shoulder, B the elbow and C the wrist. A straight arm gives 180 degrees."),
    ("code", '''def angle_by_hand(a, b, c):
    """Angle ABC in degrees from three (x, y) points."""
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    cos_theta = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    return float(np.degrees(np.arccos(np.clip(cos_theta, -1, 1))))

print("Straight arm :", angle_by_hand((0, 0), (1, 0), (2, 0)))
print("Right angle  :", angle_by_hand((0, 0), (1, 0), (1, 1)))
print("Bent 60 deg  :", round(angle_by_hand((0, 0), (1, 0), (1.5, 0.866)), 1))

# The shared module gives the same answers.
for pts in [((0, 0), (1, 0), (2, 0)), ((0, 0), (1, 0), (1, 1)), ((0.2, 0.9), (0.5, 0.4), (0.9, 0.7))]:
    assert abs(angle_by_hand(*pts) - pose.angle_between(*pts)) < 1e-9
print("angle_by_hand matches pitchvision.pose.angle_between")'''),
    ("md", "## 4. A synthetic bowling action\n\nThe function below builds a simple stick figure for each frame: a run-up, "
           "a delivery stride, the bowling arm coming over, and a follow-through. `style` changes the action so we can "
           "compare two deliveries. **These are made-up landmark positions, not a real person.**"),
    ("code", '''L = pose.LM     # landmark name -> index in MediaPipe's list of 33

def synthetic_delivery(n_frames=30, lean=8.0, front_knee=172.0, head_drift=0.02, speed_wobble=0.0, seed=0):
    """Return frames of fake landmarks: each is an array (33, 4) of x, y, z, visibility (normalised 0-1)."""
    rng = np.random.default_rng(seed)
    frames = []
    release = int(n_frames * 0.6)
    for f in range(n_frames):
        t = f / (n_frames - 1)
        lm = np.zeros((33, 4)); lm[:, 3] = 0.0
        x0 = 0.15 + 0.6 * t + speed_wobble * np.sin(f * 1.7) * 0.01         # moving across the frame
        hip = np.array([x0, 0.55])
        after = max(0.0, (f - release) / (n_frames - release))
        tilt = np.radians(lean + 25 * after)                                 # leans forward in the follow-through
        sh = hip + 0.22 * np.array([np.sin(tilt), -np.cos(tilt)])
        head = sh + np.array([head_drift * (f / release) if f <= release else head_drift + 0.05 * after, -0.09])
        stride = 0.05 + 0.13 * min(1.0, f / release)
        knee_bend = np.radians(180 - front_knee)
        ankle_f = hip + np.array([stride, 0.33]); ankle_b = hip + np.array([-stride, 0.33])
        knee_f = (hip + ankle_f) / 2 + np.array([0.06 * np.sin(knee_bend), 0.0])
        knee_b = (hip + ankle_b) / 2 + np.array([-0.01, 0.0])
        swing = np.pi * min(1.0, f / release)                                 # bowling arm rotates up and over
        arm = 0.2 * np.array([-np.cos(swing) * 0.6, -np.sin(swing)])
        wrist_b = sh + arm; elbow_b = sh + arm / 2
        front_up = max(0.0, 1 - f / release)
        elbow_f = sh + np.array([0.08, -0.08 * front_up + 0.05]); wrist_f = elbow_f + np.array([0.07, -0.08 * front_up + 0.06])
        pts = {"nose": head, "left_ear": head + [-0.015, 0], "right_ear": head + [0.015, 0],
               "left_shoulder": sh + [-0.025, 0], "right_shoulder": sh + [0.025, 0.0],
               "left_elbow": elbow_f, "left_wrist": wrist_f, "right_elbow": elbow_b, "right_wrist": wrist_b,
               "left_hip": hip + [-0.02, 0], "right_hip": hip + [0.02, 0],
               "left_knee": knee_f, "right_knee": knee_b, "left_ankle": ankle_f, "right_ankle": ankle_b,
               "left_heel": ankle_f + [-0.01, 0.01], "right_heel": ankle_b + [-0.01, 0.01],
               "left_foot_index": ankle_f + [0.03, 0.01], "right_foot_index": ankle_b + [0.03, 0.01]}
        for name, p in pts.items():
            lm[L[name], :2] = np.array(p) + rng.normal(0, 0.002, 2)          # a little landmark jitter
            lm[L[name], 3] = 0.95
        frames.append(lm)
    return frames

delivery_a = synthetic_delivery(seed=1)
print(len(delivery_a), "frames, each with", delivery_a[0].shape[0], "landmarks")'''),
    ("code", '''def draw_figure(ax, lm, title=""):
    for a, b in pose.SKELETON:
        if lm[a, 3] > 0.5 and lm[b, 3] > 0.5:
            ax.plot([lm[a, 0], lm[b, 0]], [lm[a, 1], lm[b, 1]], color=INK, lw=2)
    seen = lm[:, 3] > 0.5
    ax.scatter(lm[seen, 0], lm[seen, 1], color=YELLOW, edgecolor=INK, zorder=3, s=30)
    ax.set_xlim(0, 1); ax.set_ylim(1, 0); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    ax.set_title(title, fontsize=10)

fig, axes = plt.subplots(1, 5, figsize=(14, 3.2))
for ax, f in zip(axes, [0, 8, 14, 18, 28]):
    draw_figure(ax, delivery_a[f], f"frame {f}")
fig.suptitle("Synthetic landmarks through one delivery (not a real person)"); plt.show()'''),
    ("md", "## 5. Measurements for each frame\n\n`pose.frame_metrics` turns one frame's landmarks into indicators:\n\n"
           "| Indicator | Meaning |\n|---|---|\n| elbow / knee angle | interior joint angle in degrees |\n"
           "| trunk lean | tilt of the hip-to-shoulder line from vertical |\n| shoulder tilt | tilt of the shoulder line from level |\n"
           "| head offset | how far the head is sideways from the middle of the feet, in torso lengths (a balance indicator) |\n"
           "| stride ratio | distance between the feet, in torso lengths |\n\n"
           "A landmark with visibility below 0.5 is treated as missing, and any indicator that needs it is left empty."),
    ("code", '''def measure(frames, fps=30.0):
    return [{"frame": i, "t": i / fps, "metrics": pose.frame_metrics(lm)} for i, lm in enumerate(frames)]

seq_a = measure(delivery_a)
table = pd.DataFrame([{"frame": f["frame"], **{k: f["metrics"][k] for k in
                      ("trunk_lean", "shoulder_tilt", "head_offset", "stride_ratio", "left_knee_angle", "right_elbow_angle")}} for f in seq_a])
table.round(2).iloc[::5]'''),
    ("code", '''fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
axes[0].plot(table["frame"], table["trunk_lean"], color=INK); axes[0].set_title("Trunk lean (degrees from vertical)")
axes[1].plot(table["frame"], table["left_knee_angle"], color=GREEN); axes[1].set_title("Front knee angle (degrees)")
axes[2].plot(table["frame"], table["head_offset"], color=RED); axes[2].set_title("Head offset (torso lengths)")
for ax in axes: ax.set_xlabel("frame")
plt.show()'''),
    ("md", "## 6. Summarising the delivery\n\n`pose.summarise_sequence` finds the **release frame** (the frame where the "
           "bowling wrist is highest), reads the indicators at that moment, measures how steady the run-up speed was "
           "(coefficient of variation = standard deviation / mean of the hip's speed), and writes coaching observations. "
           "Every observation states the measurement that triggered it."),
    ("code", '''summary_a = pose.summarise_sequence(seq_a, mode="bowling")
print("Status:", summary_a["status"], "| bowling arm:", summary_a["indicators"]["bowling_arm"], "| release frame:", summary_a["key_frame"])
for o in summary_a["observations"]:
    print(f"- [{o['kind']}] {o['text']}\\n    measured: {o['evidence']}")
print("\\n" + summary_a["disclaimer"])'''),
    ("md", "## 7. Comparing two deliveries\n\nDelivery B is generated with a flexed front knee, more trunk lean, a head that "
           "falls away, and an uneven run-up."),
    ("code", '''delivery_b = synthetic_delivery(lean=24, front_knee=132, head_drift=0.14, speed_wobble=3.0, seed=2)
summary_b = pose.summarise_sequence(measure(delivery_b), mode="bowling")
comparison = pose.compare_analyses(summary_a, summary_b)
pd.DataFrame(comparison["rows"]).round(2)'''),
    ("code", '''fig, axes = plt.subplots(1, 2, figsize=(8, 4))
draw_figure(axes[0], delivery_a[summary_a["key_frame"]], "Delivery A at release")
draw_figure(axes[1], delivery_b[summary_b["key_frame"]], "Delivery B at release")
plt.show()
print("Observations for delivery B:")
for o in summary_b["observations"]:
    print(f"- [{o['kind']}] {o['text']}  ({o['evidence']})")
print("\\n" + comparison["note"])'''),
    ("md", "## 8. Too little to measure\n\nIf a person is found in fewer than five frames, nothing is reported."),
    ("code", '''short = pose.summarise_sequence(measure(delivery_a[:3]), mode="bowling")
print(short["status"], "-", short["reason"])'''),
    ("md", "## 9. The video pipeline\n\nThis section runs on a real file. With no video supplied it writes a tiny synthetic "
           "clip (a moving dot, no person) to show frame extraction working and to show what happens when MediaPipe finds nobody."),
    ("code", '''import tempfile, os
path = VIDEO_PATH
if path is None:
    path = os.path.join(tempfile.mkdtemp(), "synthetic_no_person.mp4")
    tracking.write_synthetic_ball_video(path)
    print("No video supplied: using a synthetic clip with no person in it.")

cap, info = tracking.open_video(path); cap.release()
print("Video:", info)
frames = list(tracking.extract_frames(path, every=max(1, info["frame_count"] // 6), max_frames=6))
fig, axes = plt.subplots(1, len(frames), figsize=(14, 2.6))
for ax, (idx, t, img) in zip(axes, frames):
    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); ax.set_title(f"frame {idx}", fontsize=9); ax.axis("off")
plt.show()'''),
    ("code", '''# Full analysis: MediaPipe on the sampled frames, then the same summary as above.
try:
    result = pose.analyse_video(path, mode=MODE)
    print("Status:", result["status"], "| frames with a person:", result.get("frames_with_pose", 0), "of", result["frames_processed"])
    if result["status"] != "ok":
        print("Reason:", result["reason"])
    else:
        for o in result["observations"]:
            print(f"- [{o['kind']}] {o['text']}  ({o['evidence']})")
        import base64, io
        from PIL import Image
        shots = result["annotated_frames"][:4]
        fig, axes = plt.subplots(1, len(shots), figsize=(14, 4))
        for ax, s in zip(np.atleast_1d(axes), shots):
            ax.imshow(Image.open(io.BytesIO(base64.b64decode(s["image"].split(",")[1])))); ax.axis("off")
            ax.set_title(f"frame {s['frame']}" + (" (key frame)" if s["key"] else ""))
        plt.show()
except pose.PoseError as e:
    print("Pose estimation is not available here:", e)
except tracking.VideoError as e:
    print("The video could not be read:", e)'''),
] + closing(
    "- Joint angles come from the dot-product formula; the hand version and `pitchvision.pose.angle_between` agree exactly.\n"
    "- On the synthetic figures, the analysis picks out the release frame and reports the differences that were built into delivery B "
    "(flexed front knee, more trunk lean, head outside the base, uneven run-up).\n"
    "- With too few frames, or no person in the clip, the result is 'insufficient' rather than a guess.",
    "The indicators are best used to compare one bowler's deliveries with each other, filmed from the same position. "
    "Thresholds in the observations (for example a front knee below 140 degrees) are coaching rules of thumb, not standards.",
    "- 2-D angles from one camera change with camera position and lens.\n- Fast arm movement blurs at 30 fps; landmarks on the bowling arm are least reliable near release.\n"
    "- Differences of a few degrees are within the model's error.\n- No medical, injury-risk or legality conclusion can be drawn.\n"
    "- The demonstration above uses synthetic landmarks; the real-video path was exercised only on a clip with no person in it.",
    "The Bowling Lab (Action analyzer), Batting Lab (Action analyzer) and Fielding Lab (Catching technique) upload a clip to "
    "`POST /api/video/pose`, which calls `pitchvision.pose.analyse_video`: the same `frame_metrics`, `summarise_sequence` and "
    "`compare_analyses` used here.",
)

# ---------------------------------------------------------------------------------------------------------------

NB03 = header(
    "03 · Cricket Ball Tracking",
    "Find a cricket ball in video frames with OpenCV, follow it with a Kalman filter, and be honest about how well that worked.",
    "numpy, matplotlib, opencv-python-headless",
) + [
    ("md", "## 1. Use your own video\n\nSet `VIDEO_PATH` to a clip of one delivery filmed from a fixed camera. With "
           "`VIDEO_PATH = None` the notebook writes a **synthetic** clip (a red dot that flies, bounces and rises) for "
           "which the true ball position is known in every frame, so tracking error can be measured."),
    ("code", '''VIDEO_PATH = None        # e.g. "delivery.mp4"
BALL_COLOUR = "red"      # "red", "white", "pink" or None (motion only)

import cv2, os, tempfile
from pitchvision import tracking, trajectory

truth = None
path = VIDEO_PATH
if path is None:
    path = os.path.join(tempfile.mkdtemp(), "synthetic_ball.mp4")
    truth = tracking.write_synthetic_ball_video(path, noise=4.0, seed=3)
    print("Using a SYNTHETIC clip with known ball positions.")
cap, info = tracking.open_video(path); cap.release()
info'''),
    ("md", "## 2. Step by step on one frame\n\n1. **Background subtraction** learns what the still scene looks like and "
           "marks pixels that changed.\n2. **Contours** outline each moving blob.\n3. Each blob is scored for **roundness**: "
           "circularity = 4π·area / perimeter² (1.0 for a perfect circle), and optionally for matching the ball's colour."),
    ("code", '''bg = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=28, detectShadows=False)
frames = list(tracking.extract_frames(path, max_frames=80, resize_width=960))
masks = [bg.apply(img) for _, _, img in frames]
k = min(len(frames) - 1, 24)                                   # a frame part-way through the flight
idx, t, img = frames[k]
candidates = tracking.detect_candidates(img, masks[k], BALL_COLOUR)

fig, axes = plt.subplots(1, 3, figsize=(15, 3.6))
axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); axes[0].set_title(f"frame {idx}")
axes[1].imshow(masks[k], cmap="gray"); axes[1].set_title("moving pixels (foreground mask)")
axes[2].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); axes[2].set_title(f"{len(candidates)} ball-like blob(s)")
for c in candidates:
    axes[2].add_patch(plt.Circle((c["x"], c["y"]), max(c["r"] * 2.5, 8), fill=False, color=YELLOW, lw=2))
for ax in axes: ax.axis("off")
plt.show()
pd.DataFrame(candidates).round(2)'''),
    ("md", "## 3. Linking detections with a Kalman filter\n\nThe filter keeps an estimate of the ball's position and velocity. "
           "Each frame it **predicts** where the ball should be, then **corrects** itself with the nearest detection. A "
           "detection far from the prediction is ignored. If the ball is not found, the filter coasts for up to four frames; "
           "those positions are marked `observed = False` so they are never mistaken for measurements."),
    ("code", '''result = tracking.track_ball(path, colour=BALL_COLOUR)
print("Status:", result["status"])
print("Observed points :", result["observed_count"])
print("Predicted points:", result["predicted_count"], "(filled in while the ball was not detected)")
print("Detection rate  :", round(result["detection_rate"] * 100), "%")
print("Confidence      :", result["confidence_label"], f"({result['confidence']:.2f})")
track = pd.DataFrame(result["points"])
track.head(8).round(2)'''),
    ("code", '''fig, ax = plt.subplots(figsize=(9, 5))
ax.imshow(cv2.cvtColor(frames[0][2], cv2.COLOR_BGR2RGB), alpha=0.55,
          extent=[0, info["width"], info["height"], 0])
obs, pred = track[track["observed"]], track[~track["observed"]]
ax.plot(track["x"], track["y"], color=INK, lw=1, alpha=0.5)
ax.scatter(obs["x"], obs["y"], color=INK, s=28, label="observed")
ax.scatter(pred["x"], pred["y"], facecolors="none", edgecolors=RED, s=60, label="predicted (ball not detected)")
if truth:
    tr = pd.DataFrame(truth["truth"]); ax.plot(tr["x"], tr["y"], "--", color=YELLOW, lw=1.5, label="true path (synthetic)")
ax.set_title("Tracked ball positions"); ax.legend(); ax.grid(False); plt.show()'''),
    ("md", "## 4. How accurate was it?\n\nOnly possible because the clip is synthetic and the true position is known."),
    ("code", '''if truth:
    tr = pd.DataFrame(truth["truth"]).set_index("frame")
    joined = obs.set_index("frame").join(tr, rsuffix="_true").dropna(subset=["x_true"])
    err = np.hypot(joined["x"] - joined["x_true"], joined["y"] - joined["y_true"])
    print(f"Mean error {err.mean():.2f} px, worst {err.max():.2f} px over {len(err)} observed points")
    print(f"Ball visible in {len(tr)} frames; detected in {len(joined)} ({len(joined) / len(tr) * 100:.0f}%)")
    bounce = trajectory.detect_bounce(result["points"])
    print("Bounce found at frame", bounce.get("frame"), "| true bounce frame", truth["bounce_frame"])
else:
    print("No ground truth for a real video: accuracy cannot be measured, only the confidence indicators above.")'''),
    ("md", "## 5. What makes tracking fail\n\nWe add more and more camera noise to the synthetic clip and watch the detection "
           "rate. Real footage has worse problems (motion blur, a tiny ball, players in the way)."),
    ("code", '''rows = []
for noise in [0, 4, 8, 14, 22]:
    p = os.path.join(tempfile.mkdtemp(), f"noise_{noise}.mp4")
    t_ = tracking.write_synthetic_ball_video(p, noise=noise, seed=5)
    r = tracking.track_ball(p, colour="red")
    rows.append({"noise": noise, "status": r["status"], "observed": r["observed_count"], "true_frames": len(t_["truth"]),
                 "confidence": round(r["confidence"], 2), "label": r["confidence_label"]})
noise_table = pd.DataFrame(rows); noise_table'''),
    ("code", '''fig, ax = plt.subplots()
ax.plot(noise_table["noise"], noise_table["observed"] / noise_table["true_frames"] * 100, marker="o", color=INK)
ax.set_xlabel("Camera noise added (standard deviation, grey levels)"); ax.set_ylabel("Ball frames detected (%)")
ax.set_ylim(0, 105); ax.set_title("Detection falls as the picture gets noisier (SYNTHETIC clips)"); plt.show()

# A clip with nothing moving gives 'insufficient', not an error and not an invented track.
still = os.path.join(tempfile.mkdtemp(), "still.mp4")
w = cv2.VideoWriter(still, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 180))
for _ in range(20): w.write(np.full((180, 320, 3), 90, np.uint8))
w.release()
r = tracking.track_ball(still)
print(r["status"], "-", r["reason"])
track.to_csv(EXPORTS / "ball_track_example.csv", index=False)'''),
] + closing(
    "- Background subtraction plus a roundness test finds the ball in the synthetic clip; a Kalman filter links the detections.\n"
    "- On the clean synthetic clip the mean position error is around a pixel and the bounce frame is found within a frame or two.\n"
    "- Detection falls away as picture noise rises, and a clip with no moving ball returns 'insufficient'.",
    "Tracking quality depends far more on the footage than on the algorithm. A fixed camera, good light, a ball that contrasts "
    "with the background and a high frame rate (120-240 fps) matter most.",
    "- At 30 fps a 100 km/h ball moves about 0.9 m between frames and smears into a streak.\n- The ball is a few pixels wide in a wide shot and is hidden by the bowler and batter.\n"
    "- Any small round moving object can be mistaken for the ball.\n- Positions are pixels, not metres: one camera cannot measure depth.\n"
    "- The accuracy figures here come from a synthetic clip with a clean, bright ball; real footage will be worse.",
    "The Bowling Lab (Ball tracking, Swing and seam) and DRS Studio upload a clip to `POST /api/video/track`, which calls "
    "`pitchvision.tracking.track_ball` and returns the same observed/predicted points, detection rate and confidence shown here.",
)

# ---------------------------------------------------------------------------------------------------------------

NB04 = header(
    "04 · DRS and Trajectory Simulation",
    "Fit a ball's path, project it to the stumps with a simple physical model, and show how uncertain the answer is. "
    "An **educational** simulation: it is not Hawk-Eye and not an umpiring tool.",
) + [
    ("md", "## 1. Why one camera cannot reproduce professional DRS\n\n"
           "Professional ball tracking uses six or more synchronised, calibrated, high-speed cameras around the ground. "
           "Each camera gives a line of sight to the ball; where the lines cross gives the ball's position in three "
           "dimensions to within a few millimetres.\n\n"
           "A single phone camera gives **one** line of sight. A ball that looks 'here' in the image could be anywhere "
           "along that line: nearer and lower, or further and higher. Depth is simply not in the picture. On top of that, "
           "an uncalibrated camera has unknown lens distortion, the ball is blurred and often hidden near the pad, and a "
           "30 fps video has only two or three frames between bounce and impact.\n\n"
           "So this notebook does something more modest and honest:\n\n"
           "1. Use the one thing a single camera *can* locate on the pitch: the **bounce point**, because it lies on the ground.\n"
           "2. Let a person enter the impact point and height.\n3. Project the path with a stated physical model.\n"
           "4. Vary the inputs inside their uncertainty and report how often the ball hits the stumps."),
    ("md", "## 2. Coordinates\n\n- **x**: metres across from middle stump. Positive = off side.\n"
           "- **y**: metres from the striker's stumps toward the bowler (stumps at y = 0).\n- **z**: height above the ground.\n\n"
           "The wicket is 22.86 cm wide and 71.1 cm tall; the ball's radius is 3.6 cm."),
    ("code", '''from pitchvision import trajectory, sample_data
from pitchvision.constants import STUMP_HEIGHT_M, WICKET_HALF_WIDTH_M, BALL_RADIUS_M, GRAVITY, PITCH_LENGTH_M
print(f"Wicket half-width {WICKET_HALF_WIDTH_M:.4f} m, stump height {STUMP_HEIGHT_M} m, ball radius {BALL_RADIUS_M} m")'''),
    ("md", "## 3. From tracked pixels to a bounce point\n\nWe start from a tracked path in image pixels (synthetic here; "
           "from notebook 03 for a real clip). Before the bounce the ball moves down the image; after it, up. Fitting one "
           "straight line to the vertical position on each side of every possible split, and keeping the best split, finds the bounce."),
    ("code", '''points = sample_data.synthetic_track(seed=4, noise=1.5)      # SYNTHETIC pixel track
bounce = trajectory.detect_bounce(points)
tr = pd.DataFrame(points)
fig, ax = plt.subplots()
ax.plot(tr["t"], tr["y"], "o-", color=INK, ms=4)
ax.axvline(bounce["t"], color=RED, ls="--", label=f"bounce at frame {bounce['frame']} (confidence {bounce['confidence']:.2f})")
ax.invert_yaxis(); ax.set_xlabel("time (s)"); ax.set_ylabel("vertical position in the image (px, down is larger)")
ax.set_title("Finding the bounce (SYNTHETIC track)"); ax.legend(); plt.show()'''),
    ("md", "## 4. Calibration: placing the bounce on the pitch\n\nFour points on the ground with known positions (the ends of "
           "the two popping creases) define a **homography**: a 3×3 matrix that maps any *ground* point in the image to "
           "pitch metres. It only works for points on the ground, which is exactly why the bounce can be placed and a ball in the air cannot."),
    ("code", '''targets = trajectory.standard_calibration_targets()
for t_ in targets: print(t_)

# Pretend the camera maps pitch metres to pixels like this (in real use you click the four points on a frame).
camera = np.array([[60.0, 4.0, 320.0], [1.5, -14.0, 420.0], [0.0, 0.0035, 1.0]])
def to_image(x, y):
    p = camera @ np.array([x, y, 1.0]); return [p[0] / p[2], p[1] / p[2]]

clicked = [to_image(t_["x"], t_["y"]) for t_ in targets]
H = trajectory.fit_homography(clicked, [[t_["x"], t_["y"]] for t_ in targets])
u, v = to_image(0.15, 6.8)                                   # a ball that really bounced at x = 0.15 m, y = 6.8 m
print("Recovered bounce point:", tuple(round(c, 3) for c in trajectory.image_to_pitch(H, u, v)))

# How much does a 3-pixel error in clicking the corners move the answer?
rng = np.random.default_rng(0)
spread = []
for _ in range(300):
    noisy = [[a + rng.normal(0, 3), b + rng.normal(0, 3)] for a, b in clicked]
    spread.append(trajectory.image_to_pitch(trajectory.fit_homography(noisy, [[t_["x"], t_["y"]] for t_ in targets]), u, v))
spread = np.array(spread)
print(f"With 3 px clicking error: x varies by ±{spread[:, 0].std() * 100:.1f} cm, y by ±{spread[:, 1].std() * 100:.1f} cm (1 standard deviation)")'''),
    ("md", "## 5. The physical model\n\nAfter the bounce we assume:\n\n- constant speed **v** along the pitch;\n"
           "- a straight line sideways (no further swing or spin);\n- gravity on height, no air drag.\n\n"
           "With the ball pitching at $(x_p, y_p, 0)$ and hitting the pad at $(x_i, y_i, z_i)$:\n\n"
           "$$t_1 = \\frac{y_p - y_i}{v},\\qquad v_{z0} = \\frac{z_i + \\tfrac12 g t_1^2}{t_1}$$\n\n"
           "and at the stumps ($t_2 = y_p / v$):\n\n"
           "$$z_{stumps} = v_{z0} t_2 - \\tfrac12 g t_2^2,\\qquad x_{stumps} = x_p + \\frac{x_i - x_p}{y_p - y_i}\\, y_p$$"),
    ("code", '''def project_by_hand(pitch_x, pitch_y, impact_x, impact_y, impact_z, speed_kmh):
    v = speed_kmh / 3.6
    t1 = (pitch_y - impact_y) / v
    t2 = pitch_y / v
    vz0 = (impact_z + 0.5 * GRAVITY * t1 ** 2) / t1
    z = vz0 * t2 - 0.5 * GRAVITY * t2 ** 2
    x = pitch_x + (impact_x - pitch_x) / (pitch_y - impact_y) * pitch_y
    return x, z

case = dict(pitch_x=0.10, pitch_y=6.5, impact_x=0.06, impact_y=2.2, impact_z=0.32, speed_kmh=105)
x_hand, z_hand = project_by_hand(**case)
res = trajectory.simulate_drs(**case)
print(f"By hand : x = {x_hand * 100:.1f} cm from middle, z = {z_hand * 100:.1f} cm high")
print(f"Module  : x = {res['projection']['x'] * 100:.1f} cm, z = {res['projection']['z'] * 100:.1f} cm")
assert abs(x_hand - res["projection"]["x"]) < 1e-9 and abs(z_hand - res["projection"]["z"]) < 1e-9'''),
    ("md", "## 6. Uncertainty\n\nThe entered positions are not exact. We redo the projection 4,000 times with each position "
           "moved by a random amount (3 cm standard deviation for careful manual entry) and the speed by 10%. The cloud of "
           "results shows where the ball could be at the stumps.\n\n**Decision rule:** at least 80% of the cloud hitting → "
           "*hitting*; at most 20% → *missing*; otherwise → *inconclusive*."),
    ("code", '''def draw_stumps(ax):
    for s in (-WICKET_HALF_WIDTH_M, 0, WICKET_HALF_WIDTH_M):
        ax.add_patch(plt.Rectangle((s - 0.018, 0), 0.036, STUMP_HEIGHT_M, color=YELLOW, ec=INK))
    ax.axhline(0, color=INK, lw=2)
    ax.set_xlim(-0.6, 0.6); ax.set_ylim(-0.05, 1.2); ax.set_aspect("equal")
    ax.set_xlabel("across (m): leg side  <-  ->  off side"); ax.set_ylabel("height (m)")

def cloud(case, sigma=0.03, speed_sigma=10, n=4000, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        c = dict(case)
        for k in ("pitch_x", "pitch_y", "impact_x", "impact_y", "impact_z"):
            c[k] = c[k] + rng.normal(0, sigma)
        c["speed_kmh"] = c["speed_kmh"] * (1 + rng.normal(0, speed_sigma / 100))
        if c["pitch_y"] - c["impact_y"] > 0.05:
            out.append(project_by_hand(**c))
    return np.array(out)

cases = {"Hitting": case,
         "Missing (sliding down leg)": dict(pitch_x=0.05, pitch_y=6.5, impact_x=-0.16, impact_y=2.2, impact_z=0.3, speed_kmh=105),
         "Inconclusive (clipping off stump)": dict(pitch_x=0.0, pitch_y=6.0, impact_x=0.08, impact_y=2.0, impact_z=0.3, speed_kmh=110)}
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (title, c) in zip(axes, cases.items()):
    pts = cloud(c, sigma=0.03 if "Inconclusive" not in title else 0.06)
    r = trajectory.simulate_drs(**c, position_sigma_m=0.03 if "Inconclusive" not in title else 0.06)
    draw_stumps(ax)
    ax.scatter(pts[:, 0], pts[:, 1], s=2, alpha=0.15, color=RED if r["decision"] == "hitting" else GREEN if r["decision"] == "missing" else INK)
    ax.set_title(f"{title}\\n{r['decision'].upper()}: {r['projection']['hit_probability'] * 100:.0f}% of paths hit", fontsize=10)
plt.show()'''),
    ("md", "## 7. Why extrapolation is the weak point\n\nThe further the ball still has to travel after hitting the pad, and "
           "the shorter the distance it travelled between bounce and pad, the more a small input error grows. Real DRS "
           "treats less than 40 cm of post-bounce travel as too little to judge; so does this simulation."),
    ("code", '''rows = []
for impact_y in [0.8, 1.5, 2.5, 3.5, 4.5, 5.5]:
    r = trajectory.simulate_drs(0.0, 6.5, 0.0, impact_y, 0.3, speed_kmh=105)
    rows.append({"impact distance from stumps (m)": impact_y, "travel after bounce (m)": round(6.5 - impact_y, 1),
                 "sideways uncertainty at stumps (cm, 1 sd)": round(r["projection"]["x_sigma"] * 100, 1),
                 "height uncertainty (cm, 1 sd)": round(r["projection"]["z_sigma"] * 100, 1), "decision": r["decision"]})
sens = pd.DataFrame(rows); display(sens)

fig, ax = plt.subplots()
ax.plot(sens.iloc[:, 0], sens.iloc[:, 2], marker="o", color=INK, label="sideways")
ax.plot(sens.iloc[:, 0], sens.iloc[:, 3], marker="o", color=RED, label="height")
ax.axhline(WICKET_HALF_WIDTH_M * 100, color=YELLOW, ls="--", label="half the wicket's width")
ax.set_xlabel("How far from the stumps the ball hit the pad (m)"); ax.set_ylabel("Uncertainty at the stumps (cm)")
ax.set_title("The same 3 cm input error grows with extrapolation"); ax.legend(); plt.show()

short = trajectory.simulate_drs(0.0, 2.3, 0.0, 2.0, 0.1)
print("Short travel:", short["decision"], "-", short["reason"])'''),
    ("md", "## 8. Simplified LBW logic (Law 36)\n\nA batter is out LBW only if **all** of these hold:\n\n"
           "1. The ball is not a no-ball.\n2. It pitched in line with the stumps or outside off, **not outside leg**.\n"
           "3. It did not touch the bat first.\n4. It hit the batter in line with the stumps, **or** outside off if no shot was offered.\n"
           "5. It would have gone on to hit the stumps.\n\n"
           "Simplification: the centre of the ball is used for the pitching and impact tests (real DRS uses more than half the ball)."),
    ("code", '''examples = {
    "Plumb in front": dict(pitch_x=0.0, pitch_y=6.0, impact_x=0.0, impact_y=2.0, impact_z=0.3),
    "Pitched outside leg": dict(pitch_x=-0.30, pitch_y=6.0, impact_x=-0.02, impact_y=2.0, impact_z=0.3),
    "Impact outside off, shot offered": dict(pitch_x=0.5, pitch_y=7.0, impact_x=0.20, impact_y=2.0, impact_z=0.3),
    "Impact outside off, no shot": dict(pitch_x=0.5, pitch_y=7.0, impact_x=0.20, impact_y=2.0, impact_z=0.3, shot_offered=False),
    "No-ball": dict(pitch_x=0.0, pitch_y=6.0, impact_x=0.0, impact_y=2.0, impact_z=0.3, no_ball=True),
    "Too high": dict(pitch_x=0.0, pitch_y=4.0, impact_x=0.0, impact_y=2.5, impact_z=0.75, speed_kmh=120),
    "Missing data": dict(pitch_x=None, pitch_y=None, impact_x=0.0, impact_y=2.0, impact_z=0.3),
}
rows = []
for name, c in examples.items():
    r = trajectory.simulate_drs(**c)
    rows.append({"case": name, "pitched": r.get("pitched", "-"), "impact": r.get("impact", "-"), "wickets": r["decision"],
                 "LBW decision": r.get("lbw", "inconclusive"), "failed conditions": ", ".join(x["name"] for x in r["conditions"] if x["pass"] is False) or "-"})
pd.DataFrame(rows)'''),
    ("code", '''# Every result carries its assumptions and limitations.
r = trajectory.simulate_drs(**case)
print("ASSUMPTIONS"); [print(" -", a) for a in r["assumptions"]]
print("LIMITATIONS"); [print(" -", a) for a in r["limitations"]]
pd.DataFrame(rows).to_csv(EXPORTS / "drs_examples.csv", index=False)'''),
    ("md", "## 9. Before the bounce: a drag-free flight\n\nFor completeness, the path from the hand to the pitch for a ball "
           "released 2 m high. Faster balls travel flatter; slower balls need more loop to reach the same length."),
    ("code", '''fig, ax = plt.subplots()
for kmh, colour in [(70, GREEN), (100, INK), (130, RED)]:
    p = pd.DataFrame(trajectory.flight_path(2.0, kmh, 6.5))
    ax.plot(p["y"], p["z"], color=colour, label=f"{kmh} km/h")
ax.invert_xaxis(); ax.set_xlabel("distance from the striker's stumps (m)"); ax.set_ylabel("height (m)")
ax.set_title("Release to a good length, no air drag"); ax.legend(); plt.show()'''),
] + closing(
    "- The projection formulas written by hand match `pitchvision.trajectory.simulate_drs` exactly.\n"
    "- With 3 cm input uncertainty, the uncertainty at the stumps grows from a few centimetres to more than the wicket's half-width as the impact moves away from the stumps.\n"
    "- The simulation returns hitting, missing or inconclusive, and applies the LBW conditions separately from the ball-tracking result.",
    "The useful output is not the single projected point but the spread around it. When the spread straddles the edge of the stumps, the honest answer is 'inconclusive'.",
    "- No depth from one camera: impact height and distance are human estimates.\n- No air drag, swing after the bounce, or spin are modelled.\n"
    "- The 80% / 20% decision thresholds are a choice made for teaching, not an official standard.\n"
    "- The ball's centre is used for the pitching and impact tests.\n- This is not an official DRS and must not be used to make or dispute umpiring decisions.",
    "DRS Studio sends the entered points to `POST /api/drs/simulate`, which calls `trajectory.simulate_drs` and draws the same "
    "projection, 95% range, decision, LBW conditions, assumptions and limitations. The 'Track from video' tab uses `detect_bounce` "
    "and `fit_homography` to supply the pitching point.",
)

NOTEBOOKS = {
    "01_bowling_speed_analysis.ipynb": NB01,
    "02_bowling_action_analysis.ipynb": NB02,
    "03_cricket_ball_tracking.ipynb": NB03,
    "04_drs_trajectory_simulation.ipynb": NB04,
}
