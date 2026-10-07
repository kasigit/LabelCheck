"""Government Health Warning check (strict).

Three independent sub-checks, each with its own status:
  1. Wording  — word-for-word against the 27 CFR Part 16 statement.
  2. Capitals — the prefix must be exactly "GOVERNMENT WARNING:" in all caps.
  3. Bold     — the prefix must be visually bolder than the body text.

The wording/capitals checks are pure text functions (easy to test). The bold check needs
the original image and the OCR boxes, so it is split out and only runs in the full
pipeline; `check_warning_text` covers the text-only parts.

Reference text — verify against ttb.gov before release and keep it here as the single
source of truth. (Recorded as an assumption in docs/ASSUMPTIONS.md.)
"""

from __future__ import annotations

import re

import cv2
import numpy as np
from rapidfuzz import fuzz

from app.models import FieldStatus, WarningResult, WarningSubCheck
from app.services.ocr import OcrLine

# The canonical statement (27 CFR Part 16). One constant, used everywhere.
GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# The prefix that must be in all caps and bold.
PREFIX = "GOVERNMENT WARNING:"

# Thresholds for the sub-checks.
TOKEN_MATCH_RATIO = 80  # a found word within this fuzzy ratio of an expected word "matches"
MAX_MISSING_FRACTION = 0.45  # tolerate this fraction of expected words missing (OCR drops)
BOLD_MATCH_RATIO = 1.25  # prefix/body stroke-width ratio >= this -> bold
BOLD_REVIEW_RATIO = 1.05  # between review and match ratios -> REVIEW
SMALL_TEXT_FRACTION = 0.40  # warning < 40% of median line height -> "very small" note
MIN_MEASURABLE_TEXT_PX = 12  # boxes smaller than this can't be measured reliably


def _collapse_ws(text: str) -> str:
    """Collapse all runs of whitespace (incl. line breaks) to single spaces, and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    """Lowercase word tokens with surrounding punctuation stripped (keeps digits)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w]


def find_warning_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """Return the OCR lines making up the warning block, in reading order.

    Locate the line containing "GOVERNMENT WARNING" (case-insensitive), then take every
    line at or below it (the warning sits at the bottom of a label) and sort by vertical
    then horizontal position. Sorting matters: OCR engines don't guarantee top-to-bottom
    output order, and joining lines out of order would corrupt the word-for-word check.
    """
    # Space-insensitive match: some OCR engines render the all-caps prefix with no space
    # ("GOVERNMENTWARNING:"), so we compare with whitespace removed.
    prefix_line = next(
        (ln for ln in lines if "governmentwarning" in re.sub(r"\s", "", ln.text.casefold())),
        None,
    )
    if prefix_line is None:
        return []
    # A small tolerance so a prefix on the same visual line isn't excluded by rounding.
    cutoff = prefix_line.top - 5
    block = [ln for ln in lines if ln.top >= cutoff]
    return sorted(block, key=lambda ln: (ln.top, ln.box[0][0] if ln.box else 0))


