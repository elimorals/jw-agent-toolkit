"""`jw jwpub` — inspect, extract, or BUILD a JWPUB.

Sub-commands:
  inspect <path>     metadata + TOC (default; --extract decrypts text).
  build <folder>     pack HTML+media as a .jwpub (F54.4, uses writers.jwpub).
"""

from __future__ import annotations

from pathlib import Path

import typer
from jw_core.parsers.jwpub import JwpubError, parse_jwpub, parse_jwpub_metadata
from jw_core.writers.jwpub import JwpubBuilder
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

jwpub_app = typer.Typer(help="Inspect or build .jwpub publications.")


@jwpub_app.command("inspect")
def jwpub_cmd(
    path: Path = typer.Argument(..., exists=True, help="Path to a .jwpub file"),
    extract: bool = typer.Option(
        False,
        "--extract",
        "-x",
        help="Decrypt + print the text of each document (slower).",
    ),
    max_docs: int = typer.Option(
        0,
        "--max",
        help="Limit output to the first N documents (0 = all).",
    ),
) -> None:
    """Inspect a JWPUB: metadata + TOC, or decrypt and print text with --extract."""
    try:
        if extract:
            pub = parse_jwpub(path)
        else:
            pub = parse_jwpub_metadata(path)
    except JwpubError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    header = (
        f"[bold cyan]{pub.title}[/bold cyan]\n"
        f"symbol={pub.symbol}  year={pub.year}  type={pub.publication_type}\n"
        f"documents={pub.document_count}  "
        f"decrypted={pub.decrypted_text_available}"
    )
    console.print(Panel(header, title=f"JWPUB · {path.name}", border_style="cyan"))

    docs = pub.documents[:max_docs] if max_docs > 0 else pub.documents

    if not extract:
        table = Table()
        table.add_column("#", justify="right", style="dim")
        table.add_column("Chapter", justify="right")
        table.add_column("Title", style="bold")
        table.add_column("Paragraphs", justify="right")
        table.add_column("Pages", justify="right")
        for d in docs:
            pages = (
                f"{d.first_page_number or '?'}-{d.last_page_number or '?'}"
                if d.first_page_number or d.last_page_number
                else ""
            )
            table.add_row(
                str(d.document_id),
                str(d.chapter_number or ""),
                (d.title or d.toc_title)[:60],
                str(d.paragraph_count),
                pages,
            )
        console.print(table)
        return

    # Extract mode: print decrypted text per document.
    for d in docs:
        if not d.paragraphs:
            continue
        console.print(
            Panel(
                "\n\n".join(d.paragraphs[:5])
                + (f"\n\n[dim]… {len(d.paragraphs) - 5} more paragraphs[/dim]" if len(d.paragraphs) > 5 else ""),
                title=f"{d.document_id}. {d.title}",
                border_style="green",
            )
        )


@jwpub_app.command("build")
def jwpub_build(
    folder: Path = typer.Argument(..., exists=True, file_okay=False, help="Folder with *.html files (+ optional same-named subfolders for media)."),
    out: Path = typer.Option(..., "--out", "-o", help="Output .jwpub path."),
    symbol: str = typer.Option(..., "--symbol", "-s", help="Publication symbol, e.g. `ex22`."),
    title: str = typer.Option(..., "--title", "-t", help="Publication title."),
    year: int = typer.Option(..., "--year", "-y", help="Publication year."),
    meps_language_index: int = typer.Option(0, "--lang", "-l", help="MEPS language id (0 = English)."),
    issue_tag_number: int = typer.Option(0, "--issue", help="Issue tag number for periodicals (e.g. w22 → 20220600)."),
) -> None:
    """Pack a folder of HTML+media into a `.jwpub` (F54.4).

    Layout expected:

        folder/
          chapter1.html
          chapter1/
            image1.jpg
            audio1.mp3
          chapter2.html

    The output is a fully-formed `.jwpub` consumable by JW Library nativo.
    """
    html_files = sorted(folder.glob("*.html"))
    if not html_files:
        console.print(f"[red]No *.html files found in {folder}[/red]")
        raise typer.Exit(code=1)

    builder = JwpubBuilder(
        symbol=symbol,
        title=title,
        year=year,
        meps_language_index=meps_language_index,
        issue_tag_number=issue_tag_number,
    )
    for html in html_files:
        media_dir = html.with_suffix("")
        media: list[Path] = []
        if media_dir.is_dir():
            for m in sorted(media_dir.iterdir()):
                if m.is_file():
                    media.append(m)
        builder.add_document(
            title=html.stem,
            content=html.read_text(encoding="utf-8"),
            media=media,
        )
    written = builder.build(out)
    console.print(f"[green]Wrote[/green] {written} ({len(html_files)} documents)")

