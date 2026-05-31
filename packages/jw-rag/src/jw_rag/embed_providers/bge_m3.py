"""Stub for BGE-M3 — implemented in Task 5."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class BGEM3Provider:
    name = "bge-m3"
    target: Target = "cpu"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("BGEM3Provider not implemented yet (Task 5)")
