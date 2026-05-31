"""`jw song` — Kingdom Songs metadata lookup (no lyrics).

Examples:
    jw song 5                       # English, song #5
    jw song 5 --lang es
    jw song week                    # this week's songs (workbook + enrich)
    jw song week --date 2026-07-13 --lang pt
"""

from __future__ import annotations

import asyncio

import typer
from jw_core.songs import SongLookupError, get_registry
from jw_core.songs.integration import enrich_with_songs
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

song_app = typer.Typer(
    name="song",
    help="Kingdom Songs metadata (no lyrics).",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={"allow_interspersed_args": True},
)


@song_app.callback()
def _root(
    ctx: typer.Context,
    number: int | None = typer.Argument(None, help="Song number (1..151)"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
) -> None:
    """Top-level: `jw song 5 --lang es`."""

    if ctx.invoked_subcommand is not None:
        return
    if number is None:
        console.print("[red]Usage:[/red] jw song <number> [--lang en|es|pt]")
        raise typer.Exit(code=2)
    _print_song(number, language)


@song_app.command("week")
def _week(
    date: str = typer.Option("", "--date", "-d", help="ISO date (default: today)"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
) -> None:
    """Print the three songs scheduled for the meeting week containing `date`."""

    from jw_agents import workbook_helper

    result = asyncio.run(workbook_helper(date or None, language=language, include_comments=False))
    enrich_with_songs(result, language=language)
    song_findings = [f for f in result.findings if f.metadata.get("source") == "kingdom_song"]
    if not song_findings:
        console.print(
            "[yellow]No song metadata found for this week. The workbook may not have declared song numbers.[/yellow]"
        )
        raise typer.Exit(code=0)

    week_of = result.metadata.get("week_of", "?")
    console.print(Panel(f"Songs for the week of [bold]{week_of}[/bold]", title="jw song week", border_style="cyan"))

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("slot", width=10)
    table.add_column("#", width=5, justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("theme", overflow="fold")
    table.add_column("scriptures", overflow="fold")
    for f in song_findings:
        meta = f.citation.metadata
        table.add_row(
            str(meta.get("slot", "")),
            str(meta.get("number", "")),
            f.citation.title,
            f.excerpt,
            ", ".join(meta.get("scriptures") or []),
        )
    console.print(table)


def _print_song(number: int, language: str) -> None:
    registry = get_registry(language)
    try:
        song = registry.lookup(number)
    except SongLookupError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    body = Table.grid(padding=(0, 2))
    body.add_column(style="bold cyan", no_wrap=True)
    body.add_column()
    body.add_row("Number", str(song.number))
    body.add_row("Title", song.title)
    body.add_row("Theme", song.theme)
    body.add_row("Scriptures", ", ".join(song.scriptures) or "—")
    body.add_row("URL", song.canonical_url or "—")
    body.add_row("Publication", song.pub_symbol)
    body.add_row("Language", song.language)
    console.print(Panel(body, title=f"Kingdom Song #{song.number}", border_style="green"))
