"""Ollama local embed provider (httpx → http://localhost:11434).

Requires `ollama serve` running + `ollama pull nomic-embed-text`. Detected
by GET /api/tags returning 200 within 0.5s. Embeds via POST /api/embeddings
one text at a time (Ollama API doesn't batch).
"""

from __future__ import annotations

import os

import httpx
import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_DEFAULT_BASE = "http://localhost:11434"
_DEFAULT_MODEL = "nomic-embed-text"


class OllamaEmbedProvider:
    name = "ollama"
    target: Target = "cpu"
    dim = 768

    def __init__(self, *, base_url: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE)
        self.model = os.getenv("OLLAMA_EMBED_MODEL", _DEFAULT_MODEL)
        self._transport = transport

    def is_available(self) -> bool:
        try:
            with httpx.Client(transport=self._transport, timeout=0.5) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        rows: list[np.ndarray] = []
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            for text in texts:
                r = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                r.raise_for_status()
                rows.append(np.array(r.json()["embedding"], dtype=np.float32))
        return l2_normalize(np.stack(rows, axis=0))
