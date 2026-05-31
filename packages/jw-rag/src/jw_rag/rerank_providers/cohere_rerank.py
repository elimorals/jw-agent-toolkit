"""Stub for Cohere rerank v3.5 — implemented in Task 13."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class CohereRerankV35Provider:
    name = "cohere-rerank"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("CohereRerankV35Provider not implemented yet (Task 13)")
