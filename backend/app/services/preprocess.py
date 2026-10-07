"""Image preprocessing with OpenCV.

Goal: give the OCR engine a clean, upright, well-contrasted image without spending more
than a few hundred milliseconds. We deliberately keep the *color* original around too,
because the Government Warning bold check measures stroke width on the real pixels.
"""

from __future__ import annotations

import cv2
import numpy as np


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode raw image bytes into a BGR numpy array, or None if it isn't an image."""
    buffer = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image


def resize_long_edge(image: np.ndarray, max_edge: int) -> np.ndarray:
    """Downscale so the longest edge is at most `max_edge` px. Never upscales."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return image
    scale = max_edge / longest
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _estimate_skew_angle(gray: np.ndarray) -> float:
    """Estimate a small skew angle (degrees) from the dominant text-line orientation.

    Uses the minimum-area rectangle of the thresholded foreground. Returns 0 if the
    estimate is unreliable or large (we only correct gentle tilt from handheld photos).
    """
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return 0.0
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    # minAreaRect angles wrap; normalize to [-45, 45].
    if angle < -45:
        angle += 90
    if angle > 45:
        angle -= 90
    return angle if abs(angle) <= 20 else 0.0


def _deskew(image: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Rotate the image to remove a small estimated skew."""
    angle = _estimate_skew_angle(gray)
    if abs(angle) < 0.5:  # not worth rotating
        return image
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess(image: np.ndarray, max_edge: int) -> tuple[np.ndarray, np.ndarray]:
    """Prepare an image for OCR.

    Returns (ocr_image, color_image):
      - ocr_image: resized, deskewed, CLAHE-enhanced BGR image fed to the OCR engine.
      - color_image: resized + deskewed color image kept for the bold stroke-width check.

    CLAHE (adaptive histogram equalization) is applied on the L channel, which lifts
    local contrast and tames glare/soft lighting without blowing out the whole image.
    """
    resized = resize_long_edge(image, max_edge)

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    deskewed = _deskew(resized, gray)

    # CLAHE on the lightness channel for glare/contrast.
    lab = cv2.cvtColor(deskewed, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lightness = clahe.apply(lightness)
    enhanced = cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)

    return enhanced, deskewed