def check_wording(found_text: str, min_confidence: float = 1.0) -> WarningSubCheck:
    """Check the warning wording against the canonical statement, robustly.

    Why not a literal word-for-word diff? OCR routinely drops or garbles whole lines, even
    on clean images, so an exact comparison would reject correct warnings constantly. We
    instead compare at the word level, in two directions:

      - Words the label HAS that don't appear in the standard ("foreign" words) indicate a
        genuinely reworded warning, e.g. "impairs" -> "reduces" — that's a MISMATCH.
        (If the warning was read with low OCR confidence, a foreign word is more likely an
        OCR error than real rewording, so we downgrade to REVIEW.)
      - Words the standard has that the label is MISSING are tolerated up to a point: they
        usually mean OCR dropped a line, not that the label is wrong. Too many missing
        (we couldn't read most of it) -> REVIEW rather than a confident MATCH.

    First an exact check short-circuits to a clean MATCH when the text is perfect.
    """
    # Re-insert the space some OCR engines drop in the glued all-caps prefix, so
    # "GOVERNMENTWARNING" tokenizes as two words. Case is preserved (the capitals check
    # relies on it); only a space is added.
    found_text = re.sub(r"(?i)(government)\s*(warning)", r"\1 \2", found_text)

    if _collapse_ws(found_text) == _collapse_ws(GOVERNMENT_WARNING):
        return WarningSubCheck(status=FieldStatus.MATCH, reason="Wording matches exactly.")

    expected_words = _words(GOVERNMENT_WARNING)
    found_words = _words(found_text)
    if not found_words:
        return WarningSubCheck(status=FieldStatus.NOT_FOUND, reason="No warning wording was read.")

    def matches_any(word: str, pool: list[str]) -> bool:
        return any(fuzz.ratio(word, p) >= TOKEN_MATCH_RATIO for p in pool)

    foreign = [w for w in found_words if not matches_any(w, expected_words)]
    matched_expected = sum(1 for e in expected_words if matches_any(e, found_words))
    missing_fraction = 1 - matched_expected / len(expected_words)

    if foreign:
        word = foreign[0]
        if min_confidence < 0.80:
            return WarningSubCheck(
                status=FieldStatus.REVIEW,
                reason=f"Wording may differ (read '{word}') — image quality is low, check by eye.",
            )
        return WarningSubCheck(
            status=FieldStatus.MISMATCH,
            reason=f"Wording differs from the standard warning (found '{word}').",
        )

    if missing_fraction <= MAX_MISSING_FRACTION:
        return WarningSubCheck(
            status=FieldStatus.MATCH, reason="Wording matches the standard warning."
        )
    return WarningSubCheck(
        status=FieldStatus.REVIEW,
        reason="Only part of the warning could be read — check the wording by eye.",
    )


def check_capitals(found_text: str) -> WarningSubCheck:
    """The prefix must be exactly 'GOVERNMENT WARNING:' in all caps, with the colon."""
    collapsed = _collapse_ws(found_text)

    # Case-insensitive locate the prefix region (up to and including the first colon).
    # \s* (not \s+) so a glued "GOVERNMENTWARNING:" from some OCR engines still matches.
    m = re.match(r"\s*government\s*warning\s*:?", collapsed, re.IGNORECASE)
    if not m:
        return WarningSubCheck(
            status=FieldStatus.MISMATCH,
            reason="Couldn't find the 'GOVERNMENT WARNING:' prefix.",
        )
    actual_prefix = m.group(0).strip()

    if not actual_prefix.endswith(":"):
        return WarningSubCheck(
            status=FieldStatus.MISMATCH,
            reason="The 'GOVERNMENT WARNING' prefix is missing its colon.",
        )
    if actual_prefix.replace(" ", "") != PREFIX.replace(" ", ""):
        return WarningSubCheck(
            status=FieldStatus.MISMATCH,
            reason=f"Prefix must be all capitals; label shows '{actual_prefix}'.",
        )
    return WarningSubCheck(status=FieldStatus.MATCH, reason="Prefix is in all capitals.")


def _median_stroke_width(image: np.ndarray, box: list[list[float]]) -> float | None:
    """Estimate stroke width inside `box` via a distance transform of the binarized crop.

    Bold text has thicker strokes, so the median distance-to-background inside the glyphs
    is larger. Returns None when the crop is too small/empty to measure.
    """
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0, x1 = int(min(xs)), int(max(xs))
    y0, y1 = int(min(ys)), int(max(ys))
    if (x1 - x0) < 2 or (y1 - y0) < MIN_MEASURABLE_TEXT_PX:
        return None

    crop = image[max(y0, 0) : y1, max(x0, 0) : x1]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    # Otsu threshold; text is dark on light, so invert so glyphs are foreground (255).
    _th, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
    stroke_pixels = dist[dist > 0]
    if stroke_pixels.size == 0:
        return None
    # Stroke half-width ~ median of the distance transform over glyph pixels; x2 for width.
    return float(np.median(stroke_pixels)) * 2.0


