"""`jw grep` — literal concordance search over the local index.

Usage:
    jw grep "<phrase>"                      # search
    jw grep "<phrase>" --language es        # filter by language
    jw grep --build-index file.jwpub        # add one publication
    jw grep --build-index ~/lib --recursive # add every .epub/.jwpub under dir
    jw grep --stats                         # show index stats
"""

from __future__ import annotations

from pathlib import Path

import typer
from jw_core.concordance import (
    ConcordanceStore,
    build_index,
    concordance_search,
    default_db_path,
)
from jw_core.concordance.search import is_safe_query
from rich.console import Console
from rich.table import Table

console = Console()


def _expand_paths(paths: list[Path], recursive: bool) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            patterns = ("**/*.epub", "**/*.jwpub") if recursive else ("*.epub", "*.jwpub")
            for pattern in patterns:
                out.extend(sorted(p.glob(pattern)))
        elif p.suffix.lower() in {".epub", ".jwpub"}:
            out.append(p)
    return out


def grep_cmd(
    query: str = typer.Argument("", help="FTS5 query — use \"...\" for phrases"),
    language: str | None = typer.Option(None, "--language", "-l", help="ISO code (en/es/pt/...)"),
    source_kind: str | None = typer.Option(None, "--kind", help="'nwt' | 'jwpub' | 'epub'"),
    max_results: int = typer.Option(50, "--max", "-n", help="Cap result count"),
    build_index_paths: list[Path] = typer.Option(
        [],
        "--build-index",
        help="Path(s) to .epub/.jwpub or directories to ingest before searching",
        exists=False,
    ),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Scan directories recursively"),
    force: bool = typer.Option(False, "--force", help="Re-index even if sha256 unchanged"),
    stats: bool = typer.Option(False, "--stats", help="Print index stats and exit"),
) -> None:
    """Exact-match concordance over the local corpus."""

    db = default_db_path()

    if stats:
        store = ConcordanceStore(db_path=db)
        try:
            counts = store.stats()
            total = store.count()
        finally:
            store.close()
        if not total:
            console.print("[yellow]Concordance index is empty[/yellow]")
            return
        table = Table(title=f"Concordance index ({db})")
        table.add_column("source_kind")
        table.add_column("entries", justify="right")
        for k, n in sorted(counts.items()):
            table.add_row(k, str(n))
        table.add_row("[bold]total[/bold]", f"[bold]{total}[/bold]")
        console.print(table)
        return

    if build_index_paths:
        if not language:
            console.print("[red]--build-index requires --language[/red]")
            raise typer.Exit(code=2)
        files = _expand_paths(build_index_paths, recursive=recursive)
        if not files:
            console.print("[yellow]No .epub/.jwpub files found in given paths[/yellow]")
        n = build_index(paths=files, language=language, db_path=db, force=force)
        console.print(f"[green]Indexed[/green] {len(files)} file(s) → {n} new entry(ies)")
        if not query:
            return

    if not query:
        console.print("[yellow]Nothing to do — pass a query or --build-index or --stats[/yellow]")
        raise typer.Exit(code=2)

    if not is_safe_query(query):
        console.print(
            "[red]Regex metacharacters detected.[/red] "
            "This command supports FTS5 syntax (phrases, AND/OR/NEAR) — not regex."
        )
        raise typer.Exit(code=2)

    hits = concordance_search(
        query,
        language=language,
        source_kind=source_kind,
        max_results=max_results,
        db_path=db,
    )

    if not hits:
        console.print("[yellow]No matches[/yellow]")
        return

    table = Table(show_lines=False)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("source", style="magenta", no_wrap=True)
    table.add_column("ref", no_wrap=True)
    table.add_column("snippet")
    for i, h in enumerate(hits, start=1):
        table.add_row(str(i), h.source_kind, h.ref, h.snippet)
    console.print(table)

    # Print URL footnotes if available.
    for i, h in enumerate(hits, start=1):
        if h.url:
            console.print(f"  [{i}] {h.url}", style="dim")
