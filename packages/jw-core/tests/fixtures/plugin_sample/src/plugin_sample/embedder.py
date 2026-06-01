"""Embedder stub. Deterministic zero vectors."""

from __future__ import annotations


class SampleEmbedder:
    name = "plugin_sample_embedder"
    target = "cpu"
    dim = 8

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]
