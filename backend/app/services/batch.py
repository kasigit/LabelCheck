"""Batch verification: validate a CSV + ZIP up front, then process in a worker pool.

Design choices driven by the backend skill and non-negotiables:
  - Validate EVERYTHING before starting (CSV columns, per-row required fields, image<->row
    correspondence, file types) and return every problem at once.
  - Process in a ProcessPoolExecutor sized to CPU count; stream each result into the job
    as it finishes so the UI can show progress and partial results.
  - Job store is an in-memory dict keyed by UUID with a 1-hour TTL, cleaned by a
    background task. No database, no disk persistence of uploads.
  - Guard against zip-slip (paths with '..' or absolute) and zip bombs (cap total
    uncompressed size).
"""

from __future__ import annotations

import csv
import io
import threading
import time
import uuid
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from pydantic import ValidationError

from app.config import get_settings
from app.models import (
    ApplicationRow,
    BatchItemResult,
    BatchStatus,
    BatchStatusResponse,
    FieldStatus,
)
from app.services.pipeline import verify

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
_EXPECTED_CSV_COLUMNS = {
    "image_filename",
    "beverage_type",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "country_of_origin",
}


# ======================================================================================
# Validation
# ======================================================================================
def parse_csv(csv_bytes: bytes) -> tuple[list[ApplicationRow], list[str]]:
    """Parse the applications CSV into rows, collecting human-readable problems.

    Returns (valid_rows, problems). A row with a validation error is skipped and reported;
    we still return the rows that parsed so the caller can see totals.
    """
    problems: list[str] = []
    text = csv_bytes.decode("utf-8-sig")  # tolerate a BOM from Excel exports
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        return [], ["The CSV file is empty."]

    missing = _EXPECTED_CSV_COLUMNS - set(reader.fieldnames)
    if missing:
        problems.append(f"The CSV is missing these columns: {', '.join(sorted(missing))}.")
        return [], problems

    rows: list[ApplicationRow] = []
    for i, raw in enumerate(reader, start=2):  # row 1 is the header
        try:
            rows.append(ApplicationRow(**{k: raw.get(k) for k in _EXPECTED_CSV_COLUMNS}))
        except ValidationError as exc:
            for err in exc.errors():
                loc = err["loc"][0] if err["loc"] else "row"
                problems.append(f"Row {i}: {loc} is invalid ({err['msg']}).")
    return rows, problems


def read_zip_images(zip_bytes: bytes) -> tuple[dict[str, bytes], list[str]]:
    """Safely read images from the uploaded ZIP into {filename: bytes}.

    Applies zip-slip and zip-bomb guards and skips non-image entries. Returns
    (images_by_basename, problems).
    """
    settings = get_settings()
    problems: list[str] = []
    images: dict[str, bytes] = {}

    if len(zip_bytes) > settings.batch_max_zip_bytes:
        return {}, [f"The ZIP is larger than {settings.batch_max_zip_bytes // (1024 * 1024)} MB."]

    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {}, ["That file isn't a valid ZIP archive."]

    total_uncompressed = 0
    for info in archive.infolist():
        name = info.filename
        if info.is_dir():
            continue
        # Zip-slip guard: reject absolute paths and any '..' traversal.
        if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
            problems.append(f"Skipped unsafe path in ZIP: '{name}'.")
            continue

        base = name.replace("\\", "/").split("/")[-1]
        ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
        if ext not in _IMAGE_EXTENSIONS:
            continue  # ignore readme/CSV/etc. silently

        total_uncompressed += info.file_size
        if total_uncompressed > settings.batch_max_uncompressed_bytes:
            return {}, ["The ZIP expands to too much data (possible zip bomb)."]
        if info.file_size > settings.batch_max_image_bytes:
            problems.append(f"'{base}' is larger than the per-image limit; skipped.")
            continue

        images[base] = archive.read(info)

    if len(images) > settings.batch_max_images:
        return {}, [f"The ZIP has more than {settings.batch_max_images} images."]

    return images, problems


