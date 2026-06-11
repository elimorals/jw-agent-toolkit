"""End-to-end engine for book-camera (Fase 71).

Takes either a captured image path (runs Tesseract via F70 ocr_image)
OR a pre-extracted OCR text, classifies it, and emits a
`CameraFrameResult` with suggested actions ready for the UI.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from jw_core.book_camera.classifier import classify_content
from jw_core.book_camera.models import CameraFrameResult
from jw_core.book_camera.router import suggested_actions_for

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _run_ocr(image_path: str, language: str) -> tuple[str, float]:
    """Run F70 OCR pipeline on `image_path`. Returns (text, confidence).

    Confidence is heuristic: 0.85 if Tesseract returned non-empty text,
    0.0 otherwise. A real provider can override this in the future.
    """
    from jw_core.verification.image_quote.ocr_cleanup import (
        OCRUnavailableError,
        cleanup_ocr_text,
        ocr_image,
    )
    from jw_core.verification.image_quote.preprocess import load_image

    pil_image, _meta = load_image(image_path)
    try:
        raw = ocr_image(pil_image, language=language)
    except OCRUnavailableError:
        raise
    cleaned = cleanup_ocr_text(raw)
    conf = 0.85 if cleaned else 0.0
    return (cleaned, conf)


def analyze_capture(
    *,
    image_path: str | None = None,
    ocr_text: str | None = None,
    language: str = "es",
    ocr_confidence: float | None = None,
) -> CameraFrameResult:
    """Run the book-camera pipeline.

    Either `image_path` (will run OCR) or `ocr_text` (skip OCR) must be
    provided. If both are passed, `ocr_text` wins.
    """

    if ocr_text is None and image_path is None:
        raise ValueError(
            "analyze_capture requires either image_path or ocr_text"
        )

    if ocr_text is None:
        assert image_path is not None  # for mypy
        text, conf = _run_ocr(image_path, language)
    else:
        text = ocr_text
        conf = ocr_confidence if ocr_confidence is not None else 0.95

    detected = classify_content(text)
    actions = suggested_actions_for(detected, language=language)
    return CameraFrameResult(
        captured_at=_now_iso(),
        ocr_text=text,
        ocr_confidence=conf,
        detected=detected,
        suggested_actions=actions,
    )
