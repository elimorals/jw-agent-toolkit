"""BAAI/bge-reranker-v2-m3 cross-encoder reranker (sentence-transformers)."""

from __future__ import annotations

import importlib.util
from typing import Any

from jw_rag.embed_providers.bge_m3 import _detect_target
from jw_rag.rerank_providers.factory import Target

_MODEL = "BAAI/bge-reranker-v2-m3"


class BGERerankerV2M3Provider:
    name = "bge-v2-m3"

    def __init__(self) -> None:
        self._target: Target | None = None
        self._model: Any = None

    @property
    def target(self) -> Target:
        if self._target is None:
            self._target = _detect_target()
        return self._target

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

            device = "mps" if self.target == "mlx" else ("cuda" if self.target == "nvidia" else "cpu")
            self._model = CrossEncoder(_MODEL, device=device)
        return self._model

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        model = self._ensure_model()
        pairs = [(query, c) for c in candidates]
        scores = model.predict(pairs)
        return [float(s) for s in scores]
