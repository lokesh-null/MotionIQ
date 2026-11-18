"""FastAPI entrypoint for MotionIQ Sports Biomechanics Platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router
from app.core.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)
app.include_router(reports_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "motioniq-backend"}
