"""Tests for embed provider factory: env override + auto-detect + fallback."""

from __future__ import annotations

import pytest
from jw_rag.embed import FakeEmbedder
from jw_rag.embed_providers import get_default_embedder, list_available_embedders


def test_env_override_picks_named_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_EMBED_PROVIDER", "fake-bge-m3")
    p = get_default_embedder()
    assert p.name == "bge-m3"
    assert p.dim == 1024


def test_env_override_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_EMBED_PROVIDER", "nope-xyz")
    with pytest.raises(ValueError, match="unknown"):
        get_default_embedder()


def test_default_falls_back_to_fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strip every relevant env var + force the registry to "no real provider available"
    for var in ("JW_EMBED_PROVIDER", "COHERE_API_KEY", "JINA_API_KEY", "VOYAGE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")  # api only; no keys → none available
    p = get_default_embedder()
    assert isinstance(p, FakeEmbedder)


def test_list_available_returns_only_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "VOYAGE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JINA_API_KEY", "test-key")
    names = [p.name for p in list_available_embedders()]
    assert "jina" in names
    assert "cohere" not in names


def test_provider_order_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PROVIDER_ORDER", "cpu,api")
    monkeypatch.delenv("JW_EMBED_PROVIDER", raising=False)
    # With cpu first and no SDKs installed, we still expect fake fallback
    # but list_available_embedders should put cpu providers before api.
    targets = [p.target for p in list_available_embedders()]
    if "cpu" in targets and "api" in targets:
        assert targets.index("cpu") < targets.index("api")
