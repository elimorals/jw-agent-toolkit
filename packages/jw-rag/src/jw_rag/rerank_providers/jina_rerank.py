"""Jina jina-reranker-v2-base-multilingual (HTTPS, no SDK)."""

from __future__ import annotations

import os

import httpx

from jw_rag.rerank_providers.factory import Target

_API_URL = "https://api.jina.ai/v1/rerank"
_MODEL = "jina-reranker-v2-base-multilingual"


class JinaRerankerV2Provider:
    name = "jina-rerank"
    target: Target = "api"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def is_available(self) -> bool:
        return bool(os.getenv("JINA_API_KEY"))

    def __repr__(self) -> str:
        key = os.getenv("JINA_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"JinaRerankerV2Provider(key={masked})"

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        key = os.getenv("JINA_API_KEY")
        if not key:
            raise RuntimeError("JINA_API_KEY not set")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": _MODEL, "query": query, "documents": candidates, "top_n": len(candidates)}
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            r = client.post(_API_URL, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        scores = [0.0] * len(candidates)
        for item in data["results"]:
            scores[int(item["index"])] = float(item["relevance_score"])
        return scores
