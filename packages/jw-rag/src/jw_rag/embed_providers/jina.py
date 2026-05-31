"""Stub for Jina embeddings — implemented in Task 7."""

from __future__ import annotations

import os

import numpy as np

from jw_rag.embed_providers.factory import Target


class JinaEmbeddingsV3Provider:
    name = "jina"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return bool(os.getenv("JINA_API_KEY"))

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("JinaEmbeddingsV3Provider not implemented yet (Task 7)")
