"""Tests for jw_core.integrations.meps_catalog."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_core.integrations import meps_catalog as mod
from jw_core.integrations.meps_catalog import (
    MepsCatalog,
    default_catalog_path,
)
from jw_core.models import JwpubDocument, JwpubMetadata


def _fake_meta(
    *,
    symbol: str = "bh",
    language_index: int = 0,
    title: str = "Bible Teach",
    year: int = 2014,
    publication_type: str = "Book",
    documents: list[JwpubDocument] | None = None,
) -> JwpubMetadata:
    return JwpubMetadata(
        title=title,
        short_title=title[:32],
        symbol=symbol,
        language_index=language_index,
        publication_type=publication_type,
        year=year,
        manifest_hash="h",
        schema_version=1,
        document_count=len(documents or []),
        documents=documents or [],
        source_path="/fake.jwpub",
    )


def _doc(
    *,
    document_id: int,
    meps_document_id: int | None = None,
    title: str = "",
    chapter_number: int | None = None,
) -> JwpubDocument:
    return JwpubDocument(
        document_id=document_id,
        meps_document_id=meps_document_id or document_id,
        title=title,
        toc_title=title,
        chapter_number=chapter_number,
    )


@pytest.fixture
def patched_parse(monkeypatch: pytest.MonkeyPatch):
    """Replace `parse_jwpub_metadata` with a controllable stub."""
    queued: list[JwpubMetadata] = []

    def fake(_path):  # noqa: ANN001
        if not queued:
            raise AssertionError("No fake metadata queued for parse_jwpub_metadata")
        return queued.pop(0)

    monkeypatch.setattr(mod, "parse_jwpub_metadata", fake)
    return queued


# ── default_catalog_path ────────────────────────────────────────────────


def test_default_path_uses_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_MEPS_CATALOG_PATH", str(tmp_path / "custom.db"))
    assert default_catalog_path() == tmp_path / "custom.db"


def test_default_path_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_MEPS_CATALOG_PATH", raising=False)
    p = default_catalog_path()
    assert p.name == "meps_catalog.db"
    assert ".jw-agent-toolkit" in p.parts


# ── index_jwpub ─────────────────────────────────────────────────────────


def test_index_jwpub_persists_pub_and_documents(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(
        _fake_meta(
            documents=[
                _doc(document_id=10, title="Chapter 1", chapter_number=1),
                _doc(document_id=11, title="Chapter 2", chapter_number=2),
            ]
        )
    )
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        result = cat.index_jwpub("/whatever.jwpub")
        assert result["pub_code"] == "bh"
        assert result["documents"] == 2
        pubs = cat.list_publications(pub_code="bh")
        assert len(pubs) == 1
        assert pubs[0].title == "Bible Teach"
        docs = cat.find_documents(pub_code="bh")
        assert {d.chapter_number for d in docs} == {1, 2}


def test_index_jwpub_is_idempotent(tmp_path: Path, patched_parse) -> None:
    meta = _fake_meta(documents=[_doc(document_id=10, title="Ch", chapter_number=1)])
    patched_parse.extend([meta, meta])
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/p.jwpub")
        cat.index_jwpub("/p.jwpub")
        # Still one publication, one document — no duplicates.
        assert cat.stats()["publications"] == 1
        assert cat.stats()["documents"] == 1


def test_index_jwpub_handles_multi_language(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(_fake_meta(language_index=0, documents=[_doc(document_id=1, title="EN")]))
    patched_parse.append(_fake_meta(language_index=4, title="La Verdad", documents=[_doc(document_id=2, title="ES")]))
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/en.jwpub")
        cat.index_jwpub("/es.jwpub")
        pubs = cat.list_publications(pub_code="bh")
        # Each language version is its own publication row.
        assert len(pubs) == 2
        assert {p.language_index for p in pubs} == {0, 4}


def test_index_jwpub_rejects_missing_symbol(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(_fake_meta(symbol="", documents=[]))
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat, pytest.raises(ValueError, match="symbol"):
        cat.index_jwpub("/broken.jwpub")


# ── find_documents / list_publications ──────────────────────────────────


def test_find_documents_by_chapter(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(
        _fake_meta(
            documents=[
                _doc(document_id=10, chapter_number=1, title="Ch1"),
                _doc(document_id=11, chapter_number=2, title="Ch2"),
                _doc(document_id=12, chapter_number=3, title="Ch3"),
            ]
        )
    )
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/p.jwpub")
        docs = cat.find_documents(pub_code="bh", chapter_number=2)
        assert len(docs) == 1
        assert docs[0].title == "Ch2"


def test_find_documents_by_meps_id(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(
        _fake_meta(
            documents=[
                _doc(document_id=10, meps_document_id=12345, title="A"),
                _doc(document_id=11, meps_document_id=67890, title="B"),
            ]
        )
    )
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/p.jwpub")
        docs = cat.find_documents(meps_document_id=67890)
        assert [d.title for d in docs] == ["B"]


# ── resolve_docid ──────────────────────────────────────────────────────


def test_resolve_docid_prefers_english_when_no_language(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(_fake_meta(language_index=4, documents=[_doc(document_id=99, title="ES")]))
    patched_parse.append(_fake_meta(language_index=0, documents=[_doc(document_id=10, title="EN")]))
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/es.jwpub")
        cat.index_jwpub("/en.jwpub")
        picked = cat.resolve_docid("bh")
        assert picked is not None
        assert picked.title == "EN"
        assert picked.language_index == 0


def test_resolve_docid_honors_explicit_language(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(_fake_meta(language_index=4, documents=[_doc(document_id=99)]))
    patched_parse.append(_fake_meta(language_index=0, documents=[_doc(document_id=10)]))
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/es.jwpub")
        cat.index_jwpub("/en.jwpub")
        picked = cat.resolve_docid("bh", language_index=4)
        assert picked is not None
        assert picked.language_index == 4


def test_resolve_docid_with_chapter(tmp_path: Path, patched_parse) -> None:
    patched_parse.append(
        _fake_meta(
            documents=[
                _doc(document_id=10, chapter_number=1),
                _doc(document_id=11, chapter_number=2),
            ]
        )
    )
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        cat.index_jwpub("/p.jwpub")
        picked = cat.resolve_docid("bh", chapter_number=2)
        assert picked is not None
        assert picked.document_id == 11


def test_resolve_docid_returns_none_when_not_found(tmp_path: Path) -> None:
    with MepsCatalog(db_path=tmp_path / "catalog.db") as cat:
        assert cat.resolve_docid("nonexistent") is None


# ── Context manager ────────────────────────────────────────────────────


def test_context_manager_opens_and_closes(tmp_path: Path) -> None:
    db = tmp_path / "catalog.db"
    with MepsCatalog(db_path=db) as cat:
        assert cat.stats()["publications"] == 0
    # File should exist after first open.
    assert db.exists()
