"""Video input validation and recording-quality assessment utilities."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from app.core.config import (
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    MAX_VIDEO_DURATION_SEC,
    MIN_FILE_SIZE_BYTES,
    MIN_VIDEO_DURATION_SEC,
    MIN_VIDEO_FRAMES,
    MIN_VIDEO_HEIGHT,
    MIN_VIDEO_WIDTH,
)

CORE_LOWER_BODY_LANDMARKS = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


def validate_video_file(file_path: str | Path) -> Dict[str, Any]:
    """
    Validate uploaded or selected video file for format, size, readability,
    dimensions, frame rate, and duration.
    """
    path = Path(file_path)
    errors: List[str] = []
    warnings: List[str] = []

    if not path.exists() or not path.is_file():
        return {
            "valid": False,
            "errors": ["Video file does not exist on disk."],
            "warnings": [],
            "metadata": {},
        }

    ext = path.suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        errors.append(
            f"Unsupported video format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}."
        )

    file_size = path.stat().st_size
    if file_size < MIN_FILE_SIZE_BYTES:
        errors.append(f"Video file is too small ({file_size} bytes) to contain valid footage.")
    if file_size > MAX_FILE_SIZE_BYTES:
        errors.append(
            f"Video file exceeds maximum size limit ({file_size / (1024 * 1024):.1f} MB > {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB)."
        )

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "metadata": {"file_size_bytes": file_size}}

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {
            "valid": False,
            "errors": ["OpenCV could not open or decode this video file."],
            "warnings": [],
            "metadata": {"file_size_bytes": file_size},
        }

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        ok, first_frame = cap.read()
        if not ok or first_frame is None or first_frame.size == 0:
            errors.append("Video stream could not be decoded (failed reading initial frame).")

        if frame_count <= 0 and ok:
            # Fallback frame counting for containers without header frame count
            counted = 1
            while True:
                ret, _ = cap.read()
                if not ret:
                    break
                counted += 1
            frame_count = counted

        if fps <= 0 or not math.isfinite(fps):
            errors.append("Video has invalid or unreadable frame rate (FPS <= 0).")
            duration_sec = 0.0
        else:
            duration_sec = float(frame_count) / float(fps)

        if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
            errors.append(
                f"Video resolution {width}x{height} is below minimum {MIN_VIDEO_WIDTH}x{MIN_VIDEO_HEIGHT}."
            )
        if frame_count < MIN_VIDEO_FRAMES:
            errors.append(
                f"Video contains too few frames ({frame_count} < {MIN_VIDEO_FRAMES} minimum)."
            )
        if duration_sec > 0:
            if duration_sec < MIN_VIDEO_DURATION_SEC:
                errors.append(
                    f"Video duration ({duration_sec:.2f}s) is shorter than minimum {MIN_VIDEO_DURATION_SEC}s."
                )
            elif duration_sec > MAX_VIDEO_DURATION_SEC:
                errors.append(
                    f"Video duration ({duration_sec:.1f}s) exceeds maximum {MAX_VIDEO_DURATION_SEC:.0f}s."
                )

        if 0 < fps < 12.0:
            warnings.append(
                f"Low frame rate detected ({fps:.1f} FPS). Rapid movement phases and angular velocity estimates will have reduced temporal resolution."
            )
        if 0 < min(width, height) < 480:
            warnings.append(
                f"Low spatial resolution ({width}x{height}). Landmark precision may degrade at longer camera distances."
            )

        metadata = {
            "filename": path.name,
            "extension": ext,
            "file_size_bytes": file_size,
            "width": width,
            "height": height,
            "fps": round(fps, 3) if math.isfinite(fps) else 0.0,
            "frame_count": frame_count,
            "duration_sec": round(duration_sec, 3),
        }
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "metadata": metadata,
        }
    finally:
        cap.release()


def evaluate_recording_quality(
    frame_records: List[Dict[str, Any]],
    total_video_frames: int,
    width: int,
    height: int,
    selected_perspective: str,
    movement_type: str,
    confidence_threshold: float,
) -> Dict[str, Any]:
    """
    Assess recording quality, landmark visibility, camera perspective consistency,
    multi-person interference, and 2D monocular camera limitations.
    """
    processed_frames = len(frame_records)
    if processed_frames == 0:
        return {
            "total_frames": total_video_frames,
            "frames_processed": 0,
            "pose_detected_frames": 0,
            "valid_landmark_frames": 0,
            "valid_frame_ratio": 0.0,
            "full_body_visible_ratio": 0.0,
            "mean_landmark_confidence": 0.0,
            "multi_person_frames": 0,
            "multi_person_detected": False,
            "inferred_perspective": "unknown",
            "selected_perspective": selected_perspective,
            "perspective_compatible": False,
            "camera_stability_score": 0.0,
            "quality_status": "INSUFFICIENT",
            "landmark_visibility": {},
            "warnings": ["No frames were processed from the video."],
            "camera_limitations": ["Single 2D monocular camera cannot capture out-of-plane 3D joint rotations."],
        }

    pose_detected_frames = 0
    valid_landmark_frames = 0
    full_body_visible_frames = 0
    multi_person_frames = 0

    landmark_confs: Dict[str, List[float]] = {name: [] for name in CORE_LOWER_BODY_LANDMARKS}
    landmark_reliable_counts: Dict[str, int] = {name: 0 for name in CORE_LOWER_BODY_LANDMARKS}

    shoulder_width_ratios: List[float] = []
    hip_centers_y: List[float] = []
    ankle_centers_x: List[float] = []

    for rec in frame_records:
        if rec.get("num_poses_detected", 0) > 1:
            multi_person_frames += 1

        lms = rec.get("landmarks")
        if not lms:
            continue

        pose_detected_frames += 1

        for name, idx in CORE_LOWER_BODY_LANDMARKS.items():
            lm = lms[idx]
            conf = float(lm.get("confidence", 0.0))
            landmark_confs[name].append(conf)
            if lm.get("is_reliable", False):
                landmark_reliable_counts[name] += 1

        # Check whether at least one full body side (shoulder->hip->knee->ankle) is reliably inside frame
        left_ok = all(lms[idx]["is_reliable"] for idx in (11, 23, 25, 27))
        right_ok = all(lms[idx]["is_reliable"] for idx in (12, 24, 26, 28))

        if selected_perspective == "front":
            has_core = left_ok and right_ok
        else:
            has_core = left_ok or right_ok

        if has_core:
            valid_landmark_frames += 1

        in_bounds = False
        if left_ok or right_ok:
            check_ids = (11, 23, 25, 27) if left_ok else (12, 24, 26, 28)
            if all(0.01 <= lms[i]["x_norm"] <= 0.99 and 0.01 <= lms[i]["y_norm"] <= 0.99 for i in check_ids):
                in_bounds = True
        if in_bounds:
            full_body_visible_frames += 1

        # Perspective geometry cue: shoulder width relative to torso height in pixels
        if all(lms[i]["is_reliable"] for i in (11, 12, 23, 24)):
            sw_px = abs(lms[11]["x_px"] - lms[12]["x_px"])
            mid_sh_y = 0.5 * (lms[11]["y_px"] + lms[12]["y_px"])
            mid_hip_y = 0.5 * (lms[23]["y_px"] + lms[24]["y_px"])
            torso_px = max(1.0, abs(mid_hip_y - mid_sh_y))
            shoulder_width_ratios.append(sw_px / torso_px)

        if lms[23]["is_reliable"] and lms[24]["is_reliable"]:
            hip_centers_y.append(0.5 * (lms[23]["y_norm"] + lms[24]["y_norm"]))
        if lms[27]["is_reliable"] and lms[28]["is_reliable"]:
            ankle_centers_x.append(0.5 * (lms[27]["x_norm"] + lms[28]["x_norm"]))

    landmark_visibility: Dict[str, Dict[str, float]] = {}
    all_core_means: List[float] = []
    for name in CORE_LOWER_BODY_LANDMARKS:
        vals = landmark_confs[name]
        mean_c = float(np.mean(vals)) if vals else 0.0
        rel_ratio = float(landmark_reliable_counts[name]) / float(processed_frames)
        landmark_visibility[name] = {
            "mean_confidence": round(mean_c, 4),
            "reliable_ratio": round(rel_ratio, 4),
        }
        all_core_means.append(mean_c)

    mean_landmark_conf = float(np.mean(all_core_means)) if all_core_means else 0.0
    valid_frame_ratio = float(valid_landmark_frames) / float(processed_frames)
    full_body_visible_ratio = float(full_body_visible_frames) / float(processed_frames)

    # Infer perspective from shoulder-width to torso-height ratio
    if len(shoulder_width_ratios) >= max(3, int(0.15 * processed_frames)):
        med_sw_ratio = float(np.median(shoulder_width_ratios))
        if med_sw_ratio < 0.28:
            inferred_perspective = "side"
        elif med_sw_ratio > 0.42:
            inferred_perspective = "front"
        else:
            inferred_perspective = "oblique"
    else:
        inferred_perspective = "unknown"

    # Estimate camera stability from high-frequency second-difference jitter of ankle base position
    if len(ankle_centers_x) >= 10:
        arr = np.array(ankle_centers_x, dtype=np.float64)
        jitter = float(np.std(np.diff(arr, n=2)))
        camera_stability_score = max(0.0, min(1.0, 1.0 - jitter * 40.0))
    else:
        camera_stability_score = 0.75

    warnings: List[str] = []
    perspective_compatible = True

    if pose_detected_frames == 0:
        warnings.append("No human pose was detected in any frame.")
        perspective_compatible = False
    elif valid_frame_ratio < 0.50:
        warnings.append(
            f"Only {valid_frame_ratio * 100:.1f}% of processed frames met the landmark confidence threshold ({confidence_threshold:.2f})."
        )

    if full_body_visible_ratio < 0.65:
        warnings.append(
            f"Full body visibility was limited ({full_body_visible_ratio * 100:.1f}% of frames); partially occluded or cropped joints were excluded."
        )

    if multi_person_frames > max(2, int(0.05 * processed_frames)):
        warnings.append(
            f"Multiple people detected in {multi_person_frames} frames ({multi_person_frames / processed_frames * 100:.1f}%). Continuity tracking selected the primary athlete."
        )

    if camera_stability_score < 0.60:
        warnings.append(
            "Elevated high-frequency camera or base motion detected; a tripod or stationary surface is recommended."
        )

    if inferred_perspective != "unknown" and inferred_perspective != selected_perspective:
        if inferred_perspective == "oblique":
            warnings.append(
                f"Detected an oblique/diagonal camera angle while '{selected_perspective}' view was selected; out-of-plane foreshortening may affect projected joint angles."
            )
        else:
            warnings.append(
                f"Selected perspective '{selected_perspective}' differs from visual cues suggesting a '{inferred_perspective}' view."
            )
            perspective_compatible = False

    if movement_type in ("squat", "lunge") and selected_perspective == "front":
        warnings.append(
            "Frontal recordings allow observable left-right alignment indicators, but sagittal-plane knee flexion and squat depth are projected and less accurate than a perpendicular side view."
        )
    if movement_type == "jumping_jack" and selected_perspective == "side":
        perspective_compatible = False
        warnings.append(
            "Jumping jacks occur primarily in the frontal plane; a side-view recording cannot reliably measure bilateral arm/leg abduction."
        )

    camera_limitations = [
        "Single-camera 2D pose estimation measures projected planar angles and cannot reconstruct true 3D joint rotations (e.g., tibial torsion, pelvic yaw, or knee valgus/varus torque).",
    ]
    if selected_perspective == "side":
        camera_limitations.append(
            "In side-view recordings, the far-side limb is frequently occluded by the near-side limb; bilateral left-right symmetry comparison is withheld when occlusion occurs."
        )
    elif selected_perspective == "front":
        camera_limitations.append(
            "In frontal-view recordings, sagittal flexion angles (knee bend, hip hinge, forward trunk lean) experience geometric foreshortening toward the camera lens."
        )

    if valid_frame_ratio >= 0.75 and full_body_visible_ratio >= 0.70 and perspective_compatible:
        quality_status = "GOOD"
    elif valid_frame_ratio >= 0.40:
        quality_status = "LIMITED"
    else:
        quality_status = "INSUFFICIENT"

    return {
        "total_frames": total_video_frames,
        "frames_processed": processed_frames,
        "pose_detected_frames": pose_detected_frames,
        "valid_landmark_frames": valid_landmark_frames,
        "valid_frame_ratio": round(valid_frame_ratio, 4),
        "full_body_visible_ratio": round(full_body_visible_ratio, 4),
        "mean_landmark_confidence": round(mean_landmark_conf, 4),
        "multi_person_frames": multi_person_frames,
        "multi_person_detected": multi_person_frames > max(2, int(0.05 * processed_frames)),
        "inferred_perspective": inferred_perspective,
        "selected_perspective": selected_perspective,
        "perspective_compatible": perspective_compatible,
        "camera_stability_score": round(camera_stability_score, 4),
        "quality_status": quality_status,
        "landmark_visibility": landmark_visibility,
        "warnings": warnings,
        "camera_limitations": camera_limitations,
    }
