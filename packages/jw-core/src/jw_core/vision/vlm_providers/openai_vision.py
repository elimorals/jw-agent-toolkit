"""OpenAIVisionProvider — adapter over the openai SDK (chat.completions vision)."""

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

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


def _data_url(image: Path | bytes) -> str:
    if isinstance(image, bytes):
        media_type, raw = "image/png", image
    else:
        path = Path(image)
        media_type, _ = mimetypes.guess_type(path.name)
        raw = path.read_bytes()
        media_type = media_type or "image/png"
    encoded = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


@dataclass
class OpenAIVisionProvider:
    client: Any | None = None
    model: str | None = None
    max_tokens: int = 2048
    name: str = field(default="openai_vision", init=False)
    target: Target = field(default="api", init=False)

    def _resolved_model(self) -> str:
        return self.model or os.environ.get("JW_OPENAI_VISION_MODEL") or DEFAULT_OPENAI_MODEL

    def is_available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        if self.client is not None:
            return True
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.8, latency_ms_estimate=2500, network=True)

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        import openai  # lazy

        return openai.OpenAI()

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage:
        if not self.is_available():
            raise RuntimeError("OpenAIVisionProvider unavailable: set OPENAI_API_KEY and pip install openai.")

        text_prompt = (prompt or DEFAULT_VLM_PROMPT) + f"\n\nLanguage hint: {language}\n"
        data_url = _data_url(image)

        client = self._client()
        response = client.chat.completions.create(
            model=self._resolved_model(),
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": text_prompt},
                    ],
                }
            ],
        )
        raw_text = ""
        try:
            raw_text = response.choices[0].message.content or ""
        except Exception:  # noqa: BLE001
            raw_text = "[empty openai response]"
        blocks, lang = parse_structured_page_json(raw_text)
        return StructuredPage(
            blocks=blocks,
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=lang or language,
        )
