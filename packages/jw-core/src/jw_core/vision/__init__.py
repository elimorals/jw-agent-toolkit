"""Visual / multimodal subsystem (Module 7).

Three pieces:

  - `ocr.py`   — OCR via pytesseract (optional). When unavailable, raises
                 `OCRError` with install instructions.
  - `maps.py`  — Catalog of Biblical journeys + simple lookup helpers.
  - `slides.py`— Markdown / Marp slide generator from an outline.
"""

from jw_core.vision.maps import (
    BIBLICAL_JOURNEYS,
    BiblicalJourney,
    BiblicalLocation,
    get_journey,
    list_journeys,
    locations_near,
)
from jw_core.vision.ocr import (
    OCRError,
    extract_bible_reference_from_image,
    ocr_image,
)
from jw_core.vision.slides import (
    SlideDeck,
    build_marp_deck,
    build_simple_deck,
)

__all__ = [
    "BIBLICAL_JOURNEYS",
    "BiblicalJourney",
    "BiblicalLocation",
    "OCRError",
    "SlideDeck",
    "build_marp_deck",
    "build_simple_deck",
    "extract_bible_reference_from_image",
    "get_journey",
    "list_journeys",
    "locations_near",
    "ocr_image",
]
