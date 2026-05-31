from __future__ import annotations

import typing

import pytest

from jw_rag.rerank_providers import Reranker, Target, get_default_reranker, list_available_rerankers


def test_target_literal_values() -> None:
    assert set(typing.get_args(Target)) == {"api", "mlx", "nvidia", "cpu"}


def test_protocol_is_runtime_checkable() -> None:
    class Dummy:
        name = "dummy"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True

        def rerank(self, query: str, candidates: list[str]) -> list[float]:
            return [1.0] * len(candidates)

    assert isinstance(Dummy(), Reranker)


def test_default_fallbacks_to_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "JW_RERANK_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")
    r = get_default_reranker()
    assert r.name == "noop"
    # NoOp preserves order — every score == 1.0
    scores = r.rerank("q", ["a", "b", "c"])
    assert scores == [1.0, 1.0, 1.0]


def test_env_override_picks_named_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_RERANK_PROVIDER", "fake-bge-v2-m3")
    r = get_default_reranker()
    assert r.name == "bge-v2-m3"


def test_list_available_returns_only_ready() -> None:
    names = [r.name for r in list_available_rerankers()]
    # NoOp is always available
    assert "noop" in names
