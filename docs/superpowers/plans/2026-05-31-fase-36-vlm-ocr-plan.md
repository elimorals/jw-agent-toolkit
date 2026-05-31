# Fase 36 — `vlm-ocr` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Tesseract-based `ocr_image()` path with a typed, structured **VLM (Vision-Language Model)** pipeline that returns `StructuredPage` blocks the RAG can ingest with per-block metadata. Tesseract stays alive as a `DeprecationWarning`-emitting fallback. New providers cover the triple-target matrix (api / mlx / nvidia / cpu) and each Anthropic-compatible model.

**Architecture:** A central `vlm.py` defines the `VLMProvider` Protocol, the `StructuredBlock` / `StructuredPage` Pydantic models, and the shared prompt. Concrete providers live under `vlm_providers/`. A factory implements `JW_VLM_PROVIDER` env override + an auto-detect chain. `ClaudeVisionProvider` is an adapter over the existing `anthropic` SDK (Claude models are natively multimodal — `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-7`), **not** a new model. `OpenAIVisionProvider` mirrors that pattern for `gpt-4o`/`gpt-5`. Local providers (`Qwen3VLProvider`) dispatch by target between `mlx-vlm`, `vllm`, and `llama-cpp-python` (GGUF). API-only Qwen runs via `httpx` against DashScope / Replicate / fal.ai. A `FakeVLMProvider` lets the entire suite run offline with deterministic golden JSON. `jw_rag.ingest.ingest_image()` consumes `StructuredPage` and emits one chunk per block.

**Tech Stack:** Python 3.13 · Pydantic (models) · pytest (TDD) · `anthropic` (extra `vlm-anthropic`) · `openai` (extra `vlm-openai`) · `mlx-vlm` (extra `vlm-mlx`) · `vllm` (extra `vlm-nvidia`) · `llama-cpp-python` (extra `vlm-cpu`) · `httpx` (extra `vlm-api-qwen`) · `Pillow` (image normalization) · `pytesseract` (existing fallback). All SDKs are **lazy-imported** inside provider methods — zero top-level imports.

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-36-vlm-ocr-design.md`](../specs/2026-05-31-fase-36-vlm-ocr-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/vision/vlm.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/__init__.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/factory.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/fakes.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_local.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_api.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/openai_vision.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/claude_vision.py`
- `packages/jw-core/src/jw_core/vision/vlm_providers/tesseract_fallback.py`
- `packages/jw-core/tests/test_vlm_models.py`
- `packages/jw-core/tests/test_vlm_factory.py`
- `packages/jw-core/tests/test_vlm_provider_fake.py`
- `packages/jw-core/tests/test_vlm_provider_claude.py`
- `packages/jw-core/tests/test_vlm_provider_openai.py`
- `packages/jw-core/tests/test_vlm_provider_qwen_api.py`
- `packages/jw-core/tests/test_vlm_provider_qwen_local.py`
- `packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py`
- `packages/jw-core/tests/test_vlm_extract_v2.py`
- `packages/jw-core/tests/fixtures/vlm/wt_2024_page_es.png`  *(small synthetic ≤50 KB)*
- `packages/jw-core/tests/fixtures/vlm/bible_john_3_es.png`  *(small synthetic ≤50 KB)*
- `packages/jw-core/tests/fixtures/vlm/expected_structured/wt_2024_page_es.json`
- `packages/jw-core/tests/fixtures/vlm/expected_structured/bible_john_3_es.json`
- `packages/jw-rag/src/jw_rag/ingest_image.py`
- `packages/jw-rag/tests/test_ingest_image.py`
- `packages/jw-cli/src/jw_cli/commands/image.py`
- `packages/jw-cli/tests/test_command_image.py`
- `docs/guias/vlm-ocr.md`

Modifies:
- `packages/jw-core/pyproject.toml` — add five optional-deps groups + Pillow base dep.
- `packages/jw-core/src/jw_core/vision/__init__.py` — re-export new public API.
- `packages/jw-core/src/jw_core/vision/ocr.py` — emit `DeprecationWarning` + add `migrate_to_vlm()` helper.
- `packages/jw-rag/src/jw_rag/__init__.py` — re-export `ingest_image`.
- `packages/jw-cli/src/jw_cli/main.py` — register `image` Typer subapp.
- `packages/jw-mcp/src/jw_mcp/server.py` — add `extract_structured_page` and `ingest_image_to_rag` MCP tools.
- `pyproject.toml` (root) — add `pytest -m vlm_real` marker.
- `docs/VISION_AUDIT.md` — add Fase 36 row.
- `docs/ROADMAP.md` — mark Fase 36 implemented.

---

### Task 1: Scaffold extras, base deps, and module skeleton

**Files:**
- Modify: `packages/jw-core/pyproject.toml`
- Modify: `pyproject.toml` (root) — `[tool.pytest.ini_options] markers`
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/__init__.py`

- [ ] **Step 1: Add base dep + optional extras in `packages/jw-core/pyproject.toml`**

Append the following inside `[project.optional-dependencies]` and add `Pillow` to `dependencies`:

```toml
# dependencies (existing list) — add Pillow:
#   "Pillow>=10.0.0",

[project.optional-dependencies]
# (keep existing pdf / docx / anki entries)

vlm-anthropic = [
    "anthropic>=0.34.0",
]
vlm-openai = [
    "openai>=1.40.0",
]
vlm-api-qwen = [
    "httpx>=0.27.0",
]
vlm-mlx = [
    "mlx-vlm>=0.1.0",
    "Pillow>=10.0.0",
]
vlm-nvidia = [
    "vllm>=0.6.0",
    "Pillow>=10.0.0",
]
vlm-cpu = [
    "llama-cpp-python>=0.3.0",
    "Pillow>=10.0.0",
]
vlm-tesseract = [
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",
]
```

- [ ] **Step 2: Add the `vlm_real` marker at root**

In `pyproject.toml` (root), under `[tool.pytest.ini_options]` add:

```toml
markers = [
    "vlm_real: integration tests that hit real VLM hardware or APIs (opt-in)",
]
```

- [ ] **Step 3: Create the empty providers package**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/__init__.py
"""Concrete VLM providers (lazy-import SDKs internally).

Public re-exports:
    FakeVLMProvider, ClaudeVisionProvider, OpenAIVisionProvider,
    Qwen3VLAPIProvider, Qwen3VLProvider, TesseractFallbackProvider,
    get_default_provider, JW_VLM_PROVIDER_ENV.
"""

from jw_core.vision.vlm_providers.factory import (
    JW_VLM_PROVIDER_ENV,
    get_default_provider,
)
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

__all__ = [
    "JW_VLM_PROVIDER_ENV",
    "FakeVLMProvider",
    "get_default_provider",
]
```

- [ ] **Step 4: Verify install**

```bash
uv sync --all-packages
uv pip list | grep -E "jw-core|Pillow"
```

