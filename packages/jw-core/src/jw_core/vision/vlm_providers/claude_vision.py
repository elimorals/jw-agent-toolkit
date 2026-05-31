"""ClaudeVisionProvider — adapter over the anthropic SDK.

Important: Claude (Haiku 4.5 / Sonnet 4.6 / Opus 4.7) is natively multimodal.
This file does NOT define a new model; it wraps `client.messages.create(...)`
with content=[{"type":"image", ...}, {"type":"text", ...}]. The model is
selected by the JW_CLAUDE_VISION_MODEL env var (default claude-haiku-4-5).
"""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    CostHint,
    StructuredPage,
    Target,
    parse_structured_page_json,
)

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5"


def _read_image(image: Path | bytes) -> tuple[str, bytes]:
    """Return (media_type, raw_bytes) for the input."""

    if isinstance(image, bytes):
        return ("image/png", image)
    path = Path(image)
    media_type, _ = mimetypes.guess_type(path.name)
    return (media_type or "image/png", path.read_bytes())


@dataclass
class ClaudeVisionProvider:
    """Adapter; the heavy lifting lives in the anthropic SDK.

    Args:
        client: optional pre-constructed anthropic.Anthropic() — useful for tests.
        model:  override JW_CLAUDE_VISION_MODEL / default.
        max_tokens: caps the response.
    """

    client: Any | None = None
    model: str | None = None
    max_tokens: int = 2048
    name: str = field(default="claude_vision", init=False)
    target: Target = field(default="api", init=False)

    def _resolved_model(self) -> str:
        return self.model or os.environ.get("JW_CLAUDE_VISION_MODEL") or DEFAULT_CLAUDE_MODEL

    def is_available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        if self.client is not None:
            return True
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        # Haiku ~1.5 cents per page typical. Coarse.
        return CostHint(cents_estimate=1.5, latency_ms_estimate=3000, network=True)

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        import anthropic  # lazy

        return anthropic.Anthropic()

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage:
        if not self.is_available():
            raise RuntimeError(
                "ClaudeVisionProvider unavailable: set ANTHROPIC_API_KEY and pip install anthropic."
            )

        media_type, raw = _read_image(image)
        encoded = base64.standard_b64encode(raw).decode("ascii")
        text_prompt = (prompt or DEFAULT_VLM_PROMPT) + f"\n\nTarget language hint: {language}\n"

        client = self._client()
        response = client.messages.create(
            model=self._resolved_model(),
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": text_prompt},
                    ],
                }
            ],
        )

        text_parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        raw_text = "\n".join(text_parts).strip() or "[no text]"
        blocks, lang = parse_structured_page_json(raw_text)

        return StructuredPage(
            blocks=blocks,
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=lang or language,
        )
