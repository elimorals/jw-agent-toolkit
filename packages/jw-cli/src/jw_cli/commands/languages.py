"""`jw languages` — list languages available on jw.org."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from jw_core.clients.mediator import MediatorClient

console = Console()


def languages_cmd(
    in_language: str = typer.Option(
        "E", "--in", help="JW code of the language to display names in (E, S, T)"
    ),
    only_with_content: bool = typer.Option(
        True, "--web/--all", help="Filter to languages with web content"
    ),
    grep: str = typer.Option(
        "", "--grep", "-g", help="Substring filter on name/vernacular"
    ),
) -> None:
    """List jw.org-supported languages with their JW codes and ISO codes."""
    async def run() -> None:
        m = MediatorClient()
        try:
            langs = await m.list_languages(in_language=in_language)
        finally:
            await m.aclose()

        filtered = [
            lang for lang in langs
            if (not only_with_content or lang.has_web_content)
            and (not grep or grep.lower() in lang.name.lower() or grep.lower() in lang.vernacular.lower())
        ]
        table = Table()
        table.add_column("JW", style="bold cyan")
        table.add_column("ISO", style="green")
        table.add_column("Name")
        table.add_column("Vernacular")
        table.add_column("RTL", justify="center")
        table.add_column("Sign", justify="center")
        for lang in filtered:
            table.add_row(
                lang.code,
                lang.locale or "—",
                lang.name,
                lang.vernacular,
                "•" if lang.rtl else "",
                "🤟" if lang.is_sign_language else "",
            )
        console.print(table)
        console.print(f"\n[dim]{len(filtered)} languages shown.[/dim]")

    asyncio.run(run())
