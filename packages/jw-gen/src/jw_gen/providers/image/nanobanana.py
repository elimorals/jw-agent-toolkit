"""NanoBanana (Gemini image generation) provider — thin adapter.

Loaded only when explicitly selected. Real calls require GEMINI_API_KEY.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class NanoBananaProvider:
    name = "nanobanana"
    kind = "image"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("GEMINI_API_KEY"):
            return False
        # Honor sys.modules sentinel (None) used in tests to simulate ImportError.
        if sys.modules.get("google.genai", "missing") is None:
            return False
        try:
            importlib.import_module("google.genai")
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.04, time_s=8.0, notes="Gemini image — rough estimate")

    def generate(self, request: GenerationRequest) -> Path:
        from google import genai  # type: ignore[import-not-found]

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=request.prompt,
            number_of_images=1,
        )
        digest = abs(hash(request.prompt)) & 0xFFFFFF
        out = self.work_dir / f"nanobanana_{digest:06x}.png"
        out.write_bytes(response.generated_images[0].image.image_bytes)
        return out
