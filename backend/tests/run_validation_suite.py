"""Run full scientific validation across all downloaded real-human videos and print exact metrics."""

from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import create_analysis_record, delete_analysis_record, init_db
from app.services.video_processor import run_full_analysis_pipeline
from app.utils.geometry import calculate_angle_3pt, internal_to_flexion_angle
from app.utils.validation import validate_video_file

TEST_CASES = [
    ("sample_videos/squat_side_1.mp4", "squat", "side", 2),
    ("sample_videos/squat_front_1.mp4", "squat", "front", 3),
    ("sample_videos/squat_side_2.mp4", "squat", "front", None),
    ("sample_videos/lunge_side_1.mp4", "lunge", "side", None),
    ("sample_videos/jumping_jacks_front_1.mp4", "jumping_jack", "front", 8),
    ("sample_videos/jumping_jacks_front_2.mp4", "jumping_jack", "front", None),
    ("sample_videos/bball_jumpshot.MOV", "basketball_shooting", "side", 1),
    ("sample_videos/basketball_shot_side_1.mp4", "basketball_shooting", "side", None),  # Known low-visibility clip
]


def main() -> None:
    init_db()
    report_rows = []
    for rel_path, mv_type, persp, expected_reps in TEST_CASES:
        vid_path = PROJECT_ROOT / rel_path
        if not vid_path.exists():
            continue
        val = validate_video_file(vid_path)
        aid = f"val_{uuid.uuid4().hex[:8]}"
        create_analysis_record(aid, vid_path.name, str(vid_path), mv_type, persp, val)
        try:
            res = run_full_analysis_pipeline(aid, mv_type, persp, 0.50)
            q = res["data_quality"]
            m = res["movement_analysis"]
            a = res["assessment"]
            row = {
                "video": rel_path,
                "movement": mv_type,
                "perspective": persp,
                "frames": q["frames_processed"],
                "pose_detected_frames": q["pose_detected_frames"],
                "valid_frame_ratio": q["valid_frame_ratio"],
                "mean_conf": q["mean_landmark_confidence"],
                "quality_status": q["quality_status"],
                "inferred_perspective": q["inferred_perspective"],
                "rep_count": m["rep_count"],
                "expected_reps": expected_reps,
                "composite_score": a["composite_score"],
                "summary_metrics": m["summary_metrics"],
                "processing_time_sec": res["processing_details"]["processing_time_sec"],
            }
            report_rows.append(row)
            print(json.dumps(row))
        finally:
            # Clean up temporary validation files & db row so workspace stays clean
            # (Note: raw_video_path points to sample_videos, so clear raw_video_path before delete or delete manually!)
            from app.core.database import _get_conn
            with _get_conn() as conn:
                conn.execute("DELETE FROM analyses WHERE analysis_id = ?", (aid,))
                conn.commit()
            ann = BACKEND_ROOT / "storage" / "processed" / f"{aid}_annotated.mp4"
            pdf = BACKEND_ROOT / "storage" / "reports" / f"{aid}_report.pdf"
            ann.unlink(missing_ok=True)
            pdf.unlink(missing_ok=True)

    # Save summary JSON for VALIDATION_REPORT.md
    out_json = BACKEND_ROOT / "tests" / "validation_results.json"
    out_json.write_text(json.dumps(report_rows, indent=2))
    print(f"\nSaved {len(report_rows)} validation results to {out_json}")


if __name__ == "__main__":
    main()
