"""TesseractFallbackProvider — wraps the legacy ocr_image() in a VLMProvider.

Always emits a DeprecationWarning on use. Returns a single `paragraph` block
containing the raw OCR text (no structure). The factory will pick this as
the last-resort entry in DEFAULT_CHAIN when nothing else is available.
"""

from __future__ import annotations

import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from jw_core.vision.ocr import ocr_image
from jw_core.vision.vlm import (
    CostHint,
    StructuredBlock,
    StructuredPage,
    Target,
)

_LANG_HINT = {"en": "eng", "es": "spa", "pt": "por"}


def _probe() -> bool:
    """Import pytesseract; return True on success. Raises on missing module."""

    import pytesseract  # noqa: F401

    return True


@dataclass
class TesseractFallbackProvider:
    name: str = field(default="tesseract_fallback", init=False)
    target: Target = field(default="cpu", init=False)

    def is_available(self) -> bool:
        try:
            return _probe()
        except Exception:  # noqa: BLE001
            return False

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.0, latency_ms_estimate=500, network=False)

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,  # noqa: ARG002
        *,
        language: str = "en",
    ) -> StructuredPage:
        warnings.warn(
            "Using Tesseract fallback for OCR. Install mlx-vlm, set "
            "ANTHROPIC_API_KEY, or configure JW_VLM_PROVIDER to get structured output.",
            DeprecationWarning,
            stacklevel=2,
        )
        lang_code = _LANG_HINT.get(language, "eng+spa+por")
        if isinstance(image, bytes):
            f = tempfile.NamedTemporaryFile(prefix="jwvlm-", suffix=".png", delete=False)
            f.write(image)
            f.close()
            path: Path | str = f.name
        else:
            path = image
        raw_text = ocr_image(path, language=lang_code)
        return StructuredPage(
            blocks=[
                StructuredBlock(
                    kind="paragraph",
                    text=raw_text or "[empty OCR]",
                    lang_hint=language,
                )
            ],
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=language,
        )
