"""Core VLM types, prompt template, and Protocol.

Triple-target taxonomy:
  - "api"    — remote service (Claude, OpenAI, Qwen DashScope, ...)
  - "mlx"    — Apple Silicon via mlx-vlm
  - "nvidia" — CUDA via vllm
  - "cpu"    — CPU-only via llama-cpp-python or pure-Python fakes

This module imports NO optional SDK at module level.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

BlockKind = Literal[
    "header",
    "paragraph",
    "citation",
    "footnote",
    "bible_ref",
    "caption",
]

Target = Literal["api", "nvidia", "mlx", "cpu"]


class CostHint(BaseModel):
    """Coarse cost / latency hint a provider can advertise."""

    cents_estimate: float = 0.0
    latency_ms_estimate: int = 0
    network: bool = False


class StructuredBlock(BaseModel):
    """One typed block extracted from a page image."""

    kind: BlockKind
    text: str
    bbox: tuple[float, float, float, float] | None = None
    lang_hint: str = "en"
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("bbox")
    @classmethod
    def _check_bbox(cls, v: tuple[float, float, float, float] | None) -> tuple[float, float, float, float] | None:
        if v is None:
            return v
        for coord in v:
            if not 0.0 <= coord <= 1.0:
                raise ValueError(f"bbox coordinate out of [0,1]: {coord}")
        x1, y1, x2, y2 = v
        if x1 > x2 or y1 > y2:
            raise ValueError(f"bbox not ordered: {v}")
        return v


class StructuredPage(BaseModel):
    """Canonical output of a VLMProvider for one image."""

    blocks: list[StructuredBlock]
    source_image: str | None = None
    provider_name: str
    target: Target
    raw_text_fallback: str
    language_detected: str | None = None

    def text_only(self) -> str:
        """Return concatenated block text (newline-separated)."""

        return "\n".join(b.text for b in self.blocks).strip()


DEFAULT_VLM_PROMPT = """You are an OCR system specialized in JW publications and Bible pages.
Read the image and return STRICT JSON with this schema:

{
  "blocks": [
    {"kind": "header|paragraph|citation|footnote|bible_ref|caption",
     "text": "...",
     "bbox": [x1, y1, x2, y2] | null,
     "lang_hint": "en|es|pt|...",
     "confidence": 0.0..1.0 | null}
  ],
  "language_detected": "en|es|pt|..."
}

Rules:
- bbox coordinates are normalized in [0,1] with origin top-left.
- Output ONLY valid JSON, no markdown fences, no commentary.
- Preserve original spelling and punctuation.
- "bible_ref" applies to inline scripture references (e.g. "John 3:16").
- "citation" applies to footnote-style citations of WT publications.
"""


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def parse_structured_page_json(raw: str) -> tuple[list[StructuredBlock], str | None]:
    """Parse the raw VLM string into (blocks, language_detected).

    Best-effort: strips markdown fences, tolerates trailing prose, and if all
    else fails returns a single `paragraph` block containing the raw text — so
    callers always get something usable.
    """

    candidate = raw.strip()
    m = _JSON_FENCE_RE.match(candidate)
    if m:
        candidate = m.group(1).strip()
    # Try the first {...} balanced span if extra prose surrounds JSON.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start : end + 1]
    try:
        data = json.loads(candidate)
    except Exception:  # noqa: BLE001
        return (
            [StructuredBlock(kind="paragraph", text=raw.strip() or "[empty VLM output]")],
            None,
        )
    if not isinstance(data, dict):
        return ([StructuredBlock(kind="paragraph", text=raw.strip())], None)
    blocks_raw = data.get("blocks") or []
    blocks: list[StructuredBlock] = []
    for item in blocks_raw:
        if not isinstance(item, dict):
            continue
        try:
            blocks.append(StructuredBlock.model_validate(item))
        except Exception:  # noqa: BLE001
            blocks.append(StructuredBlock(kind="paragraph", text=str(item.get("text", ""))))
    if not blocks:
        blocks = [StructuredBlock(kind="paragraph", text=raw.strip() or "[empty]")]
    language = data.get("language_detected") if isinstance(data, dict) else None
    return blocks, (language if isinstance(language, str) else None)


class VLMProvider(Protocol):
    """Contract every VLM backend implements."""

    name: str
    target: Target

    def is_available(self) -> bool: ...

    def cost_estimate(self, image: Path | bytes) -> CostHint: ...

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage: ...


def extract_bible_reference_from_image_v2(
    image_path: Path | str,
    *,
    language: str = "en",
    provider: VLMProvider | None = None,
) -> dict[str, object]:
    """V2 of extract_bible_reference_from_image — VLM-first with fallback.

    Returns:
        {
            "structured_page": StructuredPage,
            "reference": BibleRef.model_dump() | None,
            "text": str,                  # = page.raw_text_fallback (compat)
            "language_hint": str,
        }
    """

    from jw_core.parsers.reference import parse_reference

    if provider is None:
        from jw_core.vision.vlm_providers import get_default_provider

        provider = get_default_provider()

    page = provider.extract_structured(Path(image_path), language=language)

    # Prefer parsing the first bible_ref block; else parse the full text.
    ref = None
    for block in page.blocks:
        if block.kind == "bible_ref":
            parsed = parse_reference(block.text)
            if parsed is not None:
                ref = parsed
                break
    if ref is None:
        ref = parse_reference(page.raw_text_fallback) or parse_reference(page.text_only())

    return {
        "structured_page": page,
        "reference": ref.model_dump() if ref else None,
        "text": page.raw_text_fallback,
        "language_hint": language,
    }