def validate_batch(
    rows: list[ApplicationRow],
    images: dict[str, bytes],
) -> tuple[list[tuple[ApplicationRow, bytes]], list[str]]:
    """Cross-check rows against images; return (processable_pairs, problems)."""
    problems: list[str] = []
    pairs: list[tuple[ApplicationRow, bytes]] = []

    referenced = {r.image_filename for r in rows}
    for row in rows:
        if row.image_filename not in images:
            problems.append(f"Row for '{row.image_filename}': no matching image in the ZIP.")
            continue
        pairs.append((row, images[row.image_filename]))

    for name in images:
        if name not in referenced:
            problems.append(f"Image '{name}' has no row in the CSV.")

    return pairs, problems


# ======================================================================================
# In-memory job store with TTL
# ======================================================================================
class _Job:
    """Mutable server-side state for one batch run (never serialized to disk)."""

    def __init__(self, batch_id: str, pairs: list[tuple[ApplicationRow, bytes]]):
        self.batch_id = batch_id
        self.pairs = pairs
        self.total = len(pairs)
        self.status = BatchStatus.QUEUED
        self.results: list[BatchItemResult] = []
        self.created_at = time.monotonic()
        self.lock = threading.Lock()


class BatchStore:
    """Thread-safe registry of batch jobs with a background TTL sweep."""

    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    # --- lifecycle ---------------------------------------------------------------------
    def create(self, pairs: list[tuple[ApplicationRow, bytes]]) -> _Job:
        job = _Job(uuid.uuid4().hex, pairs)
        with self._lock:
            self._jobs[job.batch_id] = job
        return job

    def get(self, batch_id: str) -> _Job | None:
        with self._lock:
            return self._jobs.get(batch_id)

    def sweep_expired(self) -> None:
        """Drop jobs older than the configured TTL (called periodically)."""
        ttl = get_settings().batch_ttl_seconds
        now = time.monotonic()
        with self._lock:
            expired = [bid for bid, job in self._jobs.items() if now - job.created_at > ttl]
            for bid in expired:
                del self._jobs[bid]

    # --- processing --------------------------------------------------------------------
    def start(self, job: _Job) -> None:
        """Kick off processing in a background thread so the request returns immediately."""
        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()

    def _run(self, job: _Job) -> None:
        """Process all pairs in a process pool, streaming results into the job."""
        settings = get_settings()
        workers = settings.batch_workers or None  # None => ProcessPoolExecutor picks CPU count
        job.status = BatchStatus.RUNNING
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_verify_pair, row.model_dump(), img): row.image_filename
                    for row, img in job.pairs
                }
                for future in as_completed(futures):
                    filename = futures[future]
                    item = _collect(future, filename)
                    with job.lock:
                        job.results.append(item)
            job.status = BatchStatus.DONE
        except Exception as exc:  # noqa: BLE001 - surface any pool failure as job failure
            job.status = BatchStatus.FAILED
            with job.lock:
                job.results.append(
                    BatchItemResult(
                        image_filename="(batch)",
                        overall=FieldStatus.MISMATCH,
                        error=f"The batch failed to process: {exc}",
                    )
                )

    def snapshot(self, job: _Job) -> BatchStatusResponse:
        """A consistent read of the job for the status endpoint."""
        with job.lock:
            results = list(job.results)
        return BatchStatusResponse(
            batch_id=job.batch_id,
            status=job.status,
            done=len(results),
            total=job.total,
            results=results,
        )


def _collect(future, filename: str) -> BatchItemResult:
    """Turn a finished future into a BatchItemResult, capturing per-item errors."""
    try:
        result = future.result()
        return BatchItemResult(image_filename=filename, overall=result.overall, result=result)
    except Exception as exc:  # noqa: BLE001 - one bad label must not sink the batch
        return BatchItemResult(
            image_filename=filename,
            overall=FieldStatus.MISMATCH,
            error=f"Couldn't process this label: {exc}",
        )


def _verify_pair(row_dict: dict, image_bytes: bytes):
    """Top-level worker function (must be importable for ProcessPoolExecutor pickling)."""
    row = ApplicationRow(**row_dict)
    # ApplicationRow extends ApplicationData, so it is accepted by verify() directly.
    return verify(image_bytes, row)


# Module-level singleton store, shared by the API layer.
store = BatchStore()