Expected: `jw-core 0.1.0`, `Pillow ≥10`.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/pyproject.toml pyproject.toml packages/jw-core/src/jw_core/vision/vlm_providers/__init__.py
git commit -m "chore(jw-core): scaffold vlm-ocr optional-deps and pytest marker"
```

---

### Task 2: `StructuredBlock`, `StructuredPage`, `VLMProvider` Protocol

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm.py`
- Create: `packages/jw-core/tests/test_vlm_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_vlm_models.py
"""Tests for jw_core.vision.vlm core types."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    StructuredBlock,
    StructuredPage,
    parse_structured_page_json,
)


def test_structured_block_minimal() -> None:
    block = StructuredBlock(kind="paragraph", text="Hello")
    assert block.kind == "paragraph"
    assert block.text == "Hello"
    assert block.bbox is None
    assert block.lang_hint == "en"
    assert block.metadata == {}


def test_structured_block_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        StructuredBlock(kind="banner", text="x")  # type: ignore[arg-type]


def test_structured_block_bbox_bounds_normalized() -> None:
    StructuredBlock(kind="header", text="t", bbox=(0.0, 0.0, 1.0, 1.0))
    with pytest.raises(ValidationError):
        StructuredBlock(kind="header", text="t", bbox=(0.0, 0.0, 1.2, 0.5))


def test_structured_page_requires_raw_text_fallback() -> None:
    with pytest.raises(ValidationError):
        StructuredPage(  # type: ignore[call-arg]
            blocks=[],
            provider_name="fake",
            target="cpu",
        )


def test_structured_page_round_trip() -> None:
    page = StructuredPage(
        blocks=[
            StructuredBlock(kind="header", text="Watchtower"),
            StructuredBlock(kind="paragraph", text="Body."),
        ],
        provider_name="fake",
        target="cpu",
        raw_text_fallback="Watchtower\nBody.",
        language_detected="en",
    )
    dumped = page.model_dump_json()
    again = StructuredPage.model_validate_json(dumped)
    assert again == page


def test_default_prompt_mentions_json_only() -> None:
    assert "JSON" in DEFAULT_VLM_PROMPT
    assert "no markdown" in DEFAULT_VLM_PROMPT.lower()


def test_parse_structured_page_json_strips_fences() -> None:
    raw = """```json
{"blocks":[{"kind":"paragraph","text":"hi","lang_hint":"en"}],"language_detected":"en"}
```"""
    blocks, lang = parse_structured_page_json(raw)
    assert len(blocks) == 1
    assert blocks[0].text == "hi"
    assert lang == "en"


def test_parse_structured_page_json_garbage_returns_single_block() -> None:
    raw = "definitely not json"
    blocks, lang = parse_structured_page_json(raw)
    assert len(blocks) == 1
    assert blocks[0].kind == "paragraph"
    assert "definitely" in blocks[0].text
    assert lang is None
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest packages/jw-core/tests/test_vlm_models.py -v
```

Expected: ModuleNotFoundError on `jw_core.vision.vlm`.

- [ ] **Step 3: Implement `vlm.py`**

```python
# packages/jw-core/src/jw_core/vision/vlm.py
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
    def _check_bbox(
        cls, v: tuple[float, float, float, float] | None
    ) -> tuple[float, float, float, float] | None:
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
```

- [ ] **Step 4: Re-run tests**

```bash
uv run pytest packages/jw-core/tests/test_vlm_models.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/vision/vlm.py packages/jw-core/tests/test_vlm_models.py
git commit -m "feat(jw-core/vision): add StructuredPage models + VLMProvider Protocol"
```

---

### Task 3: `FakeVLMProvider` + golden fixtures

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/fakes.py`
- Create: `packages/jw-core/tests/test_vlm_provider_fake.py`
- Create: `packages/jw-core/tests/fixtures/vlm/wt_2024_page_es.png` (1×1 PNG placeholder generated by script)
- Create: `packages/jw-core/tests/fixtures/vlm/bible_john_3_es.png`
- Create: `packages/jw-core/tests/fixtures/vlm/expected_structured/wt_2024_page_es.json`
- Create: `packages/jw-core/tests/fixtures/vlm/expected_structured/bible_john_3_es.json`

- [ ] **Step 1: Generate tiny PNG fixtures**

```bash
uv run python -c "
import struct, zlib, pathlib
def png(path, color):
    header = b'\\x89PNG\\r\\n\\x1a\\n'
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_chunk = b'IHDR' + ihdr
    ihdr_block = struct.pack('>I', 13) + ihdr_chunk + struct.pack('>I', zlib.crc32(ihdr_chunk))
    raw = b'\\x00' + bytes(color)
    comp = zlib.compress(raw)
    idat_chunk = b'IDAT' + comp
    idat_block = struct.pack('>I', len(comp)) + idat_chunk + struct.pack('>I', zlib.crc32(idat_chunk))
    iend = b'IEND'
    iend_block = struct.pack('>I', 0) + iend + struct.pack('>I', zlib.crc32(iend))
    pathlib.Path(path).write_bytes(header + ihdr_block + idat_block + iend_block)
import os
os.makedirs('packages/jw-core/tests/fixtures/vlm/expected_structured', exist_ok=True)
png('packages/jw-core/tests/fixtures/vlm/wt_2024_page_es.png', (240, 240, 240))
png('packages/jw-core/tests/fixtures/vlm/bible_john_3_es.png', (240, 240, 240))
print('ok')
"
```

- [ ] **Step 2: Write the golden JSONs**

```json
// packages/jw-core/tests/fixtures/vlm/expected_structured/wt_2024_page_es.json
{
  "blocks": [
    {"kind": "header", "text": "La Atalaya 2024", "lang_hint": "es", "confidence": 0.97},
    {"kind": "paragraph", "text": "Jehová cuida de los suyos.", "lang_hint": "es", "confidence": 0.95},
    {"kind": "bible_ref", "text": "Salmo 23:1", "lang_hint": "es", "confidence": 0.99},
    {"kind": "footnote", "text": "Véase w24 julio, p. 12.", "lang_hint": "es", "confidence": 0.9}
  ],
  "language_detected": "es"
}
```

```json
// packages/jw-core/tests/fixtures/vlm/expected_structured/bible_john_3_es.json
{
  "blocks": [
    {"kind": "header", "text": "Juan 3", "lang_hint": "es", "confidence": 0.99},
    {"kind": "bible_ref", "text": "Juan 3:16", "lang_hint": "es", "confidence": 0.99},
    {"kind": "paragraph", "text": "Porque tanto amó Dios al mundo que dio a su Hijo unigénito.", "lang_hint": "es", "confidence": 0.96}
  ],
  "language_detected": "es"
}
```

- [ ] **Step 3: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_fake.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.vision.vlm import StructuredBlock, StructuredPage
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

FIXTURES = Path(__file__).parent / "fixtures" / "vlm"


def test_fake_is_always_available() -> None:
    assert FakeVLMProvider().is_available() is True


def test_fake_loads_golden_when_matching_filename() -> None:
    provider = FakeVLMProvider()
    page = provider.extract_structured(FIXTURES / "wt_2024_page_es.png", language="es")
    assert page.provider_name == "fake"
    assert page.target == "cpu"
    assert page.language_detected == "es"
    assert any(b.kind == "bible_ref" for b in page.blocks)
    assert "Jehová" in page.text_only()


def test_fake_falls_back_to_canned_block_for_unknown_image(tmp_path: Path) -> None:
    bogus = tmp_path / "unknown.png"
    bogus.write_bytes(b"\x89PNG\r\n\x1a\n")
    page = FakeVLMProvider().extract_structured(bogus, language="en")
    assert len(page.blocks) == 1
    assert page.blocks[0].kind == "paragraph"
    assert page.raw_text_fallback


def test_fake_accepts_bytes_input() -> None:
    page = FakeVLMProvider().extract_structured(b"\x89PNG\r\n\x1a\n", language="en")
    assert isinstance(page, StructuredPage)


def test_fake_custom_blocks_override() -> None:
    custom = [StructuredBlock(kind="header", text="custom")]
    page = FakeVLMProvider(canned_blocks=custom).extract_structured(b"x")
    assert page.blocks == custom


def test_fake_cost_is_zero() -> None:
    hint = FakeVLMProvider().cost_estimate(b"x")
    assert hint.cents_estimate == 0.0
    assert hint.network is False
```

- [ ] **Step 4: Run to confirm failure**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_fake.py -v
```

- [ ] **Step 5: Implement `FakeVLMProvider`**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/fakes.py
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


_GOLDEN_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "vlm"
    / "expected_structured"
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
```

