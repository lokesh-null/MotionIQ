"""Pydantic models for MotionIQ API requests and responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    analysis_id: str
    filename: str
    movement_type: str
    camera_perspective: str
    validation: Dict[str, Any]


class SampleUploadRequest(BaseModel):
    sample_id: str
    movement_type: Optional[str] = None
    camera_perspective: Optional[str] = None


class ProcessRequest(BaseModel):
    analysis_id: str
    movement_type: str = Field(..., pattern="^(squat|lunge|jumping_jack|basketball_shooting)$")
    camera_perspective: str = Field(default="side", pattern="^(side|front)$")
    confidence_threshold: float = Field(default=0.50, ge=0.20, le=0.90)
    criteria_overrides: Optional[Dict[str, float]] = None


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: str  # uploaded, queued, processing, completed, failed
    stage: str
    frames_processed: int
    total_frames: int
    progress_percent: float
    current_operation: str
    movement_type: str
    camera_perspective: str
    filename: str
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    has_video: bool = False
    has_report: bool = False


class AnalysisListItem(BaseModel):
    analysis_id: str
    status: str
    movement_type: str
    camera_perspective: str
    filename: str
    created_at: str
    completed_at: Optional[str] = None
    rep_count: Optional[int] = None
    composite_score: Optional[float] = None
    quality_status: Optional[str] = None
