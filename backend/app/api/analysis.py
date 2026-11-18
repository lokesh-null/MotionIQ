"""Analysis REST API endpoints for upload, validation, processing, status, results, and video streaming."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import (
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    SAMPLE_VIDEO_CATALOG,
    SAMPLE_VIDEOS_DIR,
    SUPPORTED_MOVEMENTS,
    UPLOADS_DIR,
)
from app.core.database import (
    create_analysis_record,
    delete_analysis_record,
    get_analysis_record,
    list_analyses_records,
    update_analysis_progress,
)
from app.models.schemas import (
    AnalysisListItem,
    AnalysisStatusResponse,
    ProcessRequest,
    SampleUploadRequest,
    UploadResponse,
)
from app.services.video_processor import run_full_analysis_pipeline
from app.utils.validation import validate_video_file

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Track running background tasks in memory to prevent garbage collection
_active_tasks: Dict[str, asyncio.Task[Any]] = {}


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in base)
    return cleaned or "upload.mp4"


@router.get("/movements")
async def get_movements() -> Dict[str, Any]:
    """Return available movement modules and recording perspective guidelines."""
    return {
        "movements": list(SUPPORTED_MOVEMENTS.values()),
        "guidelines": {
            "side": {
                "title": "Side-View Recording (Sagittal Plane)",
                "checklist": [
                    "Keep the entire body (head to feet) visible inside the frame throughout the exercise.",
                    "Position the camera approximately perpendicular (90 deg) to your movement direction.",
                    "Mount the camera on a tripod or stable stationary surface at hip/waist height.",
                    "Ensure even lighting with clear contrast between clothing and background.",
                    "Avoid baggy clothing that obscures knee, hip, or ankle landmarks.",
                ],
                "suitable_for": [
                    "Sagittal-plane joint kinematics",
                    "Squat depth & knee flexion",
                    "Hip flexion & trunk inclination",
                    "Lunge front/rear knee flexion",
                    "Shooting-arm elbow/shoulder trajectory",
                ],
            },
            "front": {
                "title": "Frontal Recording (Coronal Plane)",
                "checklist": [
                    "Face the camera directly so both left and right limbs remain unobstructed.",
                    "Ensure adequate distance so overhead arm reaches (e.g., jumping jacks) remain inside frame.",
                    "Mount the camera level and stationary to minimize perspective distortion.",
                    "Ensure uniform lighting and minimal background clutter or bystanders.",
                ],
                "suitable_for": [
                    "Observable left-right alignment indicators",
                    "Bilateral shoulder abduction & jumping jacks",
                    "Movement symmetry comparisons",
                    "Lower-limb lateral spread tracking",
                ],
            },
        },
    }


@router.get("/samples")
async def list_sample_videos() -> List[Dict[str, Any]]:
    """List verified real human sample recordings available on disk for demonstration and testing."""
    items: List[Dict[str, Any]] = []
    for item in SAMPLE_VIDEO_CATALOG:
        path = SAMPLE_VIDEOS_DIR / item["filename"]
        if path.exists():
            items.append({**item, "file_size_bytes": path.stat().st_size})
    return items


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    movement_type: str = Form("squat"),
    camera_perspective: str = Form("side"),
) -> UploadResponse:
    """Upload a user video, store safely, and validate format, dimensions, duration, and readability."""
    if movement_type not in SUPPORTED_MOVEMENTS:
        raise HTTPException(status_code=400, detail=f"Unsupported movement_type '{movement_type}'.")
    if camera_perspective not in ("side", "front"):
        raise HTTPException(status_code=400, detail="camera_perspective must be 'side' or 'front'.")

    orig_name = _safe_filename(file.filename or "video.mp4")
    ext = Path(orig_name).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}.",
        )

    analysis_id = str(uuid.uuid4())
    dest_path = UPLOADS_DIR / f"{analysis_id}_{orig_name}"

    total_written = 0
    try:
        with open(dest_path, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > MAX_FILE_SIZE_BYTES:
                    out_f.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit.",
                    )
                out_f.write(chunk)
    finally:
        await file.close()

    validation = validate_video_file(dest_path)
    if not validation["valid"]:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="; ".join(validation["errors"]))

    create_analysis_record(
        analysis_id=analysis_id,
        filename=orig_name,
        raw_video_path=str(dest_path),
        movement_type=movement_type,
        camera_perspective=camera_perspective,
        validation=validation,
    )

    return UploadResponse(
        analysis_id=analysis_id,
        filename=orig_name,
        movement_type=movement_type,
        camera_perspective=camera_perspective,
        validation=validation,
    )


@router.post("/upload-sample", response_model=UploadResponse)
async def upload_sample_video(payload: SampleUploadRequest) -> UploadResponse:
    """Copy a local verified real human sample recording into a new analysis session."""
    sample_entry = next((s for s in SAMPLE_VIDEO_CATALOG if s["id"] == payload.sample_id), None)
    if not sample_entry:
        raise HTTPException(status_code=404, detail=f"Sample '{payload.sample_id}' not found.")

    src_path = SAMPLE_VIDEOS_DIR / sample_entry["filename"]
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="Sample video file missing from disk.")

    movement_type = payload.movement_type or sample_entry["movement_type"]
    camera_perspective = payload.camera_perspective or sample_entry["camera_perspective"]
    if movement_type not in SUPPORTED_MOVEMENTS:
        raise HTTPException(status_code=400, detail=f"Unsupported movement_type '{movement_type}'.")
    if camera_perspective not in ("side", "front"):
        raise HTTPException(status_code=400, detail="camera_perspective must be 'side' or 'front'.")

    analysis_id = str(uuid.uuid4())
    dest_path = UPLOADS_DIR / f"{analysis_id}_{sample_entry['filename']}"
    shutil.copy2(src_path, dest_path)

    validation = validate_video_file(dest_path)
    if not validation["valid"]:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="; ".join(validation["errors"]))

    create_analysis_record(
        analysis_id=analysis_id,
        filename=sample_entry["filename"],
        raw_video_path=str(dest_path),
        movement_type=movement_type,
        camera_perspective=camera_perspective,
        validation=validation,
    )

    return UploadResponse(
        analysis_id=analysis_id,
        filename=sample_entry["filename"],
        movement_type=movement_type,
        camera_perspective=camera_perspective,
        validation=validation,
    )


@router.post("/process", response_model=AnalysisStatusResponse)
async def start_processing(payload: ProcessRequest) -> AnalysisStatusResponse:
    """Launch non-blocking background video pose estimation and biomechanics analysis."""
    rec = get_analysis_record(payload.analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis record not found.")

    if rec["status"] == "processing" and payload.analysis_id in _active_tasks:
        return await get_analysis_status(payload.analysis_id)

    update_analysis_progress(
        payload.analysis_id,
        status="processing",
        stage="queued",
        progress_percent=1.0,
        current_operation="Initializing computer vision pipeline",
        movement_type=payload.movement_type,
        camera_perspective=payload.camera_perspective,
        confidence_threshold=payload.confidence_threshold,
        error_message="",
    )

    async def _worker() -> None:
        try:
            await asyncio.to_thread(
                run_full_analysis_pipeline,
                payload.analysis_id,
                payload.movement_type,
                payload.camera_perspective,
                payload.confidence_threshold,
                payload.criteria_overrides,
            )
        except Exception:
            # Error status is persisted inside run_full_analysis_pipeline
            pass
        finally:
            _active_tasks.pop(payload.analysis_id, None)

    _active_tasks[payload.analysis_id] = asyncio.create_task(_worker())
    return await get_analysis_status(payload.analysis_id)


@router.get("", response_model=List[AnalysisListItem])
async def list_analyses() -> List[AnalysisListItem]:
    """Return stored assessments ordered newest first (empty list when none exist)."""
    rows = list_analyses_records()
    return [AnalysisListItem(**row) for row in rows]


@router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(analysis_id: str) -> AnalysisStatusResponse:
    """Return live processing stage, processed frames, total frames, and status."""
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    has_video = bool(rec.get("annotated_video_path") and Path(rec["annotated_video_path"]).exists())
    has_report = bool(rec.get("report_pdf_path") and Path(rec["report_pdf_path"]).exists())
    return AnalysisStatusResponse(
        analysis_id=rec["analysis_id"],
        status=rec["status"],
        stage=rec["stage"],
        frames_processed=int(rec["frames_processed"] or 0),
        total_frames=int(rec["total_frames"] or 0),
        progress_percent=float(rec["progress_percent"] or 0.0),
        current_operation=rec["current_operation"],
        movement_type=rec["movement_type"],
        camera_perspective=rec["camera_perspective"],
        filename=rec["filename"],
        created_at=rec["created_at"],
        completed_at=rec.get("completed_at"),
        error_message=rec.get("error_message") or None,
        has_video=has_video,
        has_report=has_report,
    )


@router.get("/{analysis_id}/results")
async def get_analysis_results(analysis_id: str) -> Dict[str, Any]:
    """Return full biomechanical measurements, movement phases, repetitions, and assessment results."""
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if rec["status"] == "failed":
        raise HTTPException(status_code=409, detail=rec.get("error_message") or "Analysis failed.")
    if rec["status"] != "completed" or not rec.get("results"):
        raise HTTPException(status_code=202, detail="Analysis is still processing.")
    return rec["results"]


@router.get("/{analysis_id}/raw-video")
async def get_raw_video(analysis_id: str) -> FileResponse:
    """Stream the uploaded raw video safely for pre-analysis preview."""
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    path = Path(rec["raw_video_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Raw video file missing.")
    return FileResponse(path=str(path), filename=rec["filename"], media_type="video/mp4")


@router.get("/{analysis_id}/video")
async def get_annotated_video(analysis_id: str) -> FileResponse:
    """Stream the processed skeleton-annotated H.264 video."""
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    ann_path = rec.get("annotated_video_path")
    if not ann_path or not Path(ann_path).exists():
        raise HTTPException(status_code=404, detail="Annotated video is not available yet.")
    return FileResponse(
        path=ann_path,
        filename=f"motioniq_{analysis_id[:8]}_annotated.mp4",
        media_type="video/mp4",
    )


@router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: str) -> Dict[str, str]:
    """Delete an analysis record and its associated temporary/processed files."""
    if analysis_id in _active_tasks:
        raise HTTPException(status_code=409, detail="Cannot delete an analysis while it is actively running.")
    deleted = delete_analysis_record(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {"deleted": analysis_id}