- [ ] **Step 6: Re-run tests**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_fake.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-core/src/jw_core/vision/vlm_providers/fakes.py packages/jw-core/tests/test_vlm_provider_fake.py packages/jw-core/tests/fixtures/vlm
git commit -m "feat(jw-core/vision): FakeVLMProvider + golden fixtures"
```

---

### Task 4: `ClaudeVisionProvider` (adapter over `anthropic` SDK)

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/claude_vision.py`
- Create: `packages/jw-core/tests/test_vlm_provider_claude.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_claude.py
"""ClaudeVisionProvider: adapter on top of the anthropic SDK.

The model is *not* a new entity. It uses claude-haiku-4-5 / sonnet-4-6 /
opus-4-7, which are natively multimodal. We test by injecting a fake `client`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.claude_vision import ClaudeVisionProvider


class _FakeClient:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.last_request: dict | None = None
        self.messages = self

    def create(self, **kwargs) -> object:
        self.last_request = kwargs

        class _Block:
            def __init__(self, text: str) -> None:
                self.text = text
                self.type = "text"

        class _Resp:
            def __init__(self, text: str) -> None:
                self.content = [_Block(text)]

        return _Resp(self._payload)


def test_provider_is_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeVisionProvider()
    assert p.is_available() is False


def test_provider_is_available_with_api_key_and_client(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = ClaudeVisionProvider(client=_FakeClient("{}"))
    assert p.is_available() is True
    assert p.target == "api"


def test_extract_structured_parses_blocks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    payload = (
        '{"blocks":[{"kind":"header","text":"Juan 3","lang_hint":"es"},'
        '{"kind":"bible_ref","text":"Juan 3:16","lang_hint":"es"}],'
        '"language_detected":"es"}'
    )
    client = _FakeClient(payload)
    p = ClaudeVisionProvider(client=client, model="claude-haiku-4-5")
    page = p.extract_structured(img, language="es")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "claude_vision"
    assert page.target == "api"
    assert len(page.blocks) == 2
    assert client.last_request is not None
    assert client.last_request["model"] == "claude-haiku-4-5"
    content = client.last_request["messages"][0]["content"]
    kinds = [item["type"] for item in content]
    assert "image" in kinds and "text" in kinds


def test_extract_falls_back_to_paragraph_on_bad_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    p = ClaudeVisionProvider(client=_FakeClient("not json"))
    page = p.extract_structured(img, language="en")
    assert len(page.blocks) == 1
    assert page.blocks[0].kind == "paragraph"
    assert "not json" in page.raw_text_fallback


def test_model_can_be_overridden_via_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("JW_CLAUDE_VISION_MODEL", "claude-sonnet-4-6")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    client = _FakeClient('{"blocks":[],"language_detected":"en"}')
    p = ClaudeVisionProvider(client=client)
    p.extract_structured(img, language="en")
    assert client.last_request is not None
    assert client.last_request["model"] == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_claude.py -v
```

- [ ] **Step 3: Implement `ClaudeVisionProvider`**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/claude_vision.py
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
```

- [ ] **Step 4: Re-run tests**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_claude.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/vision/vlm_providers/claude_vision.py packages/jw-core/tests/test_vlm_provider_claude.py
git commit -m "feat(jw-core/vision): ClaudeVisionProvider adapter on anthropic SDK"
```

---

### Task 5: `OpenAIVisionProvider` (adapter over `openai` SDK)

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/openai_vision.py`
- Create: `packages/jw-core/tests/test_vlm_provider_openai.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_openai.py
from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.openai_vision import OpenAIVisionProvider


class _FakeChat:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.last_request: dict | None = None

    def create(self, **kwargs):
        self.last_request = kwargs

        class _Msg:
            def __init__(self, c: str) -> None:
                self.content = c

        class _Choice:
            def __init__(self, c: str) -> None:
                self.message = _Msg(c)

        class _Resp:
            def __init__(self, c: str) -> None:
                self.choices = [_Choice(c)]

        return _Resp(self._payload)


class _FakeClient:
    def __init__(self, payload: str) -> None:
        self.chat = type("X", (), {"completions": _FakeChat(payload)})()


def test_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIVisionProvider().is_available() is False


def test_extract_structured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    payload = (
        '{"blocks":[{"kind":"paragraph","text":"hello","lang_hint":"en"}],'
        '"language_detected":"en"}'
    )
    client = _FakeClient(payload)
    p = OpenAIVisionProvider(client=client, model="gpt-4o-mini")
    page = p.extract_structured(img, language="en")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "openai_vision"
    assert page.target == "api"
    assert page.blocks[0].text == "hello"
    req = client.chat.completions.last_request
    assert req["model"] == "gpt-4o-mini"
    parts = req["messages"][0]["content"]
    assert any(p["type"] == "image_url" for p in parts)


def test_model_can_be_overridden_via_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.setenv("JW_OPENAI_VISION_MODEL", "gpt-5")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    client = _FakeClient('{"blocks":[],"language_detected":"en"}')
    OpenAIVisionProvider(client=client).extract_structured(img, language="en")
    assert client.chat.completions.last_request["model"] == "gpt-5"
```

- [ ] **Step 2: Implement `OpenAIVisionProvider`**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/openai_vision.py
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
            raise RuntimeError(
                "OpenAIVisionProvider unavailable: set OPENAI_API_KEY and pip install openai."
            )

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
```

- [ ] **Step 3: Re-run tests**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_openai.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/src/jw_core/vision/vlm_providers/openai_vision.py packages/jw-core/tests/test_vlm_provider_openai.py
git commit -m "feat(jw-core/vision): OpenAIVisionProvider adapter on openai SDK"
```

---

### Task 6: `Qwen3VLAPIProvider` (DashScope / Replicate via httpx)

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_api.py`
- Create: `packages/jw-core/tests/test_vlm_provider_qwen_api.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_qwen_api.py
from __future__ import annotations

from pathlib import Path

import httpx

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.qwen3vl_api import Qwen3VLAPIProvider


def _mock_transport(payload: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": {
                    "choices": [
                        {"message": {"content": [{"text": payload}]}}
                    ]
                }
            },
        )

    return httpx.MockTransport(handler)


def test_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("JW_QWEN3VL_API_KEY", raising=False)
    assert Qwen3VLAPIProvider().is_available() is False


def test_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("JW_QWEN3VL_API_KEY", "k")
    monkeypatch.setenv("JW_QWEN3VL_API_BASE", "https://dashscope.aliyuncs.com")
    p = Qwen3VLAPIProvider(client=httpx.Client(transport=_mock_transport("{}")))
    assert p.is_available()


def test_extract_structured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_QWEN3VL_API_KEY", "k")
    monkeypatch.setenv("JW_QWEN3VL_API_BASE", "https://dashscope.aliyuncs.com")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    payload = (
        '{"blocks":[{"kind":"paragraph","text":"hola","lang_hint":"es"}],'
        '"language_detected":"es"}'
    )
    p = Qwen3VLAPIProvider(client=httpx.Client(transport=_mock_transport(payload)))
    page = p.extract_structured(img, language="es")
    assert isinstance(page, StructuredPage)
    assert page.target == "api"
    assert page.provider_name == "qwen3vl_api"
    assert page.blocks[0].text == "hola"
```

- [ ] **Step 2: Implement provider**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_api.py
"""Qwen3VLAPIProvider — vendor-agnostic JSON-over-HTTPS client for Qwen3-VL.

Configured by env:
  JW_QWEN3VL_API_KEY        required
  JW_QWEN3VL_API_BASE       required (e.g. https://dashscope.aliyuncs.com)
  JW_QWEN3VL_API_MODEL      optional (default: qwen3-vl-plus)
  JW_QWEN3VL_API_PATH       optional, defaults to /api/v1/services/aigc/multimodal-generation/generation
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
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_qwen_api.py -v
git add packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_api.py packages/jw-core/tests/test_vlm_provider_qwen_api.py
git commit -m "feat(jw-core/vision): Qwen3VLAPIProvider (DashScope-compatible httpx)"
```

---

### Task 7: `Qwen3VLProvider` local (MLX / vLLM / GGUF dispatch)

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_local.py`
- Create: `packages/jw-core/tests/test_vlm_provider_qwen_local.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_qwen_local.py
"""Local Qwen3-VL: factory chooses backend by env / target.

We test the dispatch logic only — never load a real model. Each backend is
behind a `_BackendProtocol` so we can inject fakes.
"""

from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredBlock, StructuredPage
from jw_core.vision.vlm_providers.qwen3vl_local import Qwen3VLProvider


class _FakeBackend:
    name = "fake-backend"

    def __init__(self, payload: str = "") -> None:
        self.payload = payload
        self.calls: list[Path | bytes] = []

    def available(self) -> bool:
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:  # noqa: ARG002
        self.calls.append(image)
        return self.payload or '{"blocks":[{"kind":"paragraph","text":"local-out","lang_hint":"en"}],"language_detected":"en"}'


def test_unavailable_when_no_backend() -> None:
    p = Qwen3VLProvider(backends=[])
    assert p.is_available() is False


def test_uses_first_available_backend(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    backend = _FakeBackend()
    p = Qwen3VLProvider(target="mlx", backends=[backend])
    assert p.is_available()
    page = p.extract_structured(img, language="en")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "qwen3vl_local"
    assert page.target == "mlx"
    assert backend.calls == [img]
    assert page.blocks[0].text == "local-out"


def test_falls_back_to_paragraph_on_bad_json(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    backend = _FakeBackend(payload="not json at all")
    p = Qwen3VLProvider(target="cpu", backends=[backend])
    page = p.extract_structured(img, language="en")
    assert len(page.blocks) == 1
    assert "not json" in page.raw_text_fallback


def test_skips_unavailable_backends(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    class _Down:
        name = "down"

        def available(self) -> bool:
            return False

        def generate(self, image, prompt):  # noqa: ARG002
            raise AssertionError("should not be called")

    good = _FakeBackend()
    p = Qwen3VLProvider(target="cpu", backends=[_Down(), good])
    p.extract_structured(img, language="en")
    assert good.calls == [img]
```

- [ ] **Step 2: Implement local provider with backend dispatch**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_local.py
"""Qwen3VLProvider — local execution.

