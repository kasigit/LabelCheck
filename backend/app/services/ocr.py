"""RapidOCR wrapper: image -> text lines with bounding boxes and confidence.

RapidOCR runs PaddleOCR models on ONNX Runtime, on CPU, fully offline (the models are
bundled in the pip wheel). The engine is expensive to construct, so it is loaded exactly
once at startup via `get_engine()` and reused for every request.

We keep the bounding boxes, not just the text: the Government Warning bold check and the
"where on the label" reasoning both need pixel geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np


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


@lru_cache
def get_engine():  # pragma: no cover - thin wrapper around a third-party constructor
    """Construct the RapidOCR engine once and cache it.

    Imported lazily so that unit tests for the pure matching/warning logic don't need the
    heavy OCR dependency installed.
    """
    from rapidocr_onnxruntime import RapidOCR

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
