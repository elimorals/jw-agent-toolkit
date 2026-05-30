"""`jw topic` — search the Watch Tower Publications Index by subject."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_core.clients.topic_index import TopicIndexClient, TopicIndexError

console = Console()


def topic_cmd(
    query: str = typer.Argument(..., help="Subject to look up (e.g. 'Trinity')."),
    lang: str = typer.Option("E", "--lang", "-l", help="JW language code (E, S, T)."),
    limit: int = typer.Option(5, "--limit", "-n", help="Max candidate subjects."),
    fetch_top: bool = typer.Option(
        True, "--fetch/--no-fetch",
        help="Also fetch the top subject's full page and show its subheadings.",
    ),
    max_subheadings: int = typer.Option(
        12, "--max-sub", help="Limit subheadings shown (0 = all).",
    ),
) -> None:
    """Search the WT Publications Index and print top subjects with citations."""
    async def run() -> None:
        client = TopicIndexClient()
        try:
            results = await client.search_subjects(
                query, language=lang, limit=limit
            )
            if not results:
                console.print(f"[yellow]No subjects found for[/yellow] {query!r}")
                return

            table = Table(title=f"Search: {query!r}")
            table.add_column("#", justify="right", style="dim")
            table.add_column("Score", justify="right")
            table.add_column("Title", style="bold")
            table.add_column("docid")
            for i, r in enumerate(results, 1):
                table.add_row(
                    str(i), f"{r['score']:.0f}", r["title"], r["docid"] or "—",
                )
            console.print(table)

            if not fetch_top or not results[0]["docid"]:
                return

            top = results[0]
            console.print(
                f"\n[cyan]Fetching top subject:[/cyan] {top['title']!r} "
                f"(docid={top['docid']})\n"
            )
            try:
                subject = await client.get_subject_page(top["docid"], language="en")
            except TopicIndexError as e:
                console.print(f"[red]Could not fetch subject:[/red] {e}")
                return

            console.print(Panel(
                f"[bold cyan]{subject.title}[/bold cyan]\n"
                f"subheadings={len(subject.subheadings)}  "
                f"citations={subject.total_citations}  "
                f"style={subject.style}\n"
                f"[dim]see_also:[/dim] {', '.join(subject.see_also[:5])}",
                title="Subject", border_style="cyan",
            ))

            subheads = subject.subheadings
            if max_subheadings > 0:
                subheads = subheads[:max_subheadings]
            sub_table = Table()
            sub_table.add_column("Level", justify="center")
            sub_table.add_column("Heading", style="bold")
            sub_table.add_column("Citations")
            for sh in subheads:
                level = "[green]top[/green]" if sh.is_top_level else "[dim]sub[/dim]"
                cits = "; ".join(c.text for c in sh.citations[:5])
                if len(sh.citations) > 5:
                    cits += f" [dim]… +{len(sh.citations) - 5}[/dim]"
                sub_table.add_row(level, sh.heading[:60], cits[:80])
            console.print(sub_table)
        finally:
            await client.aclose()

    asyncio.run(run())
