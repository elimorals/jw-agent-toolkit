"""Stub for Voyage embeddings — implemented in Task 9."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class VoyageMultilingualProvider:
    name = "voyage"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("VoyageMultilingualProvider not implemented yet (Task 9)")
