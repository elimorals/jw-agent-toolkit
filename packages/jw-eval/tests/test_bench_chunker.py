"""chunker_bench orchestration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_eval.bench.chunker_bench import (
    BenchConfig,
    BenchReport,
    load_doctrinal_queries,
    run_chunker_bench,
)


def test_load_doctrinal_queries_returns_per_language() -> None:
    path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "chunker_bench"
        / "doctrinal_queries.yaml"
    )
    qs = load_doctrinal_queries(path)
    assert len(qs) >= 10
    langs = {q.language for q in qs}
    assert {"es", "en", "pt"} <= langs


class _StubStore:
    def __init__(self, rankings: dict[str, list[str]]) -> None:
        self._rankings = rankings

    def search(self, query: str, k: int = 10) -> list[Any]:
        urls = self._rankings.get(query, [])

        class _Result:
            def __init__(self, url: str) -> None:
                self.metadata = {"source_url": url}

        return [_Result(u) for u in urls[:k]]


def test_run_chunker_bench_computes_per_language(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: es
    query: "trinidad"
    expected_citations:
      - https://example/es/trinity
  - id: q2
    language: en
    query: "trinity"
    expected_citations:
      - https://example/en/trinity
""",
        encoding="utf-8",
    )

    rankings_paragraph = {
        "trinidad": ["https://example/es/wrong"] * 9 + ["https://example/es/trinity"],
        "trinity": ["https://example/en/trinity"] + ["https://example/en/wrong"] * 9,
    }
    rankings_semantic = {
        "trinidad": ["https://example/es/trinity"] + ["https://example/es/wrong"] * 9,
        "trinity": ["https://example/en/trinity"] + ["https://example/en/wrong"] * 9,
    }
    stores = {
        "paragraph": _StubStore(rankings_paragraph),
        "semantic": _StubStore(rankings_semantic),
    }

    def store_factory(variant: str):
        return stores[variant]

    config = BenchConfig(
        variants=["paragraph", "semantic"],
        queries_path=queries_path,
        k=10,
    )
    report = run_chunker_bench(config, store_factory=store_factory)
    assert isinstance(report, BenchReport)
    es_p = report.per_language["paragraph"]["es"]["ndcg10_mean"]
    es_s = report.per_language["semantic"]["es"]["ndcg10_mean"]
    assert es_s > es_p


def test_bench_reports_delta_with_ci(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: en
    query: "x"
    expected_citations:
      - https://example/x
""",
        encoding="utf-8",
    )
    stores = {
        "paragraph": _StubStore({"x": ["https://example/wrong"] * 10}),
        "semantic": _StubStore({"x": ["https://example/x"] + ["https://example/wrong"] * 9}),
    }

    report = run_chunker_bench(
        BenchConfig(
            variants=["paragraph", "semantic"],
            queries_path=queries_path,
            k=10,
        ),
        store_factory=lambda v: stores[v],
    )
    assert "delta_semantic_vs_paragraph" in report.summary
    assert report.summary["delta_semantic_vs_paragraph"]["delta_pct"] > 0


def test_bench_skips_unknown_language_gracefully(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: zz
    query: "?"
    expected_citations:
      - https://example/q
""",
        encoding="utf-8",
    )
    stores = {"paragraph": _StubStore({"?": ["https://example/q"]})}
    report = run_chunker_bench(
        BenchConfig(variants=["paragraph"], queries_path=queries_path, k=10),
        store_factory=lambda v: stores[v],
    )
    assert "zz" in report.per_language["paragraph"]
