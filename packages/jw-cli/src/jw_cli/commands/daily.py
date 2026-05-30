"""`jw daily` — today's daily text from wol.jw.org."""

from __future__ import annotations

import asyncio

import typer
from jw_core.clients.wol import WOLClient
from jw_core.parsers.daily_text import parse_daily_text
from rich.console import Console
from rich.panel import Panel

console = Console()


def daily_cmd(
    lang: str = typer.Option("es", "--lang", "-l", help="ISO code (en/es/pt)"),
) -> None:
    """Fetch and print today's daily text."""

    async def run() -> None:
        wol = WOLClient()
        try:
            url, html = await wol.get_today_homepage(language=lang)
        finally:
            await wol.aclose()
        text = parse_daily_text(html)
        if text is None:
            console.print(f"[red]Could not extract daily text from[/red] {url}")
            raise typer.Exit(code=1)
        body = (
            f"[bold cyan]{text.date}[/bold cyan]\n\n"
            f"[italic]{text.scripture}[/italic]\n\n"
            f"{text.commentary}\n\n"
            f"[dim]{url}[/dim]"
        )
        console.print(Panel(body, title="Daily Text", border_style="cyan"))

    asyncio.run(run())
