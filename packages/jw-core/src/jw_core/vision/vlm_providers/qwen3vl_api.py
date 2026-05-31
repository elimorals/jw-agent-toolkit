"""Qwen3VLAPIProvider — vendor-agnostic JSON-over-HTTPS client for Qwen3-VL.

Configured by env:
  JW_QWEN3VL_API_KEY        required
  JW_QWEN3VL_API_BASE       required (e.g. https://dashscope.aliyuncs.com)
  JW_QWEN3VL_API_MODEL      optional (default: qwen3-vl-plus)
  JW_QWEN3VL_API_PATH       optional, defaults to
                            /api/v1/services/aigc/multimodal-generation/generation
"""

from __future__ import annotations

import base64
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    CostHint,
    StructuredPage,
    Target,
    parse_structured_page_json,
)

DEFAULT_MODEL = "qwen3-vl-plus"
DEFAULT_PATH = "/api/v1/services/aigc/multimodal-generation/generation"


def _data_url(image: Path | bytes) -> str:
    if isinstance(image, bytes):
        media_type, raw = "image/png", image
    else:
        media_type, _ = mimetypes.guess_type(Path(image).name)
        raw = Path(image).read_bytes()
        media_type = media_type or "image/png"
    return f"data:{media_type};base64,{base64.standard_b64encode(raw).decode('ascii')}"


@dataclass
class Qwen3VLAPIProvider:
    client: httpx.Client | None = None
    timeout: float = 60.0
    name: str = field(default="qwen3vl_api", init=False)
    target: Target = field(default="api", init=False)

    def _key(self) -> str | None:
        return os.environ.get("JW_QWEN3VL_API_KEY")

    def _base(self) -> str | None:
        return os.environ.get("JW_QWEN3VL_API_BASE")

    def is_available(self) -> bool:
        return bool(self._key() and self._base())

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.5, latency_ms_estimate=4000, network=True)

    def _http(self) -> httpx.Client:
        return self.client or httpx.Client(timeout=self.timeout)

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage:
        if not self.is_available():
            raise RuntimeError(
                "Qwen3VLAPIProvider unavailable: set JW_QWEN3VL_API_KEY and JW_QWEN3VL_API_BASE."
            )
        path = os.environ.get("JW_QWEN3VL_API_PATH", DEFAULT_PATH)
        model = os.environ.get("JW_QWEN3VL_API_MODEL", DEFAULT_MODEL)
        prompt_text = (prompt or DEFAULT_VLM_PROMPT) + f"\nLanguage hint: {language}\n"

        body: dict[str, Any] = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": _data_url(image)},
                            {"text": prompt_text},
                        ],
                    }
                ]
            },
            "parameters": {"result_format": "message"},
        }
        url = f"{self._base()}{path}"
        http = self._http()
        try:
            r = http.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {self._key()}"},
            )
            r.raise_for_status()
            data = r.json()
        finally:
            if self.client is None:
                http.close()

        # DashScope shape: output.choices[0].message.content -> [{"text": "..."}]
        raw_text = ""
        try:
            content = data["output"]["choices"][0]["message"]["content"]
            if isinstance(content, list):
                raw_text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
            elif isinstance(content, str):
                raw_text = content
        except Exception:  # noqa: BLE001
            raw_text = str(data)

        blocks, lang = parse_structured_page_json(raw_text)
        return StructuredPage(
            blocks=blocks,
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=lang or language,
        )
