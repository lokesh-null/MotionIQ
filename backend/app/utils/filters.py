"""Temporal gap-handling, Savitzky-Golay smoothing, and timestamped angular velocity utilities."""

from __future__ import annotations

import math
from typing import List, Optional, Sequence
import numpy as np
from scipy.signal import savgol_filter


def interpolate_short_gaps(
    series: Sequence[Optional[float]],
    max_gap: int = 4,
) -> List[Optional[float]]:
    """
    Linearly interpolate ONLY short internal gaps (<= max_gap consecutive None values)
    that are bounded on both sides by valid observations.

    Longer missing segments or leading/trailing missing values remain None so that
    measurements are never fabricated over extended occlusions.
    """
    n = len(series)
    if n == 0:
        return []
    out: List[Optional[float]] = [
        float(v) if (v is not None and math.isfinite(float(v))) else None for v in series
    ]

    i = 0
    while i < n:
        if out[i] is not None:
            i += 1
            continue

        gap_start = i
        while i < n and out[i] is None:
            i += 1
        gap_end = i  # first valid index after gap (or n)
        gap_len = gap_end - gap_start

        if gap_start > 0 and gap_end < n and gap_len <= max_gap:
            left_val = out[gap_start - 1]
            right_val = out[gap_end]
            assert left_val is not None and right_val is not None
            for k in range(gap_len):
                frac = (k + 1) / (gap_len + 1)
                out[gap_start + k] = left_val + frac * (right_val - left_val)

    return out


def smooth_series(
    series: Sequence[Optional[float]],
    fps: float,
    window_sec: float = 0.22,
    polyorder: int = 2,
) -> List[Optional[float]]:
    """
    Apply Savitzky-Golay smoothing independently to each contiguous valid segment.
    Preserves None entries for missing observations.
    """
    n = len(series)
    if n == 0:
        return []

    safe_fps = fps if (fps and math.isfinite(fps) and fps > 1.0) else 30.0
    raw_win = max(5, int(round(safe_fps * window_sec)))
    if raw_win % 2 == 0:
        raw_win += 1

    out: List[Optional[float]] = [
        float(v) if (v is not None and math.isfinite(float(v))) else None for v in series
    ]

    i = 0
    while i < n:
        if out[i] is None:
            i += 1
            continue
        seg_start = i
        while i < n and out[i] is not None:
            i += 1
        seg_end = i
        seg_len = seg_end - seg_start

        if seg_len >= 5:
            win = min(raw_win, seg_len if seg_len % 2 == 1 else seg_len - 1)
            if win > polyorder and win >= 5:
                segment = np.array(out[seg_start:seg_end], dtype=np.float64)
                smoothed = savgol_filter(segment, window_length=win, polyorder=polyorder, mode="interp")
                for offset, val in enumerate(smoothed):
                    out[seg_start + offset] = float(val)

    return out


def compute_angular_velocity(
    angles: Sequence[Optional[float]],
    timestamps_sec: Sequence[float],
    fps: float,
    max_dt_sec: float = 0.35,
) -> List[Optional[float]]:
    """
    Compute angular velocity (degrees / second) using actual frame timestamps.

    Only computes velocity across consecutive valid angle samples where
    1e-4 < dt <= max_dt_sec, then lightly smooths valid segments.
    """
    n = len(angles)
    if n == 0 or len(timestamps_sec) != n:
        return [None] * n

    raw_vel: List[Optional[float]] = [None] * n
    for i in range(1, n):
        a_prev = angles[i - 1]
        a_curr = angles[i]
        if a_prev is None or a_curr is None:
            continue
        if not (math.isfinite(a_prev) and math.isfinite(a_curr)):
            continue
        dt = float(timestamps_sec[i]) - float(timestamps_sec[i - 1])
        if 1e-4 < dt <= max_dt_sec:
            raw_vel[i] = (float(a_curr) - float(a_prev)) / dt

    # Lightly smooth angular velocity to suppress frame-to-frame derivative jitter
    return smooth_series(raw_vel, fps=fps, window_sec=0.20, polyorder=2)
