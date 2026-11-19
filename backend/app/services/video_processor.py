"""End-to-end video processing, skeleton annotation rendering, and H.264 transcoding pipeline."""

from __future__ import annotations

import math
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import cv2
import imageio_ffmpeg

_PIPELINE_LOCK = threading.Lock()

from app.core.config import PROCESSED_DIR, REPORTS_DIR, SUPPORTED_MOVEMENTS
from app.core.database import (
    complete_analysis_record,
    get_analysis_record,
    update_analysis_progress,
    utc_now_iso,
)
from app.services.assessment_engine import run_assessment
from app.services.biomechanics import compute_biomechanics
from app.services.movement_classifier import classify_movement_and_reps
from app.services.pose_estimator import (
    POSE_CONNECTIONS,
    compute_even_scaled_dimensions,
    extract_pose_landmarks,
    release_native_memory,
)
from app.services.report_generator import generate_pdf_report
from app.utils.validation import evaluate_recording_quality, validate_video_file

PHASE_COLORS_BGR = {
    "STANDING": (180, 185, 190),
    "STARTING_POSITION": (180, 185, 190),
    "INITIAL_STANDING": (180, 185, 190),
    "PREPARATION": (180, 185, 190),
    "PREPARATION_DIP": (96, 184, 244),
    "DESCENDING": (96, 184, 244),
    "DESCENT": (96, 184, 244),
    "OUTWARD_MOVEMENT": (96, 184, 244),
    "UPWARD_EXTENSION": (96, 184, 244),
    "BOTTOM": (160, 214, 54),
    "MAXIMUM_EXTENSION": (160, 214, 54),
    "RELEASE_POINT": (160, 214, 54),
    "ASCENDING": (235, 195, 70),
    "ASCENT": (235, 195, 70),
    "RETURN_MOVEMENT": (235, 195, 70),
    "FOLLOW_THROUGH": (235, 195, 70),
    "RETURN_TO_STANDING": (160, 214, 54),
}


def _draw_label_pill(
    frame: Any,
    text: str,
    x: int,
    y: int,
    bg_color: tuple[int, int, int] = (20, 28, 38),
    text_color: tuple[int, int, int] = (244, 247, 250),
    font_scale: float = 0.45,
) -> None:
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, 1)
    pad_x, pad_y = 6, 4
    px = max(4, min(w - tw - 2 * pad_x - 4, x))
    py = max(th + 2 * pad_y + 4, min(h - 4, y))
    cv2.rectangle(frame, (px, py - th - pad_y), (px + tw + 2 * pad_x, py + pad_y), bg_color, -1)
    cv2.rectangle(frame, (px, py - th - pad_y), (px + tw + 2 * pad_x, py + pad_y), (54, 214, 160), 1)
    cv2.putText(frame, text, (px + pad_x, py), font, font_scale, text_color, 1, cv2.LINE_AA)


