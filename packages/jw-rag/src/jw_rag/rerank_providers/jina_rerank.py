"""Stub for Jina reranker v2 — implemented in Task 14."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class JinaRerankerV2Provider:
    name = "jina-rerank"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("JinaRerankerV2Provider not implemented yet (Task 14)")
