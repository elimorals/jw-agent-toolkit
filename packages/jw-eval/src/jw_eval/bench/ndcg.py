"""NDCG@k with binary relevance and bootstrap 95 % CI.

Plain Python (no numpy) so it runs in any test env without extra deps.
"""

from __future__ import annotations

import math
import random


def dcg_at_k(relevances: list[int], k: int) -> float:
    """Discounted Cumulative Gain at rank k with binary relevances."""

    out = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        out += rel / math.log2(i + 1)
    return out


def ndcg_at_k(relevances: list[int], *, n_relevant: int, k: int) -> float:
    """Normalized DCG. n_relevant is |R|, total relevant docs in ground truth."""

    if n_relevant <= 0:
        return 0.0
    ideal_rels = [1] * min(n_relevant, k)
    idcg = dcg_at_k(ideal_rels, k)
    if idcg <= 0:
        return 0.0
    return dcg_at_k(relevances, k) / idcg


def bootstrap_ci_95(
    per_query_scores: list[float],
    *,
    n_resamples: int = 1000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap (2.5 / 97.5) for the mean of per-query NDCG."""

    if not per_query_scores:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(per_query_scores)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [per_query_scores[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return lo, hi
