"""`jw chapter 43 3 --lang en` — fetch and render a Bible chapter."""

from __future__ import annotations

import asyncio

import typer
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from rich.console import Console

console = Console()


def chapter_cmd(
    book_num: int = typer.Argument(..., help="Book number 1-66 (1=Genesis, 66=Revelation)"),
    chapter: int = typer.Argument(..., help="Chapter number"),
    lang: str = typer.Option("en", "--lang", "-l", help="ISO code (en/es/pt)"),
    publication: str = typer.Option("nwtsty", "--pub", help="Bible edition"),
    max_paragraphs: int = typer.Option(0, "--max", help="Limit paragraphs (0 = all)"),
) -> None:
    """Fetch a Bible chapter from wol.jw.org and print it."""
    if not 1 <= book_num <= 66:
        console.print(f"[red]book_num must be 1..66, got[/red] {book_num}")
        raise typer.Exit(code=1)

    async def run() -> None:
        wol = WOLClient()
        try:
            url, html = await wol.get_bible_chapter(book_num, chapter, language=lang, publication=publication)
        finally:
            await wol.aclose()
        article = parse_article(html)
        console.print(f"[bold cyan]{article.title}[/bold cyan]")
        console.print(f"[dim]{url}[/dim]\n")
        paragraphs = article.paragraphs
        if max_paragraphs > 0:
            paragraphs = paragraphs[:max_paragraphs]
        for p in paragraphs:
            console.print(p)
            console.print()

    asyncio.run(run())
