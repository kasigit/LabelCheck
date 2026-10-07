"""The verification pipeline: raw image bytes + application -> VerificationResult.

Stages (per the backend skill):
    preprocess.py -> ocr.py -> extract.py -> matching.py + warning.py

This module is the single orchestrator. It is synchronous and CPU-bound by design; the
API layer runs it in a thread/process pool so it never blocks the event loop, and the
batch worker calls it directly inside worker processes.
"""

from __future__ import annotations

import time

from app.config import get_settings
from app.models import (
    ApplicationData,
    FieldResult,
    FieldStatus,
    VerificationResult,
    WarningResult,
    WarningSubCheck,
)
from app.rules import field_label, field_order, requirement_for
from app.services import extract, matching
from app.services.preprocess import decode_image, preprocess
from app.services.warning import check_warning

# Severity order for "worst status wins" across the whole result.
_SEVERITY = {
    FieldStatus.MISMATCH: 4,
    FieldStatus.NOT_FOUND: 3,
    FieldStatus.REVIEW: 2,
    FieldStatus.MATCH: 1,
    FieldStatus.NOT_REQUIRED: 0,
}


def worst_status(statuses: list[FieldStatus]) -> FieldStatus:
    """Return the most severe status. NOT_REQUIRED never wins; empty -> MATCH."""
    candidates = [s for s in statuses if s is not FieldStatus.NOT_REQUIRED]
    if not candidates:
        return FieldStatus.MATCH
    return max(candidates, key=lambda s: _SEVERITY[s])


def _check_field(
    field: str,
    application: ApplicationData,
    lines: list,
) -> FieldResult:
    """Compare one application field against the label, honoring the beverage rules."""
    beverage = application.beverage_type.value
    requirement = requirement_for(field, beverage)
    expected = getattr(application, field)
    label = field_label(field)

    # If the application didn't provide a value, it is NOT_REQUIRED for optional/imports
    # fields. A blank *required* field is a data-entry problem, surfaced as REVIEW.
    if not expected:
        if requirement == "required":
            return FieldResult(
                field=field,
                label=label,
                expected=None,
                found=None,
                status=FieldStatus.REVIEW,
                reason="The application didn't include this required field.",
                confidence=1.0,
            )
        return FieldResult(
            field=field,
            label=label,
            expected=None,
            found=None,
            status=FieldStatus.NOT_REQUIRED,
            reason="Not provided in the application for this beverage type.",
            confidence=1.0,
        )

    # Route to the right comparator and extractor per field.
    if field == "alcohol_content":
        found, conf = extract.extract_alcohol(lines)
        status, reason = matching.match_alcohol(expected, found, found_confidence=conf)
    elif field == "net_contents":
        found, conf = extract.extract_net_contents(lines)
        status, reason = matching.match_net_contents(expected, found)
    else:
        found, conf = extract.extract_text_field(expected, lines)
        # Bottler addresses are split/reordered across lines, and country is usually
        # prefixed on the label ("Product of France" vs application "France"). token_set
        # handles both because it compares on the set of words, ignoring extras/order.
        use_token_set = field in {"bottler_name_address", "country_of_origin"}
        status, reason = matching.match_text(expected, found, use_token_set=use_token_set)

    return FieldResult(
        field=field,
        label=label,
        expected=expected,
        found=found,
        status=status,
        reason=reason,
        confidence=round(conf, 3),
    )


def _unreadable_result(elapsed_ms: int) -> VerificationResult:
    """Build a clear 'couldn't read the label' result instead of guessing."""
    nf = WarningSubCheck(status=FieldStatus.NOT_FOUND, reason="Couldn't read the label.")
    return VerificationResult(
        overall=FieldStatus.NOT_FOUND,
        fields=[],
        warning=WarningResult(
            found=False,
            overall=FieldStatus.NOT_FOUND,
            wording=nf,
            capitals=nf,
            bold=nf,
        ),
        timings_ms={"total": elapsed_ms},
        image_readable=False,
        message="We couldn't read this image clearly. Try a straight, well-lit photo of the label.",
    )


def verify(image_bytes: bytes, application: ApplicationData) -> VerificationResult:
    """Run the full verification pipeline on one label."""
    settings = get_settings()
    t0 = time.perf_counter()

    image = decode_image(image_bytes)
    if image is None:
        return _unreadable_result(int((time.perf_counter() - t0) * 1000))

    # --- Preprocess --------------------------------------------------------------------
    t_pre = time.perf_counter()
    ocr_image, color_image = preprocess(image, settings.max_image_edge_px)
    pre_ms = int((time.perf_counter() - t_pre) * 1000)

    # --- OCR ---------------------------------------------------------------------------
    # Imported lazily so pure-logic tests don't require the OCR dependency.
    from app.services.ocr import run_ocr

    t_ocr = time.perf_counter()
    lines = run_ocr(ocr_image)
    ocr_ms = int((time.perf_counter() - t_ocr) * 1000)

    # Nothing legible at all -> clear unreadable message.
    if not lines:
        return _unreadable_result(int((time.perf_counter() - t0) * 1000))

    # --- Match + warning ---------------------------------------------------------------
    t_match = time.perf_counter()
    field_results = [_check_field(field, application, lines) for field in field_order()]
    warning = check_warning(lines, color_image)
    match_ms = int((time.perf_counter() - t_match) * 1000)

    total_ms = int((time.perf_counter() - t0) * 1000)

    overall = worst_status([fr.status for fr in field_results] + [warning.overall])

    return VerificationResult(
        overall=overall,
        fields=field_results,
        warning=warning,
        timings_ms={
            "preprocess": pre_ms,
            "ocr": ocr_ms,
            "match": match_ms,
            "total": total_ms,
        },
        image_readable=True,
    )
