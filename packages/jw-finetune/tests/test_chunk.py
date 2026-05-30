"""Tests for the records_to_chunks adapter over jw_rag.chunker."""

from __future__ import annotations

from jw_finetune.data.chunk import records_to_chunks
from jw_finetune.data.models import ParagraphRecord


def _rec(text: str, pub: str = "w24", doc: str = "001",
         lang: str = "es") -> ParagraphRecord:
    return ParagraphRecord(
        text=text, pub_code=pub, language=lang, kind="watchtower",
        source_path="x", doc_id=doc, section_ref=f"{pub} {doc}",
    )


def test_chunks_preserve_metadata() -> None:
    records = [
        _rec("Párrafo uno con suficiente texto para ser conservado."),
        _rec("Párrafo dos más largo. Tiene varias oraciones. Para chunking."),
    ]
    chunks = records_to_chunks(records, max_chars=400, min_chars=20)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.metadata["language"] == "es"
        assert c.metadata["pub_code"] == "w24"
        assert c.metadata["kind"] == "watchtower"


def test_chunks_grouped_by_source() -> None:
    records = [
        _rec("Texto pub A doc 1 con cierta cantidad de contenido aquí.", pub="w24", doc="1"),
        _rec("Texto pub A doc 2 con cierta cantidad de contenido aquí.", pub="w24", doc="2"),
        _rec("Texto pub B doc 1 con cierta cantidad de contenido aquí.", pub="g23", doc="1"),
    ]
    chunks = records_to_chunks(records, max_chars=500, min_chars=20)
    source_ids = {c.source_id for c in chunks}
    assert "w24:1" in source_ids
    assert "w24:2" in source_ids
    assert "g23:1" in source_ids


def test_chunks_empty_input() -> None:
    assert records_to_chunks([], max_chars=500, min_chars=20) == []
