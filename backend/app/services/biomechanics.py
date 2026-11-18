"""Reusable biomechanics calculation engine for joint angles, angular velocities, trajectories, and symmetry."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from app.utils.filters import compute_angular_velocity, interpolate_short_gaps, smooth_series
from app.utils.geometry import (
    ANGLE_CONVENTIONS,
    Point2D,
    calculate_angle_3pt,
    calculate_trunk_inclination,
    euclidean_distance,
    internal_to_flexion_angle,
    midpoint,
)

# Which landmarks & angles are biomechanically relevant per movement module
MOVEMENT_ANGLE_PROFILES: Dict[str, List[str]] = {
    "squat": [
        "left_knee_internal",
        "left_knee_flexion",
        "right_knee_internal",
        "right_knee_flexion",
        "left_hip_internal",
        "left_hip_flexion",
        "right_hip_internal",
        "right_hip_flexion",
        "trunk_inclination",
    ],
    "lunge": [
        "left_knee_internal",
        "left_knee_flexion",
        "right_knee_internal",
        "right_knee_flexion",
        "left_hip_internal",
        "left_hip_flexion",
        "right_hip_internal",
        "right_hip_flexion",
        "trunk_inclination",
    ],
    "jumping_jack": [
        "left_shoulder_angle",
        "right_shoulder_angle",
        "left_hip_internal",
        "right_hip_internal",
        "left_elbow_internal",
        "right_elbow_internal",
    ],
    "basketball_shooting": [
        "left_elbow_internal",
        "left_elbow_flexion",
        "right_elbow_internal",
        "right_elbow_flexion",
        "left_shoulder_angle",
        "right_shoulder_angle",
        "left_knee_flexion",
        "right_knee_flexion",
        "trunk_inclination",
    ],
}

TRAJECTORY_LANDMARKS: Dict[str, Dict[str, int]] = {
    "squat": {"left_hip": 23, "right_hip": 24, "left_knee": 25, "right_knee": 26, "left_shoulder": 11, "right_shoulder": 12},
    "lunge": {"left_hip": 23, "right_hip": 24, "left_knee": 25, "right_knee": 26, "left_ankle": 27, "right_ankle": 28},
    "jumping_jack": {"left_wrist": 15, "right_wrist": 16, "left_ankle": 27, "right_ankle": 28, "left_shoulder": 11, "right_shoulder": 12},
    "basketball_shooting": {"left_wrist": 15, "right_wrist": 16, "left_elbow": 13, "right_elbow": 14, "left_shoulder": 11, "right_shoulder": 12, "right_hip": 24},
}


def _extract_smoothed_landmark_points(
    frame_records: List[Dict[str, Any]],
    landmark_idx: int,
    fps: float,
) -> Tuple[List[Optional[Point2D]], List[float]]:
    """
    Extract smoothed pixel coordinate trajectories for a single landmark across frames,
    interpolating only short <=3-frame internal dropouts and keeping unreliable spans as None.
    """
    xs: List[Optional[float]] = []
    ys: List[Optional[float]] = []
    confs: List[float] = []

    for rec in frame_records:
        lms = rec.get("landmarks")
        if not lms or landmark_idx >= len(lms):
            xs.append(None)
            ys.append(None)
            confs.append(0.0)
            continue
        lm = lms[landmark_idx]
        confs.append(float(lm.get("confidence", 0.0)))
        if lm.get("is_reliable", False):
            xs.append(float(lm["x_px"]))
            ys.append(float(lm["y_px"]))
        else:
            xs.append(None)
            ys.append(None)

    xs_interp = interpolate_short_gaps(xs, max_gap=3)
    ys_interp = interpolate_short_gaps(ys, max_gap=3)
    xs_smooth = smooth_series(xs_interp, fps=fps, window_sec=0.18, polyorder=2)
    ys_smooth = smooth_series(ys_interp, fps=fps, window_sec=0.18, polyorder=2)

    pts: List[Optional[Point2D]] = []
    for x, y in zip(xs_smooth, ys_smooth):
        if x is not None and y is not None and math.isfinite(x) and math.isfinite(y):
            pts.append((x, y))
        else:
            pts.append(None)
    return pts, confs


def _summarize_angle_series(
    angles: Sequence[Optional[float]],
    velocities: Sequence[Optional[float]],
    confs: Sequence[float],
    label: str,
    convention_key: str,
) -> Dict[str, Any]:
    """Compute statistical summary for an angle time series without fabricating missing observations."""
    valid_angles = [float(a) for a in angles if a is not None and math.isfinite(a)]
    valid_vels = [abs(float(v)) for v in velocities if v is not None and math.isfinite(v)]
    n_total = len(angles)
    n_valid = len(valid_angles)
    valid_ratio = (float(n_valid) / float(n_total)) if n_total > 0 else 0.0
    mean_conf = float(np.mean(confs)) if confs else 0.0

    conv = ANGLE_CONVENTIONS.get(convention_key, {})

    if n_valid == 0:
        return {
            "label": label,
            "convention_key": convention_key,
            "definition": conv.get("definition", ""),
            "landmarks": conv.get("landmarks", ""),
            "valid_frames": 0,
            "total_frames": n_total,
            "valid_ratio": 0.0,
            "mean_confidence": round(mean_conf, 4),
            "sufficient_data": False,
            "mean_deg": None,
            "min_deg": None,
            "max_deg": None,
            "std_deg": None,
            "rom_deg": None,
            "peak_angular_velocity_deg_s": None,
        }

    arr = np.array(valid_angles, dtype=np.float64)
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    return {
        "label": label,
        "convention_key": convention_key,
        "definition": conv.get("definition", ""),
        "landmarks": conv.get("landmarks", ""),
        "valid_frames": n_valid,
        "total_frames": n_total,
        "valid_ratio": round(valid_ratio, 4),
        "mean_confidence": round(mean_conf, 4),
        "sufficient_data": valid_ratio >= 0.35 and n_valid >= 5,
        "mean_deg": round(float(np.mean(arr)), 2),
        "min_deg": round(min_val, 2),
        "max_deg": round(max_val, 2),
        "std_deg": round(float(np.std(arr)), 2),
        "rom_deg": round(max_val - min_val, 2),
        "peak_angular_velocity_deg_s": round(float(np.max(valid_vels)), 2) if valid_vels else None,
    }


def _compute_bilateral_symmetry(
    left_series: Sequence[Optional[float]],
    right_series: Sequence[Optional[float]],
    timestamps: Sequence[float],
    joint_name: str,
    camera_perspective: str,
    inferred_perspective: str,
) -> Dict[str, Any]:
    """
    Compare left and right joint angles ONLY when both sides are simultaneously visible
    and the camera perspective supports meaningful bilateral comparison.
    """
    n = len(left_series)
    paired_diffs: List[Optional[float]] = [None] * n
    left_vals: List[float] = []
    right_vals: List[float] = []
    abs_diffs: List[float] = []

    for i in range(n):
        l_val = left_series[i]
        r_val = right_series[i]
        if l_val is not None and r_val is not None and math.isfinite(l_val) and math.isfinite(r_val):
            diff = float(l_val) - float(r_val)
            paired_diffs[i] = round(diff, 2)
            left_vals.append(float(l_val))
            right_vals.append(float(r_val))
            abs_diffs.append(abs(diff))

    paired_ratio = (float(len(abs_diffs)) / float(n)) if n > 0 else 0.0

    # Perspective compatibility check
    perspective_allows = (
        camera_perspective == "front"
        or inferred_perspective == "front"
        or (inferred_perspective == "oblique" and paired_ratio >= 0.70)
    )

    if len(abs_diffs) < max(5, int(0.45 * n)):
        return {
            "joint": joint_name,
            "is_valid_comparison": False,
            "paired_frames": len(abs_diffs),
            "paired_ratio": round(paired_ratio, 4),
            "mean_abs_diff_deg": None,
            "max_abs_diff_deg": None,
            "correlation": None,
            "difference_series_deg": paired_diffs,
            "reason": (
                f"Insufficient simultaneous left/right observations ({len(abs_diffs)}/{n} frames, "
                f"{paired_ratio * 100:.1f}%) to compare {joint_name} symmetry."
            ),
        }

    if not perspective_allows:
        return {
            "joint": joint_name,
            "is_valid_comparison": False,
            "paired_frames": len(abs_diffs),
            "paired_ratio": round(paired_ratio, 4),
            "mean_abs_diff_deg": None,
            "max_abs_diff_deg": None,
            "correlation": None,
            "difference_series_deg": paired_diffs,
            "reason": (
                f"Camera perspective ('{camera_perspective}') is sagittal/side-oriented; "
                "near-to-far limb parallax and occlusion prevent valid 2D left-right symmetry comparison."
            ),
        }

    corr: Optional[float] = None
    if len(left_vals) >= 5 and np.std(left_vals) > 1e-3 and np.std(right_vals) > 1e-3:
        corr = round(float(np.corrcoef(left_vals, right_vals)[0, 1]), 4)

    return {
        "joint": joint_name,
        "is_valid_comparison": True,
        "paired_frames": len(abs_diffs),
        "paired_ratio": round(paired_ratio, 4),
        "mean_abs_diff_deg": round(float(np.mean(abs_diffs)), 2),
        "max_abs_diff_deg": round(float(np.max(abs_diffs)), 2),
        "correlation": corr,
        "difference_series_deg": paired_diffs,
        "reason": "Both sides simultaneously visible under frontal/compatible framing (2D projected comparison).",
    }


def compute_biomechanics(
    pose_data: Dict[str, Any],
    movement_type: str,
    camera_perspective: str,
    inferred_perspective: str,
) -> Dict[str, Any]:
    """
    Run biomechanical kinematics calculations on extracted pose landmark sequences.
    """
    frame_records: List[Dict[str, Any]] = pose_data["frame_records"]
    fps: float = float(pose_data.get("effective_fps") or 30.0)
    timestamps: List[float] = [round(float(rec["timestamp_sec"]), 4) for rec in frame_records]
    n_frames = len(frame_records)

    needed_indices = {11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28}
    pts: Dict[int, List[Optional[Point2D]]] = {}
    confs: Dict[int, List[float]] = {}
    for idx in needed_indices:
        pts[idx], confs[idx] = _extract_smoothed_landmark_points(frame_records, idx, fps)

    relevant_keys = set(MOVEMENT_ANGLE_PROFILES.get(movement_type, MOVEMENT_ANGLE_PROFILES["squat"]))

    angles_raw: Dict[str, List[Optional[float]]] = {}
    angle_confs: Dict[str, List[float]] = {}

    def _triplet_confs(a_idx: int, b_idx: int, c_idx: int) -> List[float]:
        return [min(confs[a_idx][i], confs[b_idx][i], confs[c_idx][i]) for i in range(n_frames)]

    def _compute_triplet_angle(a_idx: int, b_idx: int, c_idx: int) -> List[Optional[float]]:
        return [calculate_angle_3pt(pts[a_idx][i], pts[b_idx][i], pts[c_idx][i]) for i in range(n_frames)]

    # Compute only movement-relevant joint angles
    if "left_knee_internal" in relevant_keys or "left_knee_flexion" in relevant_keys:
        lk_int = _compute_triplet_angle(23, 25, 27)
        angles_raw["left_knee_internal"] = lk_int
        angles_raw["left_knee_flexion"] = [internal_to_flexion_angle(v) for v in lk_int]
        c_lk = _triplet_confs(23, 25, 27)
        angle_confs["left_knee_internal"] = c_lk
        angle_confs["left_knee_flexion"] = c_lk

    if "right_knee_internal" in relevant_keys or "right_knee_flexion" in relevant_keys:
        rk_int = _compute_triplet_angle(24, 26, 28)
        angles_raw["right_knee_internal"] = rk_int
        angles_raw["right_knee_flexion"] = [internal_to_flexion_angle(v) for v in rk_int]
        c_rk = _triplet_confs(24, 26, 28)
        angle_confs["right_knee_internal"] = c_rk
        angle_confs["right_knee_flexion"] = c_rk

    if "left_hip_internal" in relevant_keys or "left_hip_flexion" in relevant_keys:
        lh_int = _compute_triplet_angle(11, 23, 25)
        angles_raw["left_hip_internal"] = lh_int
        angles_raw["left_hip_flexion"] = [internal_to_flexion_angle(v) for v in lh_int]
        c_lh = _triplet_confs(11, 23, 25)
        angle_confs["left_hip_internal"] = c_lh
        angle_confs["left_hip_flexion"] = c_lh

    if "right_hip_internal" in relevant_keys or "right_hip_flexion" in relevant_keys:
        rh_int = _compute_triplet_angle(12, 24, 26)
        angles_raw["right_hip_internal"] = rh_int
        angles_raw["right_hip_flexion"] = [internal_to_flexion_angle(v) for v in rh_int]
        c_rh = _triplet_confs(12, 24, 26)
        angle_confs["right_hip_internal"] = c_rh
        angle_confs["right_hip_flexion"] = c_rh

    if "left_elbow_internal" in relevant_keys or "left_elbow_flexion" in relevant_keys:
        le_int = _compute_triplet_angle(11, 13, 15)
        angles_raw["left_elbow_internal"] = le_int
        angles_raw["left_elbow_flexion"] = [internal_to_flexion_angle(v) for v in le_int]
        c_le = _triplet_confs(11, 13, 15)
        angle_confs["left_elbow_internal"] = c_le
        angle_confs["left_elbow_flexion"] = c_le

    if "right_elbow_internal" in relevant_keys or "right_elbow_flexion" in relevant_keys:
        re_int = _compute_triplet_angle(12, 14, 16)
        angles_raw["right_elbow_internal"] = re_int
        angles_raw["right_elbow_flexion"] = [internal_to_flexion_angle(v) for v in re_int]
        c_re = _triplet_confs(12, 14, 16)
        angle_confs["right_elbow_internal"] = c_re
        angle_confs["right_elbow_flexion"] = c_re

    if "left_shoulder_angle" in relevant_keys:
        angles_raw["left_shoulder_angle"] = _compute_triplet_angle(23, 11, 13)
        angle_confs["left_shoulder_angle"] = _triplet_confs(23, 11, 13)

    if "right_shoulder_angle" in relevant_keys:
        angles_raw["right_shoulder_angle"] = _compute_triplet_angle(24, 12, 14)
        angle_confs["right_shoulder_angle"] = _triplet_confs(24, 12, 14)

    if "trunk_inclination" in relevant_keys:
        trunk_vals: List[Optional[float]] = []
        trunk_confs: List[float] = []
        for i in range(n_frames):
            # Prefer mid-hip to mid-shoulder when both sides reliable; fallback to the visible side
            mid_hip = midpoint(pts[23][i], pts[24][i])
            mid_sh = midpoint(pts[11][i], pts[12][i])
            if mid_hip is not None and mid_sh is not None:
                trunk_vals.append(calculate_trunk_inclination(mid_hip, mid_sh))
                trunk_confs.append(min(confs[11][i], confs[12][i], confs[23][i], confs[24][i]))
            elif pts[23][i] is not None and pts[11][i] is not None:
                trunk_vals.append(calculate_trunk_inclination(pts[23][i], pts[11][i]))
                trunk_confs.append(min(confs[11][i], confs[23][i]))
            elif pts[24][i] is not None and pts[12][i] is not None:
                trunk_vals.append(calculate_trunk_inclination(pts[24][i], pts[12][i]))
                trunk_confs.append(min(confs[12][i], confs[24][i]))
            else:
                trunk_vals.append(None)
                trunk_confs.append(0.0)
        angles_raw["trunk_inclination"] = trunk_vals
        angle_confs["trunk_inclination"] = trunk_confs

    # Smooth valid angle series and compute angular velocities using actual timestamps
    angles_smoothed: Dict[str, List[Optional[float]]] = {}
    angular_velocities: Dict[str, List[Optional[float]]] = {}
    joint_summaries: Dict[str, Dict[str, Any]] = {}

    CONVENTION_MAP = {
        "left_knee_internal": ("Left Knee Internal Angle", "knee_internal"),
        "right_knee_internal": ("Right Knee Internal Angle", "knee_internal"),
        "left_knee_flexion": ("Left Knee Flexion Angle", "knee_flexion"),
        "right_knee_flexion": ("Right Knee Flexion Angle", "knee_flexion"),
        "left_hip_internal": ("Left Hip Internal Angle", "hip_internal"),
        "right_hip_internal": ("Right Hip Internal Angle", "hip_internal"),
        "left_hip_flexion": ("Left Hip Flexion Angle", "hip_flexion"),
        "right_hip_flexion": ("Right Hip Flexion Angle", "hip_flexion"),
        "left_elbow_internal": ("Left Elbow Internal Angle", "elbow_internal"),
        "right_elbow_internal": ("Right Elbow Internal Angle", "elbow_internal"),
        "left_elbow_flexion": ("Left Elbow Flexion Angle", "elbow_flexion"),
        "right_elbow_flexion": ("Right Elbow Flexion Angle", "elbow_flexion"),
        "left_shoulder_angle": ("Left Shoulder Angle", "shoulder_angle"),
        "right_shoulder_angle": ("Right Shoulder Angle", "shoulder_angle"),
        "trunk_inclination": ("Trunk Inclination", "trunk_inclination"),
    }

    for key in relevant_keys:
        if key not in angles_raw:
            continue
        sm = smooth_series(angles_raw[key], fps=fps, window_sec=0.20, polyorder=2)
        sm_rounded = [round(v, 2) if (v is not None and math.isfinite(v)) else None for v in sm]
        vel = compute_angular_velocity(sm, timestamps_sec=timestamps, fps=fps)
        vel_rounded = [round(v, 2) if (v is not None and math.isfinite(v)) else None for v in vel]
        angles_smoothed[key] = sm_rounded
        angular_velocities[key] = vel_rounded
        label, conv_key = CONVENTION_MAP[key]
        joint_summaries[key] = _summarize_angle_series(
            sm_rounded, vel_rounded, angle_confs[key], label=label, convention_key=conv_key
        )

    # Movement-specific normalized positional kinematics (depth, arm elevation, stance spread)
    kinematic_ratios: Dict[str, List[Optional[float]]] = {
        "left_hip_depth_ratio": [],
        "right_hip_depth_ratio": [],
        "left_arm_elevation_ratio": [],
        "right_arm_elevation_ratio": [],
        "ankle_spread_ratio": [],
    }
    for i in range(n_frames):
        # Hip vertical depth relative to knee normalized by thigh length (+ means hip below knee in image y)
        l_thigh = euclidean_distance(pts[23][i], pts[25][i])
        if l_thigh and l_thigh > 10.0 and pts[23][i] and pts[25][i]:
            kinematic_ratios["left_hip_depth_ratio"].append(round((pts[23][i][1] - pts[25][i][1]) / l_thigh, 3))
        else:
            kinematic_ratios["left_hip_depth_ratio"].append(None)

        r_thigh = euclidean_distance(pts[24][i], pts[26][i])
        if r_thigh and r_thigh > 10.0 and pts[24][i] and pts[26][i]:
            kinematic_ratios["right_hip_depth_ratio"].append(round((pts[24][i][1] - pts[26][i][1]) / r_thigh, 3))
        else:
            kinematic_ratios["right_hip_depth_ratio"].append(None)

        l_torso = euclidean_distance(pts[11][i], pts[23][i])
        if l_torso and l_torso > 10.0 and pts[11][i] and pts[15][i]:
            kinematic_ratios["left_arm_elevation_ratio"].append(round((pts[11][i][1] - pts[15][i][1]) / l_torso, 3))
        else:
            kinematic_ratios["left_arm_elevation_ratio"].append(None)

        r_torso = euclidean_distance(pts[12][i], pts[24][i])
        if r_torso and r_torso > 10.0 and pts[12][i] and pts[16][i]:
            kinematic_ratios["right_arm_elevation_ratio"].append(round((pts[12][i][1] - pts[16][i][1]) / r_torso, 3))
        else:
            kinematic_ratios["right_arm_elevation_ratio"].append(None)

        torso_ref = l_torso or r_torso
        if torso_ref and torso_ref > 10.0 and pts[27][i] and pts[28][i]:
            ankle_dist = abs(pts[27][i][0] - pts[28][i][0])
            kinematic_ratios["ankle_spread_ratio"].append(round(ankle_dist / torso_ref, 3))
        else:
            kinematic_ratios["ankle_spread_ratio"].append(None)

    # Joint 2D normalized trajectories for key movement joints
    traj_map = TRAJECTORY_LANDMARKS.get(movement_type, TRAJECTORY_LANDMARKS["squat"])
    trajectories: Dict[str, List[Dict[str, Optional[float]]]] = {}
    for joint_label, lm_idx in traj_map.items():
        series = []
        for i in range(n_frames):
            lms = frame_records[i].get("landmarks")
            if lms and lms[lm_idx]["is_reliable"]:
                series.append(
                    {
                        "t": timestamps[i],
                        "x": round(float(lms[lm_idx]["x_norm"]), 4),
                        "y": round(float(lms[lm_idx]["y_norm"]), 4),
                    }
                )
            else:
                series.append({"t": timestamps[i], "x": None, "y": None})
        trajectories[joint_label] = series

    # Bilateral movement symmetry checks
    symmetry: Dict[str, Any] = {}
    if "left_knee_flexion" in angles_smoothed and "right_knee_flexion" in angles_smoothed:
        symmetry["knee_flexion"] = _compute_bilateral_symmetry(
            angles_smoothed["left_knee_flexion"],
            angles_smoothed["right_knee_flexion"],
            timestamps,
            "Knee Flexion",
            camera_perspective,
            inferred_perspective,
        )
    if "left_hip_flexion" in angles_smoothed and "right_hip_flexion" in angles_smoothed:
        symmetry["hip_flexion"] = _compute_bilateral_symmetry(
            angles_smoothed["left_hip_flexion"],
            angles_smoothed["right_hip_flexion"],
            timestamps,
            "Hip Flexion",
            camera_perspective,
            inferred_perspective,
        )
    if "left_shoulder_angle" in angles_smoothed and "right_shoulder_angle" in angles_smoothed:
        symmetry["shoulder_angle"] = _compute_bilateral_symmetry(
            angles_smoothed["left_shoulder_angle"],
            angles_smoothed["right_shoulder_angle"],
            timestamps,
            "Shoulder Elevation/Abduction",
            camera_perspective,
            inferred_perspective,
        )
    if "left_hip_internal" in angles_smoothed and "right_hip_internal" in angles_smoothed and movement_type == "jumping_jack":
        symmetry["hip_internal"] = _compute_bilateral_symmetry(
            angles_smoothed["left_hip_internal"],
            angles_smoothed["right_hip_internal"],
            timestamps,
            "Hip Abduction/Internal Angle",
            camera_perspective,
            inferred_perspective,
        )

    return {
        "timestamps_sec": timestamps,
        "angles_deg": angles_smoothed,
        "angular_velocities_deg_s": angular_velocities,
        "joint_summaries": joint_summaries,
        "kinematic_ratios": kinematic_ratios,
        "trajectories": trajectories,
        "symmetry": symmetry,
        "angle_conventions": {
            k: v for k, v in ANGLE_CONVENTIONS.items() if any(k in rk for rk in relevant_keys)
        },
    }
