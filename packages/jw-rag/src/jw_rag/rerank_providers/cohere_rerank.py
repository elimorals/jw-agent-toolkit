"""Cohere rerank-multilingual-v3.5 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from jw_rag.rerank_providers.factory import Target

_MODEL = "rerank-multilingual-v3.5"


class CohereRerankV35Provider:
    name = "cohere-rerank"
    target: Target = "api"

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("COHERE_API_KEY"):
            return False
        return importlib.util.find_spec("cohere") is not None

    def __repr__(self) -> str:
        key = os.getenv("COHERE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"CohereRerankV35Provider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import cohere  # type: ignore[import-not-found]

            self._client = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
        return self._client

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        client = self._ensure_client()
        resp = client.rerank(
            model=_MODEL,
            query=query,
            documents=candidates,
            top_n=len(candidates),
        )
        # API returns scores indexed by reordered position; map back to input order.
        scores = [0.0] * len(candidates)
        for r in resp.results:
            scores[r.index] = float(r.relevance_score)
        return scores