def check_bold(
    image: np.ndarray,
    warning_lines: list[OcrLine],
) -> WarningSubCheck:
    """Compare the stroke width of the prefix against the body text of the warning."""
    if not warning_lines:
        return WarningSubCheck(status=FieldStatus.NOT_FOUND, reason="No warning to measure.")

    prefix_line = warning_lines[0]
    body_lines = warning_lines[1:] or warning_lines

    prefix_sw = _median_stroke_width(image, prefix_line.box)
    body_sws = [sw for ln in body_lines if (sw := _median_stroke_width(image, ln.box))]
    if prefix_sw is None or not body_sws:
        return WarningSubCheck(
            status=FieldStatus.REVIEW,
            reason="Text is too small to measure boldness reliably — check by eye.",
        )

    ratio = prefix_sw / (float(np.median(body_sws)) or 1e-9)
    if ratio >= BOLD_MATCH_RATIO:
        return WarningSubCheck(status=FieldStatus.MATCH, reason="Prefix appears bold.")
    if ratio >= BOLD_REVIEW_RATIO:
        return WarningSubCheck(
            status=FieldStatus.REVIEW,
            reason="Prefix may not be clearly bold — check by eye.",
        )
    return WarningSubCheck(
        status=FieldStatus.MISMATCH,
        reason="'GOVERNMENT WARNING:' doesn't appear to be bold.",
    )


def _worst(*statuses: FieldStatus) -> FieldStatus:
    """Worst-status-wins over the warning sub-checks."""
    order = {
        FieldStatus.MISMATCH: 4,
        FieldStatus.NOT_FOUND: 3,
        FieldStatus.REVIEW: 2,
        FieldStatus.MATCH: 1,
        FieldStatus.NOT_REQUIRED: 0,
    }
    return max(statuses, key=lambda s: order[s])


def check_warning(
    lines: list[OcrLine],
    image: np.ndarray | None = None,
) -> WarningResult:
    """Run all three sub-checks and assemble a WarningResult.

    `image` is optional: when omitted (pure text tests), the bold check is reported as
    REVIEW ("couldn't measure") rather than failing.
    """
    warning_lines = find_warning_lines(lines)

    if not warning_lines:
        nf = WarningSubCheck(
            status=FieldStatus.NOT_FOUND, reason="No Government Warning found on the label."
        )
        return WarningResult(
            found=False,
            overall=FieldStatus.NOT_FOUND,
            wording=nf,
            capitals=nf,
            bold=nf,
            found_text=None,
        )

    found_text = " ".join(ln.text for ln in warning_lines)
    min_conf = min((ln.confidence for ln in warning_lines), default=1.0)

    wording = check_wording(found_text, min_conf)
    capitals = check_capitals(found_text)
    if image is not None:
        bold = check_bold(image, warning_lines)
    else:
        bold = WarningSubCheck(status=FieldStatus.REVIEW, reason="Boldness not measured.")

    # Non-blocking "very small text" note.
    note = None
    other_heights = [ln.height for ln in lines if ln not in warning_lines and ln.height > 0]
    if other_heights:
        median_other = float(np.median(other_heights))
        warning_heights = [ln.height for ln in warning_lines if ln.height > 0] or [0]
        warning_height = float(np.median(warning_heights))
        if median_other > 0 and warning_height < SMALL_TEXT_FRACTION * median_other:
            note = "Warning text is very small compared with the rest of the label."

    overall = _worst(wording.status, capitals.status, bold.status)
    return WarningResult(
        found=True,
        overall=overall,
        wording=wording,
        capitals=capitals,
        bold=bold,
        found_text=found_text,
        note=note,
    )
