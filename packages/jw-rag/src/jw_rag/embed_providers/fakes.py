"""Deterministic Fake embed providers — one per real provider.

These are used by tests to exercise the Protocol + factory wiring without
loading any real model or touching the network. They piggy-back on the
existing FakeEmbedder hash trick but expose the same name/dim/target shape
as their real siblings, so factory code can be tested against them.
"""

from __future__ import annotations

import hashlib

import numpy as np

from jw_rag.embed_providers.factory import Target


def _hash_embed(texts: list[str], dim: int, salt: str) -> np.ndarray:
    """Deterministic L2-normalized embeddings using SHA-256 seed bytes."""
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)
    out = np.empty((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        seeds: list[int] = []
        for offset in range((dim * 4 + 31) // 32):
            digest = hashlib.sha256(f"{salt}|{offset}|{text}".encode()).digest()
            for j in range(0, 32, 4):
                seeds.append(int.from_bytes(digest[j : j + 4], "big"))
        arr = np.array(seeds[:dim], dtype=np.float64)
        arr = (arr / (2**32 - 1)) * 2.0 - 1.0
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        out[i] = arr.astype(np.float32)
    return out


class _BaseFake:
    name: str
    target: Target
    dim: int

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> np.ndarray:
        return _hash_embed(texts, self.dim, salt=self.name)


class FakeBGEM3(_BaseFake):
    name = "bge-m3"
    target: Target = "cpu"
    dim = 1024


class FakeMultilingualE5(_BaseFake):
    name = "multilingual-e5"
    target: Target = "cpu"
    dim = 1024


class FakeJinaEmbed(_BaseFake):
    name = "jina"
    target: Target = "api"
    dim = 1024


class FakeCohereEmbed(_BaseFake):
    name = "cohere"
    target: Target = "api"
    dim = 1024


class FakeVoyageEmbed(_BaseFake):
    name = "voyage"
    target: Target = "api"
    dim = 1024


class FakeOllamaEmbed(_BaseFake):
    name = "ollama"
    target: Target = "cpu"
    dim = 768
