"""Benchmark utilities for jw-eval (NDCG@k, bootstrap CI, chunker bench)."""

from jw_eval.bench.ndcg import bootstrap_ci_95, dcg_at_k, ndcg_at_k

__all__ = ["bootstrap_ci_95", "dcg_at_k", "ndcg_at_k"]
