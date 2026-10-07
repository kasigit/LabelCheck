"""Shared test fixtures and capability checks.

The pure-logic tests (matching, warning, parsing) always run. The pipeline/sample/
performance tests need the heavy OCR dependency and the generated sample set, so they are
skipped cleanly when those aren't present — keeping `pytest` green on a minimal install
while still exercising everything in CI (where OCR and samples are available).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Repo layout: backend/tests/ -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "samples"
EXPECTED_JSON = SAMPLES_DIR / "expected.json"

ocr_available = importlib.util.find_spec("rapidocr_onnxruntime") is not None
samples_available = EXPECTED_JSON.exists()

requires_ocr = pytest.mark.skipif(not ocr_available, reason="rapidocr-onnxruntime not installed")
requires_samples = pytest.mark.skipif(not samples_available, reason="sample set not generated")


@pytest.fixture(scope="session")
def expected_map() -> dict:
    """The samples/expected.json mapping, or an empty dict if absent."""
    if not samples_available:
        return {}
    with EXPECTED_JSON.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def warm_client():
    """A FastAPI TestClient with the OCR model warmed once (so cold start isn't timed)."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:  # lifespan warms the model
        yield client
