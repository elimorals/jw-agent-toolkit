"""OCR adapter — relies on `pytesseract` if available.

Use case (VISION.md): "OCR sobre fotos de la Biblia física o de páginas de
publicaciones — útil cuando alguien comparte una foto y quieres saber qué
dice".

We keep this **optional**: if `pytesseract` isn't installed, calling
`ocr_image` raises `OCRError` with install hints. The reference parser
runs purely on the resulting text, so it always works once OCR is set up.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRError(RuntimeError):
    pass


def ocr_image(
    image_path: str | Path,
    *,
    language: str = "eng",
) -> str:
    """Run OCR on an image and return the extracted text.

    Args:
        image_path: PNG/JPG/BMP path.
        language: tesseract language code ('eng', 'spa', 'por'). Multiple
            languages can be combined: 'eng+spa'.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise OCRError(
            "OCR requires `pytesseract` and `Pillow`. Install via:\n"
            "  pip install pytesseract Pillow\n"
            "And install tesseract on your OS (brew install tesseract on macOS)."
        ) from e
    try:
        image = Image.open(image_path)
    except Exception as e:
        raise OCRError(f"Could not open image {image_path!r}: {e}") from e
    try:
        text = pytesseract.image_to_string(image, lang=language)
    except Exception as e:
        raise OCRError(f"Tesseract OCR failed: {e}") from e
    return text


_OCR_LANG_HINT = {"en": "eng", "es": "spa", "pt": "por"}


def extract_bible_reference_from_image(
    image_path: str | Path,
    *,
    language: str = "en",
) -> dict[str, object]:
    """OCR an image and try to parse the first Bible reference in it.

    Returns a dict with `text` (full OCR) and `reference` (None or a
    parsed `BibleRef.model_dump()`).
    """
    from jw_core.parsers.reference import parse_reference

    lang_code = _OCR_LANG_HINT.get(language, "eng+spa+por")
    text = ocr_image(image_path, language=lang_code)
    ref = parse_reference(text)
    return {
        "text": text,
        "reference": ref.model_dump() if ref else None,
        "language_hint": language,
    }


def normalize_ocr_text(text: str) -> str:
    """Cosmetic cleanup useful before feeding OCR output to other parsers."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────
# Fase 36 — migration helpers + deprecation wrapper for the legacy path.
# ocr_image() itself stays untouched (other modules import it). Wrapping
# `extract_bible_reference_from_image` is enough to flag callers.
# ─────────────────────────────────────────────────────────────────────────

import warnings as _warnings  # noqa: E402


def migrate_to_vlm():
    """Return a callable replacement for ocr_image() that uses the VLM factory.

    Usage:
        ocr_image = migrate_to_vlm()
        text = ocr_image(path, language="es")

    The returned callable preserves the (path, language=) signature for drop-in
    swaps but uses the configured VLM provider underneath.
    """

    from jw_core.vision.vlm_providers import get_default_provider

    def _impl(image_path, *, language: str = "en") -> str:
        provider = get_default_provider()
        if provider is None:  # pragma: no cover - safety net
            raise RuntimeError("no VLM provider available; install one and retry")
        page = provider.extract_structured(image_path, language=language)
        return page.raw_text_fallback

    return _impl


def _deprecate(msg: str) -> None:
    _warnings.warn(msg, DeprecationWarning, stacklevel=3)


# Wrap extract_bible_reference_from_image to emit a warning. To avoid editing
# the original definition above and risking subtle bugs in tests, we override
# the symbol exported from this module.
_orig_extract = extract_bible_reference_from_image  # type: ignore[assignment]


def extract_bible_reference_from_image(  # type: ignore[no-redef]
    image_path,
    *,
    language: str = "en",
) -> dict[str, object]:
    _deprecate(
        "extract_bible_reference_from_image() is deprecated; use "
        "jw_core.vision.vlm.extract_bible_reference_from_image_v2() with a VLM provider."
    )
    return _orig_extract(image_path, language=language)
