"""Embedder protocol + a deterministic FakeEmbedder.

Real embedders (OpenAI, sentence-transformers) live in `embed_providers.py`
and are imported lazily so the base package stays light.

The FakeEmbedder is hash-based and deterministic — same input always yields
the same vector. Useful for tests and for sanity-checking the pipeline
before plugging a real model.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class Embedder(Protocol):
    """Anything that turns texts into a (N, dim) float32 array."""

    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return a (len(texts), self.dim) float32 array of L2-normalized embeddings."""
        ...


class FakeEmbedder:
    """Deterministic hash-based embedder for tests and offline development.

    NOT semantically meaningful — but reproducible across runs and machines.
    Same text always maps to the same unit vector, so cosine similarity is
    well-defined; different texts produce uncorrelated vectors.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            out[i] = self._embed_one(text)
        return out

    def _embed_one(self, text: str) -> np.ndarray:
        # Build a vector by hashing chunks of the text deterministically.
        # We seed with multiple hashes so the vector has more than 32 bytes of
        # entropy regardless of self.dim.
        seeds: list[int] = []
        for offset in range((self.dim * 4 + 31) // 32):
            digest = hashlib.sha256(f"{offset}|{text}".encode()).digest()
            for j in range(0, 32, 4):
                seeds.append(int.from_bytes(digest[j : j + 4], "big"))
        # Map to [-1, 1] floats.
        arr = np.array(seeds[: self.dim], dtype=np.float64)
        arr = (arr / (2**32 - 1)) * 2.0 - 1.0
        # L2 normalize so cosine similarity is just a dot product.
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.astype(np.float32)


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Normalize each row of `matrix` to unit length. Safe for zero rows."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms
