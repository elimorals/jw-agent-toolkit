"""`jw workbook` — discover this week's meeting workbook + WT study.

Usage:
    jw workbook                        # today's week, English
    jw workbook --date 2026-07-20
    jw workbook --lang es --no-comments
"""

from __future__ import annotations

import asyncio

import typer
from jw_agents import workbook_helper
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def workbook_command(
    date: str = typer.Option("", "--date", "-d", help="ISO date (default: today)"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language code"),
    no_watchtower: bool = typer.Option(False, "--no-watchtower", help="Skip Watchtower fetch"),
    no_comments: bool = typer.Option(False, "--no-comments", help="Skip comment suggestions"),
    comments_per_paragraph: int = typer.Option(1, "--cpp", help="Comments per WT paragraph (1-3)"),
) -> None:
    """Print the week's workbook program and Watchtower study assignments."""
    result = asyncio.run(
        workbook_helper(
            date or None,
            language=language,
            include_watchtower=not no_watchtower,
            include_comments=not no_comments,
            comments_per_paragraph=max(1, min(3, comments_per_paragraph)),
        )
    )

    header = (
        f"Week of {result.metadata.get('week_of', '?')} · "
        f"Workbook [bold]{result.metadata.get('workbook_code', '?')}[/bold] · "
        f"Watchtower [bold]{result.metadata.get('watchtower_code', '—')}[/bold]"
    )
    console.print(Panel(header, title="jw workbook", border_style="cyan"))

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]⚠[/yellow] {w}")

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("source", width=22, overflow="fold")
    table.add_column("summary", overflow="fold")
    table.add_column("excerpt", overflow="fold", max_width=80)
    for f in result.findings:
        src = f.metadata.get("source", "")
        excerpt = (f.excerpt or "")[:240]
        table.add_row(src, f.summary[:80], excerpt)
    console.print(table)
