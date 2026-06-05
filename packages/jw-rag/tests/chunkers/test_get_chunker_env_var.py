"""get_chunker() honors JW_CHUNKER env var with explicit precedence."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_rag.chunkers import ParagraphChunker, get_chunker
from jw_rag.chunkers.llm_chunker import LLMChunker
from jw_rag.chunkers.semantic_chunker import SemanticChunker


def test_default_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_CHUNKER", raising=False)
    assert isinstance(get_chunker(), ParagraphChunker)


def test_env_var_selects_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    assert isinstance(get_chunker(), SemanticChunker)


def test_env_var_selects_llm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_CHUNKER", "llm")
    monkeypatch.setenv("JW_CHUNK_CACHE_DIR", str(tmp_path))
    assert isinstance(get_chunker(), LLMChunker)


def test_arg_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    assert isinstance(get_chunker(name="paragraph"), ParagraphChunker)


def test_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "totally-bogus")
    with pytest.raises(ValueError, match="Unknown chunker"):
        get_chunker()


def test_ingest_article_uses_get_chunker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ingest must route through get_chunker."""

    import jw_rag.ingest as ingest_mod

    seen: dict[str, str | None] = {}

    def fake_get_chunker(name=None, **kwargs):
        seen["name"] = name
        return ParagraphChunker()

    monkeypatch.setattr(ingest_mod, "get_chunker", fake_get_chunker, raising=True)
    chunker = ingest_mod._resolve_chunker(None)
    assert chunker.name == "paragraph"
    assert "name" in seen
