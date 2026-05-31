from __future__ import annotations

import json

import httpx
import pytest

from jw_rag.rerank_providers.jina_rerank import JinaRerankerV2Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert JinaRerankerV2Provider().is_available() is False


def test_is_available_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake")
    assert JinaRerankerV2Provider().is_available() is True


def test_rerank_remaps_index_to_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["query"] == "q"
        assert body["documents"] == ["a", "b", "c"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 2, "relevance_score": 0.1},
                    {"index": 0, "relevance_score": 0.9},
                    {"index": 1, "relevance_score": 0.5},
                ]
            },
        )

    p = JinaRerankerV2Provider(transport=httpx.MockTransport(handler))
    assert p.rerank("q", ["a", "b", "c"]) == [0.9, 0.5, 0.1]


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(JinaRerankerV2Provider())
