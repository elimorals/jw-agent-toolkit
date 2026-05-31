"""Voyage AI voyage-multilingual-2 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_MODEL = "voyage-multilingual-2"


class VoyageMultilingualProvider:
    name = "voyage"
    target: Target = "api"
    dim = 1024

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("VOYAGE_API_KEY"):
            return False
        return importlib.util.find_spec("voyageai") is not None

    def __repr__(self) -> str:
        key = os.getenv("VOYAGE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"VoyageMultilingualProvider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import voyageai  # type: ignore[import-not-found]

            self._client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        client = self._ensure_client()
        resp = client.embed(texts, model=_MODEL, input_type="document")
        matrix = np.array(resp.embeddings, dtype=np.float32)
        return l2_normalize(matrix)
