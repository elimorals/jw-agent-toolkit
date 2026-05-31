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
