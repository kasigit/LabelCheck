"""Pydantic request/response models and the CSV row schema.

These models are the single source of truth for the API contract. They drive the
OpenAPI schema that the frontend generates its TypeScript types from, so field names
are kept stable and descriptive. Keep business logic out of this module — it only
describes shapes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------------------
# Status enums
# --------------------------------------------------------------------------------------
class FieldStatus(str, Enum):
    """Outcome of comparing one field (or one warning sub-check).

    The ordering here is also the severity order used to compute the overall result:
    MISMATCH is worst, NOT_REQUIRED is ignored. See `worst_status` in services/pipeline.
    """

    MATCH = "match"
    REVIEW = "review"  # probably fine, but the agent should glance at it
    MISMATCH = "mismatch"
    NOT_FOUND = "not_found"  # a required field could not be found on the label
    NOT_REQUIRED = "not_required"  # not required for this beverage type / not provided


class BeverageType(str, Enum):
    BEER = "beer"
    WINE = "wine"
    SPIRITS = "spirits"


# --------------------------------------------------------------------------------------
# Per-field result
# --------------------------------------------------------------------------------------
class FieldResult(BaseModel):
    """Result of checking a single application field against the label."""

    field: str = Field(description="Machine field name, e.g. 'brand_name'.")
    label: str = Field(description="Human-friendly field label, e.g. 'Brand name'.")
    expected: str | None = Field(description="Value from the application (what it should say).")
    found: str | None = Field(description="Value read from the label image, if any.")
    status: FieldStatus
    reason: str = Field(description="One plain-English sentence explaining the status.")
    confidence: float = Field(ge=0.0, le=1.0, description="0–1 confidence in the read/compare.")


# --------------------------------------------------------------------------------------
# Government Warning result (three independent sub-checks)
# --------------------------------------------------------------------------------------
class WarningSubCheck(BaseModel):
    """One of the three Government Warning sub-checks (wording / capitals / bold)."""

    status: FieldStatus
    reason: str


class WarningResult(BaseModel):
    """The strict Government Health Warning check.

    The warning is made of three independent sub-checks so the UI can show each one. An
    `overall` rolls them up with the same worst-status-wins rule used elsewhere.
    """

    found: bool = Field(description="Whether a warning block was located at all.")
    overall: FieldStatus
    wording: WarningSubCheck
    capitals: WarningSubCheck
    bold: WarningSubCheck
    found_text: str | None = Field(
        default=None, description="The warning text read from the label."
    )
    note: str | None = Field(
        default=None,
        description="Non-blocking note, e.g. that the warning text is very small.",
    )


# --------------------------------------------------------------------------------------
# Top-level verification result
# --------------------------------------------------------------------------------------
class VerificationResult(BaseModel):
    """Everything the UI needs to render a single-label result."""

    overall: FieldStatus = Field(description="Worst status across all fields and the warning.")
    fields: list[FieldResult]
    warning: WarningResult
    timings_ms: dict[str, int] = Field(
        description="Per-stage timings: preprocess, ocr, match, total.",
    )
    image_readable: bool = Field(
        default=True,
        description="False when the image could not be read at all (too blurry/dark).",
    )
    message: str | None = Field(
        default=None,
        description="Optional top-level message, e.g. when the image is unreadable.",
    )


# --------------------------------------------------------------------------------------
# Application input (single verify)
# --------------------------------------------------------------------------------------
class ApplicationData(BaseModel):
    """The application values a label is checked against (the 'expected' side).

    All fields except beverage_type are optional strings. A blank/omitted optional field
    means "not provided" and is reported as NOT_REQUIRED rather than failing — this is how
    beer/wine labels without an ABV, or domestic products without a country of origin, are
    handled. See the `label-rules` skill and rules/beverage_rules.yaml.
    """

    beverage_type: BeverageType
    brand_name: str | None = None
    class_type: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    bottler_name_address: str | None = None
    country_of_origin: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        """Treat empty/whitespace-only strings as None so blanks mean 'not provided'."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


# --------------------------------------------------------------------------------------
# Batch models
# --------------------------------------------------------------------------------------
class ApplicationRow(ApplicationData):
    """One row of the uploaded applications CSV.

    Extends ApplicationData with the image filename that ties the row to an image in the
    uploaded ZIP. Parsing a CSV row through this model gives us free validation and
    blank-to-None handling.
    """

    image_filename: str


class BatchStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class BatchItemResult(BaseModel):
    """One label's result within a batch, plus the overall status for quick sorting."""

    image_filename: str
    overall: FieldStatus
    result: VerificationResult | None = None
    error: str | None = None


class BatchCreateResponse(BaseModel):
    """Returned from POST /api/batch after validation."""

    batch_id: str
    total: int = Field(description="Number of valid label/application pairs queued.")
    problems: list[str] = Field(
        default_factory=list,
        description="All validation problems found up front, as plain-English sentences.",
    )


class BatchStatusResponse(BaseModel):
    """Returned from GET /api/batch/{id}; carries partial results while running."""

    batch_id: str
    status: BatchStatus
    done: int
    total: int
    results: list[BatchItemResult]


class HealthResponse(BaseModel):
    status: str = "ok"
    ocr_model_loaded: bool
