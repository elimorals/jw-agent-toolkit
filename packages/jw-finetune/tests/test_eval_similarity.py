"""Tests for the embedding-similarity evaluator."""

from __future__ import annotations

import json
from pathlib import Path

from jw_finetune.eval.similarity import (
    _cosine,
    evaluate_similarity,
    load_gold_set,
)


class FakeEmbedder:
    """Returns a deterministic vector per text — useful for similarity tests."""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        out = []
        for t in texts:
            h = hashlib.md5(t.encode("utf-8")).digest()
            vec = [(h[i % len(h)] - 128) / 128.0 for i in range(self.dim)]
            out.append(vec)
        return out


def test_cosine_identical_vectors() -> None:
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert abs(_cosine(a, b) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors() -> None:
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_opposite_vectors() -> None:
    assert _cosine([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_zero_vector_returns_zero() -> None:
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_evaluate_similarity_perfect_match() -> None:
    """When generate returns gold verbatim, similarity should be 1.0."""
    gold = [("Q1?", "A1."), ("Q2?", "A2.")]
    result = evaluate_similarity(
        gold,
        generate_fn=lambda p: dict(gold)[p],
        embedder=FakeEmbedder(),
    )
    assert result.n_prompts == 2
    assert abs(result.mean_similarity - 1.0) < 1e-6


def test_evaluate_similarity_handles_generator_failure() -> None:
    """If generate_fn raises, the prompt gets an empty answer."""

    def broken(p: str) -> str:
        if "fail" in p:
            raise RuntimeError("boom")
        return "ok"

    gold = [("works", "ok"), ("fail-please", "ok")]
    result = evaluate_similarity(
        gold,
        generate_fn=broken,
        embedder=FakeEmbedder(),
    )
    assert result.n_prompts == 2
    # One should have lower similarity (empty answer)
    sims = [p["similarity"] for p in result.per_prompt]
    assert sims[0] != sims[1]


def test_evaluate_similarity_empty_gold() -> None:
    result = evaluate_similarity(
        [],
        generate_fn=lambda p: "x",
        embedder=FakeEmbedder(),
    )
    assert result.n_prompts == 0
    assert result.mean_similarity == 0.0


def test_load_gold_set(tmp_path: Path) -> None:
    p = tmp_path / "gold.jsonl"
    p.write_text(
        json.dumps({"prompt": "Q1", "answer": "A1"})
        + "\n"
        + json.dumps({"question": "Q2", "gold": "A2"})
        + "\n"
        + "\n"  # blank line
        + "not-json\n"  # malformed
        + json.dumps({"prompt": "Q3", "answer": "A3"})
        + "\n",
        encoding="utf-8",
    )
    pairs = load_gold_set(p)
    assert len(pairs) == 3
    assert pairs[0] == ("Q1", "A1")
    assert pairs[1] == ("Q2", "A2")
    assert pairs[2] == ("Q3", "A3")
