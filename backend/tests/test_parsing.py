"""Tests for the low-level parsers (ABV, proof, net contents) and CSV row parsing."""

from __future__ import annotations

import pytest

from app.models import ApplicationRow, BeverageType
from app.services.matching import parse_alcohol, parse_net_contents


@pytest.mark.parametrize(
    ("text", "abv", "proof"),
    [
        ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
        ("ALC 45% BY VOL", 45.0, None),
        ("45.0% ABV", 45.0, None),
        ("no alcohol here", None, None),
    ],
)
def test_parse_alcohol(text, abv, proof):
    assert parse_alcohol(text) == (abv, proof)


@pytest.mark.parametrize(
    ("text", "ml"),
    [
        ("750 mL", 750.0),
        ("750ML", 750.0),
        ("75 cl", 750.0),
        ("1 L", 1000.0),
        ("12 FL OZ", pytest.approx(354.88, abs=0.1)),
        ("25.4 fl. oz.", pytest.approx(751.2, abs=0.5)),
        ("no volume", None),
    ],
)
def test_parse_net_contents(text, ml):
    assert parse_net_contents(text) == ml


def test_application_row_blank_optional_becomes_none():
    row = ApplicationRow(
        image_filename="a.png",
        beverage_type="beer",
        brand_name="Acme",
        class_type="Lager",
        alcohol_content="   ",  # blank -> None
        net_contents="355 mL",
        bottler_name_address="Acme, OH",
        country_of_origin="",
    )
    assert row.alcohol_content is None
    assert row.country_of_origin is None
    assert row.beverage_type is BeverageType.BEER
