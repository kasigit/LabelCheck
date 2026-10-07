"""Domain rule data + a tiny loader for beverage_rules.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

Requirement = Literal["required", "optional", "imports"]

_RULES_PATH = Path(__file__).with_name("beverage_rules.yaml")


@lru_cache
def _load() -> dict:
    with _RULES_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def field_order() -> list[str]:
    """Field names in the order they should appear in results (YAML order)."""
    return list(_load()["fields"].keys())


def field_label(field: str) -> str:
    """Human-friendly label for a field, e.g. 'Brand name'."""
    return _load()["fields"][field]["label"]


def requirement_for(field: str, beverage: str) -> Requirement:
    """How `field` is required for `beverage` ('required' | 'optional' | 'imports')."""
    return _load()["fields"][field][beverage]
