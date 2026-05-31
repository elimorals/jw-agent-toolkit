from __future__ import annotations

import sys
import types

import pytest

from jw_rag.rerank_providers.cohere_rerank import CohereRerankV35Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    assert CohereRerankV35Provider().is_available() is False


def test_rerank_with_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "fake")

    class StubResult:
        def __init__(self, idx: int, score: float) -> None:
            self.index = idx
            self.relevance_score = score

    class StubResponse:
        results = [StubResult(0, 0.9), StubResult(1, 0.2), StubResult(2, 0.5)]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def rerank(self, *, model: str, query: str, documents: list[str], top_n: int) -> StubResponse:
            assert top_n == len(documents)
            return StubResponse()

    fake_module = types.ModuleType("cohere")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cohere", fake_module)

    scores = CohereRerankV35Provider().rerank("q", ["a", "b", "c"])
    # Scores must be ordered to match original document order, not response order.
    assert scores == [0.9, 0.2, 0.5]


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(CohereRerankV35Provider())
