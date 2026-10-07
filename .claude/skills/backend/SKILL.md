---
name: backend
description: Conventions for the LabelCheck FastAPI backend — API endpoints, service layout, the 5-second performance budget, OCR and image preprocessing, CSV/ZIP batch handling, and no-storage rules. Use when building or changing anything under backend/.
---

# Backend (Python 3.12 + FastAPI)

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness + whether the OCR model is loaded |
| `POST` | `/api/verify` | Multipart: `image` file + `application` JSON → `VerificationResult` |
| `POST` | `/api/batch` | Multipart: `csv` file + `images` ZIP → `{batch_id, total, problems[]}` |
| `GET` | `/api/batch/{id}` | `{status, done, total, results[]}` (partial results while running) |
| `GET` | `/api/batch/{id}/export.csv` | Results as CSV download |

- Route handlers in `app/api/` are thin: validate, call a service, return a model. No business logic.
- All request/response shapes are Pydantic models in `app/models.py`. They drive the OpenAPI schema that
  the frontend generates types from — keep field names stable and descriptive.
- Errors: raise `HTTPException` with a **user-readable** `detail` ("The ZIP has no images in it."). The frontend
  shows `detail` directly.

## Core result model (shape, not exact code)

```python
class FieldStatus(str, Enum):
    MATCH = "match"
    REVIEW = "review"        # probably fine, agent should glance
    MISMATCH = "mismatch"
    NOT_FOUND = "not_found"  # required field not found on label
    NOT_REQUIRED = "not_required"

class FieldResult(BaseModel):
    field: str
    expected: str | None
    found: str | None
    status: FieldStatus
    reason: str              # one plain-English sentence
    confidence: float        # 0–1

class VerificationResult(BaseModel):
    overall: FieldStatus     # worst status across fields
    fields: list[FieldResult]
    warning: WarningResult   # see label-rules skill
    timings_ms: dict[str, int]   # preprocess, ocr, match, total
```

## Pipeline

`preprocess.py` → `ocr.py` → `extract.py` → `matching.py` + `warning.py`

1. **Preprocess (OpenCV):** resize to max 2000px long edge; convert to grayscale; CLAHE for contrast and glare;
   deskew from text-line angle. Keep the color original for the bold check.
2. **OCR (RapidOCR):** returns text lines with bounding boxes and confidence. Keep boxes — the warning bold
   check and "where on the label" both need them.
3. **Extract:** locate candidate values for each field. Use the expected value from the application to search
   (fuzzy-find the brand name among OCR lines) rather than trying to parse a label from scratch.
4. **Match / warning:** domain rules live in the `label-rules` skill. Load it before touching these files.

## Performance budget (≤ 5 s per label, target ≤ 3 s)

- **Load the OCR model once** at startup (FastAPI `lifespan`), never per request.
- OCR is CPU-bound: run it in a thread/process pool (`run_in_executor`), never directly in an `async def`.
- Record `timings_ms` for every stage in the response and log them. If `total` > 4000 ms, log a warning.
- Don't add a stage that costs > 500 ms without measuring it first.

## Batch processing

- Validate everything **before** starting: CSV columns, required fields per beverage type, every row's
  `image_filename` exists in the ZIP, every image has a row, file types are images. Return all problems at once.
- Process with a `ProcessPoolExecutor` sized to CPU count. Stream results into the job as each label finishes.
- Job store: in-memory dict keyed by UUID, **TTL 1 hour**, cleaned up by a background task. No database, no disk.
- Limits: ZIP ≤ 500 MB, ≤ 500 images, each image ≤ 20 MB. Reject with a clear message above that.
- Guard against zip-slip and zip bombs: ignore paths with `..` or absolute paths; cap total uncompressed size.

### CSV schema (`applications.csv`)

```
image_filename,beverage_type,brand_name,class_type,alcohol_content,net_contents,bottler_name_address,country_of_origin
```

- `beverage_type` ∈ `beer | wine | spirits`.
- Optional columns may be blank depending on `rules/beverage_rules.yaml`.
- Parse with Pydantic (`ApplicationRow`); collect row-level errors as `"Row 14: alcohol_content is missing (required for spirits)."`

## Data handling

- Never write uploads to persistent disk. Use `SpooledTemporaryFile`/in-memory bytes; if a temp file is
  unavoidable, delete it in a `finally`.
- Don't log image contents or full field values at INFO level.
- No outbound HTTP at runtime. The optional cloud vision fallback (if ever added) sits behind
  `LABELCHECK_CLOUD_VISION=false` by default and must fail soft.

## Code style

- Type hints everywhere; Ruff for lint + format.
- Pure functions in `services/` wherever possible (input → output, no globals) so they're easy to unit test.
- Config via environment variables read once in `app/config.py` (pydantic-settings).
