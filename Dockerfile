# Single-container build: compile the React app, then serve it from FastAPI alongside the
# API. The OCR models are baked into the image via pip (rapidocr-onnxruntime bundles them),
# so the running container makes NO outbound network calls — it works behind a firewall.

# ---- Stage 1: build the frontend -----------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # -> /app/frontend/dist

# ---- Stage 2: Python runtime ---------------------------------------------------------
FROM python:3.12-slim AS runtime

# OpenCV needs a couple of shared libs even in headless mode.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LABELCHECK_STATIC_DIR=/app/static

# Install backend dependencies first (better layer caching).
COPY backend/pyproject.toml ./backend/
RUN pip install --no-cache-dir ./backend

# Backend source and the built frontend.
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./static

WORKDIR /app/backend
EXPOSE 8000

# One worker: the OCR model and the in-memory batch store are per-process; scale out with
# more containers rather than more workers so a batch's results stay in one place.
# Bind to $PORT when the platform supplies one (e.g. Railway), else default to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
