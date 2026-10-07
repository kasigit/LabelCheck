"""Batch verification endpoints: create, poll status, and export CSV.

POST /api/batch       -> validate the CSV + ZIP up front, queue the job, return problems.
GET  /api/batch/{id}  -> status + partial results while running.
GET  /api/batch/{id}/export.csv -> results so far as a CSV download.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.models import BatchCreateResponse, BatchStatusResponse
from app.services import batch as batch_service

router = APIRouter()


@router.post("/batch", response_model=BatchCreateResponse)
async def create_batch(
    csv_file: UploadFile = File(..., alias="csv", description="applications.csv"),
    images: UploadFile = File(..., description="ZIP of label images"),
) -> BatchCreateResponse:
    # Read both uploads into memory (never persisted to disk).
    csv_bytes = await csv_file.read()
    zip_bytes = await images.read()

    rows, csv_problems = batch_service.parse_csv(csv_bytes)
    image_map, zip_problems = batch_service.read_zip_images(zip_bytes)
    pairs, cross_problems = batch_service.validate_batch(rows, image_map)

    problems = csv_problems + zip_problems + cross_problems

    if not pairs:
        # Nothing processable: tell the user everything that's wrong, at once.
        detail = "Nothing could be processed. " + (
            " ".join(problems) if problems else "No valid label/application pairs were found."
        )
        raise HTTPException(status_code=400, detail=detail)

    job = batch_service.store.create(pairs)
    batch_service.store.start(job)
    return BatchCreateResponse(batch_id=job.batch_id, total=job.total, problems=problems)


@router.get("/batch/{batch_id}", response_model=BatchStatusResponse)
def batch_status(batch_id: str) -> BatchStatusResponse:
    job = batch_service.store.get(batch_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="That batch has expired or was never created. Please upload again.",
        )
    return batch_service.store.snapshot(job)


@router.get("/batch/{batch_id}/export.csv")
def export_batch(batch_id: str) -> StreamingResponse:
    job = batch_service.store.get(batch_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That batch has expired. Please upload again.")

    snapshot = batch_service.store.snapshot(job)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["image_filename", "overall", "field", "expected", "found", "status", "reason"])
    for item in snapshot.results:
        if item.result is None:
            writer.writerow(
                [item.image_filename, item.overall.value, "", "", "", "error", item.error or ""]
            )
            continue
        for fr in item.result.fields:
            writer.writerow(
                [
                    item.image_filename,
                    item.overall.value,
                    fr.label,
                    fr.expected or "",
                    fr.found or "",
                    fr.status.value,
                    fr.reason,
                ]
            )
        w = item.result.warning
        writer.writerow(
            [
                item.image_filename,
                item.overall.value,
                "Government Warning",
                "",
                w.found_text or "",
                w.overall.value,
                "",
            ]
        )

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="labelcheck-{batch_id[:8]}.csv"'},
    )
