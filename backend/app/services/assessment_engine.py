"""Evidence-based biomechanical assessment engine with transparent criteria and missing-data safeguards."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

STATUS_GOOD = "GOOD"
STATUS_NEEDS_IMPROVEMENT = "NEEDS IMPROVEMENT"
STATUS_OUTSIDE = "OUTSIDE REFERENCE RANGE"
STATUS_INSUFFICIENT = "INSUFFICIENT DATA"

SOURCE_BIOMECH = "ESTABLISHED_BIOMECHANICAL_DEFINITION"
SOURCE_RESEARCH = "RESEARCH_SUPPORTED_REFERENCE"
SOURCE_PROTOTYPE = "ENGINEERING_PROTOTYPE_THRESHOLD"

DEFAULT_CRITERIA: Dict[str, Dict[str, float]] = {
    "squat_knee_flexion_good_min": 85.0,
    "squat_knee_flexion_needs_min": 65.0,
    "squat_knee_flexion_max": 145.0,
    "squat_trunk_good_max": 35.0,
    "squat_trunk_needs_max": 50.0,
    "squat_cv_good_max": 10.0,
    "squat_cv_needs_max": 18.0,
    "squat_sym_diff_good_max": 8.0,
    "squat_sym_diff_needs_max": 15.0,
    "lunge_front_knee_good_min": 80.0,
    "lunge_front_knee_needs_min": 60.0,
    "lunge_rear_knee_good_min": 70.0,
    "lunge_rear_knee_needs_min": 50.0,
    "lunge_trunk_good_max": 25.0,
    "lunge_trunk_needs_max": 38.0,
    "jj_shoulder_good_min": 135.0,
    "jj_shoulder_needs_min": 105.0,
    "jj_spread_good_min": 0.55,
    "jj_spread_needs_min": 0.35,
    "jj_sym_diff_good_max": 10.0,
    "jj_sym_diff_needs_max": 18.0,
    "bball_elbow_release_min": 135.0,
    "bball_elbow_release_max": 175.0,
    "bball_shoulder_release_min": 100.0,
    "bball_shoulder_release_max": 155.0,
}

STATUS_SCORE_MAP = {
    STATUS_GOOD: 100.0,
    STATUS_NEEDS_IMPROVEMENT: 70.0,
    STATUS_OUTSIDE: 40.0,
}


def _make_param(
    name: str,
    measured_value: Optional[float],
    unit: str,
    reference_range: str,
    criteria_source: str,
    status: str,
    explanation: str,
    confidence: float,
    weight: float,
    recommendation: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "parameter_name": name,
        "measured_value": round(float(measured_value), 2) if (measured_value is not None and math.isfinite(measured_value)) else None,
        "unit": unit,
        "reference_range": reference_range,
        "criteria_source": criteria_source,
        "status": status,
        "explanation": explanation,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
        "weight": weight,
        "recommendation": recommendation,
    }


def _evaluate_squat(
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    quality: Dict[str, Any],
    cfg: Dict[str, float],
) -> List[Dict[str, Any]]:
    params: List[Dict[str, Any]] = []
    reps = movement.get("repetitions", [])
    summary = movement.get("summary_metrics", {})
    consistency = movement.get("consistency", {})
    mean_conf = quality.get("mean_landmark_confidence", 0.0)
    persp = quality.get("selected_perspective", "side")

    # 1. Squat Depth (Peak Knee Flexion)
    avg_knee = summary.get("avg_max_knee_flexion_deg")
    avg_depth_ratio = summary.get("avg_hip_depth_ratio")
    if avg_knee is None or len(reps) == 0:
        params.append(
            _make_param(
                "Squat Depth (Peak Knee Flexion)",
                None,
                "deg",
                f">= {cfg['squat_knee_flexion_good_min']:.0f} deg flexion (near parallel)",
                SOURCE_RESEARCH,
                STATUS_INSUFFICIENT,
                "No complete squat repetitions with reliable lower-body landmarks were detected to quantify peak knee flexion.",
                mean_conf,
                weight=0.30,
                recommendation="Ensure full body from shoulders to ankles remains visible throughout the squat cycle.",
            )
        )
    elif persp == "front" and quality.get("inferred_perspective") == "front":
        # Frontal foreshortening reduces true sagittal flexion angle reliability
        params.append(
            _make_param(
                "Squat Depth (Projected Knee Flexion)",
                avg_knee,
                "deg",
                "Sagittal view required for true flexion depth",
                SOURCE_BIOMECH,
                STATUS_INSUFFICIENT,
                f"Projected frontal knee flexion averaged {avg_knee:.1f} deg across {len(reps)} repetitions, but frontal perspective foreshortens sagittal knee flexion; use a side view for accurate depth assessment.",
                mean_conf * 0.65,
                weight=0.30,
                recommendation="Record a perpendicular side view for sagittal-plane squat depth evaluation.",
            )
        )
    else:
        depth_ctx = f" (hip-to-knee vertical ratio {avg_depth_ratio:+.2f} thigh lengths)" if avg_depth_ratio is not None else ""
        if cfg["squat_knee_flexion_good_min"] <= avg_knee <= cfg["squat_knee_flexion_max"]:
            st = STATUS_GOOD
            exp = f"Peak knee flexion averaged {avg_knee:.1f} deg across {len(reps)} repetition(s){depth_ctx}, meeting the target sagittal flexion zone ({cfg['squat_knee_flexion_good_min']:.0f}-{cfg['squat_knee_flexion_max']:.0f} deg)."
            rec = None
        elif cfg["squat_knee_flexion_needs_min"] <= avg_knee < cfg["squat_knee_flexion_good_min"]:
            st = STATUS_NEEDS_IMPROVEMENT
            exp = f"Peak knee flexion averaged {avg_knee:.1f} deg{depth_ctx}, which is {cfg['squat_knee_flexion_good_min'] - avg_knee:.1f} deg short of the {cfg['squat_knee_flexion_good_min']:.0f} deg parallel-depth prototype threshold."
            rec = "Focus on controlled hip and knee descent depth as mobility and stance width allow."
        else:
            st = STATUS_OUTSIDE
            exp = f"Peak knee flexion averaged {avg_knee:.1f} deg{depth_ctx}, outside the reference squat flexion window ({cfg['squat_knee_flexion_needs_min']:.0f}-{cfg['squat_knee_flexion_max']:.0f} deg)."
            rec = "Check squat depth target and ensure camera is positioned perpendicular to the movement plane."
        params.append(
            _make_param(
                "Squat Depth (Peak Knee Flexion)",
                avg_knee,
                "deg",
                f"{cfg['squat_knee_flexion_good_min']:.0f}-{cfg['squat_knee_flexion_max']:.0f} deg",
                SOURCE_PROTOTYPE,
                st,
                exp,
                mean_conf,
                weight=0.30,
                recommendation=rec,
            )
        )

    # 2. Trunk Inclination
    avg_trunk = summary.get("avg_max_trunk_inclination_deg")
    avg_trunk_delta = summary.get("avg_trunk_inclination_delta_deg")
    base_trunk = movement.get("standing_trunk_baseline_deg")
    if avg_trunk is None or len(reps) == 0:
        params.append(
            _make_param(
                "Peak Trunk Inclination",
                None,
                "deg",
                f"<= {cfg['squat_trunk_good_max']:.0f} deg from vertical",
                SOURCE_PROTOTYPE,
                STATUS_INSUFFICIENT,
                "Trunk landmarks (shoulder and hip) were not sufficiently tracked during repetitions.",
                mean_conf,
                weight=0.25,
            )
        )
    else:
        delta_txt = (
            f" (increasing by {avg_trunk_delta:+.1f} deg from your {base_trunk:.1f} deg initial standing posture)"
            if (avg_trunk_delta is not None and base_trunk is not None)
            else ""
        )
        if avg_trunk <= cfg["squat_trunk_good_max"]:
            st = STATUS_GOOD
            exp = f"Trunk inclination peaked at an average of {avg_trunk:.1f} deg from vertical{delta_txt}, remaining within the upright control threshold (<= {cfg['squat_trunk_good_max']:.0f} deg)."
            rec = None
        elif avg_trunk <= cfg["squat_trunk_needs_max"]:
            st = STATUS_NEEDS_IMPROVEMENT
            exp = f"Your trunk inclination averaged {avg_trunk:.1f} deg at maximum descent{delta_txt}, moderately exceeding the {cfg['squat_trunk_good_max']:.0f} deg prototype target."
            rec = "Keep chest elevated and synchronize hip hinge with knee travel during descent."
        else:
            st = STATUS_OUTSIDE
            exp = f"Trunk inclination reached an average of {avg_trunk:.1f} deg{delta_txt}, exceeding the {cfg['squat_trunk_needs_max']:.0f} deg upper reference limit for upright torso control."
            rec = "Reduce excessive forward torso lean by checking ankle dorsiflexion mobility and stance alignment."
        params.append(
            _make_param(
                "Peak Trunk Inclination",
                avg_trunk,
                "deg",
                f"<= {cfg['squat_trunk_good_max']:.0f} deg",
                SOURCE_PROTOTYPE,
                st,
                exp,
                mean_conf,
                weight=0.25,
                recommendation=rec,
            )
        )

    # 3. Descent / Ascent Tempo Control
    avg_desc = summary.get("avg_descent_duration_sec")
    avg_asc = summary.get("avg_ascent_duration_sec")
    if avg_desc is None or avg_asc is None or avg_asc <= 0.05 or len(reps) == 0:
        params.append(
            _make_param(
                "Descent-to-Ascent Tempo Control",
                None,
                "ratio",
                "1.0 - 2.5x descent/ascent ratio",
                SOURCE_PROTOTYPE,
                STATUS_INSUFFICIENT,
                "Insufficient valid repetition phase transitions to quantify descent-to-ascent tempo.",
                mean_conf,
                weight=0.15,
            )
        )
    else:
        ratio = avg_desc / avg_asc
        if 0.85 <= ratio <= 2.60 and avg_desc >= 0.55:
            st = STATUS_GOOD
            exp = f"Average descent lasted {avg_desc:.2f}s versus {avg_asc:.2f}s ascent (ratio {ratio:.2f}), demonstrating controlled eccentric lowering."
            rec = None
        elif 0.55 <= ratio <= 3.50 and avg_desc >= 0.35:
            st = STATUS_NEEDS_IMPROVEMENT
            exp = f"Average descent duration was {avg_desc:.2f}s vs {avg_asc:.2f}s ascent (ratio {ratio:.2f}), slightly fast or asymmetric relative to controlled tempo."
            rec = "Aim for a deliberate 1-2 second controlled descent before driving upward."
        else:
            st = STATUS_OUTSIDE
            exp = f"Descent duration ({avg_desc:.2f}s) relative to ascent ({avg_asc:.2f}s, ratio {ratio:.2f}) fell outside controlled movement tempo guidelines."
            rec = "Slow down the lowering phase to maintain consistent joint control into the bottom position."
        params.append(
            _make_param(
                "Descent-to-Ascent Tempo Control",
                ratio,
                "ratio",
                "0.85 - 2.60 (descent >= 0.55s)",
                SOURCE_PROTOTYPE,
                st,
                exp,
                mean_conf,
                weight=0.15,
                recommendation=rec,
            )
        )

    # 4. Repetition Consistency (CV of Peak Knee Flexion)
    knee_cv = (consistency.get("max_knee_flexion_deg") or {}).get("cv_percent")
    knee_std = (consistency.get("max_knee_flexion_deg") or {}).get("std")
    if knee_cv is None or len(reps) < 2:
        params.append(
            _make_param(
                "Repetition Depth Consistency (CV)",
                None,
                "%",
                f"<= {cfg['squat_cv_good_max']:.0f}% CV",
                SOURCE_BIOMECH,
                STATUS_INSUFFICIENT,
                f"Only {len(reps)} repetition detected; at least 2 complete repetitions are required to compute inter-repetition variability.",
                mean_conf,
                weight=0.15,
            )
        )
    else:
        if knee_cv <= cfg["squat_cv_good_max"]:
            st = STATUS_GOOD
            exp = f"Peak knee flexion varied by only {knee_cv:.1f}% CV (SD = {knee_std:.1f} deg) across {len(reps)} repetitions, showing high kinematic repeatability."
            rec = None
        elif knee_cv <= cfg["squat_cv_needs_max"]:
            st = STATUS_NEEDS_IMPROVEMENT
            exp = f"Peak knee flexion showed moderate variability ({knee_cv:.1f}% CV, SD = {knee_std:.1f} deg) across {len(reps)} repetitions."
            rec = "Use a consistent depth cue or tempo count across every repetition."
        else:
            st = STATUS_OUTSIDE
            exp = f"Peak knee flexion varied substantially across repetitions ({knee_cv:.1f}% CV, SD = {knee_std:.1f} deg)."
            rec = "Standardize stance width and descent pacing to improve rep-to-rep consistency."
        params.append(
            _make_param(
                "Repetition Depth Consistency (CV)",
                knee_cv,
                "%",
                f"<= {cfg['squat_cv_good_max']:.0f}% CV",
                SOURCE_PROTOTYPE,
                st,
                exp,
                mean_conf,
                weight=0.15,
                recommendation=rec,
            )
        )

    # 5. Left-Right Knee Symmetry
    sym_knee = (biomech.get("symmetry") or {}).get("knee_flexion") or {}
    if not sym_knee.get("is_valid_comparison", False):
        params.append(
            _make_param(
                "Bilateral Knee Symmetry",
                None,
                "deg",
                f"<= {cfg['squat_sym_diff_good_max']:.0f} deg mean diff",
                SOURCE_BIOMECH,
                STATUS_INSUFFICIENT,
                sym_knee.get("reason", "Left-right knee symmetry could not be validly compared under this camera perspective."),
                mean_conf,
                weight=0.15,
                recommendation="Record a frontal view with both legs clearly unobstructed to evaluate bilateral alignment.",
            )
        )
    else:
        diff_deg = sym_knee["mean_abs_diff_deg"]
        if diff_deg <= cfg["squat_sym_diff_good_max"]:
            st = STATUS_GOOD
            exp = f"Left and right knee flexion differed by an average of {diff_deg:.1f} deg (correlation {sym_knee.get('correlation')}), indicating balanced bilateral tracking."
            rec = None
        elif diff_deg <= cfg["squat_sym_diff_needs_max"]:
            st = STATUS_NEEDS_IMPROVEMENT
            exp = f"Left-right projected knee flexion showed a moderate mean difference of {diff_deg:.1f} deg (max {sym_knee.get('max_abs_diff_deg'):.1f} deg)."
            rec = "Monitor even weight distribution and symmetric knee tracking from a level frontal camera."
        else:
            st = STATUS_OUTSIDE
            exp = f"Left-right projected knee flexion differed by {diff_deg:.1f} deg on average (max {sym_knee.get('max_abs_diff_deg'):.1f} deg)."
            rec = "Verify camera centering first, then check whether stance shift or asymmetric knee tracking occurred."
        params.append(
            _make_param(
                "Bilateral Knee Symmetry",
                diff_deg,
                "deg",
                f"<= {cfg['squat_sym_diff_good_max']:.0f} deg mean diff",
                SOURCE_PROTOTYPE,
                st,
                exp,
                mean_conf,
                weight=0.15,
                recommendation=rec,
            )
        )

    return params


def _evaluate_lunge(
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    quality: Dict[str, Any],
    cfg: Dict[str, float],
) -> List[Dict[str, Any]]:
    params: List[Dict[str, Any]] = []
    reps = movement.get("repetitions", [])
    summary = movement.get("summary_metrics", {})
    consistency = movement.get("consistency", {})
    mean_conf = quality.get("mean_landmark_confidence", 0.0)

    # 1. Front Knee Flexion
    fk = summary.get("avg_front_knee_flexion_deg")
    if fk is None or len(reps) == 0:
        params.append(_make_param("Front Knee Peak Flexion", None, "deg", f">= {cfg['lunge_front_knee_good_min']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "No valid lunge cycles detected to measure front knee flexion.", mean_conf, 0.30))
    else:
        st = STATUS_GOOD if fk >= cfg["lunge_front_knee_good_min"] else (STATUS_NEEDS_IMPROVEMENT if fk >= cfg["lunge_front_knee_needs_min"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Front Knee Peak Flexion", fk, "deg", f">= {cfg['lunge_front_knee_good_min']:.0f} deg (approx. 90 deg target)",
            SOURCE_PROTOTYPE, st,
            f"Front knee flexion averaged {fk:.1f} deg across {len(reps)} lunge repetition(s).",
            mean_conf, 0.30,
            None if st == STATUS_GOOD else "Lower smoothly until the lead thigh approaches horizontal (~90 deg knee flexion).",
        ))

    # 2. Rear Knee Flexion
    rk = summary.get("avg_rear_knee_flexion_deg")
    if rk is None or len(reps) == 0:
        params.append(_make_param("Rear Knee Peak Flexion", None, "deg", f">= {cfg['lunge_rear_knee_good_min']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "Rear knee landmarks were not reliably visible across lunge cycles.", mean_conf, 0.20))
    else:
        st = STATUS_GOOD if rk >= cfg["lunge_rear_knee_good_min"] else (STATUS_NEEDS_IMPROVEMENT if rk >= cfg["lunge_rear_knee_needs_min"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Rear Knee Peak Flexion", rk, "deg", f">= {cfg['lunge_rear_knee_good_min']:.0f} deg",
            SOURCE_PROTOTYPE, st,
            f"Rear knee flexion averaged {rk:.1f} deg at the lunge bottom position.",
            mean_conf, 0.20,
            None if st == STATUS_GOOD else "Allow the trailing knee to drop toward the floor under control.",
        ))

    # 3. Trunk Control
    tr = summary.get("avg_max_trunk_inclination_deg")
    if tr is None or len(reps) == 0:
        params.append(_make_param("Trunk Inclination Control", None, "deg", f"<= {cfg['lunge_trunk_good_max']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "Trunk landmarks insufficient during lunge cycles.", mean_conf, 0.25))
    else:
        st = STATUS_GOOD if tr <= cfg["lunge_trunk_good_max"] else (STATUS_NEEDS_IMPROVEMENT if tr <= cfg["lunge_trunk_needs_max"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Trunk Inclination Control", tr, "deg", f"<= {cfg['lunge_trunk_good_max']:.0f} deg from vertical",
            SOURCE_PROTOTYPE, st,
            f"Peak trunk inclination averaged {tr:.1f} deg from vertical during descent and bottom hold.",
            mean_conf, 0.25,
            None if st == STATUS_GOOD else "Brace the torso upright and avoid excessive forward lean over the front knee.",
        ))

    # 4. Repetition Consistency
    cv = (consistency.get("front_knee_max_flexion_deg") or {}).get("cv_percent")
    if cv is None or len(reps) < 2:
        params.append(_make_param("Lunge Depth Consistency (CV)", None, "%", "<= 12% CV", SOURCE_BIOMECH, STATUS_INSUFFICIENT, f"At least 2 lunge repetitions required (detected {len(reps)}).", mean_conf, 0.25))
    else:
        st = STATUS_GOOD if cv <= 12.0 else (STATUS_NEEDS_IMPROVEMENT if cv <= 20.0 else STATUS_OUTSIDE)
        params.append(_make_param(
            "Lunge Depth Consistency (CV)", cv, "%", "<= 12% CV",
            SOURCE_PROTOTYPE, st,
            f"Front knee flexion variability across {len(reps)} repetitions was {cv:.1f}% CV.",
            mean_conf, 0.25,
            None if st == STATUS_GOOD else "Standardize step length and bottom depth across repetitions.",
        ))

    return params


def _evaluate_jumping_jack(
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    quality: Dict[str, Any],
    cfg: Dict[str, float],
) -> List[Dict[str, Any]]:
    params: List[Dict[str, Any]] = []
    reps = movement.get("repetitions", [])
    summary = movement.get("summary_metrics", {})
    consistency = movement.get("consistency", {})
    mean_conf = quality.get("mean_landmark_confidence", 0.0)

    # 1. Arm Abduction Range (Shoulder Angle)
    sh = summary.get("avg_max_shoulder_angle_deg")
    if sh is None or len(reps) == 0:
        params.append(_make_param("Peak Shoulder Abduction Range", None, "deg", f">= {cfg['jj_shoulder_good_min']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "No complete jumping jack cycles with reliable shoulder/elbow landmarks detected.", mean_conf, 0.30))
    else:
        st = STATUS_GOOD if sh >= cfg["jj_shoulder_good_min"] else (STATUS_NEEDS_IMPROVEMENT if sh >= cfg["jj_shoulder_needs_min"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Peak Shoulder Abduction Range", sh, "deg", f">= {cfg['jj_shoulder_good_min']:.0f} deg overhead",
            SOURCE_PROTOTYPE, st,
            f"Bilateral shoulder abduction averaged {sh:.1f} deg at maximum arm elevation across {len(reps)} repetition(s).",
            mean_conf, 0.30,
            None if st == STATUS_GOOD else "Raise both arms higher toward full overhead extension at peak jump.",
        ))

    # 2. Lower-Limb Abduction (Ankle Spread Ratio)
    spread = summary.get("avg_ankle_spread_ratio")
    if spread is None or len(reps) == 0:
        params.append(_make_param("Lower-Limb Lateral Spread Ratio", None, "torso_len", f">= {cfg['jj_spread_good_min']:.2f}", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "Ankle landmarks could not be tracked reliably across repetitions.", mean_conf, 0.25))
    else:
        st = STATUS_GOOD if spread >= cfg["jj_spread_good_min"] else (STATUS_NEEDS_IMPROVEMENT if spread >= cfg["jj_spread_needs_min"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Lower-Limb Lateral Spread Ratio", spread, "torso_len", f">= {cfg['jj_spread_good_min']:.2f} torso lengths",
            SOURCE_PROTOTYPE, st,
            f"Peak inter-ankle lateral spread averaged {spread:.2f} torso lengths during jumping jack extension.",
            mean_conf, 0.25,
            None if st == STATUS_GOOD else "Step or hop feet slightly wider at maximum outward extension.",
        ))

    # 3. Bilateral Arm Symmetry
    sym_sh = (biomech.get("symmetry") or {}).get("shoulder_angle") or {}
    if not sym_sh.get("is_valid_comparison", False):
        params.append(_make_param("Bilateral Arm Symmetry", None, "deg", f"<= {cfg['jj_sym_diff_good_max']:.0f} deg", SOURCE_BIOMECH, STATUS_INSUFFICIENT, sym_sh.get("reason", "Frontal visibility insufficient for bilateral shoulder comparison."), mean_conf, 0.25))
    else:
        diff = sym_sh["mean_abs_diff_deg"]
        st = STATUS_GOOD if diff <= cfg["jj_sym_diff_good_max"] else (STATUS_NEEDS_IMPROVEMENT if diff <= cfg["jj_sym_diff_needs_max"] else STATUS_OUTSIDE)
        params.append(_make_param(
            "Bilateral Arm Symmetry", diff, "deg", f"<= {cfg['jj_sym_diff_good_max']:.0f} deg mean diff",
            SOURCE_PROTOTYPE, st,
            f"Left and right shoulder angles differed by {diff:.1f} deg on average (correlation {sym_sh.get('correlation')}).",
            mean_conf, 0.25,
            None if st == STATUS_GOOD else "Synchronize left and right arm elevation speed and peak height.",
        ))

    # 4. Repetition Consistency
    cv = (consistency.get("max_mean_shoulder_deg") or {}).get("cv_percent")
    if cv is None or len(reps) < 2:
        params.append(_make_param("Repetition Consistency (CV)", None, "%", "<= 12% CV", SOURCE_BIOMECH, STATUS_INSUFFICIENT, f"At least 2 jumping jack repetitions required (detected {len(reps)}).", mean_conf, 0.20))
    else:
        st = STATUS_GOOD if cv <= 12.0 else (STATUS_NEEDS_IMPROVEMENT if cv <= 20.0 else STATUS_OUTSIDE)
        params.append(_make_param(
            "Repetition Consistency (CV)", cv, "%", "<= 12% CV",
            SOURCE_PROTOTYPE, st,
            f"Peak shoulder abduction varied by {cv:.1f}% CV across {len(reps)} repetitions.",
            mean_conf, 0.20,
            None if st == STATUS_GOOD else "Maintain consistent overhead arm reach across every repetition.",
        ))

    return params


def _evaluate_basketball(
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    quality: Dict[str, Any],
    cfg: Dict[str, float],
) -> List[Dict[str, Any]]:
    params: List[Dict[str, Any]] = []
    reps = movement.get("repetitions", [])
    summary = movement.get("summary_metrics", {})
    mean_conf = quality.get("mean_landmark_confidence", 0.0)

    el = summary.get("avg_elbow_at_release_deg")
    if el is None or len(reps) == 0:
        params.append(_make_param("Shooting Elbow Extension at Release", None, "deg", f"{cfg['bball_elbow_release_min']:.0f}-{cfg['bball_elbow_release_max']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "No valid shot release frames detected.", mean_conf, 0.35))
    else:
        st = STATUS_GOOD if cfg["bball_elbow_release_min"] <= el <= cfg["bball_elbow_release_max"] else STATUS_NEEDS_IMPROVEMENT
        params.append(_make_param(
            "Shooting Elbow Extension at Release", el, "deg", f"{cfg['bball_elbow_release_min']:.0f}-{cfg['bball_elbow_release_max']:.0f} deg internal",
            SOURCE_PROTOTYPE, st,
            f"Shooting-arm elbow internal angle averaged {el:.1f} deg at estimated peak release frame.",
            mean_conf, 0.35,
            None if st == STATUS_GOOD else "Aim for fuller elbow extension through the follow-through release point.",
        ))

    sh = summary.get("avg_shoulder_at_release_deg")
    if sh is None or len(reps) == 0:
        params.append(_make_param("Shooting Shoulder Elevation at Release", None, "deg", f"{cfg['bball_shoulder_release_min']:.0f}-{cfg['bball_shoulder_release_max']:.0f} deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "Shoulder landmarks insufficient at release frame.", mean_conf, 0.35))
    else:
        st = STATUS_GOOD if cfg["bball_shoulder_release_min"] <= sh <= cfg["bball_shoulder_release_max"] else STATUS_NEEDS_IMPROVEMENT
        params.append(_make_param(
            "Shooting Shoulder Elevation at Release", sh, "deg", f"{cfg['bball_shoulder_release_min']:.0f}-{cfg['bball_shoulder_release_max']:.0f} deg",
            SOURCE_PROTOTYPE, st,
            f"Shoulder angle averaged {sh:.1f} deg at release across {len(reps)} shot attempt(s).",
            mean_conf, 0.35,
            None if st == STATUS_GOOD else "Elevate the shooting elbow above shoulder height for a higher release arc.",
        ))

    tr = summary.get("avg_trunk_at_release_deg")
    if tr is None or len(reps) == 0:
        params.append(_make_param("Trunk Posture at Release", None, "deg", "<= 20 deg", SOURCE_PROTOTYPE, STATUS_INSUFFICIENT, "Trunk angle unavailable at release.", mean_conf, 0.30))
    else:
        st = STATUS_GOOD if tr <= 20.0 else STATUS_NEEDS_IMPROVEMENT
        params.append(_make_param(
            "Trunk Posture at Release", tr, "deg", "<= 20 deg from vertical",
            SOURCE_PROTOTYPE, st,
            f"Trunk inclination at release averaged {tr:.1f} deg from vertical.",
            mean_conf, 0.30,
            None if st == STATUS_GOOD else "Maintain balanced upright alignment through shot release.",
        ))

    return params


def run_assessment(
    movement_type: str,
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    quality: Dict[str, Any],
    criteria_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Evaluate biomechanical measurements transparently and compute an auditable composite score
    only when sufficient valid measurements exist.
    """
    cfg = dict(DEFAULT_CRITERIA)
    if criteria_overrides:
        for k, v in criteria_overrides.items():
            if k in cfg and isinstance(v, (int, float)) and math.isfinite(float(v)):
                cfg[k] = float(v)

    if movement_type == "squat":
        parameters = _evaluate_squat(biomech, movement, quality, cfg)
    elif movement_type == "lunge":
        parameters = _evaluate_lunge(biomech, movement, quality, cfg)
    elif movement_type == "jumping_jack":
        parameters = _evaluate_jumping_jack(biomech, movement, quality, cfg)
    elif movement_type == "basketball_shooting":
        parameters = _evaluate_basketball(biomech, movement, quality, cfg)
    else:
        raise ValueError(f"Unsupported movement_type: {movement_type}")

    positive_observations = [p["explanation"] for p in parameters if p["status"] == STATUS_GOOD]
    areas_for_improvement = [
        p["explanation"] for p in parameters if p["status"] in (STATUS_NEEDS_IMPROVEMENT, STATUS_OUTSIDE)
    ]
    technique_adjustments = [
        {"parameter": p["parameter_name"], "status": p["status"], "suggestion": p["recommendation"]}
        for p in parameters
        if p.get("recommendation") and p["status"] != STATUS_GOOD
    ]

    # Composite score transparency & missing-data discipline
    total_weight = sum(p["weight"] for p in parameters)
    included = [p for p in parameters if p["status"] != STATUS_INSUFFICIENT]
    excluded = [p for p in parameters if p["status"] == STATUS_INSUFFICIENT]
    valid_weight = sum(p["weight"] for p in included)
    valid_weight_ratio = (valid_weight / total_weight) if total_weight > 0 else 0.0

    composite_score: Optional[float] = None
    composite_status = STATUS_INSUFFICIENT

    if valid_weight_ratio >= 0.55 and len(included) >= 2:
        weighted_sum = sum(STATUS_SCORE_MAP[p["status"]] * p["weight"] for p in included)
        composite_score = round(weighted_sum / valid_weight, 1)
        if composite_score >= 85.0:
            composite_status = STATUS_GOOD
        elif composite_score >= 65.0:
            composite_status = STATUS_NEEDS_IMPROVEMENT
        else:
            composite_status = STATUS_OUTSIDE

    composite_methodology = {
        "computed": composite_score is not None,
        "composite_score": composite_score,
        "composite_status": composite_status,
        "valid_weight_coverage": round(valid_weight_ratio, 3),
        "minimum_coverage_required": 0.55,
        "included_parameters": [{"name": p["parameter_name"], "weight": p["weight"], "status": p["status"]} for p in included],
        "excluded_parameters": [{"name": p["parameter_name"], "weight": p["weight"], "reason": p["explanation"]} for p in excluded],
        "normalization_method": "Weighted average over evaluated valid parameters (GOOD=100, NEEDS IMPROVEMENT=70, OUTSIDE REFERENCE RANGE=40), renormalized by valid parameter weights only when >= 55% of total weight is measurable.",
        "missing_data_handling": "Parameters marked INSUFFICIENT DATA are excluded from scoring and never assigned default passing scores; if valid weight coverage falls below 55%, no composite score is produced.",
    }

    return {
        "parameters": parameters,
        "positive_observations": positive_observations,
        "areas_for_improvement": areas_for_improvement,
        "technique_adjustments": technique_adjustments,
        "composite_score": composite_score,
        "composite_status": composite_status,
        "composite_methodology": composite_methodology,
        "prototype_disclaimer": (
            "MotionIQ is an educational and sports-performance prototype, not a clinically validated medical diagnostic tool. "
            "Engineering-defined prototype thresholds and 2D monocular camera estimates are not substitutes for 3D motion-capture lab testing or clinical evaluation."
        ),
    }
