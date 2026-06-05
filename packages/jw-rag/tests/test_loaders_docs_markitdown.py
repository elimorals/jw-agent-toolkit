"""F62 — loader markitdown para docx/pptx/xlsx.

Skipped wholesale via `pytest.importorskip` when the optional
`markitdown` dep is absent (current default dev env). The unsupported-
extension test does NOT need markitdown installed, but for symmetry we
keep the skip at module level — once the user opts into the extra,
all four tests run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DOCX = (
    Path(__file__).parent / "fixtures" / "docs" / "programa_circuito.docx"
)

pytest.importorskip(
    "markitdown", reason="markitdown not installed; opt-in [doc-markitdown]"
)


def test_ingest_docx(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    assert count > 0


def test_docx_source_id_format(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_office_doc(store, FIXTURE_DOCX, language="es")
    chunks = store.list_chunks()
    assert any(c.source_id.startswith("doc:docx:") for c in chunks)


def test_docx_idempotent(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
    from jw_rag.store import VectorStore

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count1 = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    count2 = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    assert count1 > 0 and count2 == 0


def test_unsupported_extension_raises(tmp_path):
    from jw_rag.embed import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
    from jw_rag.store import VectorStore

    fake_file = tmp_path / "thing.xyz"
    fake_file.write_text("nope")
    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    with pytest.raises(ValueError, match="unsupported extension"):
        ingest_office_doc(store, fake_file, language="es")
