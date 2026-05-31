"""Stub for Ollama embeddings — implemented in Task 10."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class OllamaEmbedProvider:
    name = "ollama"
    target: Target = "cpu"
    dim = 768

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("OllamaEmbedProvider not implemented yet (Task 10)")
