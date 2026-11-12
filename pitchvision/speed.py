"""Bowling speed: unit conversion and statistics.

IMPORTANT
---------
speed = distance / time gives the AVERAGE speed of the ball over the measured
distance. A cricket ball slows down through the air and loses more speed when
it bounces, so the average is always LOWER than the speed at release. A radar
gun reports something close to release speed. Never compare the two as if they
were the same quantity.
"""
from __future__ import annotations

import math
import statistics
from typing import Iterable, Optional

# Exact conversion factors to SI base units.
DISTANCE_TO_M = {"m": 1.0, "ft": 0.3048, "yd": 0.9144}
TIME_TO_S = {"s": 1.0, "ms": 0.001}

MS_TO_KMH = 3.6
MS_TO_MPH = 3600.0 / 1609.344      # 2.2369362920544...


class SpeedInputError(ValueError):
    """Raised when a speed calculation receives an invalid input."""


def to_metres(value: float, unit: str) -> float:
    if unit not in DISTANCE_TO_M:
        raise SpeedInputError(f"Unknown distance unit '{unit}'. Use one of {sorted(DISTANCE_TO_M)}.")
    return float(value) * DISTANCE_TO_M[unit]


def from_metres(metres: float, unit: str) -> float:
    if unit not in DISTANCE_TO_M:
        raise SpeedInputError(f"Unknown distance unit '{unit}'. Use one of {sorted(DISTANCE_TO_M)}.")
    return float(metres) / DISTANCE_TO_M[unit]


def to_seconds(value: float, unit: str) -> float:
    if unit not in TIME_TO_S:
        raise SpeedInputError(f"Unknown time unit '{unit}'. Use one of {sorted(TIME_TO_S)}.")
    return float(value) * TIME_TO_S[unit]


def ms_to_kmh(v: float) -> float:
    return v * MS_TO_KMH


def ms_to_mph(v: float) -> float:
    return v * MS_TO_MPH


def kmh_to_ms(v: float) -> float:
    return v / MS_TO_KMH


def mph_to_kmh(v: float) -> float:
    return v * 1.609344


def average_speed(distance: float, time: float, distance_unit: str = "m", time_unit: str = "s") -> dict:
    """Average ball speed over a measured distance.

    Returns a dict with the normalised inputs and the speed in m/s, km/h, mph.
    """
    for name, v in (("distance", distance), ("time", time)):
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
            raise SpeedInputError(f"{name} must be a real number.")
    if distance <= 0:
        raise SpeedInputError("Distance must be greater than zero.")
    if time <= 0:
        raise SpeedInputError("Time must be greater than zero.")
    d_m = to_metres(distance, distance_unit)
    t_s = to_seconds(time, time_unit)
    v = d_m / t_s
    return {
        "distance_m": d_m,
        "time_s": t_s,
        "speed_ms": v,
        "speed_kmh": ms_to_kmh(v),
        "speed_mph": ms_to_mph(v),
        "kind": "average",   # never "release"
    }


def speed_summary(speeds_kmh: Iterable[Optional[float]]) -> dict:
    """Average, max, min, most recent, spread. Missing values (None/NaN) are skipped.

    `speeds_kmh` must be in chronological order (oldest first).
    """
    clean = [float(s) for s in speeds_kmh if s is not None and not (isinstance(s, float) and math.isnan(s))]
    if not clean:
        return {"count": 0, "average": None, "max": None, "min": None, "recent": None,
                "median": None, "std_dev": None}
    return {
        "count": len(clean),
        "average": statistics.fmean(clean),
        "max": max(clean),
        "min": min(clean),
        "recent": clean[-1],
        "median": statistics.median(clean),
        # Sample standard deviation needs at least two readings.
        "std_dev": statistics.stdev(clean) if len(clean) > 1 else None,
    }


def speed_trend(speeds_kmh: list[float]) -> dict:
    """Least-squares slope of speed against reading number (km/h per reading).

    With fewer than 3 readings a trend is not reported.
    """
    clean = [float(s) for s in speeds_kmh if s is not None]
    n = len(clean)
    if n < 3:
        return {"slope_per_reading": None, "change_first_to_last_third": None, "n": n}
    xs = list(range(n))
    mx, my = statistics.fmean(xs), statistics.fmean(clean)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, clean)) / sxx
    third = max(1, n // 3)
    change = statistics.fmean(clean[-third:]) - statistics.fmean(clean[:third])
    return {"slope_per_reading": slope, "change_first_to_last_third": change, "n": n}


def compare_radar_to_estimate(radar_kmh: float, estimate_kmh: float) -> dict:
    """Difference between a radar reading and a distance/time or video estimate.

    The radar reading is expected to be HIGHER because it is close to release
    speed while the estimate is an average over the flight.
    """
    diff = radar_kmh - estimate_kmh
    return {
        "radar_kmh": radar_kmh,
        "estimate_kmh": estimate_kmh,
        "difference_kmh": diff,
        "estimate_as_pct_of_radar": (estimate_kmh / radar_kmh * 100.0) if radar_kmh else None,
        "note": "Radar is near release speed; the estimate is an average over the flight, "
                "so a positive difference is expected and is not an error.",
    }
