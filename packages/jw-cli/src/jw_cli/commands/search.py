"""`jw search "amor"` — search jw.org via the CDN API."""

from __future__ import annotations

import asyncio

import typer
from jw_core.clients.cdn import VALID_FILTERS, CDNClient
from jw_core.languages import get_language
from rich.console import Console
from rich.table import Table

console = Console()


def search_cmd(
    query: str = typer.Argument(..., help="Search terms"),
    filter_type: str = typer.Option(
        "all",
        "--filter",
        "-f",
        help=f"One of: {', '.join(sorted(VALID_FILTERS))}",
    ),
    lang: str = typer.Option("en", "--lang", "-l", help="ISO code (en/es/pt)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search jw.org content."""
    if filter_type not in VALID_FILTERS:
        console.print(f"[red]Invalid filter:[/red] {filter_type}")
        raise typer.Exit(code=1)

    try:
        language = get_language(lang)
    except KeyError:
        console.print(f"[red]Unknown language:[/red] {lang}")
        raise typer.Exit(code=1) from None

    async def run() -> None:
        cdn = CDNClient()
        try:
            data = await cdn.search(query, filter_type=filter_type, language=language.jw_code, limit=limit)
        finally:
            await cdn.aclose()

        _render_results(data, query, filter_type, lang)

    asyncio.run(run())


def _render_results(data: dict, query: str, filter_type: str, lang: str) -> None:
    results = _flatten_results(data.get("results", []))
    if not results:
        console.print(f"[yellow]No results for[/yellow] {query!r}")
        return

    console.print(
        f"[bold]Query:[/bold] {query!r}   "
        f"[bold]Filter:[/bold] {filter_type}   "
        f"[bold]Lang:[/bold] {lang}   "
        f"[bold]Results:[/bold] {len(results)}"
    )
    table = Table(show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Snippet")
    table.add_column("URL", style="blue")
    for i, r in enumerate(results, 1):
        title = (r.get("title", "") or "").strip()
        snippet = (r.get("snippet", "") or "").strip()
        url = (r.get("links", {}) or {}).get("wol") or (r.get("links", {}) or {}).get("jw.org") or ""
        table.add_row(str(i), title[:60], snippet[:80], url[:60])
    console.print(table)


def _flatten_results(results: list) -> list:
    """Flatten 'group' entries into a flat list of items."""
    flat = []
    for r in results:
        if isinstance(r, dict):
            if r.get("type") == "group":
                flat.extend(r.get("results", []))
            else:
                flat.append(r)
    return flat
