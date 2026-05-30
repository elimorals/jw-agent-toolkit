"""`jw download fg --lang E --format EPUB --out ./downloads/`."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from jw_core.clients.pub_media import PubMediaClient, PubMediaError, VALID_FORMATS

console = Console()


def download_cmd(
    pub: str = typer.Argument(..., help="Publication code (e.g. 'fg', 'nwt', 'rr')"),
    lang: str = typer.Option("E", "--lang", "-l", help="JW language code (E, S, T)"),
    file_format: str = typer.Option(
        "EPUB", "--format", "-f",
        help=f"One of: {', '.join(sorted(VALID_FORMATS))}",
    ),
    bible_book: int | None = typer.Option(
        None, "--book", help="Bible book number 1-66 (only for pub=nwt/nwtsty)"
    ),
    issue: int | None = typer.Option(
        None, "--issue", help="Issue YYYYMM (for magazines)"
    ),
    out: Path = typer.Option(
        Path("./downloads"), "--out", "-o", help="Output directory"
    ),
    list_only: bool = typer.Option(
        False, "--list", help="List available files but don't download"
    ),
) -> None:
    """Download a publication in the requested format."""
    file_format = file_format.upper()
    if file_format not in VALID_FORMATS:
        console.print(f"[red]Invalid format:[/red] {file_format}")
        raise typer.Exit(code=1)

    async def run() -> None:
        client = PubMediaClient()
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold]{task.description}[/bold]"),
                transient=True,
            ) as progress:
                progress.add_task(f"Fetching catalog for {pub!r}…", total=None)
                publication = await client.get_publication(
                    pub,
                    language=lang,
                    issue=issue,
                    bible_book=bible_book,
                    file_format=file_format,
                )

            files = publication.files_by_format(file_format)
            if not files:
                console.print(
                    f"[yellow]No {file_format} files for {pub!r} in language {lang!r}[/yellow]"
                )
                raise typer.Exit(code=2)

            console.print(
                f"[bold]{publication.pub_name or pub}[/bold] — {len(files)} {file_format} file(s)"
            )
            for f in files:
                size_mb = f.size_bytes / (1024 * 1024) if f.size_bytes else 0
                book_label = f" book={f.bible_book}" if f.bible_book else ""
                console.print(
                    f"  • {f.filename}  ({size_mb:.1f} MB){book_label}"
                )

            if list_only:
                return

            out.mkdir(parents=True, exist_ok=True)
            for f in files:
                dest = out / f.filename
                console.print(f"  [cyan]↓[/cyan] {f.filename} → {dest}")
                await client.download(f, dest)
            console.print(f"\n[green]Downloaded {len(files)} file(s) to {out}[/green]")
        except PubMediaError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1) from None
        finally:
            await client.aclose()

    asyncio.run(run())
