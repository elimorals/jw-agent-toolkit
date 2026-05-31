"""Stub for multilingual E5 — implemented in Task 6."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class MultilingualE5Provider:
    name = "multilingual-e5"
    target: Target = "cpu"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("MultilingualE5Provider not implemented yet (Task 6)")
