"""Tests for jw_core.vision.vlm core types."""

from __future__ import annotations

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
