"""Movement-phase detection, repetition counting, and movement-specific kinematic analysis."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from scipy.signal import find_peaks

from app.utils.filters import interpolate_short_gaps, smooth_series


def _select_primary_side_series(
    left: Sequence[Optional[float]],
    right: Sequence[Optional[float]],
    left_summary: Optional[Dict[str, Any]],
    right_summary: Optional[Dict[str, Any]],
    camera_perspective: str,
) -> Tuple[List[Optional[float]], str]:
    """
    Choose the most reliable 1D signal for temporal movement segmentation.
    - Frontal view: average left and right when both are valid; fallback to whichever side is valid.
    - Side view: pick the side with higher valid frame ratio and confidence (the camera-facing near limb).
    """
    n = len(left)
    l_ratio = (left_summary or {}).get("valid_ratio", 0.0)
    l_conf = (left_summary or {}).get("mean_confidence", 0.0)
    r_ratio = (right_summary or {}).get("valid_ratio", 0.0)
    r_conf = (right_summary or {}).get("mean_confidence", 0.0)

    if camera_perspective == "front":
        merged: List[Optional[float]] = []
        for l_v, r_v in zip(left, right):
            if l_v is not None and r_v is not None:
                merged.append(0.5 * (float(l_v) + float(r_v)))
            elif l_v is not None:
                merged.append(float(l_v))
            elif r_v is not None:
                merged.append(float(r_v))
            else:
                merged.append(None)
        return merged, "bilateral_mean"

    l_score = l_ratio * 0.6 + l_conf * 0.4
    r_score = r_ratio * 0.6 + r_conf * 0.4
    if l_score >= r_score:
        return [float(v) if v is not None else None for v in left], "left"
    return [float(v) if v is not None else None for v in right], "right"


def _fill_for_segmentation(series: Sequence[Optional[float]]) -> Tuple[np.ndarray, np.ndarray]:
    """Build a contiguous numpy array for peak/valley search and a boolean validity mask."""
    n = len(series)
    valid_mask = np.array([v is not None and math.isfinite(float(v)) for v in series], dtype=bool)
    if not np.any(valid_mask):
        return np.zeros(n, dtype=np.float64), valid_mask
    idx = np.arange(n)
    vals = np.array([float(series[i]) if valid_mask[i] else 0.0 for i in range(n)], dtype=np.float64)
    filled = np.interp(idx, idx[valid_mask], vals[valid_mask])
    return filled, valid_mask


def _find_cycle_boundaries(
    signal: np.ndarray,
    peak_idx: int,
    prev_peak_idx: int,
    next_peak_idx: int,
    fps: float,
    baseline_val: float,
) -> Tuple[int, int, int, int]:
    """
    Given a peak index, find (start_idx, bottom_start_idx, bottom_end_idx, end_idx)
    representing the movement cycle boundaries.
    """
    n = len(signal)
    peak_val = float(signal[peak_idx])
    amplitude = max(10.0, peak_val - baseline_val)

    # Search backward for valley (start of descent)
    left_limit = max(0, prev_peak_idx + 1 if prev_peak_idx >= 0 else 0)
    # Find minimum between left_limit and peak_idx
    if peak_idx > left_limit:
        search_left = signal[left_limit:peak_idx]
        min_left_rel = int(np.argmin(search_left))
        valley_left = left_limit + min_left_rel
        # Tighten start to where descent actually begins (> baseline + 10% of amplitude)
        thresh_start = float(signal[valley_left]) + 0.08 * (peak_val - float(signal[valley_left]))
        start_idx = valley_left
        for k in range(peak_idx, valley_left - 1, -1):
            if signal[k] <= thresh_start:
                start_idx = k
                break
    else:
        start_idx = max(0, peak_idx - 1)

    # Search forward for valley (end of ascent)
    right_limit = min(n, next_peak_idx if next_peak_idx >= 0 else n)
    if right_limit > peak_idx + 1:
        search_right = signal[peak_idx + 1 : right_limit]
        min_right_rel = int(np.argmin(search_right))
        valley_right = peak_idx + 1 + min_right_rel
        thresh_end = float(signal[valley_right]) + 0.08 * (peak_val - float(signal[valley_right]))
        end_idx = valley_right
        for k in range(peak_idx, valley_right + 1):
            if signal[k] <= thresh_end:
                end_idx = k
                break
    else:
        end_idx = min(n - 1, peak_idx + 1)

    # Bottom plateau: within 8% of peak amplitude (or >= 5 deg from peak)
    bottom_tol = max(4.0, 0.08 * amplitude)
    bottom_start = peak_idx
    while bottom_start > start_idx and signal[bottom_start - 1] >= peak_val - bottom_tol:
        bottom_start -= 1
    bottom_end = peak_idx
    while bottom_end < end_idx and signal[bottom_end + 1] >= peak_val - bottom_tol:
        bottom_end += 1

    return start_idx, bottom_start, bottom_end, end_idx


def _resample_cycle(series: Sequence[Optional[float]], start_idx: int, end_idx: int, num_points: int = 21) -> List[Optional[float]]:
    """Resample a slice of a time series onto 0%..100% normalized cycle progress."""
    if end_idx <= start_idx or start_idx < 0 or end_idx >= len(series):
        return [None] * num_points
    sub = series[start_idx : end_idx + 1]
    valid_x = [i for i, v in enumerate(sub) if v is not None and math.isfinite(float(v))]
    if len(valid_x) < 2:
        return [None] * num_points
    valid_y = [float(sub[i]) for i in valid_x]
    target_x = np.linspace(0, len(sub) - 1, num_points)
    interp_y = np.interp(target_x, valid_x, valid_y)
    return [round(float(y), 2) for y in interp_y]


def _stats(vals: Sequence[Optional[float]]) -> Dict[str, Optional[float]]:
    clean = [float(v) for v in vals if v is not None and math.isfinite(float(v))]
    if not clean:
        return {"mean": None, "std": None, "min": None, "max": None, "cv_percent": None}
    arr = np.array(clean, dtype=np.float64)
    mean_v = float(np.mean(arr))
    std_v = float(np.std(arr))
    cv = (std_v / abs(mean_v) * 100.0) if (len(clean) >= 2 and abs(mean_v) > 1e-6) else None
    return {
        "mean": round(mean_v, 2),
        "std": round(std_v, 2),
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
        "cv_percent": round(cv, 2) if cv is not None else None,
    }


def _analyze_squat(biomech: Dict[str, Any], camera_perspective: str) -> Dict[str, Any]:
    timestamps = biomech["timestamps_sec"]
    angles = biomech["angles_deg"]
    summaries = biomech["joint_summaries"]
    ratios = biomech["kinematic_ratios"]
    n = len(timestamps)
    fps = (n - 1) / max(0.1, timestamps[-1] - timestamps[0]) if n >= 2 else 30.0

    primary_knee_flex, primary_side = _select_primary_side_series(
        angles.get("left_knee_flexion", [None] * n),
        angles.get("right_knee_flexion", [None] * n),
        summaries.get("left_knee_flexion"),
        summaries.get("right_knee_flexion"),
        camera_perspective,
    )
    primary_hip_flex, _ = _select_primary_side_series(
        angles.get("left_hip_flexion", [None] * n),
        angles.get("right_hip_flexion", [None] * n),
        summaries.get("left_hip_flexion"),
        summaries.get("right_hip_flexion"),
        camera_perspective,
    )
    primary_depth_ratio, _ = _select_primary_side_series(
        ratios["left_hip_depth_ratio"],
        ratios["right_hip_depth_ratio"],
        summaries.get("left_knee_flexion"),
        summaries.get("right_knee_flexion"),
        camera_perspective,
    )
    trunk_inc = angles.get("trunk_inclination", [None] * n)

    sig, valid_mask = _fill_for_segmentation(primary_knee_flex)
    valid_ratio = float(np.mean(valid_mask)) if n > 0 else 0.0
    phases = ["STANDING"] * n

    if n < 5 or valid_ratio < 0.25:
        return {
            "movement_type": "squat",
            "primary_side_tracked": primary_side,
            "rep_count": 0,
            "frame_phases": phases,
            "repetitions": [],
            "consistency": {},
            "summary_metrics": {"sufficient_data": False},
        }

    baseline_knee = float(np.percentile(sig[valid_mask], 15))
    min_peak_height = max(45.0, baseline_knee + 30.0)
    min_dist = max(2, int(round(0.75 * fps)))
    peaks, _ = find_peaks(sig, height=min_peak_height, prominence=26.0, distance=min_dist)

    # Filter out peaks that sit in completely unreliable frames
    valid_peaks = [int(p) for p in peaks if np.any(valid_mask[max(0, p - 2) : min(n, p + 3)])]

    # Standing trunk inclination baseline from first 15% of standing frames (or lowest knee flexion frames)
    standing_trunk_vals = [
        float(trunk_inc[i])
        for i in range(n)
        if trunk_inc[i] is not None and primary_knee_flex[i] is not None and primary_knee_flex[i] <= baseline_knee + 12.0
    ]
    standing_trunk_baseline = float(np.median(standing_trunk_vals)) if standing_trunk_vals else None

    repetitions: List[Dict[str, Any]] = []
    for rep_idx, p_idx in enumerate(valid_peaks):
        prev_p = valid_peaks[rep_idx - 1] if rep_idx > 0 else -1
        next_p = valid_peaks[rep_idx + 1] if rep_idx + 1 < len(valid_peaks) else -1
        s_idx, b_start, b_end, e_idx = _find_cycle_boundaries(sig, p_idx, prev_p, next_p, fps, baseline_knee)

        if e_idx <= s_idx or (timestamps[e_idx] - timestamps[s_idx]) < 0.45:
            continue

        for k in range(s_idx, b_start):
            phases[k] = "DESCENDING"
        for k in range(b_start, b_end + 1):
            phases[k] = "BOTTOM"
        for k in range(b_end + 1, e_idx + 1):
            phases[k] = "ASCENDING"
        # Mark brief post-ascent settle frame as RETURN_TO_STANDING
        if e_idx < n:
            phases[e_idx] = "RETURN_TO_STANDING"

        descent_dur = round(float(timestamps[b_start] - timestamps[s_idx]), 3)
        bottom_hold = round(float(timestamps[b_end] - timestamps[b_start]), 3)
        ascent_dur = round(float(timestamps[e_idx] - timestamps[b_end]), 3)
        total_dur = round(float(timestamps[e_idx] - timestamps[s_idx]), 3)

        rep_knee_vals = [primary_knee_flex[k] for k in range(s_idx, e_idx + 1) if primary_knee_flex[k] is not None]
        rep_hip_vals = [primary_hip_flex[k] for k in range(s_idx, e_idx + 1) if primary_hip_flex[k] is not None]
        rep_trunk_vals = [trunk_inc[k] for k in range(s_idx, e_idx + 1) if trunk_inc[k] is not None]
        rep_depth_vals = [primary_depth_ratio[k] for k in range(b_start, b_end + 1) if primary_depth_ratio[k] is not None]

        max_knee_flex = round(float(max(rep_knee_vals)), 2) if rep_knee_vals else None
        min_knee_int = round(max(0.0, 180.0 - max_knee_flex), 2) if max_knee_flex is not None else None
        max_hip_flex = round(float(max(rep_hip_vals)), 2) if rep_hip_vals else None
        min_hip_int = round(max(0.0, 180.0 - max_hip_flex), 2) if max_hip_flex is not None else None
        max_trunk = round(float(max(rep_trunk_vals)), 2) if rep_trunk_vals else None
        trunk_delta = (
            round(max_trunk - standing_trunk_baseline, 2)
            if (max_trunk is not None and standing_trunk_baseline is not None)
            else None
        )
        depth_ratio_bottom = round(float(np.mean(rep_depth_vals)), 3) if rep_depth_vals else None

        # Bilateral knee difference at bottom if both sides valid
        lk_bottom = angles.get("left_knee_flexion", [None] * n)[p_idx]
        rk_bottom = angles.get("right_knee_flexion", [None] * n)[p_idx]
        bilateral_diff_bottom = (
            round(abs(float(lk_bottom) - float(rk_bottom)), 2)
            if (lk_bottom is not None and rk_bottom is not None)
            else None
        )

        repetitions.append(
            {
                "rep_number": len(repetitions) + 1,
                "start_frame": s_idx,
                "bottom_frame": p_idx,
                "end_frame": e_idx,
                "start_time_sec": round(float(timestamps[s_idx]), 3),
                "bottom_time_sec": round(float(timestamps[p_idx]), 3),
                "end_time_sec": round(float(timestamps[e_idx]), 3),
                "duration_sec": total_dur,
                "descent_duration_sec": descent_dur,
                "bottom_hold_sec": bottom_hold,
                "ascent_duration_sec": ascent_dur,
                "descent_ascent_ratio": round(descent_dur / ascent_dur, 2) if ascent_dur > 0.05 else None,
                "max_knee_flexion_deg": max_knee_flex,
                "min_knee_internal_deg": min_knee_int,
                "max_hip_flexion_deg": max_hip_flex,
                "min_hip_internal_deg": min_hip_int,
                "max_trunk_inclination_deg": max_trunk,
                "trunk_inclination_delta_deg": trunk_delta,
                "hip_depth_ratio_at_bottom": depth_ratio_bottom,
                "bilateral_knee_diff_at_bottom_deg": bilateral_diff_bottom,
                "normalized_primary_curve": _resample_cycle(primary_knee_flex, s_idx, e_idx),
            }
        )

    rep_durs = [r["duration_sec"] for r in repetitions]
    desc_durs = [r["descent_duration_sec"] for r in repetitions]
    asc_durs = [r["ascent_duration_sec"] for r in repetitions]
    max_knees = [r["max_knee_flexion_deg"] for r in repetitions]
    max_hips = [r["max_hip_flexion_deg"] for r in repetitions]
    max_trunks = [r["max_trunk_inclination_deg"] for r in repetitions]
    trunk_deltas = [r["trunk_inclination_delta_deg"] for r in repetitions]
    depth_ratios = [r["hip_depth_ratio_at_bottom"] for r in repetitions]

    consistency = {
        "repetition_duration_sec": _stats(rep_durs),
        "descent_duration_sec": _stats(desc_durs),
        "ascent_duration_sec": _stats(asc_durs),
        "max_knee_flexion_deg": _stats(max_knees),
        "max_hip_flexion_deg": _stats(max_hips),
        "max_trunk_inclination_deg": _stats(max_trunks),
        "sufficient_for_consistency": len(repetitions) >= 2,
    }

    total_active_dur = round(sum(r["duration_sec"] for r in repetitions), 3) if repetitions else round(float(timestamps[-1] - timestamps[0]), 3)
    return {
        "movement_type": "squat",
        "primary_side_tracked": primary_side,
        "primary_signal_label": "Primary Knee Flexion (deg)",
        "primary_signal_deg": [round(v, 2) if v is not None else None for v in primary_knee_flex],
        "rep_count": len(repetitions),
        "total_movement_duration_sec": total_active_dur,
        "standing_trunk_baseline_deg": round(standing_trunk_baseline, 2) if standing_trunk_baseline is not None else None,
        "frame_phases": phases,
        "repetitions": repetitions,
        "consistency": consistency,
        "summary_metrics": {
            "sufficient_data": len(repetitions) > 0 or valid_ratio >= 0.5,
            "avg_rep_duration_sec": consistency["repetition_duration_sec"]["mean"],
            "avg_descent_duration_sec": consistency["descent_duration_sec"]["mean"],
            "avg_ascent_duration_sec": consistency["ascent_duration_sec"]["mean"],
            "avg_max_knee_flexion_deg": consistency["max_knee_flexion_deg"]["mean"],
            "avg_max_hip_flexion_deg": consistency["max_hip_flexion_deg"]["mean"],
            "avg_max_trunk_inclination_deg": consistency["max_trunk_inclination_deg"]["mean"],
            "avg_trunk_inclination_delta_deg": _stats(trunk_deltas)["mean"],
            "avg_hip_depth_ratio": _stats(depth_ratios)["mean"],
        },
    }


def _analyze_lunge(biomech: Dict[str, Any], camera_perspective: str) -> Dict[str, Any]:
    timestamps = biomech["timestamps_sec"]
    angles = biomech["angles_deg"]
    summaries = biomech["joint_summaries"]
    n = len(timestamps)
    fps = (n - 1) / max(0.1, timestamps[-1] - timestamps[0]) if n >= 2 else 30.0

    lk = angles.get("left_knee_flexion", [None] * n)
    rk = angles.get("right_knee_flexion", [None] * n)
    lh = angles.get("left_hip_flexion", [None] * n)
    rh = angles.get("right_hip_flexion", [None] * n)
    trunk = angles.get("trunk_inclination", [None] * n)

    # Combined max knee flexion per frame tracks whichever leg is flexing deeper into the lunge
    combined_knee: List[Optional[float]] = []
    for i in range(n):
        if lk[i] is not None and rk[i] is not None:
            combined_knee.append(max(float(lk[i]), float(rk[i])))
        elif lk[i] is not None:
            combined_knee.append(float(lk[i]))
        elif rk[i] is not None:
            combined_knee.append(float(rk[i]))
        else:
            combined_knee.append(None)

    sig, valid_mask = _fill_for_segmentation(combined_knee)
    valid_ratio = float(np.mean(valid_mask)) if n > 0 else 0.0
    phases = ["STARTING_POSITION"] * n

    if n < 5 or valid_ratio < 0.25:
        return {
            "movement_type": "lunge",
            "primary_side_tracked": "combined",
            "rep_count": 0,
            "frame_phases": phases,
            "repetitions": [],
            "consistency": {},
            "summary_metrics": {"sufficient_data": False},
        }

    baseline_knee = float(np.percentile(sig[valid_mask], 15))
    min_peak_height = max(45.0, baseline_knee + 28.0)
    min_dist = max(2, int(round(0.75 * fps)))
    peaks, _ = find_peaks(sig, height=min_peak_height, prominence=25.0, distance=min_dist)
    valid_peaks = [int(p) for p in peaks if np.any(valid_mask[max(0, p - 2) : min(n, p + 3)])]

    repetitions: List[Dict[str, Any]] = []
    for rep_idx, p_idx in enumerate(valid_peaks):
        prev_p = valid_peaks[rep_idx - 1] if rep_idx > 0 else -1
        next_p = valid_peaks[rep_idx + 1] if rep_idx + 1 < len(valid_peaks) else -1
        s_idx, b_start, b_end, e_idx = _find_cycle_boundaries(sig, p_idx, prev_p, next_p, fps, baseline_knee)
        if e_idx <= s_idx or (timestamps[e_idx] - timestamps[s_idx]) < 0.45:
            continue

        for k in range(s_idx, b_start):
            phases[k] = "DESCENT"
        for k in range(b_start, b_end + 1):
            phases[k] = "BOTTOM"
        for k in range(b_end + 1, e_idx + 1):
            phases[k] = "ASCENT"
        if e_idx < n:
            phases[e_idx] = "RETURN_TO_STANDING"

        # Identify front vs rear knee at bottom based on hip flexion (front leg has greater hip flexion!)
        lh_p = lh[p_idx]
        rh_p = rh[p_idx]
        lk_p = lk[p_idx]
        rk_p = rk[p_idx]

        if lh_p is not None and rh_p is not None:
            front_is_left = lh_p >= rh_p
        elif lk_p is not None and rk_p is not None:
            front_is_left = lk_p >= rk_p
        else:
            front_is_left = lk_p is not None

        front_series = lk if front_is_left else rk
        rear_series = rk if front_is_left else lk
        front_hip_series = lh if front_is_left else rh

        front_vals = [front_series[k] for k in range(s_idx, e_idx + 1) if front_series[k] is not None]
        rear_vals = [rear_series[k] for k in range(s_idx, e_idx + 1) if rear_series[k] is not None]
        hip_vals = [front_hip_series[k] for k in range(s_idx, e_idx + 1) if front_hip_series[k] is not None]
        trunk_vals = [trunk[k] for k in range(s_idx, e_idx + 1) if trunk[k] is not None]

        descent_dur = round(float(timestamps[b_start] - timestamps[s_idx]), 3)
        ascent_dur = round(float(timestamps[e_idx] - timestamps[b_end]), 3)
        total_dur = round(float(timestamps[e_idx] - timestamps[s_idx]), 3)

        repetitions.append(
            {
                "rep_number": len(repetitions) + 1,
                "front_leg": "left" if front_is_left else "right",
                "start_frame": s_idx,
                "bottom_frame": p_idx,
                "end_frame": e_idx,
                "start_time_sec": round(float(timestamps[s_idx]), 3),
                "bottom_time_sec": round(float(timestamps[p_idx]), 3),
                "end_time_sec": round(float(timestamps[e_idx]), 3),
                "duration_sec": total_dur,
                "descent_duration_sec": descent_dur,
                "ascent_duration_sec": ascent_dur,
                "front_knee_max_flexion_deg": round(float(max(front_vals)), 2) if front_vals else None,
                "rear_knee_max_flexion_deg": round(float(max(rear_vals)), 2) if rear_vals else None,
                "front_knee_rom_deg": round(float(max(front_vals) - min(front_vals)), 2) if len(front_vals) >= 2 else None,
                "max_hip_flexion_deg": round(float(max(hip_vals)), 2) if hip_vals else None,
                "max_trunk_inclination_deg": round(float(max(trunk_vals)), 2) if trunk_vals else None,
                "normalized_primary_curve": _resample_cycle(front_series, s_idx, e_idx),
            }
        )

    rep_durs = [r["duration_sec"] for r in repetitions]
    front_knees = [r["front_knee_max_flexion_deg"] for r in repetitions]
    rear_knees = [r["rear_knee_max_flexion_deg"] for r in repetitions]
    trunks = [r["max_trunk_inclination_deg"] for r in repetitions]
    roms = [r["front_knee_rom_deg"] for r in repetitions]

    # Compare left-lead vs right-lead reps when both sides were performed
    left_lead_knees = [r["front_knee_max_flexion_deg"] for r in repetitions if r["front_leg"] == "left" and r["front_knee_max_flexion_deg"] is not None]
    right_lead_knees = [r["front_knee_max_flexion_deg"] for r in repetitions if r["front_leg"] == "right" and r["front_knee_max_flexion_deg"] is not None]
    lead_side_diff = (
        round(abs(float(np.mean(left_lead_knees)) - float(np.mean(right_lead_knees))), 2)
        if left_lead_knees and right_lead_knees
        else None
    )

    consistency = {
        "repetition_duration_sec": _stats(rep_durs),
        "front_knee_max_flexion_deg": _stats(front_knees),
        "rear_knee_max_flexion_deg": _stats(rear_knees),
        "max_trunk_inclination_deg": _stats(trunks),
        "front_knee_rom_deg": _stats(roms),
        "sufficient_for_consistency": len(repetitions) >= 2,
    }

    return {
        "movement_type": "lunge",
        "primary_side_tracked": "front_leg_dynamic",
        "primary_signal_label": "Primary Knee Flexion (deg)",
        "primary_signal_deg": [round(v, 2) if v is not None else None for v in combined_knee],
        "rep_count": len(repetitions),
        "total_movement_duration_sec": round(sum(r["duration_sec"] for r in repetitions), 3) if repetitions else round(float(timestamps[-1] - timestamps[0]), 3),
        "lead_side_knee_diff_deg": lead_side_diff,
        "frame_phases": phases,
        "repetitions": repetitions,
        "consistency": consistency,
        "summary_metrics": {
            "sufficient_data": len(repetitions) > 0 or valid_ratio >= 0.5,
            "avg_rep_duration_sec": consistency["repetition_duration_sec"]["mean"],
            "avg_front_knee_flexion_deg": consistency["front_knee_max_flexion_deg"]["mean"],
            "avg_rear_knee_flexion_deg": consistency["rear_knee_max_flexion_deg"]["mean"],
            "avg_max_trunk_inclination_deg": consistency["max_trunk_inclination_deg"]["mean"],
            "avg_front_knee_rom_deg": consistency["front_knee_rom_deg"]["mean"],
            "lead_side_knee_diff_deg": lead_side_diff,
        },
    }


def _analyze_jumping_jack(biomech: Dict[str, Any], camera_perspective: str) -> Dict[str, Any]:
    timestamps = biomech["timestamps_sec"]
    angles = biomech["angles_deg"]
    ratios = biomech["kinematic_ratios"]
    n = len(timestamps)
    fps = (n - 1) / max(0.1, timestamps[-1] - timestamps[0]) if n >= 2 else 30.0

    l_sh = angles.get("left_shoulder_angle", [None] * n)
    r_sh = angles.get("right_shoulder_angle", [None] * n)
    l_hip = angles.get("left_hip_internal", [None] * n)
    r_hip = angles.get("right_hip_internal", [None] * n)
    ankle_spread = ratios["ankle_spread_ratio"]
    l_arm_elev = ratios["left_arm_elevation_ratio"]
    r_arm_elev = ratios["right_arm_elevation_ratio"]

    mean_shoulder: List[Optional[float]] = []
    for lv, rv in zip(l_sh, r_sh):
        if lv is not None and rv is not None:
            mean_shoulder.append(0.5 * (float(lv) + float(rv)))
        elif lv is not None:
            mean_shoulder.append(float(lv))
        elif rv is not None:
            mean_shoulder.append(float(rv))
        else:
            mean_shoulder.append(None)

    sig, valid_mask = _fill_for_segmentation(mean_shoulder)
    valid_ratio = float(np.mean(valid_mask)) if n > 0 else 0.0
    phases = ["INITIAL_STANDING"] * n

    if n < 5 or valid_ratio < 0.25:
        return {
            "movement_type": "jumping_jack",
            "primary_side_tracked": "bilateral",
            "rep_count": 0,
            "frame_phases": phases,
            "repetitions": [],
            "consistency": {},
            "summary_metrics": {"sufficient_data": False},
        }

    baseline_sh = float(np.percentile(sig[valid_mask], 15))
    min_peak_height = max(75.0, baseline_sh + 45.0)
    min_dist = max(2, int(round(0.45 * fps)))
    peaks, _ = find_peaks(sig, height=min_peak_height, prominence=35.0, distance=min_dist)
    valid_peaks = [int(p) for p in peaks if np.any(valid_mask[max(0, p - 2) : min(n, p + 3)])]

    repetitions: List[Dict[str, Any]] = []
    for rep_idx, p_idx in enumerate(valid_peaks):
        prev_p = valid_peaks[rep_idx - 1] if rep_idx > 0 else -1
        next_p = valid_peaks[rep_idx + 1] if rep_idx + 1 < len(valid_peaks) else -1
        s_idx, b_start, b_end, e_idx = _find_cycle_boundaries(sig, p_idx, prev_p, next_p, fps, baseline_sh)
        if e_idx <= s_idx or (timestamps[e_idx] - timestamps[s_idx]) < 0.30:
            continue

        for k in range(s_idx, b_start):
            phases[k] = "OUTWARD_MOVEMENT"
        for k in range(b_start, b_end + 1):
            phases[k] = "MAXIMUM_EXTENSION"
        for k in range(b_end + 1, e_idx + 1):
            phases[k] = "RETURN_MOVEMENT"

        l_sh_vals = [l_sh[k] for k in range(s_idx, e_idx + 1) if l_sh[k] is not None]
        r_sh_vals = [r_sh[k] for k in range(s_idx, e_idx + 1) if r_sh[k] is not None]
        l_hip_vals = [l_hip[k] for k in range(s_idx, e_idx + 1) if l_hip[k] is not None]
        r_hip_vals = [r_hip[k] for k in range(s_idx, e_idx + 1) if r_hip[k] is not None]
        spread_vals = [ankle_spread[k] for k in range(s_idx, e_idx + 1) if ankle_spread[k] is not None]
        elev_vals = [
            0.5 * (l_arm_elev[k] + r_arm_elev[k])
            for k in range(s_idx, e_idx + 1)
            if l_arm_elev[k] is not None and r_arm_elev[k] is not None
        ]

        max_l_sh = round(float(max(l_sh_vals)), 2) if l_sh_vals else None
        max_r_sh = round(float(max(r_sh_vals)), 2) if r_sh_vals else None
        peak_mean_sh = (
            round(0.5 * (max_l_sh + max_r_sh), 2)
            if (max_l_sh is not None and max_r_sh is not None)
            else (max_l_sh or max_r_sh)
        )
        sh_sym_diff = round(abs(max_l_sh - max_r_sh), 2) if (max_l_sh is not None and max_r_sh is not None) else None
        hip_abduction_rom = None
        if l_hip_vals and r_hip_vals:
            hip_abduction_rom = round(0.5 * ((max(l_hip_vals) - min(l_hip_vals)) + (max(r_hip_vals) - min(r_hip_vals))), 2)

        repetitions.append(
            {
                "rep_number": len(repetitions) + 1,
                "start_frame": s_idx,
                "peak_frame": p_idx,
                "end_frame": e_idx,
                "start_time_sec": round(float(timestamps[s_idx]), 3),
                "peak_time_sec": round(float(timestamps[p_idx]), 3),
                "end_time_sec": round(float(timestamps[e_idx]), 3),
                "duration_sec": round(float(timestamps[e_idx] - timestamps[s_idx]), 3),
                "outward_duration_sec": round(float(timestamps[b_start] - timestamps[s_idx]), 3),
                "return_duration_sec": round(float(timestamps[e_idx] - timestamps[b_end]), 3),
                "max_left_shoulder_deg": max_l_sh,
                "max_right_shoulder_deg": max_r_sh,
                "max_mean_shoulder_deg": peak_mean_sh,
                "shoulder_peak_diff_deg": sh_sym_diff,
                "hip_abduction_rom_deg": hip_abduction_rom,
                "max_ankle_spread_ratio": round(float(max(spread_vals)), 3) if spread_vals else None,
                "max_arm_elevation_ratio": round(float(max(elev_vals)), 3) if elev_vals else None,
                "normalized_primary_curve": _resample_cycle(mean_shoulder, s_idx, e_idx),
            }
        )

    consistency = {
        "repetition_duration_sec": _stats([r["duration_sec"] for r in repetitions]),
        "max_mean_shoulder_deg": _stats([r["max_mean_shoulder_deg"] for r in repetitions]),
        "max_ankle_spread_ratio": _stats([r["max_ankle_spread_ratio"] for r in repetitions]),
        "hip_abduction_rom_deg": _stats([r["hip_abduction_rom_deg"] for r in repetitions]),
        "sufficient_for_consistency": len(repetitions) >= 2,
    }

    return {
        "movement_type": "jumping_jack",
        "primary_side_tracked": "bilateral",
        "primary_signal_label": "Mean Shoulder Abduction Angle (deg)",
        "primary_signal_deg": [round(v, 2) if v is not None else None for v in mean_shoulder],
        "rep_count": len(repetitions),
        "total_movement_duration_sec": round(sum(r["duration_sec"] for r in repetitions), 3) if repetitions else round(float(timestamps[-1] - timestamps[0]), 3),
        "frame_phases": phases,
        "repetitions": repetitions,
        "consistency": consistency,
        "summary_metrics": {
            "sufficient_data": len(repetitions) > 0 or valid_ratio >= 0.5,
            "avg_rep_duration_sec": consistency["repetition_duration_sec"]["mean"],
            "avg_max_shoulder_angle_deg": consistency["max_mean_shoulder_deg"]["mean"],
            "avg_ankle_spread_ratio": consistency["max_ankle_spread_ratio"]["mean"],
            "avg_hip_abduction_rom_deg": consistency["hip_abduction_rom_deg"]["mean"],
            "avg_arm_elevation_ratio": _stats([r["max_arm_elevation_ratio"] for r in repetitions])["mean"],
        },
    }


def _analyze_basketball_shooting(biomech: Dict[str, Any], camera_perspective: str) -> Dict[str, Any]:
    """Experimental basketball shooting kinematics module."""
    timestamps = biomech["timestamps_sec"]
    angles = biomech["angles_deg"]
    vels = biomech["angular_velocities_deg_s"]
    ratios = biomech["kinematic_ratios"]
    n = len(timestamps)
    fps = (n - 1) / max(0.1, timestamps[-1] - timestamps[0]) if n >= 2 else 30.0

    l_elev = ratios["left_arm_elevation_ratio"]
    r_elev = ratios["right_arm_elevation_ratio"]

    l_max_elev = max([v for v in l_elev if v is not None], default=-99.0)
    r_max_elev = max([v for v in r_elev if v is not None], default=-99.0)

    shooting_side = "right" if r_max_elev >= l_max_elev else "left"
    elev_series = r_elev if shooting_side == "right" else l_elev
    elbow_int = angles.get(f"{shooting_side}_elbow_internal", [None] * n)
    elbow_vel = vels.get(f"{shooting_side}_elbow_internal", [None] * n)
    shoulder_ang = angles.get(f"{shooting_side}_shoulder_angle", [None] * n)
    trunk_ang = angles.get("trunk_inclination", [None] * n)

    sig, valid_mask = _fill_for_segmentation(elev_series)
    valid_ratio = float(np.mean(valid_mask)) if n > 0 else 0.0
    phases = ["PREPARATION"] * n

    if n < 5 or valid_ratio < 0.25:
        return {
            "movement_type": "basketball_shooting",
            "primary_side_tracked": shooting_side,
            "rep_count": 0,
            "frame_phases": phases,
            "repetitions": [],
            "consistency": {},
            "summary_metrics": {"sufficient_data": False},
        }

    min_dist = max(3, int(round(0.9 * fps)))
    peaks, _ = find_peaks(sig, height=0.35, prominence=0.30, distance=min_dist)
    valid_peaks = [int(p) for p in peaks if np.any(valid_mask[max(0, p - 2) : min(n, p + 3)])]

    repetitions: List[Dict[str, Any]] = []
    for rep_idx, p_idx in enumerate(valid_peaks):
        prev_p = valid_peaks[rep_idx - 1] if rep_idx > 0 else -1
        next_p = valid_peaks[rep_idx + 1] if rep_idx + 1 < len(valid_peaks) else -1
        s_idx, b_start, b_end, e_idx = _find_cycle_boundaries(sig, p_idx, prev_p, next_p, fps, float(np.percentile(sig[valid_mask], 15)))
        if e_idx <= s_idx:
            continue

        # Identify preparation dip (lowest elbow internal angle before peak arm elevation)
        prep_end = max(s_idx + 1, b_start)
        dip_idx = s_idx
        min_elbow_dip = None
        for k in range(s_idx, prep_end):
            if elbow_int[k] is not None and (min_elbow_dip is None or elbow_int[k] < min_elbow_dip):
                min_elbow_dip = elbow_int[k]
                dip_idx = k

        for k in range(s_idx, dip_idx + 1):
            phases[k] = "PREPARATION_DIP"
        for k in range(dip_idx + 1, b_start):
            phases[k] = "UPWARD_EXTENSION"
        for k in range(b_start, b_end + 1):
            phases[k] = "RELEASE_POINT"
        for k in range(b_end + 1, e_idx + 1):
            phases[k] = "FOLLOW_THROUGH"

        el_at_release = elbow_int[p_idx]
        sh_at_release = shoulder_ang[p_idx]
        tr_at_release = trunk_ang[p_idx]
        ext_vels = [elbow_vel[k] for k in range(dip_idx, p_idx + 1) if elbow_vel[k] is not None and elbow_vel[k] > 0]

        repetitions.append(
            {
                "rep_number": len(repetitions) + 1,
                "shooting_arm": shooting_side,
                "start_frame": s_idx,
                "release_frame": p_idx,
                "end_frame": e_idx,
                "start_time_sec": round(float(timestamps[s_idx]), 3),
                "release_time_sec": round(float(timestamps[p_idx]), 3),
                "end_time_sec": round(float(timestamps[e_idx]), 3),
                "duration_sec": round(float(timestamps[e_idx] - timestamps[s_idx]), 3),
                "elbow_angle_at_dip_deg": round(float(min_elbow_dip), 2) if min_elbow_dip is not None else None,
                "elbow_angle_at_release_deg": round(float(el_at_release), 2) if el_at_release is not None else None,
                "shoulder_angle_at_release_deg": round(float(sh_at_release), 2) if sh_at_release is not None else None,
                "trunk_inclination_at_release_deg": round(float(tr_at_release), 2) if tr_at_release is not None else None,
                "peak_arm_elevation_ratio": round(float(sig[p_idx]), 3),
                "peak_elbow_extension_vel_deg_s": round(float(max(ext_vels)), 2) if ext_vels else None,
                "normalized_primary_curve": _resample_cycle(elbow_int, s_idx, e_idx),
            }
        )

    consistency = {
        "repetition_duration_sec": _stats([r["duration_sec"] for r in repetitions]),
        "elbow_angle_at_release_deg": _stats([r["elbow_angle_at_release_deg"] for r in repetitions]),
        "shoulder_angle_at_release_deg": _stats([r["shoulder_angle_at_release_deg"] for r in repetitions]),
        "sufficient_for_consistency": len(repetitions) >= 2,
    }

    return {
        "movement_type": "basketball_shooting",
        "experimental": True,
        "primary_side_tracked": shooting_side,
        "primary_signal_label": f"{shooting_side.title()} Arm Elevation Ratio (torso lengths)",
        "primary_signal_deg": [round(float(v) * 100.0, 2) if v is not None else None for v in elev_series],
        "rep_count": len(repetitions),
        "total_movement_duration_sec": round(sum(r["duration_sec"] for r in repetitions), 3) if repetitions else round(float(timestamps[-1] - timestamps[0]), 3),
        "frame_phases": phases,
        "repetitions": repetitions,
        "consistency": consistency,
        "ball_velocity_disclaimer": "Ball-release velocity and trajectory arc are not calculated because reliable ball tracking and metric spatial calibration are unavailable from uncalibrated 2D video.",
        "summary_metrics": {
            "sufficient_data": len(repetitions) > 0 or valid_ratio >= 0.5,
            "avg_rep_duration_sec": consistency["repetition_duration_sec"]["mean"],
            "avg_elbow_at_dip_deg": _stats([r["elbow_angle_at_dip_deg"] for r in repetitions])["mean"],
            "avg_elbow_at_release_deg": consistency["elbow_angle_at_release_deg"]["mean"],
            "avg_shoulder_at_release_deg": consistency["shoulder_angle_at_release_deg"]["mean"],
            "avg_trunk_at_release_deg": _stats([r["trunk_inclination_at_release_deg"] for r in repetitions])["mean"],
            "avg_peak_arm_elevation_ratio": _stats([r["peak_arm_elevation_ratio"] for r in repetitions])["mean"],
        },
    }


def classify_movement_and_reps(
    biomech: Dict[str, Any],
    movement_type: str,
    camera_perspective: str,
) -> Dict[str, Any]:
    """Dispatch to the movement-specific phase and repetition recognition module."""
    if movement_type == "squat":
        return _analyze_squat(biomech, camera_perspective)
    if movement_type == "lunge":
        return _analyze_lunge(biomech, camera_perspective)
    if movement_type == "jumping_jack":
        return _analyze_jumping_jack(biomech, camera_perspective)
    if movement_type == "basketball_shooting":
        return _analyze_basketball_shooting(biomech, camera_perspective)
    raise ValueError(f"Unsupported movement_type: {movement_type}")
