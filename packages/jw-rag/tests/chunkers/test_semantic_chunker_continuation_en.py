"""SemanticChunker — continuation merge in English."""

from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_en.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_en_merges_however_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="en_doc", metadata={"language": "en"})
    however_chunks = [k for k in chunks if "However" in k.text]
    assert len(however_chunks) == 1
    assert "Deuteronomy 6:4" in however_chunks[0].text
    assert however_chunks[0].metadata.get("merge_reason") == "continuation_marker"


def test_semantic_en_tolerates_max_chars_overflow_up_to_30pct() -> None:
    paragraphs = [
        "x" * 200,
        "However, additional context that should glue.",
    ]
    c = SemanticChunker(max_chars=210, min_chars=50, continuation_overflow=0.30)
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    assert len(chunks) == 1


def test_semantic_en_forces_flush_after_two_consecutive_merges() -> None:
    paragraphs = [
        "Original premise of meaningful length.",
        "However the first contrast extends the chunk.",
        "However a second contrast appears.",
        "However a third contrast must NOT keep gluing.",
    ]
    c = SemanticChunker(max_chars=400, min_chars=20)
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    assert len(chunks) >= 2