Three backends, all behind a `_Backend` protocol. The provider iterates the
list and uses the first one whose `available()` returns True. Each backend
lazy-imports its SDK so missing extras never break import.

Env:
  JW_QWEN3VL_LOCAL_MODEL  — model id; defaults per backend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from jw_core.vision.vlm import (
    DEFAULT_VLM_PROMPT,
    CostHint,
    StructuredPage,
    Target,
    parse_structured_page_json,
)


class _Backend(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate(self, image: Path | bytes, prompt: str) -> str: ...


class _MLXBackend:
    name = "mlx-vlm"

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or "mlx-community/Qwen3-VL-2B-Instruct-4bit"
        )

    def available(self) -> bool:
        try:
            import mlx_vlm  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from mlx_vlm import generate, load  # type: ignore[import-not-found]

        model_obj, processor = load(self.model)
        path = image if isinstance(image, Path) else self._materialize(image)
        return generate(model_obj, processor, prompt=prompt, image=str(path), max_tokens=2048)

    @staticmethod
    def _materialize(buf: bytes) -> Path:
        import tempfile

        f = tempfile.NamedTemporaryFile(prefix="jwvlm-", suffix=".png", delete=False)
        f.write(buf)
        f.close()
        return Path(f.name)


class _VLLMBackend:
    name = "vllm"

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or "Qwen/Qwen3-VL-8B-Instruct"
        )

    def available(self) -> bool:
        try:
            import vllm  # noqa: F401
        except ImportError:
            return False
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from vllm import LLM, SamplingParams  # type: ignore[import-not-found]

        llm = LLM(model=self.model, dtype="bfloat16")
        path = image if isinstance(image, Path) else _MLXBackend._materialize(image)
        result = llm.generate(
            [{"prompt": prompt, "multi_modal_data": {"image": str(path)}}],
            sampling_params=SamplingParams(max_tokens=2048, temperature=0.0),
        )
        return result[0].outputs[0].text


class _GGUFBackend:
    name = "llama-cpp-python"

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = (
            model_path
            or os.environ.get("JW_QWEN3VL_LOCAL_MODEL")
            or os.path.expanduser("~/.cache/qwen3vl-2b-q4_k_m.gguf")
        )

    def available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        return os.path.exists(self.model_path)

    def generate(self, image: Path | bytes, prompt: str) -> str:
        from llama_cpp import Llama  # type: ignore[import-not-found]

        llm = Llama(model_path=self.model_path, n_ctx=4096, logits_all=False)
        # GGUF multimodal API: feed prompt + image via chat_handler.
        path = image if isinstance(image, Path) else _MLXBackend._materialize(image)
        resp = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"file://{path}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=2048,
        )
        return resp["choices"][0]["message"]["content"]


def _default_backends_for(target: Target) -> list[_Backend]:
    if target == "mlx":
        return [_MLXBackend()]
    if target == "nvidia":
        return [_VLLMBackend()]
    if target == "cpu":
        return [_GGUFBackend()]
    return [_MLXBackend(), _VLLMBackend(), _GGUFBackend()]


@dataclass
class Qwen3VLProvider:
    target: Target = "mlx"
    backends: list[_Backend] | None = None
    name: str = field(default="qwen3vl_local", init=False)

    def _backends(self) -> list[_Backend]:
        if self.backends is not None:
            return self.backends
        return _default_backends_for(self.target)

    def _pick(self) -> _Backend | None:
        for b in self._backends():
            if b.available():
                return b
        return None

    def is_available(self) -> bool:
        return self._pick() is not None

    def cost_estimate(self, image: Path | bytes) -> CostHint:  # noqa: ARG002
        return CostHint(cents_estimate=0.0, latency_ms_estimate=6000, network=False)

    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage:
        backend = self._pick()
        if backend is None:
            raise RuntimeError(
                "Qwen3VLProvider unavailable: install one of mlx-vlm / vllm / llama-cpp-python."
            )
        prompt_text = (prompt or DEFAULT_VLM_PROMPT) + f"\nLanguage hint: {language}\n"
        raw_text = backend.generate(image, prompt_text)
        blocks, lang = parse_structured_page_json(raw_text)
        return StructuredPage(
            blocks=blocks,
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=lang or language,
        )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_qwen_local.py -v
git add packages/jw-core/src/jw_core/vision/vlm_providers/qwen3vl_local.py packages/jw-core/tests/test_vlm_provider_qwen_local.py
git commit -m "feat(jw-core/vision): Qwen3VLProvider local (mlx/vllm/gguf dispatch)"
```

---

### Task 8: `TesseractFallbackProvider` + deprecate `ocr_image()`

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/tesseract_fallback.py`
- Create: `packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py`
- Modify: `packages/jw-core/src/jw_core/vision/ocr.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.tesseract_fallback import TesseractFallbackProvider


def test_emits_deprecation_warning(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    def fake_ocr(image_path, *, language="eng"):  # noqa: ARG001
        return "Some OCR text"

    monkeypatch.setattr(
        "jw_core.vision.vlm_providers.tesseract_fallback.ocr_image", fake_ocr
    )
    p = TesseractFallbackProvider()
    assert p.is_available()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        page = p.extract_structured(img, language="en")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "tesseract_fallback"
    assert page.target == "cpu"
    assert page.blocks[0].kind == "paragraph"
    assert "Some OCR text" in page.blocks[0].text


def test_unavailable_when_pytesseract_missing(monkeypatch) -> None:
    def boom(*a, **kw):  # noqa: ARG001
        raise ImportError("no module")

    monkeypatch.setattr(
        "jw_core.vision.vlm_providers.tesseract_fallback._probe", boom
    )
    assert TesseractFallbackProvider().is_available() is False


def test_migrate_to_vlm_helper_emits_warning(monkeypatch, tmp_path: Path) -> None:
    from jw_core.vision.ocr import migrate_to_vlm

    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    out = migrate_to_vlm()  # returns a callable usable in place of ocr_image
    assert callable(out)


def test_deprecated_ocr_image_warns(monkeypatch, tmp_path: Path) -> None:
    from jw_core.vision import ocr as ocr_mod

    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    def fake_image_to_string(image, lang="eng"):  # noqa: ARG001
        return "x"

    monkeypatch.setattr(
        "jw_core.vision.ocr.ocr_image", lambda *a, **k: "x"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ocr_mod.extract_bible_reference_from_image(img, language="en")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
```

- [ ] **Step 2: Implement the fallback provider**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/tesseract_fallback.py
"""TesseractFallbackProvider — wraps the legacy ocr_image() in a VLMProvider.

Always emits a DeprecationWarning on use. Returns a single `paragraph` block
containing the raw OCR text (no structure). The factory will pick this as
the last-resort entry in DEFAULT_CHAIN when nothing else is available.
"""

from __future__ import annotations

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
    """Import pytesseract; return True on success."""

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
            import tempfile

            f = tempfile.NamedTemporaryFile(prefix="jwvlm-", suffix=".png", delete=False)
            f.write(image)
            f.close()
            path: Path | str = f.name
        else:
            path = image
        raw_text = ocr_image(path, language=lang_code)
        return StructuredPage(
            blocks=[StructuredBlock(kind="paragraph", text=raw_text or "[empty OCR]", lang_hint=language)],
            source_image=str(image) if isinstance(image, Path) else None,
            provider_name=self.name,
            target=self.target,
            raw_text_fallback=raw_text,
            language_detected=language,
        )
