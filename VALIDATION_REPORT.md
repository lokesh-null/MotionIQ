# MotionIQ — Scientific Validation & Testing Report

**Date:** November 18, 2026  
**Pose Estimation Model:** MediaPipe Pose Landmarker (`pose_landmarker_full.task`, 33 body landmarks, `VIDEO` mode)  
**Environment:** Windows, Python 3.14.6, OpenCV 5.1.0, SciPy 1.18.0, FastAPI 0.141.1

---

## 1. Mathematical & Geometric Verification (`pytest`)

All 7 automated tests in [test_motioniq.py](file:///c:/My%20Projects/BioMech/backend/tests/test_motioniq.py) passed (`7 passed in 30.82s`):

| Test Suite Check | Verified Condition | Result |
|---|---|---|
| Known 3-Point Joint Angles | $180^\circ$ straight, $90^\circ$ right angle, $45^\circ$, $60^\circ$, $120^\circ$ | **PASS** ($< 10^{-6}$ deg error) |
| Numerical Safeguards | `None` vertices, coincident zero-length vectors, `NaN` & `Inf` coordinates | **PASS** (safely returns `None`) |
| Aspect Ratio Scaling | Non-square `1920x1080` normalized coordinates scaled to pixels before angle computation | **PASS** ($90.0^\circ$ exact) |
| Conventions & Trunk Inclination | Internal ($180^\circ$ straight) vs Flexion ($0^\circ$ straight); $0^\circ$ vertical & $30^\circ$ trunk lean | **PASS** |
| Temporal Gap & Angular Velocity | Interpolates $\le 3$-frame gaps only, preserves long missing spans as `None`, exact $\Delta\theta/\Delta t$ on variable $\Delta t$ | **PASS** |
| Missing-Data Assessment Discipline | Empty/low-confidence data marks every parameter `INSUFFICIENT DATA` and withholds composite score (`None`) | **PASS** |
| End-to-End FastAPI Integration | Empty/invalid file rejection (`400`), `squat_side_1.mp4` full processing, H.264 stream (`200`), ReportLab PDF (`%PDF-`) | **PASS** |

---

## 2. Landmark & Joint-Angle Agreement Against Reference Annotations

Evaluated `pose_landmarker_full.task` on `sample_videos/squat_front_1.mp4` (`720x1280`, 65 frames) against the external BlazePose reference coordinates in `backend/tests/data/pose_squats.full.json` across 8 primary tracking landmarks (shoulders, hips, knees, ankles):

| Metric | Measured Error |
|---|---|
| 2D Landmark Pixel Coordinate MAE | **6.13 px** (on `720x1280` frame; `< 0.85%` frame width) |
| 2D Landmark Pixel Coordinate RMSE | **7.23 px** |
| Left Knee Flexion Angle MAE | **3.34°** |
| Left Knee Flexion Angle RMSE | **4.55°** |

---

## 3. Multi-Video Real-Human Movement Validation

Executed via [run_validation_suite.py](file:///c:/My%20Projects/BioMech/backend/tests/run_validation_suite.py) across **8 real-human athletic videos** covering all 4 movement modules:

| Video File | Movement | Perspective (Selected / Inferred) | Processed Frames | Pose Detected | Valid Frame Ratio | Mean Conf. | Quality Status | Detected Reps (Expected) | Key Kinematic Output | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| `squat_side_1.mp4` | Squat | `side` / `side` | 614 | 614 | 1.000 | 0.774 | **GOOD** | **2** (2) | Avg Peak Knee Flexion: 109.90°, Trunk Peak: 35.55° | 24.86 |
| `squat_front_1.mp4` | Squat | `front` / `front` | 65 | 65 | 1.000 | 0.967 | **GOOD** | **3** (3) | Avg Projected Knee Flexion: 81.99°, Trunk Peak: 28.26° | 3.51 |
| `squat_side_2.mp4` | Squat | `front` / `front` | 514 | 514 | 1.000 | 0.983 | **GOOD** | **6** | Avg Projected Knee Flexion: 104.46°, Trunk Peak: 1.92° | 26.64 |
| `lunge_side_1.mp4` | Lunge | `side` / `side` | 638 | 638 | 1.000 | 0.845 | **GOOD** | **8** | Front Knee Avg: 75.88°, Rear Knee Avg: 81.56° | 34.47 |
| `jumping_jacks_front_1.mp4` | Jumping Jack | `front` / `front` | 172 | 172 | 1.000 | 0.994 | **GOOD** | **8** (8) | Avg Shoulder Peak: 157.83°, Ankle Spread: 1.04x | 7.54 |
| `jumping_jacks_front_2.mp4` | Jumping Jack | `front` / `front` | 316 | 314 | 0.930 | 0.983 | **GOOD** | **11** | Avg Shoulder Peak: 141.33°, Ankle Spread: 2.47x | 10.63 |
| `bball_jumpshot.MOV` | Basketball (Exp.) | `side` / `front` | 91 | 90 | 0.989 | 0.916 | **LIMITED** | **1** (1) | Release Elbow: 115.53°, Release Shoulder: 126.42° | 5.51 |
| `basketball_shot_side_1.mp4` | Basketball (Exp.) | `side` / `front` | 300 | 122 | 0.130 | 0.622 | **INSUFFICIENT** | **0** | Score withheld (`None`); flagged insufficient visibility | 9.99 |

### Key Observations from Validation
1. **Valid Assessments:** 7 out of 8 recordings produced valid, complete kinematic assessments, annotated H.264 videos, and PDF reports. On every recording with known ground-truth repetition counts (`squat_side_1.mp4` = 2, `squat_front_1.mp4` = 3, `jumping_jacks_front_1.mp4` = 8, `bball_jumpshot.MOV` = 1), repetition count agreement was **4/4 (100%)**.
2. **Observed Failure Case & Safe Handling (`basketball_shot_side_1.mp4`):** In this clip, rapid camera motion, cuts, and cropped/occluded lower-body frames caused pose detection to succeed on only 122/300 frames and valid full-body landmark coverage to drop to **13.0%**. MotionIQ accurately classified quality as **`INSUFFICIENT`**, reported 0 repetitions, marked parameters as **`INSUFFICIENT DATA`**, and **withheld the composite score (`None`)** rather than fabricating scores.
3. **Perspective Mismatch Detection (`bball_jumpshot.MOV`):** Selecting `side` when visual shoulder-to-torso proportions indicated a frontal/oblique orientation (`front`) automatically downgraded quality to **`LIMITED`** and emitted an explicit perspective compatibility warning.

---

## 4. Known Limitations

1. **2D Monocular Projection:** A single 2D camera measures projected planar joint angles and cannot reconstruct true 3D joint kinematics (such as internal/external tibial rotation, pelvic yaw, or knee valgus/varus torque).
2. **Frontal vs. Sagittal Trade-off:** Frontal views under-predict sagittal knee/hip flexion due to lens foreshortening, whereas side views occlude the far-side limb and therefore cannot provide valid left-right symmetry comparisons.
3. **High-Velocity Motion Blur & Cropping:** Fast athletic bursts or cropped limbs reduce MediaPipe landmark visibility below the configurable confidence threshold (`0.50` default), intentionally causing affected frames to be masked out.
4. **No Ball Tracking or Spatial Calibration:** The experimental Basketball Shooting module tracks upper-limb joint angles and release posture only; ball-release velocity and trajectory arc are omitted because metric spatial calibration and ball tracking are not present.
5. **Non-Clinical Thresholds:** Reference bands marked `ENGINEERING PROTOTYPE THRESHOLD` are configurable educational/performance baselines and not clinically validated diagnostic cutoffs.

---

## 5. End-to-End Frontend + Backend Browser Verification (`Playwright Chromium`)

Executed via [test_frontend_e2e.py](file:///c:/My%20Projects/BioMech/backend/tests/test_frontend_e2e.py) (`1 passed in 41.74s`) against the live Vite frontend (`http://127.0.0.1:5173`) and FastAPI backend (`http://127.0.0.1:8000`):

- **Empty State Check:** Confirmed Dashboard renders `"No Movement Assessments Recorded Yet"` when SQLite contains zero records.
- **Upload & Validation UI:** Uploaded `sample_videos/squat_side_1.mp4`; UI displayed `READY FOR ANALYSIS` with `608 × 1080`, `29.97 FPS`, `614` frames, and mounted the HTML5 preview `<video>`.
- **Live Processing Progress:** Clicked `"Start Biomechanical Analysis"`, verified live stage telemetry on `/processing/:id`, and observed automatic navigation to `/results/:id`.
- **Annotated H.264 Video Playback:** Verified Chromium decoded the processed H.264 stream (`608x1080`, `20.49s`), and clicking `Play` advanced `currentTime` (`0.86s` after `0.8s`).
- **Interactive Recharts Tabs:** Verified SVG chart rendering across `Joint Angles vs Time`, `Angular Velocity`, `Repetition Comparison`, and `Phases & Joint Trajectory`, and verified honest perspective-constraint disclosure on `Left-Right Symmetry` for side-view squat footage.
- **PDF Report Download:** Verified `"Report Summary"` preview and browser download of `MotionIQ_squat_c582372d_Report.pdf` (`178,352` bytes, `%PDF-` header).
- **Dashboard Persistence & Console Cleanliness:** Verified `squat_side_1.mp4` (`91.2/100`) appeared in the Dashboard Recent Assessments table with **0** uncaught page errors and **0** console errors.

