"""Report download API endpoint."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import REPORTS_DIR
from app.core.database import get_analysis_record
from app.services.report_generator import generate_pdf_report

router = APIRouter(prefix="/api/analysis", tags=["reports"])


@router.get("/{analysis_id}/report")
async def download_report(analysis_id: str) -> FileResponse:
    """Serve (or regenerate if missing) the downloadable PDF biomechanical assessment report."""
    rec = get_analysis_record(analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if rec["status"] != "completed" or not rec.get("results"):
        raise HTTPException(status_code=409, detail="Assessment report is only available after analysis completes.")

    report_path = Path(rec["report_pdf_path"]) if rec.get("report_pdf_path") else (REPORTS_DIR / f"{analysis_id}_report.pdf")
    if not report_path.exists():
        generate_pdf_report(rec["results"], report_path)

    movement_slug = rec["movement_type"]
    return FileResponse(
        path=str(report_path),
        filename=f"MotionIQ_{movement_slug}_{analysis_id[:8]}_Report.pdf",
        media_type="application/pdf",
    )
