"""``jw drift`` - doctrinal drift analyzer (Fase 72).

Loads chunks from a local JSONL file (one chunk per line) and runs the
analyzer. Each line must look like:

    {"text": "...", "year": 1985, "embedding": [...]}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from jw_core.drift.cluster import Chunk
from jw_core.drift.engine import analyze_doctrinal_drift

drift_app = typer.Typer(
    help="Analizador de drift doctrinal (Fase 72).",
    no_args_is_help=True,
)
console = Console()


def _load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        emb = np.asarray(d["embedding"], dtype=np.float32)
        norm = float(np.linalg.norm(emb))
        if norm > 0:
            emb = emb / norm
        chunks.append(
            Chunk(
                text=str(d.get("text", "")),
                year=int(d["year"]),
                embedding=emb.astype(np.float32),
            )
        )
    return chunks


@drift_app.command("analyze")
def cmd_analyze(
    query: str = typer.Argument(..., help="Doctrinal query / concept."),
    chunks_path: str = typer.Option(
        ..., "--chunks", help="JSONL file with text/year/embedding rows."
    ),
    language: str = typer.Option("es", "--language", "-l"),
    min_chunks_per_era: int = typer.Option(3, "--min-chunks-per-era"),
    min_delta: float = typer.Option(0.05, "--min-delta"),
    export_svg: str | None = typer.Option(
        None, "--svg", help="Export drift timeline as self-contained SVG."
    ),
) -> None:
    """Analyze drift over a local chunk corpus."""

    chunks = _load_chunks(Path(chunks_path).expanduser())
    report = analyze_doctrinal_drift(
        query=query,
        chunks=chunks,
        language=language,
        min_chunks_per_era=min_chunks_per_era,
        min_delta=min_delta,
    )
    console.print_json(report.model_dump_json())

    if export_svg:
        from jw_core.drift.svg import drift_to_svg

        out = Path(export_svg).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(drift_to_svg(report))
        console.print(f"[dim]svg exported to {out}[/]")


@drift_app.command("note")
def cmd_note(
    language: str = typer.Option("es", "--language", "-l"),
) -> None:
    """Print the explanatory 'luz creciente' note for a language."""

    from jw_core.drift.explanatory_notes import get_explanatory_note

    console.print(get_explanatory_note(language))


@drift_app.command("eras")
def cmd_eras() -> None:
    """List the decades the analyzer recognizes."""

    from jw_core.drift.models import ALL_ERAS

    table = Table(title="Recognized eras")
    table.add_column("Era")
    for era in ALL_ERAS:
        table.add_row(era)
    console.print(table)
