"""`jw chunker-bench` — benchmark chunker variants on doctrinal queries.

Per-language NDCG@10 with bootstrap CI; configurable lift gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from jw_eval.bench.chunker_bench import BenchConfig, run_chunker_bench


def chunker_bench_cmd(
    variants: str = typer.Option(
        "paragraph,semantic",
        "--variants",
        help="Comma-separated chunker variants to benchmark.",
    ),
    queries: Path = typer.Option(
        Path("packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml"),
        "--queries",
        help="YAML file with doctrinal queries.",
    ),
    k: int = typer.Option(10, "--k", help="Cutoff for NDCG@k."),
    report: str = typer.Option("md", "--report", help="md | json"),
    out: Path | None = typer.Option(None, "--out", help="Write the report to this path."),
    corpus_dir: Path | None = typer.Option(
        None,
        "--corpus-dir",
        help="Directory with urls.txt to ingest before benchmarking.",
    ),
    min_lift_pct: float = typer.Option(
        10.0,
        "--min-lift",
        help="Per-language lift gate vs paragraph (default 10 %).",
    ),
) -> None:
    """Benchmark chunker variants on doctrinal queries (per-language NDCG@10)."""

    variant_list = [v.strip() for v in variants.split(",") if v.strip()]
    config = BenchConfig(variants=variant_list, queries_path=queries, k=k)

    def store_factory(variant: str):
        import os

        os.environ["JW_CHUNKER"] = variant
        return _build_corpus_store(corpus_dir, variant)

    bench = run_chunker_bench(config, store_factory=store_factory)

    if report == "md":
        rendered = _render_markdown(bench, min_lift_pct=min_lift_pct)
    else:
        rendered = json.dumps(
            {
                "per_language": bench.per_language,
                "per_query": bench.per_query,
                "summary": bench.summary,
            },
            indent=2,
            ensure_ascii=False,
        )

    if out:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(f"Wrote report to {out}")
    else:
        typer.echo(rendered)

    failures: list[str] = []
    for variant in variant_list:
        if variant == "paragraph":
            continue
        per_lang_deltas = bench.summary.get(f"delta_{variant}_vs_paragraph", {})
        for lang, payload in per_lang_deltas.items():
            if lang == "delta_pct":
                continue
            if isinstance(payload, dict) and payload.get("delta_pct", 0.0) < min_lift_pct:
                failures.append(
                    f"{variant}/{lang}: delta {payload['delta_pct']:.1f} % < {min_lift_pct:.0f} %"
                )
    if failures:
        for f in failures:
            typer.echo(f"GATE FAIL: {f}", err=True)
        raise typer.Exit(code=1)


def _build_corpus_store(corpus_dir: Path | None, variant: str) -> Any:
    """Build a VectorStore for the bench."""

    from jw_rag.store import VectorStore

    store = VectorStore(persist_dir=None)
    if corpus_dir and (corpus_dir / "urls.txt").exists():
        import asyncio

        from jw_rag.ingest import ingest_article

        urls = [
            line.strip()
            for line in (corpus_dir / "urls.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        async def _ingest_all() -> None:
            for url in urls:
                try:
                    await ingest_article(store, url, chunker=variant)
                except Exception as exc:  # noqa: BLE001
                    typer.echo(f"  warn: failed to ingest {url}: {exc}", err=True)

        asyncio.run(_ingest_all())
    return store


def _render_markdown(bench, *, min_lift_pct: float) -> str:
    lines: list[str] = []
    lines.append("# Chunker Bench Report")
    lines.append("")
    lines.append("## Per-language NDCG@10")
    lines.append("")
    lines.append("| Variant | Language | NDCG@10 mean | CI 95 % | n |")
    lines.append("|---|---|---|---|---|")
    for variant, lang_map in bench.per_language.items():
        for lang, payload in lang_map.items():
            lines.append(
                f"| {variant} | {lang} | "
                f"{payload['ndcg10_mean']:.3f} | "
                f"[{payload['ndcg10_ci_lo']:.3f}, {payload['ndcg10_ci_hi']:.3f}] | "
                f"{payload['n']} |"
            )
    lines.append("")
    lines.append(f"## Deltas vs paragraph (gate: >={min_lift_pct:.0f} % per language)")
    lines.append("")
    for key, payload in bench.summary.items():
        if not key.startswith("delta_"):
            continue
        lines.append(f"### {key}")
        for lang, info in payload.items():
            if lang == "delta_pct":
                lines.append(f"- **aggregate**: {info:+.1f} %")
            elif isinstance(info, dict):
                mark = "PASS" if info["delta_pct"] >= min_lift_pct else "FAIL"
                lines.append(
                    f"- {lang}: {info['delta_pct']:+.1f} % "
                    f"({info['baseline_mean']:.3f} -> {info['new_mean']:.3f}) — {mark}"
                )
    return "\n".join(lines)
