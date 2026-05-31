from __future__ import annotations

import pytest

from jw_rag.rerank_providers import Reranker
from jw_rag.rerank_providers.fakes import FakeBGEReranker, FakeCohereReranker, FakeJinaReranker


@pytest.mark.parametrize("cls,expected_name", [
    (FakeBGEReranker, "bge-v2-m3"),
    (FakeCohereReranker, "cohere-rerank"),
    (FakeJinaReranker, "jina-rerank"),
])
def test_fake_satisfies_protocol(cls: type, expected_name: str) -> None:
    r = cls()
    assert isinstance(r, Reranker)
    assert r.name == expected_name
    assert r.is_available() is True


def test_fake_rerank_returns_deterministic_scores_per_query() -> None:
    r = FakeBGEReranker()
    s1 = r.rerank("trinidad", ["candidate-a", "candidate-b"])
    s2 = r.rerank("trinidad", ["candidate-a", "candidate-b"])
    assert s1 == s2
    assert len(s1) == 2


def test_fake_rerank_empty_candidates() -> None:
    r = FakeJinaReranker()
    assert r.rerank("q", []) == []
