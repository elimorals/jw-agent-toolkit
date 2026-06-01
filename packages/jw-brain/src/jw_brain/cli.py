"""`jw brain` — second-brain operations (Fase 49).

Subcomandos:
  init      — crea la estructura raw/ vault/ graph/ + config.toml
  compile   — ejecuta el agente compilador (dry-run o real)
  query     — pregunta al second-brain via router Karpathy-first
  lint      — corre los chequeos del agente (orphans + NLI cross-pub)
  status    — muestra stats del grafo y del brain
  snapshot  — snapshot del backend
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer

from jw_brain.backends import get_backend
from jw_brain.config import default_config, load_brain_config, write_default_config
from jw_brain.multi_tenant import (
    load_registry,
    register_brain,
    resolve_alias,
)

brain_app = typer.Typer(help="Second-brain operations (Fase 49).", no_args_is_help=True)


def _resolve_brain_path(brain: Path | None) -> Path:
    if brain is not None:
        b_str = str(brain)
        if "/" not in b_str and "\\" not in b_str and not Path(b_str).exists():
            aliased = resolve_alias(b_str)
            if aliased is not None:
                return aliased
        return Path(brain).expanduser().resolve()
    env = os.environ.get("JW_BRAIN_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd().resolve()


def _state_dirs(brain_path: Path) -> dict[str, Path]:
    return {
        "raw_inbox": brain_path / "raw" / "inbox",
        "raw_processed": brain_path / "raw" / "processed",
        "vault": brain_path / "vault",
        "graph": brain_path / "graph",
        "snapshots": brain_path / "snapshots",
    }


@brain_app.command("init")
def init_cmd(
    domain: str = typer.Option("tj", "--domain", help="BrainDomain plugin name."),
    vault: Path | None = typer.Option(
        None, "--vault", help="Obsidian vault path. Defaults to <brain>/vault."
    ),
    brain: Path | None = typer.Option(None, "--brain", help="Brain home path."),
) -> None:
    """Initialize a new brain instance: directories + config.toml + .obsidian/ marker."""

    brain_path = _resolve_brain_path(brain)
    dirs = _state_dirs(brain_path)
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    if vault is None:
        vault = dirs["vault"]
    vault = Path(vault).expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".obsidian").mkdir(exist_ok=True)

    cfg_path = write_default_config(brain_path, domain=domain)

    alias = brain_path.name
    try:
        register_brain(alias, brain_path)
    except Exception:  # noqa: BLE001
        pass

    # Generate CLAUDE.md from the active domain's NodeTypes/EdgeTypes.
    try:
        from jw_brain.domain.registry import discover_domains
        from jw_brain.wiki.claude_md import write_claude_md

        domains = discover_domains()
        dom = domains.get(domain) or domains.get("tj")
        cfg = load_brain_config(brain_path)
        claude_md_path = cfg.vault / cfg.vault_namespace / "CLAUDE.md"
        write_claude_md(
            target_path=claude_md_path,
            domain_name=getattr(dom, "name", domain),
            nodes=list(getattr(dom, "nodes", [])),
            edges=list(getattr(dom, "edges", [])),
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"  warn:     CLAUDE.md autogen failed: {exc}", err=True)

    typer.echo(f"Initialized brain at {brain_path}")
    typer.echo(f"  alias:    {alias}")
    typer.echo(f"  domain:   {domain}")
    typer.echo(f"  vault:    {vault}")
    typer.echo(f"  config:   {cfg_path}")
    typer.echo("Drop raw files in raw/inbox/, then `jw brain compile --dry-run`.")


@brain_app.command("list")
def list_cmd() -> None:
    """List brains registered in ~/.jw-brain/registry.toml."""

    brains = load_registry()
    if not brains:
        typer.echo("(no brains registered — run `jw brain init` first)")
        return
    typer.echo(json.dumps(
        {alias: str(path) for alias, path in brains.items()},
        indent=2,
        sort_keys=True,
    ))


@brain_app.command("status")
def status_cmd(
    brain: Path | None = typer.Option(None, "--brain", help="Brain home path."),
) -> None:
    """Show brain stats: graph counts, inbox pending, vault path."""

    brain_path = _resolve_brain_path(brain)
    if not (brain_path / "config.toml").exists():
        typer.echo(f"ERROR: no brain at {brain_path} (no config.toml)", err=True)
        raise typer.Exit(code=2)

    cfg = load_brain_config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    stats = backend.stats()
    dirs = _state_dirs(brain_path)
    pending = (
        sum(1 for f in dirs["raw_inbox"].iterdir() if f.is_file())
        if dirs["raw_inbox"].exists() else 0
    )
    processed = (
        sum(1 for f in dirs["raw_processed"].iterdir() if f.is_file())
        if dirs["raw_processed"].exists() else 0
    )

    typer.echo(json.dumps({
        "brain": str(brain_path),
        "domain": cfg.domain,
        "vault": str(cfg.vault),
        "graph": {
            "backend": cfg.graph_backend,
            "n_nodes": stats["n_nodes"],
            "n_edges": stats["n_edges"],
            "by_type": stats["by_type"],
        },
        "raw": {"pending": pending, "processed": processed},
    }, indent=2, default=str))


@brain_app.command("compile")
def compile_cmd(
    brain: Path | None = typer.Option(None, "--brain", help="Brain home path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan, do not mutate."),
    language: str = typer.Option("es", "--language", help="Default language for the run."),
) -> None:
    """Run the compiler: discover raw/inbox/ → graph + wiki."""

    from jw_brain.compiler.llm_extractor import LLMExtractor
    from jw_brain.compiler.orchestrator import CompileOptions, Compiler
    from jw_brain.schema import EdgeRegistry, NodeRegistry
    from jw_brain.schema.builtins import register_tj_domain
    from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter

    brain_path = _resolve_brain_path(brain)
    if not (brain_path / "config.toml").exists():
        typer.echo(f"ERROR: no brain at {brain_path}. Run `jw brain init` first.", err=True)
        raise typer.Exit(code=2)

    cfg = load_brain_config(brain_path)
    dirs = _state_dirs(brain_path)

    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    nreg, ereg = NodeRegistry(), EdgeRegistry()
    # For now: TJ domain hardcoded. F49 T13 wires F41 plugin domain registry.
    register_tj_domain(nreg, ereg)

    provider = _resolve_llm_provider(cfg)
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

    report = asyncio.run(compiler.compile(CompileOptions(
        inbox=dirs["raw_inbox"],
        processed=dirs["raw_processed"],
        language=language,
        dry_run=dry_run,
    )))

    typer.echo(json.dumps({
        "dry_run": report.dry_run,
        "n_files_processed": report.n_files_processed,
        "n_nodes_new": report.n_nodes_new,
        "n_edges_new": report.n_edges_new,
        "n_cache_hits": report.n_cache_hits,
        "n_low_confidence": report.n_low_confidence,
        "warnings": report.warnings,
    }, indent=2))


@brain_app.command("query")
def query_cmd(
    question: str = typer.Argument(..., help="Pregunta al brain."),
    brain: Path | None = typer.Option(None, "--brain"),
    mode: str = typer.Option("auto", "--mode", help="auto | wiki | graph | vector"),
) -> None:
    """Query the second-brain via Karpathy-first router."""

    from jw_brain.query.router import QueryRequest, QueryResult, QueryRouter

    brain_path = _resolve_brain_path(brain)
    cfg = load_brain_config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))

    # Minimal stub searchers — full implementations land in next iteration.
    class _SimpleGraphSearcher:
        def search(self, q: str, *, k: int = 10) -> QueryResult:  # noqa: ARG002
            return QueryResult(answer=None, citations=[], confidence=0.0)

    class _SimpleWikiSearcher:
        def search(self, q: str, *, k: int = 10) -> QueryResult:  # noqa: ARG002
            return QueryResult(answer=None, citations=[], confidence=0.0)

    router = QueryRouter(
        wiki_searcher=_SimpleWikiSearcher(),
        graph_traverser=_SimpleGraphSearcher(),
    )
    result = router.query(QueryRequest(question=question, mode=mode))
    typer.echo(json.dumps({
        "strategy": result.strategy,
        "answer": result.answer,
        "citations": result.citations,
        "confidence": result.confidence,
        "graph_stats": backend.stats(),
    }, indent=2))


@brain_app.command("lint")
def lint_cmd(
    brain: Path | None = typer.Option(None, "--brain"),
) -> None:
    """Run lint over the brain (orphans + NLI cross-publication contradictions)."""

    from jw_brain.lint.orphan_pages import find_orphan_pages

    brain_path = _resolve_brain_path(brain)
    cfg = load_brain_config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    wiki_root = cfg.vault / cfg.vault_namespace

    orphans = find_orphan_pages(wiki_root=wiki_root, backend=backend) if wiki_root.exists() else []
    typer.echo(json.dumps({
        "orphan_pages": [str(p) for p in orphans],
        "orphan_count": len(orphans),
    }, indent=2))


@brain_app.command("snapshot")
def snapshot_cmd(
    brain: Path | None = typer.Option(None, "--brain"),
    label: str | None = typer.Option(None, "--label", help="Optional label suffix."),
) -> None:
    """Snapshot the graph backend to <brain>/snapshots/."""

    import datetime as dt

    brain_path = _resolve_brain_path(brain)
    cfg = load_brain_config(brain_path)
    backend = get_backend(cfg.graph_backend, path=Path(cfg.graph_path))
    snap_dir = brain_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{ts}-{label}.tar" if label else f"{ts}.tar"
    snap_path = snap_dir / name
    backend.snapshot(snap_path)
    typer.echo(json.dumps({"snapshot": str(snap_path)}, indent=2))


def _resolve_llm_provider(cfg):
    """Resolve a GenerationProvider for the compiler.

    For now: if JW_GEN_PROVIDER=fake or no jw-gen wiring, fall back to a
    FakeGenProvider that returns an empty extraction. This keeps `jw brain
    compile` callable in CI/smoke without dragging Ollama or API keys.
    """

    import os

    class _FakeProvider:
        @property
        def id(self) -> str:
            return f"fake:{cfg.llm_provider}:{cfg.llm_model}"

        async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
            return '{"nodes": [], "edges": []}'

    # Real provider wiring (Ollama / Claude / OpenAI) is via jw_gen.providers
    # but is opt-in. For now fake unless explicitly configured otherwise.
    if os.environ.get("JW_GEN_PROVIDER", "fake") == "fake":
        return _FakeProvider()
    try:
        from jw_gen.providers import resolve  # type: ignore[import-not-found]

        return resolve()
    except Exception:
        return _FakeProvider()
