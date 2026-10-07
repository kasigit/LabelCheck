"""Golden-sample tests: run the full pipeline over real images in samples/.

Parametrized over samples/expected.json. Image-quality cases (photographed at an angle or
with glare) accept MATCH *or* REVIEW; everything else must match exactly. When a sample
fails, decide whether the rule or the expectation is wrong — don't loosen expected.json
just to go green.

Skipped automatically when OCR or the sample set isn't available (see conftest.py).
"""

from __future__ import annotations

import json

import pytest

from app.models import ApplicationData, FieldStatus
from app.services.pipeline import verify

from .conftest import SAMPLES_DIR, ocr_available, requires_ocr, requires_samples, samples_available

# Build the parameter list at import time so each image is its own test case.
if ocr_available and samples_available:
    with (SAMPLES_DIR / "expected.json").open(encoding="utf-8") as _fh:
        _EXPECTED = json.load(_fh)
    _CASES = sorted(_EXPECTED.keys())
else:
    _EXPECTED = {}
    _CASES = []

# Cases where soft image quality means MATCH or REVIEW are both acceptable overall.
# (blurry.png is deliberately unreadable and must assert NOT_FOUND, so it's not lenient.)
_LENIENT = {"angle.png", "glare.png"}


def _load_application(filename: str) -> ApplicationData:
    import csv

    with (SAMPLES_DIR / "applications.csv").open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["image_filename"] == filename:
                row.pop("image_filename")
                return ApplicationData(**row)
    raise AssertionError(f"No application row for {filename}")


@requires_ocr
@requires_samples
@pytest.mark.parametrize("filename", _CASES)
def test_sample(filename, expected_map):
    image_bytes = (SAMPLES_DIR / "labels" / filename).read_bytes()
    result = verify(image_bytes, _load_application(filename))
    expected = expected_map[filename]

    # Overall status.
    if filename in _LENIENT:
        assert result.overall in {FieldStatus.MATCH, FieldStatus.REVIEW}
    else:
        assert result.overall.value == expected["overall"], result.model_dump()

    # Per-field statuses listed in expected.json.
    by_field = {fr.field: fr.status.value for fr in result.fields}
    by_field["warning"] = result.warning.overall.value
    for field, want in expected.get("fields", {}).items():
        if filename in _LENIENT:
            continue  # don't pin individual fields on soft-quality images
        assert by_field.get(field) == want, f"{filename}:{field} -> {by_field.get(field)}"
