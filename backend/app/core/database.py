"""SQLite persistence layer for MotionIQ analysis jobs and results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the analyses table if it does not yet exist (starts empty with zero fake records)."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                analysis_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                raw_video_path TEXT NOT NULL,
                annotated_video_path TEXT,
                report_pdf_path TEXT,
                movement_type TEXT NOT NULL,
                camera_perspective TEXT NOT NULL,
                confidence_threshold REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                frames_processed INTEGER NOT NULL DEFAULT 0,
                total_frames INTEGER NOT NULL DEFAULT 0,
                progress_percent REAL NOT NULL DEFAULT 0.0,
                current_operation TEXT NOT NULL,
                validation_json TEXT,
                results_json TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.commit()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_analysis_record(
    analysis_id: str,
    filename: str,
    raw_video_path: str,
    movement_type: str,
    camera_perspective: str,
    validation: Dict[str, Any],
) -> None:
    total_frames = int((validation.get("metadata") or {}).get("frame_count", 0) or 0)
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO analyses (
                analysis_id, filename, raw_video_path, movement_type, camera_perspective,
                status, stage, frames_processed, total_frames, progress_percent,
                current_operation, validation_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                filename,
                raw_video_path,
                movement_type,
                camera_perspective,
                "uploaded",
                "validated",
                0,
                total_frames,
                0.0,
                "Video validated and ready for processing",
                json.dumps(validation),
                utc_now_iso(),
            ),
        )
        conn.commit()


def update_analysis_progress(
    analysis_id: str,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    frames_processed: Optional[int] = None,
    total_frames: Optional[int] = None,
    progress_percent: Optional[float] = None,
    current_operation: Optional[str] = None,
    movement_type: Optional[str] = None,
    camera_perspective: Optional[str] = None,
    confidence_threshold: Optional[float] = None,
    error_message: Optional[str] = None,
) -> None:
    updates: List[str] = []
    params: List[Any] = []
    fields = {
        "status": status,
        "stage": stage,
        "frames_processed": frames_processed,
        "total_frames": total_frames,
        "progress_percent": progress_percent,
        "current_operation": current_operation,
        "movement_type": movement_type,
        "camera_perspective": camera_perspective,
        "confidence_threshold": confidence_threshold,
        "error_message": error_message,
    }
    for col, val in fields.items():
        if val is not None:
            updates.append(f"{col} = ?")
            params.append(val)
    if not updates:
        return
    params.append(analysis_id)
    with _get_conn() as conn:
        conn.execute(f"UPDATE analyses SET {', '.join(updates)} WHERE analysis_id = ?", params)
        conn.commit()


def complete_analysis_record(
    analysis_id: str,
    annotated_video_path: Optional[str],
    report_pdf_path: Optional[str],
    results: Dict[str, Any],
    total_frames: int,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE analyses
            SET status = 'completed',
                stage = 'completed',
                frames_processed = ?,
                total_frames = ?,
                progress_percent = 100.0,
                current_operation = 'Analysis, annotated video, and PDF report ready',
                annotated_video_path = ?,
                report_pdf_path = ?,
                results_json = ?,
                error_message = NULL,
                completed_at = ?
            WHERE analysis_id = ?
            """,
            (
                total_frames,
                total_frames,
                annotated_video_path,
                report_pdf_path,
                json.dumps(results),
                results.get("completed_at") or utc_now_iso(),
                analysis_id,
            ),
        )
        conn.commit()


def get_analysis_record(analysis_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get("validation_json"):
            d["validation"] = json.loads(d["validation_json"])
        if d.get("results_json"):
            d["results"] = json.loads(d["results_json"])
        return d


def list_analyses_records(limit: int = 50) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        items: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            res = json.loads(d["results_json"]) if d.get("results_json") else None
            rep_count = None
            comp_score = None
            qual_status = None
            if res:
                rep_count = (res.get("movement_analysis") or {}).get("rep_count")
                comp_score = (res.get("assessment") or {}).get("composite_score")
                qual_status = (res.get("data_quality") or {}).get("quality_status")
            items.append(
                {
                    "analysis_id": d["analysis_id"],
                    "status": d["status"],
                    "movement_type": d["movement_type"],
                    "camera_perspective": d["camera_perspective"],
                    "filename": d["filename"],
                    "created_at": d["created_at"],
                    "completed_at": d["completed_at"],
                    "rep_count": rep_count,
                    "composite_score": comp_score,
                    "quality_status": qual_status,
                }
            )
        return items


def delete_analysis_record(analysis_id: str) -> Optional[Dict[str, Any]]:
    rec = get_analysis_record(analysis_id)
    if not rec:
        return None
    with _get_conn() as conn:
        conn.execute("DELETE FROM analyses WHERE analysis_id = ?", (analysis_id,))
        conn.commit()
    for p_key in ("raw_video_path", "annotated_video_path", "report_pdf_path"):
        p_val = rec.get(p_key)
        if p_val:
            try:
                Path(p_val).unlink(missing_ok=True)
            except OSError:
                pass
    return rec
