"""Automated scientific, mathematical, and end-to-end API tests for MotionIQ."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import DB_PATH, delete_analysis_record, init_db
from app.main import app
from app.services.assessment_engine import STATUS_INSUFFICIENT, run_assessment
from app.services.biomechanics import compute_biomechanics
from app.services.pose_estimator import extract_pose_landmarks
from app.utils.filters import compute_angular_velocity, interpolate_short_gaps
from app.utils.geometry import (
    calculate_angle_3pt,
    calculate_trunk_inclination,
    internal_to_flexion_angle,
    to_pixel_coords,
)


# ---------------------------------------------------------------------------
# 1. Mathematical & Geometric Unit Tests
# ---------------------------------------------------------------------------


def test_angle_known_configurations():
    # Straight line: 180 deg
    assert calculate_angle_3pt((0.0, 0.0), (0.0, 5.0), (0.0, 10.0)) == pytest.approx(180.0, abs=1e-6)
    # Right angle: 90 deg
    assert calculate_angle_3pt((0.0, 0.0), (0.0, 5.0), (5.0, 5.0)) == pytest.approx(90.0, abs=1e-6)
    # 45 deg
    assert calculate_angle_3pt((0.0, 1.0), (0.0, 0.0), (1.0, 1.0)) == pytest.approx(45.0, abs=1e-6)
    # 60 deg equilateral triangle
    assert calculate_angle_3pt((1.0, 0.0), (0.0, 0.0), (0.5, math.sqrt(3) / 2.0)) == pytest.approx(60.0, abs=1e-6)
    # 120 deg
    assert calculate_angle_3pt((1.0, 0.0), (0.0, 0.0), (-0.5, math.sqrt(3) / 2.0)) == pytest.approx(120.0, abs=1e-6)


def test_angle_numerical_safeguards():
    # Missing points
    assert calculate_angle_3pt(None, (0.0, 0.0), (1.0, 1.0)) is None
    assert calculate_angle_3pt((0.0, 0.0), None, (1.0, 1.0)) is None
    # Zero-length vector (coincident points)
    assert calculate_angle_3pt((5.0, 5.0), (5.0, 5.0), (6.0, 7.0)) is None
    # Non-finite coordinates
    assert calculate_angle_3pt((float("nan"), 0.0), (0.0, 0.0), (1.0, 1.0)) is None
    assert calculate_angle_3pt((float("inf"), 0.0), (0.0, 0.0), (1.0, 1.0)) is None


def test_aspect_ratio_scaling_and_conventions():
    # In 1920x1080 image, equal normalized displacements should NOT yield 45 deg;
    # true geometric pixel coordinates preserve physical screen angles.
    a_px = to_pixel_coords(0.5, 0.2, 1920, 1080)
    b_px = to_pixel_coords(0.5, 0.5, 1920, 1080)
    c_px = to_pixel_coords(0.5 + (0.3 * 1080 / 1920), 0.5, 1920, 1080)
    assert calculate_angle_3pt(a_px, b_px, c_px) == pytest.approx(90.0, abs=1e-5)

    # Flexion convention: 180 internal -> 0 flexion; 90 internal -> 90 flexion
    assert internal_to_flexion_angle(180.0) == pytest.approx(0.0)
    assert internal_to_flexion_angle(90.0) == pytest.approx(90.0)
    assert internal_to_flexion_angle(None) is None

    # Trunk inclination: upright vertical upward (shoulder above hip) = 0 deg
    assert calculate_trunk_inclination((100.0, 300.0), (100.0, 100.0)) == pytest.approx(0.0, abs=1e-6)
    # 30 deg lean forward
    dx = 200.0 * math.sin(math.radians(30.0))
    dy = 200.0 * math.cos(math.radians(30.0))
    assert calculate_trunk_inclination((100.0, 300.0), (100.0 + dx, 300.0 - dy)) == pytest.approx(30.0, abs=1e-5)


def test_filtering_and_angular_velocity():
    # Short gap (2 None) interpolated; long gap (6 None) preserved as None
    series = [10.0, None, None, 40.0, None, None, None, None, None, None, 100.0]
    out = interpolate_short_gaps(series, max_gap=3)
    assert out[1] == pytest.approx(20.0)
    assert out[2] == pytest.approx(30.0)
    assert all(out[k] is None for k in range(4, 10))

    # Constant 90 deg/s angular velocity with non-uniform timestamps
    angles = [0.0, 9.0, 27.0, 45.0, 54.0, 63.0]
    times = [0.0, 0.1, 0.3, 0.5, 0.6, 0.7]
    vels = compute_angular_velocity(angles, times, fps=10.0)
    valid_vels = [v for v in vels[1:] if v is not None]
    assert len(valid_vels) == 5
    for v in valid_vels:
        assert v == pytest.approx(90.0, abs=1.0)


def test_assessment_missing_data_discipline():
    # If landmarks and reps are empty, composite score must be withheld (None) and statuses INSUFFICIENT DATA
    empty_bio = {
        "timestamps_sec": [0.0, 0.1],
        "angles_deg": {},
        "angular_velocities_deg_s": {},
        "joint_summaries": {},
        "kinematic_ratios": {},
        "trajectories": {},
        "symmetry": {},
        "angle_conventions": {},
    }
    empty_mv = {
        "movement_type": "squat",
        "repetitions": [],
        "consistency": {},
        "summary_metrics": {"sufficient_data": False},
    }
    poor_quality = {
        "mean_landmark_confidence": 0.15,
        "selected_perspective": "side",
        "inferred_perspective": "unknown",
    }
    res = run_assessment("squat", empty_bio, empty_mv, poor_quality)
    assert res["composite_score"] is None
    assert res["composite_status"] == STATUS_INSUFFICIENT
    assert all(p["status"] == STATUS_INSUFFICIENT for p in res["parameters"])


# ---------------------------------------------------------------------------
# 2. Ground-Truth Landmark & Angle Validation (pose_squats.mp4 vs pose_squats.full.json)
# ---------------------------------------------------------------------------


def test_reference_pose_squats_mae_rmse():
    video_path = PROJECT_ROOT / "sample_videos" / "squat_front_1.mp4"
    ref_path = BACKEND_ROOT / "tests" / "data" / "pose_squats.full.json"
    if not video_path.exists() or not ref_path.exists():
        pytest.skip("Reference video or JSON not present")

    ref_frames = json.loads(ref_path.read_text())
    pose_data = extract_pose_landmarks(video_path, confidence_threshold=0.50)
    bio = compute_biomechanics(pose_data, "squat", "front", "front")

    n = min(len(ref_frames), pose_data["processed_frames"])
    assert n >= 60

    coord_errors = []
    knee_angle_errors = []

    for i in range(n):
        lms = pose_data["frame_records"][i]["landmarks"]
        ref_lms = ref_frames[i]
        if not lms:
            continue
        for idx in (11, 12, 23, 24, 25, 26, 27, 28):
            if lms[idx]["is_reliable"]:
                dx = lms[idx]["x_px"] - ref_lms[idx][0]
                dy = lms[idx]["y_px"] - ref_lms[idx][1]
                coord_errors.append(math.hypot(dx, dy))

        # Compare knee flexion against raw reference keypoints
        ref_lk_int = calculate_angle_3pt(
            (ref_lms[23][0], ref_lms[23][1]),
            (ref_lms[25][0], ref_lms[25][1]),
            (ref_lms[27][0], ref_lms[27][1]),
        )
        ref_lk_flex = internal_to_flexion_angle(ref_lk_int)
        est_lk_flex = bio["angles_deg"]["left_knee_flexion"][i]
        if ref_lk_flex is not None and est_lk_flex is not None:
            knee_angle_errors.append(abs(est_lk_flex - ref_lk_flex))

    coord_mae = float(np.mean(coord_errors))
    coord_rmse = float(np.sqrt(np.mean(np.square(coord_errors))))
    angle_mae = float(np.mean(knee_angle_errors))
    angle_rmse = float(np.sqrt(np.mean(np.square(knee_angle_errors))))

    print(f"\n[Reference Validation] coord_MAE={coord_mae:.2f}px, coord_RMSE={coord_rmse:.2f}px, knee_angle_MAE={angle_mae:.2f}deg, knee_angle_RMSE={angle_rmse:.2f}deg")
    assert coord_mae < 25.0
    assert angle_mae < 10.0


# ---------------------------------------------------------------------------
# 3. End-to-End FastAPI Integration Tests
# ---------------------------------------------------------------------------


def test_api_empty_invalid_and_full_squat_pipeline(tmp_path):
    init_db()
    with TestClient(app) as client:
        # 1. Invalid file upload rejected cleanly
        bad_file = tmp_path / "notes.txt"
        bad_file.write_text("not a video")
        with open(bad_file, "rb") as f:
            resp_bad = client.post(
                "/api/analysis/upload",
                files={"file": ("notes.txt", f, "text/plain")},
                data={"movement_type": "squat", "camera_perspective": "side"},
            )
        assert resp_bad.status_code == 400

        # 2. Load real human squat side video via sample endpoint
        resp_up = client.post(
            "/api/analysis/upload-sample",
            json={"sample_id": "squat_side_1", "movement_type": "squat", "camera_perspective": "side"},
        )
        assert resp_up.status_code == 200
        analysis_id = resp_up.json()["analysis_id"]

        try:
            # 3. Trigger processing
            resp_proc = client.post(
                "/api/analysis/process",
                json={
                    "analysis_id": analysis_id,
                    "movement_type": "squat",
                    "camera_perspective": "side",
                    "confidence_threshold": 0.50,
                },
            )
            assert resp_proc.status_code == 200

            # 4. Poll until complete (TestClient executes background task inside lifespan/event loop)
            import time
            status_payload = None
            for _ in range(120):
                st = client.get(f"/api/analysis/{analysis_id}")
                assert st.status_code == 200
                status_payload = st.json()
                if status_payload["status"] in ("completed", "failed"):
                    break
                time.sleep(0.5)

            assert status_payload is not None
            assert status_payload["status"] == "completed", status_payload.get("error_message")
            assert status_payload["has_video"] is True
            assert status_payload["has_report"] is True

            # 5. Inspect results
            res = client.get(f"/api/analysis/{analysis_id}/results").json()
            assert res["movement_analysis"]["rep_count"] == 2
            assert res["data_quality"]["valid_frame_ratio"] > 0.85
            assert res["assessment"]["composite_score"] is not None

            # 6. Verify annotated H.264 video stream
            vid_resp = client.get(f"/api/analysis/{analysis_id}/video")
            assert vid_resp.status_code == 200
            assert vid_resp.headers["content-type"].startswith("video/mp4")
            assert len(vid_resp.content) > 50_000

            # 7. Verify ReportLab PDF download
            pdf_resp = client.get(f"/api/analysis/{analysis_id}/report")
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            assert pdf_resp.content[:5] == b"%PDF-"
        finally:
            delete_analysis_record(analysis_id)
