"""SemanticChunker — continuation merge in Spanish."""

from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers import get_chunker
from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_es.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_es_merges_sin_embargo_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="es_doc", metadata={"language": "es"})
    sin_embargo_chunks = [k for k in chunks if "Sin embargo" in k.text]
    assert len(sin_embargo_chunks) == 1
    target = sin_embargo_chunks[0]
    assert "Deuteronomio 6:4" in target.text
    assert target.metadata.get("merge_reason") == "continuation_marker"
    assert target.metadata.get("chunker") == "semantic"


def test_semantic_es_records_para_ids_in_metadata() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    paragraphs = _paragraphs()
    chunks = c.chunk(paragraphs, source_id="es_doc", metadata={"language": "es"})
    for ch in chunks:
        para_ids = ch.metadata.get("para_ids")
        assert isinstance(para_ids, list)
        assert all(isinstance(i, int) for i in para_ids)
        assert len(para_ids) >= 1


def test_semantic_es_via_get_chunker_env(monkeypatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    c = get_chunker()
    assert c.name == "semantic"


def test_semantic_es_falls_back_when_language_unknown() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(["xxxxxx yyyyy.", "zzzzz wwwww."], source_id="x")
    assert len(chunks) >= 1
    assert all(ch.metadata.get("chunker") in {"semantic", "paragraph"} for ch in chunks)