def render_annotated_video(
    raw_video_path: str | Path,
    output_mp4_path: str | Path,
    pose_data: Dict[str, Any],
    biomech: Dict[str, Any],
    movement: Dict[str, Any],
    movement_type: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
    """
    Generate an annotated video displaying the MediaPipe skeleton, confidence-colored landmarks,
    live joint-angle labels, movement phase, repetition counter, and actual timestamps,
    transcoded to browser-compatible H.264 MP4.
    """
    out_path = Path(output_mp4_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_raw_mp4 = out_path.with_suffix(".tmp_mp4v.mp4")

    cap = cv2.VideoCapture(str(raw_video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open source video for annotation: {raw_video_path}")

    frame_records = pose_data["frame_records"]
    sample_stride = int(pose_data.get("sample_stride", 1))
    out_w = int(pose_data["processed_width"])
    out_h = int(pose_data["processed_height"])
    eff_fps = float(pose_data.get("effective_fps") or 30.0)
    if eff_fps <= 1.0 or not math.isfinite(eff_fps):
        eff_fps = 30.0

    # Map sampled frame index -> cumulative completed reps up to that frame
    rep_end_frames = sorted(
        int(r.get("end_frame", 0)) for r in (movement.get("repetitions") or [])
    )
    frame_phases: List[str] = movement.get("frame_phases") or ["UNKNOWN"] * len(frame_records)
    angles_deg = biomech.get("angles_deg") or {}

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_raw_mp4), fourcc, eff_fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("OpenCV VideoWriter failed to initialize temporary MP4 output.")

    try:
        raw_idx = 0
        sampled_idx = 0
        total_sampled = len(frame_records)
        scale_factor = max(0.55, min(1.25, out_w / 720.0))

        while sampled_idx < total_sampled:
            ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                break
            if raw_idx % sample_stride != 0:
                raw_idx += 1
                continue

            rec = frame_records[sampled_idx]
            if frame_bgr.shape[1] != out_w or frame_bgr.shape[0] != out_h:
                canvas = cv2.resize(frame_bgr, (out_w, out_h), interpolation=cv2.INTER_AREA)
            else:
                canvas = frame_bgr.copy()

            lms = rec.get("landmarks")
            if lms:
                # Draw bone connections
                for idx_a, idx_b in POSE_CONNECTIONS:
                    if idx_a >= len(lms) or idx_b >= len(lms):
                        continue
                    la, lb = lms[idx_a], lms[idx_b]
                    if not (la["is_reliable"] and lb["is_reliable"]):
                        continue
                    pa = (int(round(la["x_px"])), int(round(la["y_px"])))
                    pb = (int(round(lb["x_px"])), int(round(lb["y_px"])))
                    cv2.line(canvas, pa, pb, (160, 214, 54), max(2, int(round(2 * scale_factor))), cv2.LINE_AA)

                # Draw landmarks colored by confidence
                for lm in lms:
                    conf = float(lm.get("confidence", 0.0))
                    if conf < 0.20:
                        continue
                    px = (int(round(lm["x_px"])), int(round(lm["y_px"])))
                    if not (0 <= px[0] < out_w and 0 <= px[1] < out_h):
                        continue
                    if lm["is_reliable"]:
                        color = (160, 214, 54)  # #36D6A0 in BGR
                    else:
                        color = (96, 184, 244)  # #F4B860 warning amber in BGR
                    radius = max(3, int(round(4 * scale_factor)))
                    cv2.circle(canvas, px, radius, color, -1, cv2.LINE_AA)
                    cv2.circle(canvas, px, radius, (11, 15, 20), 1, cv2.LINE_AA)

                # Draw live movement-relevant joint angle labels next to joints
                def _annotate_joint(lm_idx: int, label_prefix: str, series_key: str) -> None:
                    if series_key not in angles_deg or sampled_idx >= len(angles_deg[series_key]):
                        return
                    val = angles_deg[series_key][sampled_idx]
                    if val is None or not lms[lm_idx]["is_reliable"]:
                        return
                    jx = int(round(lms[lm_idx]["x_px"])) + 8
                    jy = int(round(lms[lm_idx]["y_px"])) - 6
                    _draw_label_pill(canvas, f"{label_prefix} {val:.0f}deg", jx, jy, font_scale=0.42 * scale_factor)

                if movement_type in ("squat", "lunge"):
                    _annotate_joint(25, "LK", "left_knee_flexion")
                    _annotate_joint(26, "RK", "right_knee_flexion")
                    _annotate_joint(23, "LH", "left_hip_flexion")
                    _annotate_joint(24, "RH", "right_hip_flexion")
                    # Trunk label near mid-shoulder
                    if "trunk_inclination" in angles_deg and angles_deg["trunk_inclination"][sampled_idx] is not None:
                        sh_idx = 11 if lms[11]["is_reliable"] else 12
                        if lms[sh_idx]["is_reliable"]:
                            _annotate_joint(sh_idx, "Trunk", "trunk_inclination")
                elif movement_type == "jumping_jack":
                    _annotate_joint(11, "LSh", "left_shoulder_angle")
                    _annotate_joint(12, "RSh", "right_shoulder_angle")
                    _annotate_joint(23, "LHip", "left_hip_internal")
                    _annotate_joint(24, "RHip", "right_hip_internal")
                else:
                    side = movement.get("primary_side_tracked", "right")
                    el_idx = 14 if side == "right" else 13
                    sh_idx = 12 if side == "right" else 11
                    _annotate_joint(el_idx, "El", f"{side}_elbow_internal")
                    _annotate_joint(sh_idx, "Sh", f"{side}_shoulder_angle")

            # Top HUD bar
            hud_h = max(46, int(round(48 * scale_factor)))
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, 0), (out_w, hud_h), (11, 15, 20), -1)
            cv2.addWeighted(overlay, 0.80, canvas, 0.20, 0, canvas)

            phase_label = frame_phases[sampled_idx] if sampled_idx < len(frame_phases) else "UNKNOWN"
            phase_bgr = PHASE_COLORS_BGR.get(phase_label, (244, 247, 250))
            reps_completed = sum(1 for ef in rep_end_frames if sampled_idx >= ef)
            ts_sec = float(rec.get("timestamp_sec", 0.0))

            hud_left = f"MOTIONIQ  |  {movement_type.upper()}  |  PHASE: {phase_label}"
            hud_right = f"REPS: {reps_completed}  |  {ts_sec:.2f}s"
            font = cv2.FONT_HERSHEY_SIMPLEX
            f_scale = max(0.42, 0.50 * scale_factor)
            cv2.putText(canvas, hud_left, (12, int(hud_h * 0.65)), font, f_scale, phase_bgr, 1, cv2.LINE_AA)
            (rw, _), _ = cv2.getTextSize(hud_right, font, f_scale, 1)
            cv2.putText(canvas, hud_right, (max(12, out_w - rw - 14), int(hud_h * 0.65)), font, f_scale, (244, 247, 250), 1, cv2.LINE_AA)

            writer.write(canvas)
            sampled_idx += 1
            raw_idx += 1

            if progress_callback and (sampled_idx % 10 == 0 or sampled_idx == total_sampled):
                progress_callback(sampled_idx, total_sampled, f"Rendering annotated video frame {sampled_idx}/{total_sampled}")
    finally:
        cap.release()
        writer.release()

    # Transcode to browser-playable H.264 MP4 using imageio-ffmpeg (single-thread ultrafast to avoid cloud OOM)
    release_native_memory()
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-y",
        "-threads",
        "1",
        "-i",
        str(temp_raw_mp4),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "24",
        "-x264-params",
        "rc-lookahead=0:sync-lookahead=0:ref=1:bframes=0:threads=1",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"FFmpeg H.264 transcoding failed: {proc.stderr[-400:]}")
    temp_raw_mp4.unlink(missing_ok=True)
    release_native_memory()
    return out_path


