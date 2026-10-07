"""RapidOCR wrapper: image -> text lines with bounding boxes and confidence.

RapidOCR runs PaddleOCR models on ONNX Runtime, on CPU, fully offline (the models are
bundled in the pip wheel). The engine is expensive to construct, so it is loaded exactly
once at startup via `get_engine()` and reused for every request.

We keep the bounding boxes, not just the text: the Government Warning bold check and the
"where on the label" reasoning both need pixel geometry.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

logger = logging.getLogger("labelcheck.ocr")


@dataclass
class OcrLine:
    """One recognized line of text with its geometry and confidence.

    box is the 4-point polygon RapidOCR returns, as [[x, y], ...] in pixel coordinates.
    """

    text: str
    confidence: float
    box: list[list[float]] = field(default_factory=list)

    @property
    def top(self) -> float:
        return min(p[1] for p in self.box) if self.box else 0.0

    @property
    def bottom(self) -> float:
        return max(p[1] for p in self.box) if self.box else 0.0

    @property
    def height(self) -> float:
        """Approximate text height in pixels."""
        return self.bottom - self.top


def _cgroup_cpu_quota() -> int | None:
    """Return the container's CPU quota (whole vCPUs), or None if unconstrained/unknown.

    Reads the Linux cgroup limits rather than os.cpu_count(), which reports the *host's*
    cores and badly overcounts inside a throttled container (the root cause of slow OCR on
    small cloud instances). Supports cgroup v2 (cpu.max) and v1 (cpu.cfs_quota_us).
    """
    # cgroup v2
    try:
        quota_s, period_s = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota_s != "max":
            return max(1, round(int(quota_s) / int(period_s)))
    except (OSError, ValueError):
        pass
    # cgroup v1
    try:
        quota = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        period = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if quota > 0:
            return max(1, round(quota / period))
    except (OSError, ValueError):
        pass
    return None


def _ocr_thread_count() -> int:
    """How many threads the OCR engine should use.

    Honors LABELCHECK_OCR_THREADS when set; otherwise uses the container's CPU quota,
    falling back to the host core count. Always at least 1.
    """
    from app.config import get_settings

    configured = get_settings().ocr_threads
    if configured > 0:
        return configured
    quota = _cgroup_cpu_quota()
    host = os.cpu_count() or 1
    return max(1, min(quota or host, host))


@lru_cache
def get_engine():  # pragma: no cover - thin wrapper around a third-party constructor
    """Construct the RapidOCR engine once and cache it.

    The thread pool is sized to the container's real CPU allocation (see
    `_ocr_thread_count`), which keeps ONNX Runtime from oversubscribing CPU on small
    instances. Imported lazily so the pure matching/warning tests don't need the heavy
    OCR dependency installed.
    """
    from rapidocr_onnxruntime import RapidOCR

    threads = _ocr_thread_count()
    logger.info("Initializing OCR engine with intra_op_num_threads=%d", threads)
    try:
        return RapidOCR(intra_op_num_threads=threads, inter_op_num_threads=1)
    except TypeError:
        # Older/newer RapidOCR that doesn't accept these kwargs — fall back to defaults.
        logger.warning("RapidOCR didn't accept thread kwargs; using defaults.")
        return RapidOCR()


def is_engine_loaded() -> bool:
    """True if the OCR engine has already been constructed (used by /api/health)."""
    return get_engine.cache_info().currsize > 0


def run_ocr(image: np.ndarray) -> list[OcrLine]:
    """Run OCR on a preprocessed image and return recognized lines.

    This is CPU-bound; callers must run it off the event loop (run_in_executor) so the
    server stays responsive. See services/pipeline.py and api/verify.py.
    """
    engine = get_engine()
    raw, _elapse = engine(image)
    if not raw:
        return []
    # RapidOCR returns a list of [box, text, confidence].
    return [
        OcrLine(text=text, confidence=float(conf), box=[[float(x), float(y)] for x, y in box])
        for box, text, conf in raw
    ]
