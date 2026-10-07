"""Liveness endpoint, including whether the OCR model is loaded."""

from __future__ import annotations

from fastapi import APIRouter

from app.models import HealthResponse
from app.services.ocr import is_engine_loaded

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ocr_model_loaded=is_engine_loaded())
