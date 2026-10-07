"""API contract tests.

The validation-error cases don't need OCR and always run. The happy-path verify is
covered by test_samples.py (which needs OCR + samples).
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

# Importing the app module is cheap; the OCR model is only loaded inside the lifespan,
# which TestClient(app) triggers. For these validation tests we avoid the context manager
# so no model load happens.
from app.main import app

client = TestClient(app)


def test_verify_rejects_non_image():
    resp = client.post(
        "/api/verify",
        files={"image": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"application": '{"beverage_type": "spirits"}'},
    )
    assert resp.status_code == 415
    assert "image" in resp.json()["detail"].lower()


def test_verify_rejects_bad_json():
    resp = client.post(
        "/api/verify",
        files={"image": ("l.png", io.BytesIO(b"\x89PNG"), "image/png")},
        data={"application": "not json"},
    )
    assert resp.status_code == 400


def test_batch_rejects_empty_csv():
    resp = client.post(
        "/api/batch",
        files={
            "csv": ("applications.csv", io.BytesIO(b""), "text/csv"),
            "images": ("images.zip", io.BytesIO(b"not a zip"), "application/zip"),
        },
    )
    assert resp.status_code == 400


def test_batch_status_404_for_unknown_id():
    resp = client.get("/api/batch/does-not-exist")
    assert resp.status_code == 404
