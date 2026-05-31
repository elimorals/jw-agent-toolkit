"""Embeddings-based similarity judge.

Default embedder is `FakeEmbedder`, deterministic bag-of-words token hash.
Real embedder (sentence-transformers) is loaded only if installed and selected
via factory `default_embedder()`.
"""

from __future__ import annotations

import math
import re
from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class FakeEmbedder:
    """Deterministic bag-of-words embedder. Same vocab across calls."""

    DIM = 256

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for tok in re.findall(r"\w+", text.lower()):
            vec[hash(tok) % self.DIM] += 1.0
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def default_embedder() -> Embedder:
    """Return sentence-transformers embedder if available, else FakeEmbedder."""

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError:
        return FakeEmbedder()

    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    class _STEmbedder:
        def embed(self, text: str) -> list[float]:
            return model.encode([text], normalize_embeddings=True)[0].tolist()

    return _STEmbedder()


class EmbeddingsJudge:
    """Cosine similarity over embedder output + threshold-based classification."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        threshold_pass: float = 0.78,
        threshold_review_min: float = 0.55,
    ) -> None:
        self.embedder = embedder or default_embedder()
        self.threshold_pass = threshold_pass
        self.threshold_review_min = threshold_review_min

    def cosine(self, a: str, b: str) -> float:
        va = self.embedder.embed(a)
        vb = self.embedder.embed(b)
        return sum(x * y for x, y in zip(va, vb, strict=True))

    def classify(self, score: float) -> str:
        if score >= self.threshold_pass:
            return "pass"
        if score >= self.threshold_review_min:
            return "review"
        return "fail"
