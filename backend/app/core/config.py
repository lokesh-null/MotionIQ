"""Centralized configuration for MotionIQ."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

MODELS_DIR = BACKEND_DIR / "models"
POSE_MODEL_FULL = MODELS_DIR / "pose_landmarker_full.task"
POSE_MODEL_LITE = MODELS_DIR / "pose_landmarker_lite.task"

STORAGE_DIR = BACKEND_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
REPORTS_DIR = STORAGE_DIR / "reports"
DB_PATH = STORAGE_DIR / "motioniq.db"

SAMPLE_VIDEOS_DIR = PROJECT_ROOT / "sample_videos"

for _directory in (MODELS_DIR, UPLOADS_DIR, PROCESSED_DIR, REPORTS_DIR, SAMPLE_VIDEOS_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
MIN_FILE_SIZE_BYTES = 10 * 1024  # 10 KB
MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB
MIN_VIDEO_WIDTH = 160
MIN_VIDEO_HEIGHT = 160
MIN_VIDEO_FRAMES = 10
MIN_VIDEO_DURATION_SEC = 0.5
MAX_VIDEO_DURATION_SEC = 180.0

DEFAULT_CONFIDENCE_THRESHOLD = 0.50
MIN_POSE_DETECTION_CONFIDENCE = 0.45
MIN_POSE_PRESENCE_CONFIDENCE = 0.45
MIN_TRACKING_CONFIDENCE = 0.45

# Frame sampling cap: process every frame up to 35 FPS; above that, sample near 30 FPS
MAX_ANALYSIS_FPS = 35.0
TARGET_SAMPLED_FPS = 30.0

SUPPORTED_MOVEMENTS = {
    "squat": {
        "id": "squat",
        "name": "Squat Analysis",
        "short_description": "Sagittal knee/hip flexion, trunk inclination, squat depth, repetition timing, and symmetry indicators.",
        "recommended_perspective": "side",
        "supported_perspectives": ["side", "front"],
        "status": "primary",
    },
    "lunge": {
        "id": "lunge",
        "name": "Lunge Analysis",
        "short_description": "Front and rear knee flexion, hip alignment, trunk control, phase timing, and range of motion.",
        "recommended_perspective": "side",
        "supported_perspectives": ["side", "front"],
        "status": "core",
    },
    "jumping_jack": {
        "id": "jumping_jack",
        "name": "Jumping Jack Analysis",
        "short_description": "Bilateral shoulder abduction, arm elevation, lower-limb abduction, and left-right coordination.",
        "recommended_perspective": "front",
        "supported_perspectives": ["front"],
        "status": "core",
    },
    "basketball_shooting": {
        "id": "basketball_shooting",
        "name": "Basketball Shooting Analysis",
        "short_description": "Experimental kinematic tracking of shooting-arm elbow/shoulder angles, arm elevation, and release posture.",
        "recommended_perspective": "side",
        "supported_perspectives": ["side", "front"],
        "status": "experimental",
    },
}

SAMPLE_VIDEO_CATALOG = [
    {
        "id": "squat_side_1",
        "filename": "squat_side_1.mp4",
        "title": "Bodyweight Squats — Side View",
        "movement_type": "squat",
        "camera_perspective": "side",
        "description": "Real human side-view squat recording suitable for sagittal-plane knee flexion, hip angle, depth, and trunk inclination analysis.",
    },
    {
        "id": "squat_front_1",
        "filename": "squat_front_1.mp4",
        "title": "Squats — Frontal View",
        "movement_type": "squat",
        "camera_perspective": "front",
        "description": "Frontal-view squat recording used for bilateral knee symmetry indicators and frontal tracking evaluation.",
    },
    {
        "id": "squat_side_2",
        "filename": "squat_side_2.mp4",
        "title": "Bodyweight Squats — Frontal Demo",
        "movement_type": "squat",
        "camera_perspective": "front",
        "description": "Additional real human frontal-view squat demonstration recording.",
    },
    {
        "id": "lunge_side_1",
        "filename": "lunge_side_1.mp4",
        "title": "Forward Lunges — Side View",
        "movement_type": "lunge",
        "camera_perspective": "side",
        "description": "Real human lunge recording capturing front and rear knee flexion and trunk inclination.",
    },
    {
        "id": "jumping_jacks_front_1",
        "filename": "jumping_jacks_front_1.mp4",
        "title": "Jumping Jacks — Frontal View",
        "movement_type": "jumping_jack",
        "camera_perspective": "front",
        "description": "Frontal-view jumping jack recording for bilateral arm elevation and lower-limb abduction symmetry.",
    },
    {
        "id": "basketball_shot_side_1",
        "filename": "bball_jumpshot.MOV",
        "title": "Basketball Jump Shot — Side View (.MOV)",
        "movement_type": "basketball_shooting",
        "camera_perspective": "side",
        "description": "Experimental basketball jump-shot recording (.MOV) for shooting-arm elbow/shoulder kinematics and release posture.",
    },
]
