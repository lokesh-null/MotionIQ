"""FastAPI entrypoint for MotionIQ Sports Biomechanics Platform."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router
from app.core.database import init_db
from app.services.pose_estimator import _ensure_linux_gl_libraries


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _ensure_linux_gl_libraries()
    init_db()
    yield


app = FastAPI(
    title="MotionIQ Sports Biomechanics API",
    description="Computer vision pose estimation and sports biomechanics assessment API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Disposition"],
)

app.include_router(analysis_router)
app.include_router(reports_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "motioniq-backend"}
