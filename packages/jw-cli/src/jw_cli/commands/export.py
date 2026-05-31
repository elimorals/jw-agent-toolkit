"""`jw export` — convert AgentResult JSON into markdown/pdf/docx/apkg."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import StudySheet
from jw_core.exporters.markdown import export_markdown


def export_cmd(
    source: Annotated[
        str,
        typer.Argument(help="Path to a JSON file with AgentResult.to_dict(), or '-' for stdin."),
    ],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: markdown | pdf | docx | apkg"),
    ] = "markdown",
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output path."),
    ] = Path("out.md"),
    title: Annotated[str | None, typer.Option("--title", help="Override the sheet title.")] = None,
    language: Annotated[str | None, typer.Option("--language", "-l", help="Override the sheet language.")] = None,
    citation_style: Annotated[
        str,
        typer.Option(
            "--citation-style",
            help="inline-paren | footnote | bibliography",
        ),
    ] = "footnote",
    include_citations: Annotated[bool, typer.Option("--include-citations/--no-citations")] = True,
    theme: Annotated[str, typer.Option("--theme", help="PDF theme: plain | study-sheet")] = "study-sheet",
    per_citation_cards: Annotated[
        bool,
        typer.Option(
            "--per-citation-cards/--no-per-citation-cards",
            help="Anki: emit one extra card per citation.",
        ),
    ] = False,
) -> None:
    """Convert an AgentResult JSON into a printable study sheet or Anki deck."""

    # Load AgentResult JSON.
    if source == "-":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            typer.secho(f"Invalid JSON on stdin: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
    else:
        path = Path(source)
        if not path.exists():
            typer.secho(f"File not found: {path}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        payload = json.loads(path.read_text(encoding="utf-8"))

    sheet = StudySheet.from_agent_result(
        payload,
        title=title,
        language=language,
        include_citations=include_citations,
    )

    try:
        if format == "markdown":
            written = export_markdown(sheet, out=out, citation_style=citation_style)
        elif format == "pdf":
            from jw_core.exporters.pdf import export_pdf  # lazy

            written = export_pdf(sheet, out=out, theme=theme)  # type: ignore[arg-type]
        elif format == "docx":
            from jw_core.exporters.docx import export_docx

            written = export_docx(sheet, out=out)
        elif format == "apkg":
            from jw_core.exporters.anki import export_apkg

            written = export_apkg(sheet, out=out, per_citation_cards=per_citation_cards)
        else:
            typer.secho(
                f"Unknown format {format!r}. Use: markdown | pdf | docx | apkg",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
    except MissingDependencyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=3)
    except ExportError as exc:
        typer.secho(f"Export failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=4)

    typer.secho(f"Wrote {written} ({written.stat().st_size} bytes)", fg=typer.colors.GREEN)