def run_full_analysis_pipeline(
    analysis_id: str,
    movement_type: str,
    camera_perspective: str,
    confidence_threshold: float,
    criteria_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Execute the complete MotionIQ analysis workflow synchronously (invoked inside a worker thread).
    Serializes heavy CV execution via _PIPELINE_LOCK so concurrent cloud requests never exceed 512MB RAM.
    """
    with _PIPELINE_LOCK:
        release_native_memory()
        return _run_full_analysis_pipeline_locked(
            analysis_id=analysis_id,
            movement_type=movement_type,
            camera_perspective=camera_perspective,
            confidence_threshold=confidence_threshold,
            criteria_overrides=criteria_overrides,
        )


def _run_full_analysis_pipeline_locked(
    analysis_id: str,
    movement_type: str,
    camera_perspective: str,
    confidence_threshold: float,
    criteria_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    t_start = time.perf_counter()
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise ValueError(f"Analysis record {analysis_id} not found.")

    raw_video_path = Path(rec["raw_video_path"])

    try:
        # Stage 1: Video Validation
        update_analysis_progress(
            analysis_id,
            status="processing",
            stage="video_validation",
            progress_percent=3.0,
            current_operation="Validating video format, stream readability, dimensions, and frame timestamps",
            movement_type=movement_type,
            camera_perspective=camera_perspective,
            confidence_threshold=confidence_threshold,
            error_message="",
        )
        validation = validate_video_file(raw_video_path)
        if not validation["valid"]:
            raise RuntimeError("; ".join(validation["errors"]))

        video_meta = validation["metadata"]

        # Stage 2: Frame Extraction & Pose Estimation
        def _pose_progress(done: int, total: int, msg: str) -> None:
            pct = 5.0 + 50.0 * min(1.0, float(done) / float(max(1, total)))
            update_analysis_progress(
                analysis_id,
                stage="pose_estimation",
                frames_processed=done,
                total_frames=total,
                progress_percent=round(pct, 1),
                current_operation=msg,
            )

        pose_data = extract_pose_landmarks(
            raw_video_path,
            confidence_threshold=confidence_threshold,
            progress_callback=_pose_progress,
        )

        # Stage 3: Recording Quality & Landmark Processing
        update_analysis_progress(
            analysis_id,
            stage="landmark_processing",
            frames_processed=pose_data["processed_frames"],
            total_frames=pose_data["processed_frames"],
            progress_percent=58.0,
            current_operation="Evaluating landmark reliability, camera perspective compatibility, and data quality",
        )
        data_quality = evaluate_recording_quality(
            pose_data["frame_records"],
            total_video_frames=pose_data["total_video_frames"],
            width=pose_data["processed_width"],
            height=pose_data["processed_height"],
            selected_perspective=camera_perspective,
            movement_type=movement_type,
            confidence_threshold=confidence_threshold,
        )

        # Stage 4: Biomechanical Calculations
        update_analysis_progress(
            analysis_id,
            stage="biomechanical_calculations",
            progress_percent=65.0,
            current_operation="Computing 2D joint angles, angular velocities, trajectories, and symmetry",
        )
        biomech = compute_biomechanics(
            pose_data=pose_data,
            movement_type=movement_type,
            camera_perspective=camera_perspective,
            inferred_perspective=data_quality["inferred_perspective"],
        )

        # Stage 5: Movement Phase & Repetition Analysis
        update_analysis_progress(
            analysis_id,
            stage="movement_classification",
            progress_percent=74.0,
            current_operation=f"Detecting {movement_type.replace('_', ' ')} phases, repetitions, and cycle consistency",
        )
        movement = classify_movement_and_reps(
            biomech=biomech,
            movement_type=movement_type,
            camera_perspective=camera_perspective,
        )

        # Stage 6: Technique Assessment
        update_analysis_progress(
            analysis_id,
            stage="assessment_generation",
            progress_percent=78.0,
            current_operation="Evaluating technique against biomechanical criteria and generating feedback",
        )
        assessment = run_assessment(
            movement_type=movement_type,
            biomech=biomech,
            movement=movement,
            quality=data_quality,
            criteria_overrides=criteria_overrides,
        )

        # Stage 7: Annotated Video Generation
        annotated_path = PROCESSED_DIR / f"{analysis_id}_annotated.mp4"

        def _vid_progress(done: int, total: int, msg: str) -> None:
            pct = 80.0 + 13.0 * min(1.0, float(done) / float(max(1, total)))
            update_analysis_progress(
                analysis_id,
                stage="annotated_video",
                progress_percent=round(pct, 1),
                current_operation=msg,
            )

        render_annotated_video(
            raw_video_path=raw_video_path,
            output_mp4_path=annotated_path,
            pose_data=pose_data,
            biomech=biomech,
            movement=movement,
            movement_type=movement_type,
            progress_callback=_vid_progress,
        )

        # Stage 8: PDF Report Generation
        update_analysis_progress(
            analysis_id,
            stage="report_generation",
            progress_percent=95.0,
            current_operation="Compiling PDF biomechanical assessment report",
        )
        processing_elapsed = round(time.perf_counter() - t_start, 2)
        completed_at = utc_now_iso()

        results: Dict[str, Any] = {
            "analysis_id": analysis_id,
            "movement_type": movement_type,
            "movement_label": SUPPORTED_MOVEMENTS[movement_type]["name"],
            "completed_at": completed_at,
            "video_metadata": video_meta,
            "processing_details": {
                "model_used": pose_data["model_used"],
                "confidence_threshold": confidence_threshold,
                "source_fps": pose_data["source_fps"],
                "effective_fps": pose_data["effective_fps"],
                "sample_stride": pose_data["sample_stride"],
                "processed_width": pose_data["processed_width"],
                "processed_height": pose_data["processed_height"],
                "processing_time_sec": processing_elapsed,
            },
            "data_quality": data_quality,
            "biomechanics": biomech,
            "movement_analysis": movement,
            "assessment": assessment,
        }

        report_pdf_path = REPORTS_DIR / f"{analysis_id}_report.pdf"
        generate_pdf_report(results, report_pdf_path)
        release_native_memory()

        complete_analysis_record(
            analysis_id=analysis_id,
            annotated_video_path=str(annotated_path),
            report_pdf_path=str(report_pdf_path),
            results=results,
            total_frames=pose_data["processed_frames"],
        )
        return results

    except Exception as exc:
        update_analysis_progress(
            analysis_id,
            status="failed",
            stage="failed",
            current_operation="Processing failed",
            error_message=str(exc),
        )
        raise
