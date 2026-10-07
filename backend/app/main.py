"""FastAPI application entrypoint.

Responsibilities:
  - Load the OCR model exactly once at startup (FastAPI lifespan), never per request.
  - Run a periodic background sweep that expires old batch jobs.
  - Mount the API under /api and (in production) serve the built React app.

No outbound network calls happen here or anywhere at runtime.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import batch as batch_api
from app.api import health as health_api
from app.api import verify as verify_api
from app.config import get_settings
from app.services.batch import store as batch_store
from app.services.ocr import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("labelcheck")


async def _ttl_sweeper() -> None:
    """Periodically drop expired batch jobs from the in-memory store."""
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        batch_store.sweep_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the OCR engine once so the first real request isn't slow (cold start).
    logger.info("Loading OCR model…")
    await asyncio.get_running_loop().run_in_executor(None, get_engine)
    logger.info("OCR model loaded.")

    sweeper = asyncio.create_task(_ttl_sweeper())
    try:
        yield
    finally:
        sweeper.cancel()


app = FastAPI(
    title="LabelCheck API",
    version="0.1.0",
    summary="AI-assisted TTB alcohol-label verification (prototype).",
    lifespan=lifespan,
)

# CORS is only needed in dev, where Vite (http://localhost:5173) calls the API directly.
# In production the API and the static frontend share an origin, so this is harmless.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes under /api.
app.include_router(health_api.router, prefix="/api", tags=["health"])
app.include_router(verify_api.router, prefix="/api", tags=["verify"])
app.include_router(batch_api.router, prefix="/api", tags=["batch"])

# Serve the built React app when a static directory is configured (production/Docker).
# Mounted last so it doesn't shadow /api. html=True serves index.html for client routes.
_static_dir = get_settings().static_dir
if _static_dir and Path(_static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
    logger.info("Serving frontend from %s", _static_dir)
