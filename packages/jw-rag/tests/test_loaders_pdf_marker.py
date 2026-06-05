"""F62 — loader marker_pdf.

Test uses the synthetic PDF fixture built by `build_sample_pdf.py`. If
the optional `marker-pdf` package is not installed in the dev env the
whole file is skipped (no CI failure) via `pytest.importorskip`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "pdf" / "atalaya_sample.pdf"

pytest.importorskip(
    "marker", reason="marker-pdf not installed; opt-in extra [pdf-marker]"
)


def test_pdf_marker_ingest_returns_chunk_count(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count = ingest_pdf(store, FIXTURE, language="en")
    assert count > 0


def test_pdf_marker_source_id_uses_hash(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en")
    all_chunks = store.list_chunks()
    source_ids = {c.source_id for c in all_chunks}
    assert any(sid.startswith("pdf:") for sid in source_ids)


def test_pdf_marker_idempotent(tmp_path):
    """Re-ingest mismo PDF no duplica chunks (idempotente por hash)."""
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count1 = ingest_pdf(store, FIXTURE, language="en")
    count2 = ingest_pdf(store, FIXTURE, language="en")
    assert count1 > 0
    assert count2 == 0  # No nuevos chunks en segunda pasada


def test_pdf_marker_metadata_includes_source_kind(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en", custom_meta={"sender": "hermano_pablo"})
    chunks = store.list_chunks()
    assert any(c.metadata.get("source_kind") == "pdf_marker" for c in chunks)
    assert any(c.metadata.get("sender") == "hermano_pablo" for c in chunks)


def test_pdf_marker_detects_jw_signature(tmp_path):
    """Si el PDF contiene frases-firma JW, metadata.is_jw=True.

    El fixture sintético NO contiene firma JW → is_jw debe ser False.
    """
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en")
    chunks = store.list_chunks()
    assert all(c.metadata.get("is_jw", False) is False for c in chunks)
