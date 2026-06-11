"""OCR + cleanup pipeline for the quote verifier (Fase 70).

Tesseract is import-guarded. When unavailable, callers must inject the
OCR result manually (or use a different OCR provider via Plugin SDK F41).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class OCRUnavailableError(RuntimeError):
    """Raised when no OCR backend is installed and one was requested."""


def ocr_image(image: Any, *, language: str = "es") -> str:
    """Run Tesseract over a PIL.Image and return the raw text."""

    try:
        import pytesseract  # type: ignore
    except ImportError as exc:
        raise OCRUnavailableError(
            "pytesseract not installed. Install with: "
            "pip install pytesseract && brew install tesseract"
        ) from exc
    lang_map = {"es": "spa", "en": "eng", "pt": "por"}
    lang_tag = lang_map.get(language, "eng")
    try:
        return pytesseract.image_to_string(image, lang=lang_tag)
    except Exception as exc:
        logger.warning("OCR failed (%s); returning empty text.", exc)
        return ""


def cleanup_ocr_text(raw: str) -> str:
    """Common OCR-pollution removal.

    - Collapses repeated whitespace.
    - Removes lone OCR artifacts (single non-alphanumeric chars on a line).
    - Trims leading/trailing whitespace per line.
    - Joins line continuations like `hello-\\n  world` -> `helloworld`.
    """
    if not raw:
        return ""
    # Join hyphenated line breaks: "compa-\nñero" -> "compañero"
    text = re.sub(r"-\s*\n\s*", "", raw)
    # Collapse multiple whitespace runs
    text = re.sub(r"[ \t]+", " ", text)
    # Drop lines that are just punctuation / digits noise (<= 2 non-word chars)
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if len(line) <= 2 and not any(c.isalnum() for c in line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()
