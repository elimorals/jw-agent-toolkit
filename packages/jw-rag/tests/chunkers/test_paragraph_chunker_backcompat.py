"""Bit-for-bit equality between the legacy `chunk_paragraphs` and the new
`ParagraphChunker`. If this test fails, Fase 45 has broken something.
"""

from __future__ import annotations

import pytest

from jw_rag.chunker import Chunk as ChunkLegacy
from jw_rag.chunker import chunk_paragraphs as chunk_legacy
from jw_rag.chunkers import Chunk, ParagraphChunker, get_chunker
from jw_rag.chunkers.protocol import Chunker


def _golden_paragraphs() -> list[str]:
    return [
        "Short one.",
        "Slightly longer second paragraph that should merge.",
        "x" * 1800,
        "Final paragraph with no trailing period",
        "Tiny.",
        "And one more closing sentence to round things out.",
    ]


def test_paragraph_chunker_equivalent_to_legacy() -> None:
    paragraphs = _golden_paragraphs()
    legacy = chunk_legacy(paragraphs, source_id="src", metadata={"k": "v"})
    new = ParagraphChunker().chunk(paragraphs, source_id="src", metadata={"k": "v"})

    assert len(legacy) == len(new), (len(legacy), len(new))
    for a, b in zip(legacy, new, strict=True):
        assert a.id == b.id
        assert a.text == b.text
        assert a.source_id == b.source_id
        # ParagraphChunker adds {"chunker": "paragraph"} via setdefault.
        legacy_meta_plus = {**a.metadata, "chunker": "paragraph"}
        assert b.metadata == legacy_meta_plus


def test_legacy_chunk_class_is_new_chunk_class() -> None:
    """The façade re-exports the same Chunk symbol — no two competing classes."""

    assert ChunkLegacy is Chunk


def test_paragraph_chunker_satisfies_protocol() -> None:
    chunker: Chunker = ParagraphChunker()
    assert chunker.name == "paragraph"
    assert callable(chunker.chunk)


def test_get_chunker_default_is_paragraph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_CHUNKER", raising=False)
    c = get_chunker()
    assert c.name == "paragraph"
    assert isinstance(c, ParagraphChunker)


def test_paragraph_chunker_respects_custom_thresholds() -> None:
    """Verify that constructor thresholds propagate by comparing against
    the legacy free function with the same thresholds."""

    paragraphs = ["a" * 100, "b" * 100, "c" * 100]
    legacy = chunk_legacy(paragraphs, source_id="src", max_chars=120, min_chars=10)
    new = ParagraphChunker(max_chars=120, min_chars=10).chunk(paragraphs, source_id="src")
    assert len(legacy) == len(new)
    for a, b in zip(legacy, new, strict=True):
        assert a.text == b.text


def test_paragraph_chunker_preserves_metadata_copy() -> None:
    meta = {"kind": "article", "title": "T"}
    chunks = ParagraphChunker().chunk(["one.", "two."], source_id="s", metadata=meta)
    assert meta == {"kind": "article", "title": "T"}
    assert chunks[0].metadata["kind"] == "article"
