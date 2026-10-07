"""Performance test: every sample label must verify well within the 5-second budget.

We assert both the end-to-end request time (< 5 s) and the server-measured total
(< 4 s) so there's headroom on slower hosting. The model is warmed once by the
session-scoped client fixture, so cold start isn't counted.
"""

from __future__ import annotations

import io
import json
import time

import pytest

from .conftest import SAMPLES_DIR, ocr_available, requires_ocr, requires_samples, samples_available

if ocr_available and samples_available:
    with (SAMPLES_DIR / "expected.json").open(encoding="utf-8") as _fh:
        _IMAGES = sorted(json.load(_fh).keys())
else:
    _IMAGES = []


def _application_json(filename: str) -> str:
    import csv

    with (SAMPLES_DIR / "applications.csv").open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["image_filename"] == filename:
                row.pop("image_filename")
                return json.dumps({k: v for k, v in row.items() if v})
    raise AssertionError(f"No application row for {filename}")


@requires_ocr
@requires_samples
@pytest.mark.parametrize("filename", _IMAGES)
def test_single_label_under_budget(warm_client, filename):
    image_bytes = (SAMPLES_DIR / "labels" / filename).read_bytes()
    start = time.perf_counter()
    resp = warm_client.post(
        "/api/verify",
        files={"image": (filename, io.BytesIO(image_bytes), "image/png")},
        data={"application": _application_json(filename)},
    )
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    assert elapsed < 5.0, f"{filename} took {elapsed:.2f}s (budget 5s)"
    assert resp.json()["timings_ms"]["total"] < 4000
