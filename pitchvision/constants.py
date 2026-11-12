"""Pitch geometry and classification thresholds.

Coordinate system used everywhere in PitchVision (metres):

    x  lateral position. 0 = line of middle stump.
       Positive x = OFF side of the batter on strike, negative = LEG side.
       (Entries are handedness-normalised, so "+x is off side" is always true.)
    y  distance down the pitch measured FROM THE STRIKER'S STUMPS toward the
       bowler. y = 0 at the striker's stumps, y = 20.12 at the bowler's stumps.
    z  height above the pitch surface.

All dimensions follow the MCC Laws of Cricket (Laws 6, 7, 8).
"""

# --- Pitch (Law 6, Law 7) -------------------------------------------------
PITCH_LENGTH_M = 20.12          # 22 yards, stumps to stumps
PITCH_WIDTH_M = 3.05            # 10 feet
POPPING_CREASE_M = 1.22         # 4 feet in front of the stumps
RETURN_CREASE_HALF_WIDTH_M = 1.32

# --- Wicket (Law 8) -------------------------------------------------------
STUMP_HEIGHT_M = 0.711          # 28 inches
WICKET_WIDTH_M = 0.2286         # 9 inches across all three stumps
WICKET_HALF_WIDTH_M = WICKET_WIDTH_M / 2
BALL_RADIUS_M = 0.036           # ~72 mm diameter

# Typical distance from a bowler's release point to the striker's stumps.
# The bowler releases near the popping crease at their end.
RELEASE_TO_STUMPS_M = PITCH_LENGTH_M - POPPING_CREASE_M   # 18.90 m

GRAVITY = 9.81                  # m/s^2

# --- Length bands: distance of the pitching point from the striker's stumps
# These are widely used coaching bands for pace bowling. They are conventions,
# not laws; a coach may edit them in one place here.
LENGTH_BANDS = [
    # (name, min_y inclusive, max_y exclusive)
    ("yorker", 0.0, 2.0),
    ("full", 2.0, 6.0),
    ("good", 6.0, 8.0),
    ("short", 8.0, 10.0),
    ("bouncer", 10.0, PITCH_LENGTH_M + 0.01),
]
LENGTH_ORDER = [b[0] for b in LENGTH_BANDS] + ["full_toss"]

# --- Line bands: lateral position of the pitching point (x, metres)
LINE_BANDS = [
    # (name, min_x inclusive, max_x exclusive)
    ("wide_leg", -PITCH_WIDTH_M, -0.45),
    ("leg", -0.45, -WICKET_HALF_WIDTH_M),
    ("stumps", -WICKET_HALF_WIDTH_M, WICKET_HALF_WIDTH_M + 1e-9),
    ("off", WICKET_HALF_WIDTH_M + 1e-9, 0.45),
    ("wide_off", 0.45, PITCH_WIDTH_M),
]
LINE_ORDER = [b[0] for b in LINE_BANDS]

BALLS_PER_OVER = 6
