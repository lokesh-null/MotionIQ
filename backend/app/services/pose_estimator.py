"""MediaPipe Pose Landmarker (33-landmark) extraction and multi-person continuity tracking."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

from app.core.config import (
    MAX_ANALYSIS_FPS,
    MIN_POSE_DETECTION_CONFIDENCE,
    MIN_POSE_PRESENCE_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    POSE_MODEL_FULL,
    POSE_MODEL_LITE,
    TARGET_SAMPLED_FPS,
)
from app.utils.geometry import to_pixel_coords

LANDMARK_NAMES: Tuple[str, ...] = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)

POSE_CONNECTIONS: Tuple[Tuple[int, int], ...] = (
    # Torso
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
    # Left arm
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    # Right arm
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    # Left leg
    (23, 25),
    (25, 27),
    (27, 29),
    (27, 31),
    (29, 31),
    # Right leg
    (24, 26),
    (26, 28),
    (28, 30),
    (28, 32),
    (30, 32),
    # Head / neck reference
    (0, 1),
    (0, 4),
    (1, 2),
    (2, 3),
    (4, 5),
    (5, 6),
    (7, 2),
    (8, 5),
)


def _compute_pose_anchor_and_area(pose_lms: List[Any]) -> Tuple[Tuple[float, float], float]:
    """Compute normalized hip/torso center and bounding-box area for primary-athlete tracking."""
    xs = [float(lm.x) for lm in pose_lms]
    ys = [float(lm.y) for lm in pose_lms]
    area = max(0.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    # Prefer hip midpoint (23, 24) or torso center (11, 12, 23, 24)
    center_x = 0.25 * (xs[11] + xs[12] + xs[23] + xs[24])
    center_y = 0.25 * (ys[11] + ys[12] + ys[23] + ys[24])
    return (center_x, center_y), area


def _select_primary_pose(
    poses: List[List[Any]],
    prev_anchor: Optional[Tuple[float, float]],
) -> Tuple[List[Any], Tuple[float, float]]:
    """
    Select primary athlete when multiple poses appear in a frame.
    Uses spatial continuity with the previous tracked torso center; on first detection,
    prefers the largest prominent person near the frame center.
    """
    if len(poses) == 1:
        anchor, _ = _compute_pose_anchor_and_area(poses[0])
        return poses[0], anchor

    best_idx = 0
    best_score = float("inf") if prev_anchor is not None else -float("inf")
    best_anchor = (0.5, 0.5)

    for idx, pose in enumerate(poses):
        anchor, area = _compute_pose_anchor_and_area(pose)
        if prev_anchor is not None:
            dist = math.hypot(anchor[0] - prev_anchor[0], anchor[1] - prev_anchor[1])
            if dist < best_score:
                best_score = dist
                best_idx = idx
                best_anchor = anchor
        else:
            center_penalty = math.hypot(anchor[0] - 0.5, anchor[1] - 0.5)
            score = area - 0.25 * center_penalty
            if score > best_score:
                best_score = score
                best_idx = idx
                best_anchor = anchor

    return poses[best_idx], best_anchor


def resolve_model_path() -> Path:
    """Resolve the MediaPipe Pose Landmarker .task file."""
    if POSE_MODEL_FULL.exists():
        return POSE_MODEL_FULL
    if POSE_MODEL_LITE.exists():
        return POSE_MODEL_LITE
    raise FileNotFoundError(
        f"MediaPipe Pose Landmarker model not found in {POSE_MODEL_FULL.parent}."
    )


def compute_even_scaled_dimensions(width: int, height: int, max_dim: int = 1280) -> Tuple[int, int]:
    """Scale dimensions down to at most `max_dim` on longest edge while preserving aspect ratio and even parity."""
    if width <= 0 or height <= 0:
        return (640, 480)
    scale = min(1.0, float(max_dim) / float(max(width, height)))
    w = max(2, int(round(width * scale)))
    h = max(2, int(round(height * scale)))
    if w % 2 == 1:
        w -= 1
    if h % 2 == 1:
        h -= 1
    return (max(2, w), max(2, h))


def extract_pose_landmarks(
    video_path: str | Path,
    confidence_threshold: float = 0.50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Decode video frames via OpenCV, sample frames when FPS > MAX_ANALYSIS_FPS,
    maintain actual frame timestamps, and run MediaPipe 33-landmark Pose Landmarker.
    """
    model_path = resolve_model_path()
    model_bytes = model_path.read_bytes()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    try:
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        if fps <= 0 or not math.isfinite(fps):
            fps = 30.0
        reported_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        proc_w, proc_h = compute_even_scaled_dimensions(orig_w, orig_h, max_dim=1280)

        # Sample stride for >35 FPS high-speed videos while keeping actual timestamps
        if fps > MAX_ANALYSIS_FPS:
            sample_stride = max(1, int(round(fps / TARGET_SAMPLED_FPS)))
        else:
            sample_stride = 1

        effective_fps = fps / float(sample_stride)
        estimated_total_sampled = max(1, (reported_total := max(1, reported_frame_count)) // sample_stride)

        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=2,
            min_pose_detection_confidence=MIN_POSE_DETECTION_CONFIDENCE,
            min_pose_presence_confidence=MIN_POSE_PRESENCE_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )

        frame_records: List[Dict[str, Any]] = []
        raw_frame_idx = 0
        last_mp_ts_ms = 0
        prev_anchor: Optional[Tuple[float, float]] = None

        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame_bgr = cap.read()
                if not ok or frame_bgr is None:
                    break

                # Read container timestamp before advancing
                pos_msec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                if raw_frame_idx % sample_stride != 0:
                    raw_frame_idx += 1
                    continue

                if raw_frame_idx > 0 and (not math.isfinite(pos_msec) or pos_msec <= 0.0):
                    pos_msec = (float(raw_frame_idx) / fps) * 1000.0
                elif raw_frame_idx == 0 and (not math.isfinite(pos_msec) or pos_msec < 0.0):
                    pos_msec = 0.0

                timestamp_sec = pos_msec / 1000.0
                mp_ts_ms = max(last_mp_ts_ms + 1, int(round(pos_msec)))
                last_mp_ts_ms = mp_ts_ms

                if frame_bgr.shape[1] != proc_w or frame_bgr.shape[0] != proc_h:
                    frame_proc = cv2.resize(frame_bgr, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
                else:
                    frame_proc = frame_bgr

                rgb = cv2.cvtColor(frame_proc, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(mp_image, mp_ts_ms)

                num_poses = len(result.pose_landmarks) if result.pose_landmarks else 0
                extracted_landmarks: Optional[List[Dict[str, Any]]] = None

                if num_poses > 0:
                    selected_pose, prev_anchor = _select_primary_pose(result.pose_landmarks, prev_anchor)
                    extracted_landmarks = []
                    for lm_idx, lm in enumerate(selected_pose):
                        x_norm = float(lm.x)
                        y_norm = float(lm.y)
                        z_norm = float(lm.z)
                        vis = float(getattr(lm, "visibility", 1.0) or 0.0)
                        pres = float(getattr(lm, "presence", 1.0) or 0.0)
                        conf = min(vis, pres)
                        in_frame = (0.0 <= x_norm <= 1.0) and (0.0 <= y_norm <= 1.0)
                        is_reliable = (conf >= confidence_threshold) and in_frame
                        px = to_pixel_coords(x_norm, y_norm, proc_w, proc_h)
                        extracted_landmarks.append(
                            {
                                "index": lm_idx,
                                "name": LANDMARK_NAMES[lm_idx] if lm_idx < len(LANDMARK_NAMES) else f"lm_{lm_idx}",
                                "x_norm": x_norm,
                                "y_norm": y_norm,
                                "z_norm": z_norm,
                                "x_px": px[0] if px else 0.0,
                                "y_px": px[1] if px else 0.0,
                                "visibility": vis,
                                "presence": pres,
                                "confidence": conf,
                                "is_reliable": is_reliable,
                            }
                        )

                frame_records.append(
                    {
                        "sampled_index": len(frame_records),
                        "raw_frame_index": raw_frame_idx,
                        "timestamp_sec": timestamp_sec,
                        "num_poses_detected": num_poses,
                        "landmarks": extracted_landmarks,
                    }
                )

                if progress_callback and (len(frame_records) % 5 == 0 or len(frame_records) == 1):
                    progress_callback(
                        len(frame_records),
                        max(estimated_total_sampled, len(frame_records)),
                        f"Running MediaPipe 33-landmark pose estimation (frame {len(frame_records)})",
                    )

                raw_frame_idx += 1

        if progress_callback:
            progress_callback(
                len(frame_records),
                max(1, len(frame_records)),
                "Pose landmark extraction complete",
            )

        # Compute actual observed effective FPS from timestamps when available
        if len(frame_records) >= 2:
            total_span = frame_records[-1]["timestamp_sec"] - frame_records[0]["timestamp_sec"]
            if total_span > 0.05:
                effective_fps = (len(frame_records) - 1) / total_span

        return {
            "model_used": model_path.name,
            "original_width": orig_w,
            "original_height": orig_h,
            "processed_width": proc_w,
            "processed_height": proc_h,
            "source_fps": round(fps, 3),
            "effective_fps": round(effective_fps, 3),
            "sample_stride": sample_stride,
            "total_video_frames": raw_frame_idx,
            "processed_frames": len(frame_records),
            "duration_sec": round(
                (frame_records[-1]["timestamp_sec"] - frame_records[0]["timestamp_sec"])
                if len(frame_records) >= 2
                else (raw_frame_idx / fps),
                3,
            ),
            "frame_records": frame_records,
        }
    finally:
        cap.release()
