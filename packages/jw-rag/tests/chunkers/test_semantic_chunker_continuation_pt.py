"""SemanticChunker — continuation merge in Portuguese."""

from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_pt.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_pt_merges_no_entanto_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="pt_doc", metadata={"language": "pt"})
    target = [k for k in chunks if "No entanto" in k.text]
    assert len(target) == 1
    assert "Deuteronômio 6:4" in target[0].text


def test_semantic_pt_auto_detects_language_when_unspecified() -> None:
    paragraphs = [
        "A Bíblia ensina que Jeová é o único Deus verdadeiro.",
        "No entanto, há quem afirme o contrário.",
    ]
    c = SemanticChunker(max_chars=400, min_chars=20)
    chunks = c.chunk(paragraphs, source_id="pt_doc")
    assert len(chunks) == 1
    assert chunks[0].metadata.get("language_detected") == "pt"
