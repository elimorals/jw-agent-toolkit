"""Stub for BGE reranker v2 m3 — implemented in Task 12."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class BGERerankerV2M3Provider:
    name = "bge-v2-m3"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("BGERerankerV2M3Provider not implemented yet (Task 12)")
