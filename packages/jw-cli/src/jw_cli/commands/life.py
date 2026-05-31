"""`jw life` — informational answers on life topics with citations + boundary.

This is a thin wrapper around `jw_agents.life_topics`. It never tries to
"polish" the disclaimer or hide the redirect — printing them faithfully is
part of the agent's contract.
"""

from __future__ import annotations

import asyncio
import json as _json

import typer
from jw_agents.life_topics import life_topics
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def life_cmd(
    query: str = typer.Argument(..., help='Topic or alias (e.g. "anxiety", "ansiedad", "luto").'),
    lang: str = typer.Option("en", "--lang", "-l", help="ISO language: en, es, pt."),
    top_articles: int = typer.Option(5, "--top", help="Max CDN search hits to consider."),
    fetch_top_k: int = typer.Option(3, "--fetch", help="Max articles to actually parse."),
    max_excerpts_per_article: int = typer.Option(2, "--excerpts", help="Paragraphs per article."),
    json: bool = typer.Option(False, "--json", help="Emit JSON dump of AgentResult."),
) -> None:
    """Show published material on a life topic plus the mandatory disclaimer."""

    async def run() -> None:
        result = await life_topics(
            query,
            language=lang,
            top_articles=top_articles,
            fetch_top_k=fetch_top_k,
            max_excerpts_per_article=max_excerpts_per_article,
        )

        if json:
            console.print_json(_json.dumps(result.to_dict()))
            return

        # Header
        topic_id = result.metadata.get("topic_id", "—")
        family = result.metadata.get("family", "—")
        console.print(
            Panel(
                f"[bold]Topic:[/bold] {topic_id}\n[bold]Family:[/bold] {family}\n[bold]Language:[/bold] {lang}",
                title="life_topics",
                border_style="cyan",
            )
        )

        # Sections: excerpts first, then disclaimer/redirect at the bottom.
        excerpts = [f for f in result.findings if f.metadata.get("source") in {"topic_index_entry", "cdn_search"}]
        disclaimers = [f for f in result.findings if f.metadata.get("source") == "disclaimer"]
        redirects = [f for f in result.findings if f.metadata.get("source") == "elders_redirect"]

        if excerpts:
            table = Table(title="Published material")
            table.add_column("#", justify="right", style="dim")
            table.add_column("Source")
            table.add_column("Summary")
            table.add_column("Excerpt")
            for i, f in enumerate(excerpts, 1):
                table.add_row(
                    str(i),
                    f.metadata.get("source", ""),
                    f.summary[:50],
                    (f.excerpt or "")[:100],
                )
            console.print(table)
            for f in excerpts:
                if f.citation.url:
                    console.print(f"[dim]-> {f.citation.url}[/dim]")
        else:
            console.print("[yellow]No matching published material.[/yellow]")

        for f in disclaimers:
            console.print(Panel(f.excerpt, title="Disclaimer", border_style="yellow"))
        for f in redirects:
            console.print(
                Panel(
                    f.excerpt,
                    title="Talk to your family and elders",
                    border_style="magenta",
                )
            )

        for w in result.warnings:
            console.print(f"[yellow]warn:[/yellow] {w}")

    asyncio.run(run())
