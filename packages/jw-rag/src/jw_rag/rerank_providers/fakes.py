"""Deterministic Fake rerankers."""

from __future__ import annotations

import hashlib

from jw_rag.rerank_providers.factory import Target


def _hash_score(query: str, candidate: str, salt: str) -> float:
    h = hashlib.sha256(f"{salt}|{query}|{candidate}".encode()).digest()
    raw = int.from_bytes(h[:4], "big") / (2**32 - 1)
    return float(raw)


class _BaseFakeReranker:
    name: str
    target: Target

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [_hash_score(query, c, self.name) for c in candidates]


class FakeBGEReranker(_BaseFakeReranker):
    name = "bge-v2-m3"
    target: Target = "cpu"


class FakeCohereReranker(_BaseFakeReranker):
    name = "cohere-rerank"
    target: Target = "api"


class FakeJinaReranker(_BaseFakeReranker):
    name = "jina-rerank"
    target: Target = "api"
