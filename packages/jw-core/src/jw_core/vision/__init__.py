"""Visual / multimodal subsystem (Module 7).

Four pieces:

  - `ocr.py`   — Legacy OCR via pytesseract (deprecated; use `vlm` instead).
  - `vlm.py`   — VLM-based structured page extraction (Fase 36).
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
    migrate_to_vlm,
    ocr_image,
)
from jw_core.vision.slides import (
    SlideDeck,
    build_marp_deck,
    build_simple_deck,
)
from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    CostHint,
    StructuredBlock,
    StructuredPage,
    VLMProvider,
    extract_bible_reference_from_image_v2,
    parse_structured_page_json,
)
from jw_core.vision.vlm_providers import (
    JW_VLM_PROVIDER_ENV,
    FakeVLMProvider,
    build_provider,
    get_default_provider,
)

__all__ = [
    "BIBLICAL_JOURNEYS",
    "BiblicalJourney",
    "BiblicalLocation",
    "CostHint",
    "DEFAULT_VLM_PROMPT",
    "FakeVLMProvider",
    "JW_VLM_PROVIDER_ENV",
    "OCRError",
    "SlideDeck",
    "StructuredBlock",
    "StructuredPage",
    "VLMProvider",
    "build_marp_deck",
    "build_provider",
    "build_simple_deck",
    "extract_bible_reference_from_image",
    "extract_bible_reference_from_image_v2",
    "get_default_provider",
    "get_journey",
    "list_journeys",
    "locations_near",
    "migrate_to_vlm",
    "ocr_image",
    "parse_structured_page_json",
]
