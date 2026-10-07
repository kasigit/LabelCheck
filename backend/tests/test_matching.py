"""Tests for field matching rules. Each case maps to a row in the `label-rules` skill."""

from __future__ import annotations

import pytest

from app.models import FieldStatus
from app.services.matching import (
    match_alcohol,
    match_net_contents,
    match_text,
    normalize_text,
)


# --- Text normalization + fuzzy text ---------------------------------------------------
def test_normalize_collapses_case_and_quotes():
    assert normalize_text("STONE'S THROW") == normalize_text("Stone’s Throw")


def test_text_exact_after_normalization_is_match():
    # The canonical interview case: caps vs title case -> MATCH.
    status, reason = match_text("Stone's Throw", "STONE'S THROW")
    assert status is FieldStatus.MATCH
    assert "capitaliz" in reason.lower() or "matches" in reason.lower()


def test_text_one_letter_off_is_review():
    status, _ = match_text("Old Tom Distillery", "Old Tom Distillary")
    assert status is FieldStatus.REVIEW


def test_text_clearly_different_is_mismatch():
    status, _ = match_text("Old Tom Distillery", "Acme Spirits Co")
    assert status is FieldStatus.MISMATCH


def test_text_missing_is_not_found():
    status, _ = match_text("Old Tom Distillery", None)
    assert status is FieldStatus.NOT_FOUND


def test_bottler_uses_token_set_for_reordered_address():
    status, _ = match_text(
        "Old Tom Distillery, Louisville, KY",
        "Louisville KY Old Tom Distillery",
        use_token_set=True,
    )
    assert status is FieldStatus.MATCH


# --- Alcohol content -------------------------------------------------------------------
def test_abv_equal_numerically_is_match():
    status, _ = match_alcohol("45%", "45.0% Alc./Vol.")
    assert status is FieldStatus.MATCH


def test_abv_difference_is_mismatch():
    status, _ = match_alcohol("45%", "40% Alc./Vol.")
    assert status is FieldStatus.MISMATCH


def test_proof_inconsistent_with_abv_is_mismatch():
    # 45% should be 90 proof; label claims 80 proof -> inconsistent.
    status, reason = match_alcohol("45%", "45% Alc./Vol. (80 Proof)")
    assert status is FieldStatus.MISMATCH
    assert "proof" in reason.lower()


def test_proof_consistent_is_match():
    status, _ = match_alcohol("45%", "45% Alc./Vol. (90 Proof)")
    assert status is FieldStatus.MATCH


def test_low_confidence_number_is_review():
    status, _ = match_alcohol("45%", "45% Alc./Vol.", found_confidence=0.5)
    assert status is FieldStatus.REVIEW


# --- Net contents ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("expected", "found"),
    [
        ("750 mL", "750ML"),
        ("750 mL", "75 cl"),
        ("1 L", "1000 mL"),
    ],
)
def test_net_contents_equal_after_conversion_is_match(expected, found):
    status, _ = match_net_contents(expected, found)
    assert status is FieldStatus.MATCH


def test_net_contents_fl_oz_within_tolerance_is_match():
    # 25.4 fl oz ~= 751.2 mL, within 1% of 750 mL.
    status, _ = match_net_contents("750 mL", "25.4 fl. oz.")
    assert status is FieldStatus.MATCH


def test_net_contents_different_is_mismatch():
    status, _ = match_net_contents("750 mL", "500 mL")
    assert status is FieldStatus.MISMATCH


def test_net_contents_missing_is_not_found():
    status, _ = match_net_contents("750 mL", None)
    assert status is FieldStatus.NOT_FOUND
