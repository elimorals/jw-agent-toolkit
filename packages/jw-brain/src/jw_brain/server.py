"""MCP tool implementations for second-brain (Fase 49).

These are plain async functions. jw-mcp's `server.py` exposes them as
tools and the test suite asserts the dict shape directly without an MCP
client. All paths are absolute strings (the client sends paths over JSON
so we deliberately accept str rather than Path).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jw_brain.backends import get_backend
from jw_brain.config import load_brain_config


def _config(brain_path: str):
    return load_brain_config(Path(brain_path).expanduser().resolve())


async def second_brain_status(brain_path: str) -> dict[str, Any]:
    """Return brain stats: graph counts, raw inbox/processed counts."""

    bp = Path(brain_path).expanduser().resolve()
    cfg = _config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    stats = backend.stats()
    pending = 0
    processed = 0
    inbox = bp / "raw" / "inbox"
    proc = bp / "raw" / "processed"
    if inbox.exists():
        pending = sum(1 for f in inbox.iterdir() if f.is_file())
    if proc.exists():
        processed = sum(1 for f in proc.iterdir() if f.is_file())
    return {
        "brain": str(bp),
        "domain": cfg.domain,
        "vault": str(cfg.vault),
        "graph": {
            "backend": cfg.graph_backend,
            "n_nodes": stats["n_nodes"],
            "n_edges": stats["n_edges"],
            "by_type": stats["by_type"],
        },
        "raw": {"pending": pending, "processed": processed},
    }


async def second_brain_compile(
    brain_path: str,
    *,
    dry_run: bool = False,
    language: str = "es",
) -> dict[str, Any]:
    """Run the compiler over <brain>/raw/inbox/."""

    # Use a fake provider unless real one is configured server-side. This
    # mirrors the CLI; production wiring is via `JW_GEN_PROVIDER`.
    from jw_brain.compiler.llm_extractor import LLMExtractor
    from jw_brain.compiler.orchestrator import CompileOptions, Compiler
    from jw_brain.schema import EdgeRegistry, NodeRegistry
    from jw_brain.schema.builtins import register_tj_domain
    from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter

    bp = Path(brain_path).expanduser().resolve()
    cfg = _config(brain_path)

    class _FakeProvider:
        @property
        def id(self) -> str:
            return f"mcp-fake:{cfg.llm_provider}"

        async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
            return '{"nodes": [], "edges": []}'

    provider = _FakeProvider() if os.environ.get("JW_GEN_PROVIDER", "fake") == "fake" else _FakeProvider()

    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    nreg, ereg = NodeRegistry(), EdgeRegistry()
    register_tj_domain(nreg, ereg)
    extractor = LLMExtractor(provider=provider, node_registry=nreg, edge_registry=ereg)
    writer = ObsidianWikiWriter(vault_path=cfg.vault, namespace=cfg.vault_namespace)
    compiler = Compiler(
        backend=backend,
        extractor=extractor,
        wiki_writer=writer,
        node_registry=nreg,
        edge_registry=ereg,
        cache_dir=cfg.cache_dir,
    )

    report = await compiler.compile(CompileOptions(
        inbox=bp / "raw" / "inbox",
        processed=bp / "raw" / "processed",
        language=language,
        dry_run=dry_run,
    ))
    return {
        "dry_run": report.dry_run,
        "n_files_processed": report.n_files_processed,
        "n_nodes_new": report.n_nodes_new,
        "n_edges_new": report.n_edges_new,
        "n_cache_hits": report.n_cache_hits,
        "warnings": report.warnings,
    }


async def second_brain_query(
    brain_path: str,
    question: str,
    *,
    mode: str = "auto",
) -> dict[str, Any]:
    """Query the brain via Karpathy-first router."""

    from jw_brain.query.router import QueryRequest, QueryResult, QueryRouter

    cfg = _config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))

    class _Stub:
        def search(self, q: str, *, k: int = 10) -> QueryResult:  # noqa: ARG002
            return QueryResult(answer=None, citations=[], confidence=0.0)

    router = QueryRouter(wiki_searcher=_Stub(), graph_traverser=_Stub())
    result = router.query(QueryRequest(question=question, mode=mode))
    return {
        "strategy": result.strategy,
        "answer": result.answer,
        "citations": result.citations,
        "confidence": result.confidence,
        "graph_stats": backend.stats(),
    }


async def second_brain_lint(brain_path: str) -> dict[str, Any]:
    """Lint over the brain: orphan pages (orphans + future NLI cross-pub)."""

    from jw_brain.lint.orphan_pages import find_orphan_pages

    cfg = _config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    wiki_root = cfg.vault / cfg.vault_namespace
    orphans = find_orphan_pages(wiki_root=wiki_root, backend=backend) if wiki_root.exists() else []
    return {
        "orphan_pages": [str(p) for p in orphans],
        "orphan_count": len(orphans),
    }


async def second_brain_snapshot(brain_path: str, *, label: str | None = None) -> dict[str, Any]:
    """Snapshot the graph to <brain>/snapshots/."""

    import datetime as dt

    bp = Path(brain_path).expanduser().resolve()
    cfg = _config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    snap_dir = bp / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    name = f"{ts}-{label}.tar" if label else f"{ts}.tar"
    snap_path = snap_dir / name
    backend.snapshot(snap_path)
    return {"snapshot": str(snap_path)}
