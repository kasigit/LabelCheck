"""Extract candidate field values from OCR lines.

The key idea from the `backend` skill: we do NOT try to parse a label from scratch.
Instead we use the *expected* value from the application to search the OCR output. For a
free-text field (brand, class/type, bottler, country) we find the OCR line that best
matches the expected text. For numeric fields (ABV, net contents) we scan all lines for
the first value that parses, since those have distinctive patterns.

Each extractor returns (found_text, confidence) or (None, 0.0) if nothing plausible is
present. Matching.py then decides match/review/mismatch.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.services.matching import normalize_text, parse_alcohol, parse_net_contents
from app.services.ocr import OcrLine

# Below this best-match score we consider the field simply "not found" on the label.
FOUND_SCORE_FLOOR = 55


def _best_line_for_text(expected: str, lines: list[OcrLine]) -> tuple[str | None, float]:
    """Find the OCR line (or adjacent pair) best matching `expected`.

    Returns (found_text, ocr_confidence). Tries single lines first, then adjacent pairs
    (brand names and addresses often wrap across two lines).
    """
    norm_expected = normalize_text(expected)
    if not norm_expected:
        return None, 0.0

    best_text: str | None = None
    best_conf = 0.0
    best_score = 0.0

    exp_nospace = norm_expected.replace(" ", "")

    # WRatio balances token overlap against length, so a short line that is merely a
    # *subset* of the expected value (e.g. the brand line when we're looking for the full
    # bottler address) doesn't tie with the line that actually contains the whole value.
    # We also score with spaces removed, so an all-caps line the OCR glued together
    # ("OLDTOMDISTILLARY") still matches its spaced expected value.
    def score_of(candidate: str) -> float:
        norm_cand = normalize_text(candidate)
        return max(
            fuzz.WRatio(norm_expected, norm_cand),
            fuzz.WRatio(exp_nospace, norm_cand.replace(" ", "")),
        )

    # Single lines.
    for line in lines:
        score = score_of(line.text)
        if score > best_score:
            best_score, best_text, best_conf = score, line.text, line.confidence

    # Adjacent pairs (handles values wrapped across two lines).
    for a, b in zip(lines, lines[1:], strict=False):
        combined = f"{a.text} {b.text}"
        score = score_of(combined)
        if score > best_score:
            best_score = score
            best_text = combined
            best_conf = min(a.confidence, b.confidence)

    if best_score < FOUND_SCORE_FLOOR:
        return None, 0.0
    return best_text, best_conf


def extract_text_field(expected: str, lines: list[OcrLine]) -> tuple[str | None, float]:
    """Candidate value for a free-text field, guided by the expected value."""
    return _best_line_for_text(expected, lines)


def extract_alcohol(lines: list[OcrLine]) -> tuple[str | None, float]:
    """First line that contains a parseable alcohol percentage."""
    for line in lines:
        abv, _proof = parse_alcohol(line.text)
        if abv is not None:
            return line.text, line.confidence
    return None, 0.0


def extract_net_contents(lines: list[OcrLine]) -> tuple[str | None, float]:
    """First line that contains a parseable volume."""
    for line in lines:
        if parse_net_contents(line.text) is not None:
            return line.text, line.confidence
    return None, 0.0
