"""`jw verse "Juan 3:16"` — parse a reference and print canonical info + URL."""

from __future__ import annotations

import typer
from jw_core.parsers.reference import parse_reference
from rich.console import Console
from rich.table import Table

console = Console()


def verse_cmd(
    reference: str = typer.Argument(..., help="Bible reference, e.g. 'Juan 3:16'"),
    lang: str = typer.Option("es", "--lang", "-l", help="ISO code for the URL (en/es/pt)"),
) -> None:
    """Parse a Bible reference and print its canonical structure + wol.jw.org URL."""
    ref = parse_reference(reference)
    if ref is None:
        console.print(f"[red]No Bible reference detected in:[/red] {reference!r}")
        raise typer.Exit(code=1)

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan", justify="right")
    table.add_column()
    table.add_row("Reference", ref.display())
    table.add_row("Book #", str(ref.book_num))
    table.add_row("Chapter", str(ref.chapter))
    if ref.has_verse:
        table.add_row("Verse(s)", ref.verse_range)
    table.add_row("Detected lang", ref.detected_language)
    table.add_row("Matched", repr(ref.raw_match))
    console.print(table)
    console.print()
    console.print(f"[blue underline]{ref.wol_url(lang=lang)}[/blue underline]")