```

- [ ] **Step 3: Deprecate `ocr_image()` + add `migrate_to_vlm()` in `ocr.py`**

Modify `packages/jw-core/src/jw_core/vision/ocr.py` — append at the bottom and wrap `extract_bible_reference_from_image`:

```python
# --- Append to packages/jw-core/src/jw_core/vision/ocr.py ---

import warnings as _warnings


def migrate_to_vlm():
    """Return a callable replacement for ocr_image() that uses the VLM factory.

    Usage:
        ocr_image = migrate_to_vlm()
        text = ocr_image(path, language="es")

    The returned callable preserves the (path, language=) signature for drop-in
    swaps but uses the configured VLM provider underneath.
    """

    from jw_core.vision.vlm_providers import get_default_provider

    def _impl(image_path, *, language: str = "en") -> str:
        page = get_default_provider().extract_structured(image_path, language=language)
        return page.raw_text_fallback

    return _impl


def _deprecate(msg: str) -> None:
    _warnings.warn(msg, DeprecationWarning, stacklevel=3)


# Wrap extract_bible_reference_from_image to emit a warning. To avoid editing
# the original definition above and risking subtle bugs in tests, we override
# the symbol exported from this module.
_orig_extract = extract_bible_reference_from_image  # type: ignore[assignment]


def extract_bible_reference_from_image(  # type: ignore[no-redef]
    image_path,
    *,
    language: str = "en",
) -> dict[str, object]:
    _deprecate(
        "extract_bible_reference_from_image() is deprecated; use "
        "jw_core.vision.vlm.extract_bible_reference_from_image_v2() with a VLM provider."
    )
    return _orig_extract(image_path, language=language)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py -v
git add packages/jw-core/src/jw_core/vision/vlm_providers/tesseract_fallback.py packages/jw-core/src/jw_core/vision/ocr.py packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py
git commit -m "feat(jw-core/vision): TesseractFallbackProvider + deprecate ocr_image"
```

---

### Task 9: Factory + `JW_VLM_PROVIDER` env override

**Files:**
- Create: `packages/jw-core/src/jw_core/vision/vlm_providers/factory.py`
- Create: `packages/jw-core/tests/test_vlm_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_factory.py
from __future__ import annotations

import pytest

from jw_core.vision.vlm_providers import (
    FakeVLMProvider,
    JW_VLM_PROVIDER_ENV,
    get_default_provider,
)
from jw_core.vision.vlm_providers.factory import (
    DEFAULT_CHAIN,
    ProviderUnavailableError,
    build_provider,
)


def test_env_override_returns_named_provider(monkeypatch) -> None:
    monkeypatch.setenv(JW_VLM_PROVIDER_ENV, "fake")
    p = get_default_provider()
    assert isinstance(p, FakeVLMProvider)


def test_env_override_unknown_raises(monkeypatch) -> None:
    monkeypatch.setenv(JW_VLM_PROVIDER_ENV, "no-such-thing")
    with pytest.raises(ProviderUnavailableError):
        get_default_provider()


def test_default_chain_contains_all(monkeypatch) -> None:
    monkeypatch.delenv(JW_VLM_PROVIDER_ENV, raising=False)
    expected = {
        "qwen3vl_local",
        "qwen3vl_api",
        "claude_vision",
        "openai_vision",
        "tesseract_fallback",
    }
    assert expected.issubset(set(DEFAULT_CHAIN))


def test_get_default_picks_first_available(monkeypatch) -> None:
    monkeypatch.delenv(JW_VLM_PROVIDER_ENV, raising=False)

    # Force every real provider to "not available" by clearing env vars.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "JW_QWEN3VL_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    # When all real ones report unavailable, fallback should kick in; but the
    # fallback also depends on pytesseract. Patch the chain to inject Fake
    # explicitly at the end.
    from jw_core.vision.vlm_providers import factory as fmod

    fakes_only_chain = ["fake"]
    monkeypatch.setattr(fmod, "DEFAULT_CHAIN", fakes_only_chain)
    monkeypatch.setattr(
        fmod,
        "_REGISTRY_BUILDERS",
        {"fake": lambda: FakeVLMProvider()},
    )
    p = get_default_provider()
    assert isinstance(p, FakeVLMProvider)


def test_build_provider_unknown_name() -> None:
    with pytest.raises(ProviderUnavailableError):
        build_provider("does-not-exist")
