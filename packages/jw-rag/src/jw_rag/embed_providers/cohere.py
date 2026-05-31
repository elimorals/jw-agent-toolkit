"""Stub for Cohere embeddings — implemented in Task 8."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class CohereEmbedV3Provider:
    name = "cohere"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("CohereEmbedV3Provider not implemented yet (Task 8)")
