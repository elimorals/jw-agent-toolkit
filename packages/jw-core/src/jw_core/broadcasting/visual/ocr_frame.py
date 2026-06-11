"""OCR enrichment for broadcasting visual frames (Fase 69 post-MVP).

`enrich_frames_with_ocr(frames, *, language)` mutates each
`VisualFrame.ocr_text` in place by running `jw_core.vision.ocr.ocr_image`
on the frame's `thumb_path`. Frames without a thumb path are left alone.

Reuses the F70 OCR adapter (pytesseract) instead of duplicating it; if
pytesseract isn't installed, the OCRError surfaces with the same install
hint as F70.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from jw_core.broadcasting.visual.models import VisualFrame
from jw_core.vision.ocr import OCRError, normalize_ocr_text, ocr_image

logger = logging.getLogger(__name__)


_LANG_HINT = {"en": "eng", "es": "spa", "pt": "por"}


def _resolve_lang(language: str) -> str:
    return _LANG_HINT.get(language, language)


def ocr_frame_path(
    image_path: str | Path,
    *,
    language: str = "en",
) -> str:
    """Run OCR on a single frame thumbnail and return normalised text."""

    text = ocr_image(image_path, language=_resolve_lang(language))
    return normalize_ocr_text(text)


def enrich_frames_with_ocr(
    frames: Iterable[VisualFrame],
    *,
    language: str = "en",
    overwrite: bool = False,
) -> list[VisualFrame]:
    """Return new `VisualFrame` instances with OCR text populated.

    Args:
        frames: input frames (any iterable, not consumed twice).
        language: target language ("en", "es", "pt", ...).
        overwrite: when False (default), frames that already have a
            non-empty `ocr_text` are returned unchanged. When True,
            OCR is re-run regardless.
    """

    out: list[VisualFrame] = []
    for frame in frames:
        if frame.thumb_path and (overwrite or not frame.ocr_text):
            try:
                text = ocr_frame_path(
                    frame.thumb_path, language=language
                )
            except OCRError:
                raise  # propagate install-hint to caller
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "OCR failed for frame %s @%.1fs: %s",
                    frame.video_id,
                    frame.timestamp_s,
                    exc,
                )
                text = frame.ocr_text
            out.append(frame.model_copy(update={"ocr_text": text}))
        else:
            out.append(frame)
    return out
