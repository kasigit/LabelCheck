"""Single-label verification endpoint.

Accepts a multipart POST: an image file plus the application data as a JSON string. OCR is
CPU-bound, so the pipeline runs in a thread pool (run_in_executor) to keep the event loop
free. Uploads are read into memory and never written to disk.
"""

from __future__ import annotations

import json
import logging
from asyncio import get_running_loop

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.config import get_settings
from app.models import ApplicationData, VerificationResult
from app.services.pipeline import verify

logger = logging.getLogger("labelcheck.verify")
router = APIRouter()

_IMAGE_CONTENT_PREFIX = "image/"


@router.post("/verify", response_model=VerificationResult)
async def verify_label(
    image: UploadFile = File(..., description="The label image (JPG/PNG)."),
    application: str = Form(..., description="Application data as a JSON object."),
) -> VerificationResult:
    # --- Validate the upload -----------------------------------------------------------
    if not (image.content_type or "").startswith(_IMAGE_CONTENT_PREFIX):
        raise HTTPException(
            status_code=415,
            detail="This file isn't an image. Upload a JPG or PNG.",
        )

    try:
        app_data = ApplicationData(**json.loads(application))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="The application data wasn't valid JSON."
        ) from None
    except ValidationError as exc:
        # Surface the first problem in plain words; never dump a stack trace.
        first = exc.errors()[0]
        field = first["loc"][0] if first["loc"] else "application"
        raise HTTPException(
            status_code=422, detail=f"Problem with '{field}': {first['msg']}."
        ) from None

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image was empty.")

    # --- Run the (sync, CPU-bound) pipeline off the event loop -------------------------
    loop = get_running_loop()
    result = await loop.run_in_executor(None, verify, image_bytes, app_data)

    # Performance budget logging (no image contents or full field values at INFO).
    total = result.timings_ms.get("total", 0)
    if total > get_settings().slow_label_ms:
        logger.warning("Slow label: %d ms (budget %d).", total, get_settings().slow_label_ms)

    return result