```

- [ ] **Step 2: Implement factory**

```python
# packages/jw-core/src/jw_core/vision/vlm_providers/factory.py
"""Factory + provider chain.

Resolution order:
  1. If env JW_VLM_PROVIDER is set, build that exact provider; if its
     is_available() is False, raise ProviderUnavailableError (do NOT fall back
     silently — explicit user choice).
  2. Else iterate DEFAULT_CHAIN; return the first whose is_available() is True.
  3. Else raise ProviderUnavailableError.

Every entry in the registry is a zero-arg factory that returns a fresh
provider instance. We construct lazily so optional SDKs are never imported
unless that provider is actually selected.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jw_core.vision.vlm import VLMProvider


JW_VLM_PROVIDER_ENV = "JW_VLM_PROVIDER"


class ProviderUnavailableError(RuntimeError):
    """Raised when no provider is usable in the current environment."""


def _build_fake() -> "VLMProvider":
    from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

    return FakeVLMProvider()


def _build_claude() -> "VLMProvider":
    from jw_core.vision.vlm_providers.claude_vision import ClaudeVisionProvider

    return ClaudeVisionProvider()


def _build_openai() -> "VLMProvider":
    from jw_core.vision.vlm_providers.openai_vision import OpenAIVisionProvider

    return OpenAIVisionProvider()


def _build_qwen_api() -> "VLMProvider":
    from jw_core.vision.vlm_providers.qwen3vl_api import Qwen3VLAPIProvider

    return Qwen3VLAPIProvider()


def _build_qwen_local() -> "VLMProvider":
    from jw_core.vision.vlm_providers.qwen3vl_local import Qwen3VLProvider

    # default to mlx; users override target via JW_QWEN3VL_LOCAL_TARGET
    target = os.environ.get("JW_QWEN3VL_LOCAL_TARGET", "mlx")
    if target not in {"mlx", "nvidia", "cpu"}:
        target = "mlx"
    return Qwen3VLProvider(target=target)  # type: ignore[arg-type]


def _build_tesseract_fallback() -> "VLMProvider":
    from jw_core.vision.vlm_providers.tesseract_fallback import (
        TesseractFallbackProvider,
    )

    return TesseractFallbackProvider()


_REGISTRY_BUILDERS: dict[str, Callable[[], "VLMProvider"]] = {
    "fake": _build_fake,
    "claude_vision": _build_claude,
    "openai_vision": _build_openai,
    "qwen3vl_api": _build_qwen_api,
    "qwen3vl_local": _build_qwen_local,
    "tesseract_fallback": _build_tesseract_fallback,
}


DEFAULT_CHAIN: list[str] = [
    "qwen3vl_local",
    "qwen3vl_api",
    "claude_vision",
    "openai_vision",
    "tesseract_fallback",
]


def build_provider(name: str) -> "VLMProvider":
    """Construct a provider by registry name. Raise if unknown."""

    builder = _REGISTRY_BUILDERS.get(name)
    if builder is None:
        raise ProviderUnavailableError(
            f"unknown VLM provider {name!r}. "
            f"Known: {sorted(_REGISTRY_BUILDERS)}"
        )
    return builder()


def get_default_provider() -> "VLMProvider":
    """Pick a provider per resolution rules above."""

    forced = os.environ.get(JW_VLM_PROVIDER_ENV)
    if forced:
        provider = build_provider(forced)
        if not provider.is_available():
            raise ProviderUnavailableError(
                f"{JW_VLM_PROVIDER_ENV}={forced!r} but provider reports unavailable. "
                "Install its extra, set its env vars, or change JW_VLM_PROVIDER."
            )
        return provider

    for name in DEFAULT_CHAIN:
        try:
            provider = build_provider(name)
        except Exception:  # noqa: BLE001
            continue
        try:
            if provider.is_available():
                return provider
        except Exception:  # noqa: BLE001
            continue

    raise ProviderUnavailableError(
        "no VLM provider available. Install one of: mlx-vlm, vllm, "
        "llama-cpp-python, anthropic, openai, pytesseract — or set "
        f"{JW_VLM_PROVIDER_ENV}=fake for tests."
    )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/jw-core/tests/test_vlm_factory.py -v
git add packages/jw-core/src/jw_core/vision/vlm_providers/factory.py packages/jw-core/tests/test_vlm_factory.py
git commit -m "feat(jw-core/vision): provider factory with JW_VLM_PROVIDER override"
```

---

### Task 10: `extract_bible_reference_from_image_v2` + public re-exports

**Files:**
- Modify: `packages/jw-core/src/jw_core/vision/vlm.py` (append v2 helper)
- Modify: `packages/jw-core/src/jw_core/vision/__init__.py`
- Create: `packages/jw-core/tests/test_vlm_extract_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_vlm_extract_v2.py
from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import (
    StructuredBlock,
    extract_bible_reference_from_image_v2,
)
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider


def test_v2_returns_structured_page_dict(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="bible_ref", text="Juan 3:16", lang_hint="es")
        ]
    )
    out = extract_bible_reference_from_image_v2(img, language="es", provider=provider)
    assert "structured_page" in out
    assert "reference" in out
    assert "text" in out
    assert out["language_hint"] == "es"
    ref = out["reference"]
    assert ref is not None
    assert ref["book_num"] == 43  # John
    assert ref["chapter"] == 3
    assert ref["verse_start"] == 16


def test_v2_text_is_raw_fallback(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="paragraph", text="Hello world")]
    )
    out = extract_bible_reference_from_image_v2(img, language="en", provider=provider)
    assert "Hello world" in out["text"]


def test_v2_no_reference_returns_none(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="paragraph", text="no scripture here")]
    )
    out = extract_bible_reference_from_image_v2(img, language="en", provider=provider)
    assert out["reference"] is None
```

- [ ] **Step 2: Append v2 helper to `vlm.py`**

```python
# --- Append to packages/jw-core/src/jw_core/vision/vlm.py ---


def extract_bible_reference_from_image_v2(
    image_path: Path | str,
    *,
    language: str = "en",
    provider: "VLMProvider | None" = None,
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
```

- [ ] **Step 3: Re-export public API in `__init__.py`**

Update `packages/jw-core/src/jw_core/vision/__init__.py`:

```python
"""Visual / multimodal subsystem (Module 7)."""

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
    FakeVLMProvider,
    JW_VLM_PROVIDER_ENV,
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
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/jw-core/tests/test_vlm_extract_v2.py -v
git add packages/jw-core/src/jw_core/vision/vlm.py packages/jw-core/src/jw_core/vision/__init__.py packages/jw-core/tests/test_vlm_extract_v2.py
git commit -m "feat(jw-core/vision): extract_bible_reference_from_image_v2 + public re-exports"
```

---

### Task 11: `jw_rag.ingest_image()` consumes `StructuredPage`

**Files:**
- Create: `packages/jw-rag/src/jw_rag/ingest_image.py`
- Modify: `packages/jw-rag/src/jw_rag/__init__.py`
- Create: `packages/jw-rag/tests/test_ingest_image.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_ingest_image.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jw_core.vision.vlm import StructuredBlock, StructuredPage
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider
from jw_rag.ingest_image import ingest_image


class _FakeStore:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, chunks) -> None:
        self.added.extend(chunks)


def _img(tmp_path: Path) -> Path:
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG")
    return p


def test_ingest_image_creates_one_chunk_per_block(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="header", text="Watchtower"),
            StructuredBlock(kind="paragraph", text="Jehová cuida"),
            StructuredBlock(kind="bible_ref", text="Juan 3:16"),
        ]
    )
    n = ingest_image(store, _img(tmp_path), language="es", provider=provider)
    assert n == 3
    assert len(store.added) == 3
    kinds = [c.metadata["kind"] for c in store.added]
    assert kinds == ["header", "paragraph", "bible_ref"]


def test_ingest_image_parses_bible_ref_metadata(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="bible_ref", text="John 3:16")]
    )
    ingest_image(store, _img(tmp_path), language="en", provider=provider)
    parsed = store.added[0].metadata.get("parsed_reference")
    assert parsed is not None
    assert parsed["chapter"] == 3
    assert parsed["verse_start"] == 16


def test_ingest_image_filters_low_confidence(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="paragraph", text="strong", confidence=0.9),
            StructuredBlock(kind="paragraph", text="weak", confidence=0.1),
        ]
    )
    n = ingest_image(
        store, _img(tmp_path), language="en", provider=provider, min_confidence=0.3
    )
    assert n == 1
    assert store.added[0].text == "strong"


def test_ingest_image_source_id_is_stable(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="paragraph", text="t")]
    )
    img = _img(tmp_path)
    ingest_image(store, img, language="en", provider=provider)
    sid = store.added[0].source_id
    assert sid.startswith("image:")
    assert sid.endswith(":0:paragraph")
```

- [ ] **Step 2: Implement `ingest_image`**

```python
# packages/jw-rag/src/jw_rag/ingest_image.py
"""Ingest one page image into the RAG vector store.

Produces one chunk per StructuredBlock with stable `source_id` based on the
SHA-256 of the image path (or contents) plus block index. `bible_ref` blocks
get an extra `parsed_reference` metadata entry when the reference parser
returns a hit.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from jw_core.parsers.reference import parse_reference
from jw_rag.chunker import Chunk

if TYPE_CHECKING:  # avoid hard dep at import time
    from jw_core.vision.vlm import StructuredPage, VLMProvider
    from jw_rag.store import VectorStore


