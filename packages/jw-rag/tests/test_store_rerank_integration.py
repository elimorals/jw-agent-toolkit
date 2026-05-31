"""Verify hybrid_search(rerank=True/False, reranker=...) integration.

Critical guarantees:
  1. Default call (no kwargs) with NoOpReranker output == pre-rerank top_k order.
  2. A Reranker that scores by candidate text length reorders the results.
  3. source string flips to "hybrid+rerank" when reranker active.
  4. Empty index returns [] without invoking the reranker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunker import Chunk
from jw_rag.embed import FakeEmbedder
from jw_rag.rerank_providers.factory import NoOpReranker, Reranker, Target
from jw_rag.store import VectorStore


def _store(tmp_path: Path) -> VectorStore:
    s = VectorStore(tmp_path, FakeEmbedder())
    s.add(
        [
            Chunk(id="a", text="trinity short", source_id="s1", metadata={}),
            Chunk(id="b", text="the doctrine of the trinity is taught only by humans not the bible itself", source_id="s2", metadata={}),
            Chunk(id="c", text="trinity is biblical", source_id="s3", metadata={}),
        ]
    )
    return s


class LengthReranker:
    name = "length-rerank"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [float(len(c)) for c in candidates]


def test_backwards_compat_with_noop_reranker(tmp_path: Path) -> None:
    s = _store(tmp_path)
    no_rerank = s.hybrid_search("trinity", top_k=3, rerank=False)
    with_noop = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=NoOpReranker())
    assert [h.chunk.id for h in no_rerank] == [h.chunk.id for h in with_noop]
    assert all(h.source == "hybrid" for h in no_rerank)
    assert all(h.source == "hybrid+rerank" for h in with_noop)


def test_reranker_reorders_candidates(tmp_path: Path) -> None:
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=LengthReranker())
    # LengthReranker scores by text length; longest text should be first.
    assert out[0].chunk.id == "b"
    assert out[0].source == "hybrid+rerank"


def test_reranker_protocol_isinstance() -> None:
    assert isinstance(NoOpReranker(), Reranker)


def test_empty_store_returns_empty(tmp_path: Path) -> None:
    s = VectorStore(tmp_path, FakeEmbedder())
    assert s.hybrid_search("trinity", top_k=3, rerank=True, reranker=LengthReranker()) == []


def test_candidate_pool_respected(tmp_path: Path) -> None:
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=2, candidate_pool=2, rerank=True, reranker=LengthReranker())
    assert len(out) <= 2


def test_reranker_default_falls_back_to_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When reranker=None and JW_RERANK_PROVIDER unset, fall back to NoOp behavior."""
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "JW_RERANK_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=None)
    assert len(out) == 3
    # NoOp leaves order intact and tags as hybrid+rerank.
    assert all(h.source == "hybrid+rerank" for h in out)
