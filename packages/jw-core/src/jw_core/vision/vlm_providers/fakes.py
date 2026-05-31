"""Deterministic in-memory provider used for unit tests.

Behavior:
  - If a file under tests/fixtures/vlm/expected_structured/<stem>.json exists,
    use it as the structured output. This lets tests pin exact behavior to a
    fixture image without ever touching a real model.
  - Otherwise: return a single `paragraph` block whose text is "[fake VLM]".
  - `canned_blocks` allows tests to inject arbitrary output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jw_core.vision.vlm import (
    CostHint,
    StructuredBlock,
    StructuredPage,
    Target,
)

# Resolve the in-repo golden directory relative to this file. Layout:
#   packages/jw-core/src/jw_core/vision/vlm_providers/fakes.py
#   packages/jw-core/tests/fixtures/vlm/expected_structured/
# That means 4 .parent hops + tests/fixtures/...
_GOLDEN_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "tests" / "fixtures" / "vlm" / "expected_structured"
)


@dataclass
class FakeVLMProvider:
    name: str = "fake"
    target: Target = "cpu"
    canned_blocks: list[StructuredBlock] | None = None

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.0, latency_ms_estimate=1, network=False)

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,  # noqa: ARG002
        *,
        language: str = "en",
    ) -> StructuredPage:
        if self.canned_blocks is not None:
            blocks = list(self.canned_blocks)
            return StructuredPage(
                blocks=blocks,
                source_image=str(image) if isinstance(image, Path) else None,
                provider_name=self.name,
                target=self.target,
                raw_text_fallback="\n".join(b.text for b in blocks),
                language_detected=language,
            )

        if isinstance(image, Path):
            golden = _GOLDEN_DIR / f"{image.stem}.json"
            if golden.exists():
                data = json.loads(golden.read_text(encoding="utf-8"))
                blocks = [StructuredBlock.model_validate(b) for b in data.get("blocks", [])]
                return StructuredPage(
                    blocks=blocks,
                    source_image=str(image),
                    provider_name=self.name,
                    target=self.target,
                    raw_text_fallback="\n".join(b.text for b in blocks),
                    language_detected=data.get("language_detected", language),
                )

        return StructuredPage(
            blocks=[StructuredBlock(kind="paragraph", text="[fake VLM]", lang_hint=language)],
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback="[fake VLM]",
            language_detected=language,
        )
