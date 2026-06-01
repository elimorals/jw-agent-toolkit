"""Chunker benchmark orchestrator.

Computes NDCG@10 per query, per language, per chunker variant. The
caller provides `store_factory(variant) -> VectorStore-like` so this
module stays decoupled from the real ingest pipeline.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jw_eval.bench.ndcg import bootstrap_ci_95, ndcg_at_k


@dataclass(frozen=True)
class DoctrinalQuery:
    id: str
    language: str
    query: str
    expected_citations: tuple[str, ...]


@dataclass
class BenchConfig:
    variants: list[str]
    queries_path: Path
    k: int = 10


@dataclass
class BenchReport:
    per_language: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    per_query: dict[str, dict[str, float]] = field(default_factory=dict)
    summary: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_doctrinal_queries(path: Path) -> list[DoctrinalQuery]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[DoctrinalQuery] = []
    for entry in raw.get("queries") or []:
        out.append(
            DoctrinalQuery(
                id=str(entry["id"]),
                language=str(entry["language"]),
                query=str(entry["query"]),
                expected_citations=tuple(entry.get("expected_citations") or []),
            )
        )
    return out


def _extract_urls(results: list[Any]) -> list[str]:
    out: list[str] = []
    for r in results:
        meta = getattr(r, "metadata", {}) or {}
        url = meta.get("source_url") or meta.get("citation_url")
        if url:
            out.append(url)
    return out


def _relevances(retrieved_urls: list[str], expected: tuple[str, ...]) -> list[int]:
    expected_set = set(expected)
    return [1 if u in expected_set else 0 for u in retrieved_urls]


def run_chunker_bench(
    config: BenchConfig,
    *,
    store_factory: Callable[[str], Any],
) -> BenchReport:
    queries = load_doctrinal_queries(config.queries_path)
    report = BenchReport()

    variant_lang_scores: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for variant in config.variants:
        store = store_factory(variant)
        report.per_query[variant] = {}
        for q in queries:
            results = store.search(q.query, k=config.k)
            urls = _extract_urls(results)
            rels = _relevances(urls, q.expected_citations)
            score = ndcg_at_k(rels, n_relevant=len(q.expected_citations), k=config.k)
            report.per_query[variant][q.id] = score
            variant_lang_scores[variant][q.language].append(score)

    for variant, lang_map in variant_lang_scores.items():
        report.per_language[variant] = {}
        for lang, scores in lang_map.items():
            mean = sum(scores) / len(scores) if scores else 0.0
            lo, hi = bootstrap_ci_95(scores, n_resamples=1000, seed=0)
            report.per_language[variant][lang] = {
                "ndcg10_mean": mean,
                "ndcg10_ci_lo": lo,
                "ndcg10_ci_hi": hi,
                "n": len(scores),
            }

    if "paragraph" in config.variants:
        baseline = report.per_language.get("paragraph", {})
        for variant in config.variants:
            if variant == "paragraph":
                continue
            other = report.per_language.get(variant, {})
            for lang in set(baseline) & set(other):
                base_mean = baseline[lang]["ndcg10_mean"]
                this_mean = other[lang]["ndcg10_mean"]
                if base_mean:
                    delta_pct = (this_mean - base_mean) / base_mean * 100.0
                elif this_mean > 0:
                    delta_pct = 100.0
                else:
                    delta_pct = 0.0
                report.summary.setdefault(f"delta_{variant}_vs_paragraph", {})[lang] = {
                    "delta_pct": delta_pct,
                    "baseline_mean": base_mean,
                    "new_mean": this_mean,
                }
            agg = [
                report.summary[f"delta_{variant}_vs_paragraph"][lang]["delta_pct"]
                for lang in report.summary[f"delta_{variant}_vs_paragraph"]
            ]
            report.summary[f"delta_{variant}_vs_paragraph"]["delta_pct"] = (
                sum(agg) / len(agg) if agg else 0.0
            )

    return report
