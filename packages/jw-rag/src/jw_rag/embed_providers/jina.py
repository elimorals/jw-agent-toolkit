"""Jina v3 embed provider (HTTPS, no SDK)."""

from __future__ import annotations

import os

import httpx
import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_API_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v3"


class JinaEmbeddingsV3Provider:
    name = "jina"
    target: Target = "api"
    dim = 1024

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def is_available(self) -> bool:
        return bool(os.getenv("JINA_API_KEY"))

    def __repr__(self) -> str:
        key = os.getenv("JINA_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"JinaEmbeddingsV3Provider(key={masked})"

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        key = os.getenv("JINA_API_KEY")
        if not key:
            raise RuntimeError("JINA_API_KEY not set")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": _MODEL, "input": texts}
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            r = client.post(_API_URL, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        rows = [np.array(item["embedding"], dtype=np.float32) for item in data["data"]]
        matrix = np.stack(rows, axis=0)
        return l2_normalize(matrix)
