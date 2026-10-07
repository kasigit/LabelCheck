"""Tests for the Government Warning checks (wording, capitals, and block location)."""

from __future__ import annotations

from app.models import FieldStatus
from app.services.ocr import OcrLine
from app.services.warning import (
    GOVERNMENT_WARNING,
    check_capitals,
    check_warning,
    check_wording,
    find_warning_lines,
)


def _lines(*texts: str, conf: float = 0.95) -> list[OcrLine]:
    """Build OCR lines with simple stacked boxes so height ordering is sane."""
    out = []
    for i, text in enumerate(texts):
        y = i * 20
        box = [[0, y], [100, y], [100, y + 15], [0, y + 15]]
        out.append(OcrLine(text=text, confidence=conf, box=box))
    return out


# --- Wording ---------------------------------------------------------------------------
def test_wording_exact_is_match():
    assert check_wording(GOVERNMENT_WARNING).status is FieldStatus.MATCH


def test_wording_reworded_is_mismatch():
    reworded = GOVERNMENT_WARNING.replace("impairs your ability", "reduces your ability")
    assert check_wording(reworded).status is FieldStatus.MISMATCH


# --- Capitals --------------------------------------------------------------------------
def test_capitals_all_caps_is_match():
    assert check_capitals(GOVERNMENT_WARNING).status is FieldStatus.MATCH


def test_capitals_title_case_is_mismatch():
    # Real rejection cited in interviews: "Government Warning:".
    title = GOVERNMENT_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
    assert check_capitals(title).status is FieldStatus.MISMATCH


def test_capitals_missing_colon_is_mismatch():
    no_colon = GOVERNMENT_WARNING.replace("GOVERNMENT WARNING:", "GOVERNMENT WARNING")
    assert check_capitals(no_colon).status is FieldStatus.MISMATCH


# --- Block location + overall ----------------------------------------------------------
def test_find_warning_lines_locates_block():
    lines = _lines("OLD TOM DISTILLERY", GOVERNMENT_WARNING)
    found = find_warning_lines(lines)
    assert found and "government warning" in found[0].text.casefold()


def test_missing_warning_is_not_found():
    result = check_warning(_lines("OLD TOM DISTILLERY", "750 mL"))
    assert result.found is False
    assert result.overall is FieldStatus.NOT_FOUND


def test_present_warning_without_image_reviews_bold_only():
    # Wording + capitals pass; bold can't be measured without an image -> REVIEW overall.
    result = check_warning(_lines("OLD TOM DISTILLERY", GOVERNMENT_WARNING))
    assert result.found is True
    assert result.wording.status is FieldStatus.MATCH
    assert result.capitals.status is FieldStatus.MATCH
    assert result.bold.status is FieldStatus.REVIEW
