# MotionIQ — Sports Biomechanics Analysis & Movement Assessment Platform

MotionIQ is a locally executable computer vision and sports biomechanics platform built with **FastAPI**, **OpenCV**, **MediaPipe Pose Landmarker (33 landmarks)**, **SciPy**, **ReportLab**, **React**, **TypeScript**, **Tailwind CSS**, and **Recharts**.

> **Scope & Educational Disclaimer:** MotionIQ is an educational and sports-performance prototype, not a clinically validated medical diagnostic system. Single-camera 2D monocular pose estimation measures projected planar angles and cannot reconstruct true 3D joint torques or out-of-plane rotations.

---

## Core Capabilities

1. **Computer Vision Pose Pipeline**
   - Decodes `.mp4`, `.mov`, and `.avi` videos via OpenCV with pre-processing validation (format, size, resolution, frame count, FPS, duration, readability).
   - Uses MediaPipe `PoseLandmarker` (`pose_landmarker_full.task`) in `VIDEO` mode to extract 33 human body landmarks with actual container frame timestamps (`CAP_PROP_POS_MSEC`).
   - Masks out occluded or low-confidence joints rather than computing measurements from unreliable coordinates, and handles multi-person frames via primary-athlete spatial continuity tracking.
   - Generates browser-playable annotated H.264 MP4 videos (`libx264`, `yuv420p`, `+faststart`) displaying the skeleton overlay, confidence-coded joints, live joint-angle callouts, movement phase HUD, repetition count, and timestamps.

2. **Biomechanics Calculation Engine**
   - Aspect-ratio-corrected 2D vector joint angles ($\cos\theta = \frac{u \cdot v}{|u||v|}$) with explicit distinction between **internal joint angles** ($180^\circ$ = straight) and **flexion angles** ($0^\circ$ = straight).
   - Savitzky-Golay smoothing over contiguous valid segments (preserving extended missing gaps as `null`) and timestamped angular velocity ($\text{deg/s}$).
   - Movement trajectories, repetition consistency (SD, CV%), and perspective-gated bilateral left-right symmetry comparison.

3. **Movement Analysis Modules**
   - **Squat Analysis (Primary):** Standing, Descending, Bottom, Ascending, Return to Standing; knee/hip flexion, trunk inclination + delta from standing baseline, hip depth ratio, tempo ratio, and consistency.
   - **Lunge Analysis (Core):** Dynamic front/rear leg identification, Descent/Bottom/Ascent/Return phases, front/rear knee flexion, ROM, trunk inclination, and consistency.
   - **Jumping Jack Analysis (Core):** Initial Standing, Outward Movement, Maximum Extension, Return Movement; bilateral shoulder abduction, ankle spread ratio, hip abduction ROM, and left-right coordination.
   - **Basketball Shooting Analysis (Experimental):** Preparation Dip, Upward Extension, Release Point, Follow-Through; shooting-arm elbow/shoulder kinematics and release posture (explicitly withholding ball velocity without calibrated ball tracking).

4. **Transparent Assessment & PDF Reporting**
   - Evaluates measurements against documented criteria (`GOOD`, `NEEDS IMPROVEMENT`, `OUTSIDE REFERENCE RANGE`, `INSUFFICIENT DATA`), explicitly separating established biomechanical definitions from engineering prototype thresholds.
   - Withholds composite scores when valid weight coverage is below 55%.
   - Exports multi-page ReportLab PDF reports containing metadata, repetition breakdowns, joint kinematics tables, Matplotlib angle/velocity plots, evidence-based feedback, data quality diagnostics, and limitations.

---

## Project Structure

```text
BioMech/
├── backend/
│   ├── app/
│   │   ├── api/                 # REST endpoints (analysis.py, reports.py)
│   │   ├── core/                # Config & SQLite persistence
│   │   ├── models/              # Pydantic request/response schemas
│   │   ├── services/            # pose_estimator, biomechanics, movement_classifier,
│   │   │                        # assessment_engine, video_processor, report_generator
│   │   ├── utils/               # geometry, filters, validation
│   │   └── main.py              # FastAPI application entrypoint
│   ├── models/                  # MediaPipe .task models
│   ├── storage/                 # uploads/, processed/, reports/, motioniq.db
│   ├── tests/                   # pytest suite & multi-video validation runner
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # VideoPlayer, PerformanceChart, JointMetricCard, etc.
│   │   ├── pages/               # Dashboard, NewAnalysis, Processing, AnalysisResults
│   │   ├── services/            # Typed REST API client
│   │   └── types/               # TypeScript biomechanical interfaces
│   └── package.json
├── sample_videos/               # Real human test & demonstration recordings
└── VALIDATION_REPORT.md         # Observed validation metrics & known limitations
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.14.6)
- Node.js 18+ and npm (tested on Node v24.16.0 / npm 11.13.0)

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```
Ensure `backend/models/pose_landmarker_full.task` (or `pose_landmarker_lite.task`) is present (already included in `backend/models/`).

### 2. Frontend Setup
```bash
cd frontend
npm install
```

---

## Running the Application

Start both servers in separate terminals from the project root (`BioMech/`):

### Terminal 1 — FastAPI Backend (port 8000)
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — React Vite Frontend (port 5173)
```bash
cd frontend
npm run dev
```

Open **`http://localhost:5173`** in your browser. Vite automatically proxies `/api/*` requests to `http://127.0.0.1:8000`.

---

## Running Tests & Validation

```bash
# Run mathematical, ground-truth reference, and end-to-end API integration tests
python -m pytest -s -v backend/tests/test_motioniq.py

# Run multi-video validation suite across all movement modules
python backend/tests/run_validation_suite.py
```

See [VALIDATION_REPORT.md](file:///c:/My%20Projects/BioMech/VALIDATION_REPORT.md) for measured experimental results, reference agreement errors, and known limitations.

---

## Cloud Deployment (Vercel + Render)

### 1. Deploy Backend on Render
1. Connect `https://github.com/lokesh-null/MotionIQ` in Render as a **Web Service** (or use **Blueprint** with `render.yaml`).
2. Render uses [Dockerfile](file:///c:/My%20Projects/BioMech/Dockerfile) (Docker context `.` at repo root) and checks `/api/health`.
3. Note on instance sizing: Render's Free tier (`512 MB` RAM) may run out of memory during MediaPipe + OpenCV + FFmpeg H.264 video encoding; **Starter (`512 MB`–`2 GB`) or Standard (`>= 2 GB` RAM)** is recommended for smooth video processing.
4. Set environment variable `CORS_ORIGINS` to your Vercel production URL (e.g. `https://motion-iq.vercel.app`). Preview `*.vercel.app` domains are also permitted automatically.

### 2. Deploy Frontend on Vercel
1. Import `lokesh-null/MotionIQ` in Vercel and set **Root Directory** to `frontend`.
2. Framework Preset: **Vite** (`npm run build`, output `dist`). SPA routing is handled by [vercel.json](file:///c:/My%20Projects/BioMech/frontend/vercel.json).
3. Add Environment Variable:
   - `VITE_API_BASE_URL` = `https://<your-render-service>.onrender.com` (no trailing slash).
4. Redeploy if `VITE_API_BASE_URL` is added after the first build.