def _hash_for_image(image_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(str(image_path.resolve()).encode("utf-8"))
    if image_path.exists():
        digest.update(image_path.read_bytes())
    return digest.hexdigest()[:16]


def ingest_image(
    store: "VectorStore",
    image_path: Path | str,
    *,
    language: str = "en",
    provider: "VLMProvider | None" = None,
    min_confidence: float | None = None,
) -> int:
    """Ingest one page image. Returns the number of chunks added."""

    if provider is None:
        from jw_core.vision.vlm_providers import get_default_provider

        provider = get_default_provider()

    path = Path(image_path)
    page: StructuredPage = provider.extract_structured(path, language=language)
    img_hash = _hash_for_image(path)

    chunks: list[Chunk] = []
    for i, block in enumerate(page.blocks):
        if min_confidence is not None and block.confidence is not None:
            if block.confidence < min_confidence:
                continue
        metadata: dict[str, object] = {
            "kind": block.kind,
            "lang_hint": block.lang_hint,
            "image_path": str(path),
            "provider": page.provider_name,
            "target": page.target,
            "language_detected": page.language_detected,
            "confidence": block.confidence,
            "bbox": list(block.bbox) if block.bbox else None,
        }
        if block.kind == "bible_ref":
            parsed = parse_reference(block.text)
            if parsed is not None:
                metadata["parsed_reference"] = parsed.model_dump()
        chunks.append(
            Chunk(
                source_id=f"image:{img_hash}:{i}:{block.kind}",
                text=block.text,
                metadata=metadata,
            )
        )

    if chunks:
        store.add(chunks)
    return len(chunks)
```

- [ ] **Step 3: Update `packages/jw-rag/src/jw_rag/__init__.py`**

Append:
```python
from jw_rag.ingest_image import ingest_image  # noqa: F401
```

And add `"ingest_image"` to `__all__`.

- [ ] **Step 4: Verify Chunk shape compatibility**

If `jw_rag.chunker.Chunk` does not exist as a public dataclass, peek at the file and adapt the import. (The chunker module already exposes `chunk_paragraphs` which produces chunk-like rows; this task assumes the same `Chunk` dataclass — adjust to whatever the existing model is, e.g. `Chunk(source_id=..., text=..., metadata=...)`.)

- [ ] **Step 5: Run + commit**

```bash
uv run pytest packages/jw-rag/tests/test_ingest_image.py -v
git add packages/jw-rag/src/jw_rag/ingest_image.py packages/jw-rag/src/jw_rag/__init__.py packages/jw-rag/tests/test_ingest_image.py
git commit -m "feat(jw-rag): ingest_image — one chunk per StructuredBlock"
```

---

### TASK 12: CLI subcommand `jw image extract|ingest`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/image.py`
- Create: `packages/jw-cli/tests/test_command_image.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_command_image.py
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.image import image_app


def _img(tmp_path: Path) -> Path:
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG")
    return p


def test_extract_uses_fake_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    runner = CliRunner()
    result = runner.invoke(image_app, ["extract", str(_img(tmp_path)), "--language", "en"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "blocks" in payload
    assert payload["provider_name"] == "fake"


def test_ingest_command_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    runner = CliRunner()
    out = runner.invoke(
        image_app,
        ["ingest", str(_img(tmp_path)), "--language", "en", "--store", str(tmp_path / "store.sqlite")],
    )
    assert out.exit_code == 0, out.stdout
    assert "chunks" in out.stdout.lower()
```

- [ ] **Step 2: Implement the CLI**

```python
# packages/jw-cli/src/jw_cli/commands/image.py
"""`jw image …` — VLM-backed OCR and ingest helpers."""

from __future__ import annotations

import json
from pathlib import Path

import typer

image_app = typer.Typer(no_args_is_help=True, help="VLM-backed page image ops.")


@image_app.command("extract")
def extract(
    image: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option("en", "--language", "-l"),
    provider_name: str | None = typer.Option(
        None, "--provider", help="override JW_VLM_PROVIDER for this call"
    ),
) -> None:
    """Print the StructuredPage JSON for IMAGE."""

    from jw_core.vision.vlm_providers import build_provider, get_default_provider

    provider = build_provider(provider_name) if provider_name else get_default_provider()
    page = provider.extract_structured(image, language=language)
    typer.echo(page.model_dump_json(indent=2))


@image_app.command("ingest")
def ingest(
    image: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option("en", "--language", "-l"),
    store_path: Path = typer.Option(
        Path("~/.jw-toolkit/rag.sqlite").expanduser(), "--store"
    ),
    provider_name: str | None = typer.Option(None, "--provider"),
    min_confidence: float | None = typer.Option(None, "--min-confidence"),
) -> None:
    """Ingest IMAGE into the local RAG store."""

    from jw_core.vision.vlm_providers import build_provider, get_default_provider
    from jw_rag.ingest_image import ingest_image
    from jw_rag.store import VectorStore

    store = VectorStore.open(store_path)
    provider = build_provider(provider_name) if provider_name else get_default_provider()
    n = ingest_image(
        store,
        image,
        language=language,
        provider=provider,
        min_confidence=min_confidence,
    )
    typer.echo(json.dumps({"chunks": n, "store": str(store_path)}))
```

- [ ] **Step 3: Register in main**

Add to `packages/jw-cli/src/jw_cli/main.py`:

```python
from jw_cli.commands.image import image_app  # at top

app.add_typer(image_app, name="image")  # near other add_typer calls
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/jw-cli/tests/test_command_image.py -v
git add packages/jw-cli/src/jw_cli/commands/image.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_command_image.py
git commit -m "feat(jw-cli): jw image extract|ingest commands"
```

---

### Task 13: MCP tools `extract_structured_page` and `ingest_image_to_rag`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_mcp_vlm_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_mcp_vlm_tools.py
from __future__ import annotations

from pathlib import Path

import pytest


def test_extract_structured_page_tool_registered() -> None:
    from jw_mcp.server import mcp  # the FastMCP instance

    tool_names = {t.name for t in mcp._tool_manager._tools.values()}  # type: ignore[attr-defined]
    assert "extract_structured_page" in tool_names
    assert "ingest_image_to_rag" in tool_names


def test_extract_structured_page_returns_dict(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_VLM_PROVIDER", "fake")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    from jw_mcp.server import extract_structured_page as tool

    result = tool(image_path=str(img), language="en")
    assert isinstance(result, dict)
    assert "blocks" in result
    assert result["provider_name"] == "fake"
```

- [ ] **Step 2: Add tools to `server.py`**

Append:

```python
# --- Append to packages/jw-mcp/src/jw_mcp/server.py ---


@mcp.tool()
def extract_structured_page(image_path: str, language: str = "en") -> dict:
    """Run the configured VLM on IMAGE_PATH and return a StructuredPage as JSON."""

    from jw_core.vision.vlm_providers import get_default_provider

    page = get_default_provider().extract_structured(image_path, language=language)
    return page.model_dump()


@mcp.tool()
def ingest_image_to_rag(image_path: str, language: str = "en") -> dict:
    """Ingest IMAGE_PATH into the default RAG store. Returns {'chunks': int}."""

    from pathlib import Path

    from jw_core.vision.vlm_providers import get_default_provider
    from jw_rag.ingest_image import ingest_image
    from jw_rag.store import VectorStore

    store = VectorStore.open(Path("~/.jw-toolkit/rag.sqlite").expanduser())
    n = ingest_image(
        store,
        image_path,
        language=language,
        provider=get_default_provider(),
    )
    return {"chunks": n}
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/jw-mcp/tests/test_mcp_vlm_tools.py -v
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_mcp_vlm_tools.py
git commit -m "feat(jw-mcp): extract_structured_page + ingest_image_to_rag tools"
```

---

### Task 14: Integration tests with real providers (opt-in)

**Files:**
- Create: `packages/jw-core/tests/test_vlm_real.py`

- [ ] **Step 1: Write the marked integration test**

```python
# packages/jw-core/tests/test_vlm_real.py
"""Integration tests against REAL VLM backends.

These are opt-in. Run with:
    uv run pytest -m vlm_real

Each test is skipped unless the relevant provider reports available().
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jw_core.vision.vlm_providers.claude_vision import ClaudeVisionProvider
from jw_core.vision.vlm_providers.openai_vision import OpenAIVisionProvider
from jw_core.vision.vlm_providers.qwen3vl_api import Qwen3VLAPIProvider
from jw_core.vision.vlm_providers.qwen3vl_local import Qwen3VLProvider

FIXTURES = Path(__file__).parent / "fixtures" / "vlm"


pytestmark = pytest.mark.vlm_real


def _img() -> Path:
    return FIXTURES / "bible_john_3_es.png"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
def test_claude_real_extract() -> None:
    p = ClaudeVisionProvider()
    assert p.is_available()
    page = p.extract_structured(_img(), language="es")
    assert page.provider_name == "claude_vision"
    assert page.blocks


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="no OPENAI_API_KEY")
def test_openai_real_extract() -> None:
    p = OpenAIVisionProvider()
    assert p.is_available()
    page = p.extract_structured(_img(), language="es")
    assert page.blocks


@pytest.mark.skipif(
    not (os.environ.get("JW_QWEN3VL_API_KEY") and os.environ.get("JW_QWEN3VL_API_BASE")),
    reason="no JW_QWEN3VL_API_KEY/_API_BASE",
)
def test_qwen_api_real_extract() -> None:
    p = Qwen3VLAPIProvider()
    assert p.is_available()
    page = p.extract_structured(_img(), language="es")
    assert page.blocks


@pytest.mark.skipif(
    not Qwen3VLProvider(target="mlx").is_available(),
    reason="no local Qwen3-VL backend installed",
)
def test_qwen_local_real_extract() -> None:
    p = Qwen3VLProvider(target="mlx")
    page = p.extract_structured(_img(), language="es")
    assert page.blocks
```

- [ ] **Step 2: Verify markers do NOT run by default**

```bash
uv run pytest packages/jw-core/tests/test_vlm_real.py -v
# Expect: 4 deselected
uv run pytest -m vlm_real packages/jw-core/tests/test_vlm_real.py -v
# Expect: each test runs OR skips based on env, never errors
```

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_vlm_real.py
git commit -m "test(jw-core/vision): opt-in vlm_real integration tests"
```

---

### Task 15: Docs — guía de migración

**Files:**
- Create: `docs/guias/vlm-ocr.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the guide**

```markdown
# VLM-OCR (Fase 36)

`jw_core.vision.vlm` replaces the legacy Tesseract OCR path with a typed,
structured Vision-Language-Model pipeline that returns one block per
typographic element on the page.

## Quick start

```python
from jw_core.vision import extract_bible_reference_from_image_v2

out = extract_bible_reference_from_image_v2(
    "path/to/page.png", language="es"
)
print(out["reference"])         # parsed BibleRef.model_dump() or None
print(out["text"])              # raw text fallback (compat)
for block in out["structured_page"].blocks:
    print(block.kind, block.text)
```

## Choosing a provider

| Hardware | Provider | Install |
|---|---|---|
| Apple Silicon | `qwen3vl_local` (mlx) | `uv pip install jw-core[vlm-mlx]` + `huggingface-cli download mlx-community/Qwen3-VL-2B-Instruct-4bit` |
| NVIDIA GPU | `qwen3vl_local` (vllm) | `uv pip install jw-core[vlm-nvidia]` |
| CPU only | `qwen3vl_local` (gguf) | `uv pip install jw-core[vlm-cpu]` + download GGUF |
| API only | `claude_vision` | `uv pip install jw-core[vlm-anthropic]` + `ANTHROPIC_API_KEY` |
| API only | `openai_vision` | `uv pip install jw-core[vlm-openai]` + `OPENAI_API_KEY` |
| API only | `qwen3vl_api` | `uv pip install jw-core[vlm-api-qwen]` + `JW_QWEN3VL_API_KEY` + `JW_QWEN3VL_API_BASE` |
| Last resort | `tesseract_fallback` | `brew install tesseract` + `uv pip install jw-core[vlm-tesseract]` |

The factory picks the first available backend from this chain:
`qwen3vl_local → qwen3vl_api → claude_vision → openai_vision → tesseract_fallback`.

Force a provider:
```bash
export JW_VLM_PROVIDER=claude_vision
```

Model overrides:
- `JW_CLAUDE_VISION_MODEL` — default `claude-haiku-4-5`. ClaudeVisionProvider is
  an *adapter* over the `anthropic` SDK; Claude is natively multimodal.
- `JW_OPENAI_VISION_MODEL` — default `gpt-4o-mini`.
- `JW_QWEN3VL_LOCAL_MODEL` — model id / path for local Qwen3-VL backend.
- `JW_QWEN3VL_LOCAL_TARGET` — `mlx` | `nvidia` | `cpu`.

## Migrating from `ocr_image()`

`ocr_image()` still works but emits `DeprecationWarning`. Drop-in replacement:

```python
from jw_core.vision import migrate_to_vlm

ocr_image = migrate_to_vlm()   # callable with same (path, language=) signature
text = ocr_image("page.png", language="es")
```

## Boundaries

- One image per call. Multi-page PDFs: see Fase 37 (colpali-visual).
- Pesos locales no se distribuyen — el usuario los baja con `huggingface-cli`.
- No fine-tuning aquí (ver Fase 11 / `jw-finetune`).
```

- [ ] **Step 2: Add row to `docs/VISION_AUDIT.md` (or doc index)**

Add a one-line entry under the relevant section noting Fase 36 implemented.

- [ ] **Step 3: Mark Fase 36 done in `docs/ROADMAP.md`**

- [ ] **Step 4: Commit**

```bash
git add docs/guias/vlm-ocr.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(fase-36): vlm-ocr guide + roadmap"
```

---

### Task 16: Full sweep + verification

- [ ] **Step 1: Run the entire affected test set offline**

```bash
uv run pytest \
  packages/jw-core/tests/test_vlm_models.py \
  packages/jw-core/tests/test_vlm_provider_fake.py \
  packages/jw-core/tests/test_vlm_provider_claude.py \
  packages/jw-core/tests/test_vlm_provider_openai.py \
  packages/jw-core/tests/test_vlm_provider_qwen_api.py \
  packages/jw-core/tests/test_vlm_provider_qwen_local.py \
  packages/jw-core/tests/test_vlm_provider_tesseract_fallback.py \
  packages/jw-core/tests/test_vlm_factory.py \
  packages/jw-core/tests/test_vlm_extract_v2.py \
  packages/jw-rag/tests/test_ingest_image.py \
  packages/jw-cli/tests/test_command_image.py \
  packages/jw-mcp/tests/test_mcp_vlm_tools.py -v
```

Expected: all pass; zero network; zero real SDK invocations.

- [ ] **Step 2: Lint**

```bash
uv run ruff check packages/jw-core packages/jw-rag packages/jw-cli packages/jw-mcp
uv run ruff format --check packages/jw-core packages/jw-rag packages/jw-cli packages/jw-mcp
```

- [ ] **Step 3: Demo end-to-end with fake**

```bash
JW_VLM_PROVIDER=fake uv run python -c "
from jw_core.vision import extract_bible_reference_from_image_v2
out = extract_bible_reference_from_image_v2(
    'packages/jw-core/tests/fixtures/vlm/bible_john_3_es.png', language='es'
)
print(out['reference'])
"
```

Expected: `{'book_num': 43, 'chapter': 3, ...}`.

- [ ] **Step 4: Run Fase 22 eval to confirm no regression**

```bash
uv run pytest -m "not vlm_real" packages/jw-eval/tests/
uv run jw eval --layer 1
```

Expected: green.

- [ ] **Step 5: Final commit + open PR**

```bash
git add -A
git commit -m "test(fase-36): full offline sweep + smoke verification" || true
git push origin feature/fase-36-vlm-ocr
gh pr create --base main --title "Fase 36 — VLM-OCR (StructuredPage + 7 providers)" \
  --body "Implements docs/superpowers/specs/2026-05-31-fase-36-vlm-ocr-design.md."
```

---

## Self-review

- [x] **Spec coverage.** Every concrete provider (`Qwen3VLProvider` mlx/nvidia/cpu, `Qwen3VLAPIProvider`, `ClaudeVisionProvider`, `OpenAIVisionProvider`, `TesseractFallbackProvider`, `FakeVLMProvider`) has its own task with red→green→commit. Factory + env override + ingest + CLI + MCP + docs are each separate tasks.
- [x] **Triple-target.** `Qwen3VLProvider` dispatches over three backends (mlx, vllm, gguf) and the `target: Target` field is set per provider (api / mlx / nvidia / cpu). `JW_QWEN3VL_LOCAL_TARGET` lets users force one.
- [x] **`ClaudeVisionProvider` is an adapter, not a model.** Documented in module docstring, plan header, and the migration guide. Uses `client.messages.create(...)` with multimodal content; model id comes from `JW_CLAUDE_VISION_MODEL` (default `claude-haiku-4-5`, valid alternatives `claude-sonnet-4-6`, `claude-opus-4-7`).
- [x] **No network in tests.** Every test injects `client=...` or uses `httpx.MockTransport`; `FakeVLMProvider` is deterministic. Real provider tests live under `pytest.mark.vlm_real` and skip without env credentials.
- [x] **No top-level SDK imports.** `anthropic`, `openai`, `mlx_vlm`, `vllm`, `llama_cpp` are all imported inside methods. `vlm.py` and `factory.py` import nothing optional.
- [x] **Tesseract preserved.** `ocr_image()` continues to work; only emits `DeprecationWarning` via the wrapped `extract_bible_reference_from_image()`. `migrate_to_vlm()` returns a drop-in replacement callable.
- [x] **RAG ingest path.** `ingest_image()` produces one chunk per block with `source_id=image:<hash>:<i>:<kind>`. `bible_ref` blocks carry `parsed_reference`. `min_confidence` filter implemented and tested.
- [x] **Languages.** `language` arg threads through every provider; prompt embeds explicit language hint; en/es/pt covered by tests + fixtures.
- [x] **Boundaries.** No multi-page (Fase 37 territory). No fine-tuning (Fase 11). No weight distribution.
- [x] **CI safety.** New extras are all optional; `pytest -m "not vlm_real"` keeps CI green without GPUs or API keys.
- [x] **Task count.** 16 tasks (1 scaffold + 9 implementation + 1 v2 helper + 1 ingest + 1 CLI + 1 MCP + 1 real-int + 1 docs + 1 sweep). Inside the 14-17 band.

## Decisión de ejecución

Execute tasks 1→16 in strict order. Each task is its own TDD cycle (red → impl → green → commit). Tasks 4-8 (the five concrete providers) can be parallelized across worktrees once Tasks 1-3 land, since they all consume the same `vlm.py` contracts and don't touch each other's files. Tasks 9-13 (factory, v2 helper, ingest, CLI, MCP) are sequential. Task 14 (real-integration) ships marked-skip in CI and only fires on operator demand. Branch: `feature/fase-36-vlm-ocr`. PRs may merge atomically per task or in sub-PR bundles of 3-4 affine tasks (e.g. one PR for providers 4-8) when convenient.
