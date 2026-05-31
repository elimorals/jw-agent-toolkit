"""Cohere embed-multilingual-v3.0 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_MODEL = "embed-multilingual-v3.0"


class CohereEmbedV3Provider:
    name = "cohere"
    target: Target = "api"
    dim = 1024

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("COHERE_API_KEY"):
            return False
        return importlib.util.find_spec("cohere") is not None

    def __repr__(self) -> str:
        key = os.getenv("COHERE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"CohereEmbedV3Provider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import cohere  # type: ignore[import-not-found]

            self._client = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        client = self._ensure_client()
        resp = client.embed(texts=texts, model=_MODEL, input_type="search_document")
        matrix = np.array(resp.embeddings, dtype=np.float32)
        return l2_normalize(matrix)
