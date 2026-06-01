"""LLMChunker with a deterministic fake provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunkers.fakes import FakeChunkerProvider
from jw_rag.chunkers.llm_chunker import LLMChunker


def test_llm_chunker_applies_split_action(tmp_path: Path) -> None:
    paragraphs = [
        "Aaaa aaaa aaaa.",
        "Bbbb bbbb bbbb.",
        "Cccc cccc cccc.",
        "Dddd dddd dddd.",
    ]
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 0, "after_paragraph": 1}],
    )
    # min_chars=200 ensures the 4 short paragraphs (~15 chars each) bundle
    # into a single semantic chunk before the LLM split applies.
    chunker = LLMChunker(
        provider=provider, cache_dir=tmp_path, max_chars=10000, min_chars=200,
    )
    chunks = chunker.chunk(paragraphs, source_id="t", metadata={"language": "en"})
    assert len(chunks) == 2
    assert chunks[0].text.startswith("Aaaa")
    assert "Bbbb" in chunks[0].text
    assert chunks[1].text.startswith("Cccc")
    assert all(c.metadata.get("chunker") == "llm" for c in chunks)


def test_llm_chunker_applies_merge_action(tmp_path: Path) -> None:
    paragraphs = [
        "Para1.",
        "Para2.",
        "Para3.",
    ]
    provider = FakeChunkerProvider(
        actions=[{"op": "merge", "chunk_indices": [0, 1]}],
    )
    chunker = LLMChunker(
        provider=provider, cache_dir=tmp_path, max_chars=10, min_chars=1,
    )
    chunks = chunker.chunk(paragraphs, source_id="t", metadata={"language": "en"})
    assert len(chunks) >= 1
    first_text = chunks[0].text
    assert "Para1" in first_text
    assert "Para2" in first_text


def test_llm_chunker_records_actions_in_metadata(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(
        provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1,
    )
    chunks = chunker.chunk(
        ["A test paragraph."],
        source_id="t",
        metadata={"language": "en"},
    )
    assert chunks[0].metadata.get("chunker") == "llm"
    assert chunks[0].metadata.get("llm_actions_applied") == []


def test_llm_chunker_validates_split_index(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 99, "after_paragraph": 0}],
    )
    chunker = LLMChunker(
        provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1, strict=False,
    )
    chunks = chunker.chunk(["one."], source_id="t", metadata={"language": "en"})
    assert len(chunks) >= 1


def test_llm_chunker_raises_on_invalid_action_in_strict_mode(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 99, "after_paragraph": 0}],
    )
    chunker = LLMChunker(
        provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1, strict=True,
    )
    with pytest.raises(ValueError, match="invalid chunk_index"):
        chunker.chunk(["one."], source_id="t", metadata={"language": "en"})
