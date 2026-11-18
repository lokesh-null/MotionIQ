FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgles2 \
    libegl1 \
    libglx0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.docker.txt /app/backend/requirements.docker.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.docker.txt

COPY backend /app/backend
COPY sample_videos /app/sample_videos

WORKDIR /app/backend

RUN python -c "import cv2, mediapipe as mp; from mediapipe.tasks import python as mp_tasks; from mediapipe.tasks.python import vision; opts = vision.PoseLandmarkerOptions(base_options=mp_tasks.BaseOptions(model_asset_buffer=open('models/pose_landmarker_lite.task', 'rb').read())); lm = vision.PoseLandmarker.create_from_options(opts); lm.close(); print('Docker MediaPipe PoseLandmarker OK')"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
