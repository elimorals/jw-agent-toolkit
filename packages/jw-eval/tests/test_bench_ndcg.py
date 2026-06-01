"""NDCG@10 implementation tests."""

from __future__ import annotations

import math

import pytest

from jw_eval.bench.ndcg import bootstrap_ci_95, dcg_at_k, ndcg_at_k


def test_dcg_perfect_top_k() -> None:
    rels = [1, 1, 1]
    expected = 1.0 + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    assert dcg_at_k(rels, 10) == pytest.approx(expected, abs=1e-6)


def test_ndcg_perfect_is_one() -> None:
    rels = [1, 1, 1] + [0] * 7
    assert ndcg_at_k(rels, n_relevant=3, k=10) == pytest.approx(1.0)


def test_ndcg_partial() -> None:
    rels = [0, 0, 0, 0, 1, 0, 0, 0, 1, 0]
    score = ndcg_at_k(rels, n_relevant=3, k=10)
    assert 0 < score < 1


def test_ndcg_zero_relevant() -> None:
    assert ndcg_at_k([0] * 10, n_relevant=0, k=10) == 0.0


def test_ndcg_handles_n_relevant_zero_in_ideal() -> None:
    assert ndcg_at_k([0] * 10, n_relevant=0, k=10) == 0.0


def test_bootstrap_ci_returns_bounds() -> None:
    scores = [0.5, 0.6, 0.55, 0.7, 0.65, 0.58, 0.62, 0.61, 0.6, 0.55]
    lo, hi = bootstrap_ci_95(scores, n_resamples=200, seed=42)
    assert 0.0 <= lo <= hi <= 1.0
    assert lo <= 0.6 <= hi


def test_bootstrap_ci_deterministic_with_seed() -> None:
    scores = [0.5, 0.6, 0.55]
    a = bootstrap_ci_95(scores, n_resamples=100, seed=7)
    b = bootstrap_ci_95(scores, n_resamples=100, seed=7)
    assert a == b
