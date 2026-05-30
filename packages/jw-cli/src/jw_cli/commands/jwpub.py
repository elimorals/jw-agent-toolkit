"""`jw jwpub` — inspect or extract a downloaded JWPUB file."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_core.parsers.jwpub import JwpubError, parse_jwpub, parse_jwpub_metadata

console = Console()


def jwpub_cmd(
    path: Path = typer.Argument(..., exists=True, help="Path to a .jwpub file"),
    extract: bool = typer.Option(
        False, "--extract", "-x",
        help="Decrypt + print the text of each document (slower).",
    ),
    max_docs: int = typer.Option(
        0, "--max", help="Limit output to the first N documents (0 = all).",
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
                if d.first_page_number or d.last_page_number else ""
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
        console.print(Panel(
            "\n\n".join(d.paragraphs[:5]) +
            (f"\n\n[dim]… {len(d.paragraphs) - 5} more paragraphs[/dim]"
             if len(d.paragraphs) > 5 else ""),
            title=f"{d.document_id}. {d.title}",
            border_style="green",
        ))
