"""`jw omnilingual` — bootstrap + diagnose the Omnilingual ASR provider.

The provider lives in a dedicated Python 3.12 venv (fairseq2 has no cp313
wheels). This command installs / inspects / transcribes against that venv.
"""

from __future__ import annotations

from pathlib import Path

import typer
from jw_core.audio.asr_providers.omnilingual import OmnilingualProvider
from jw_core.audio.transcription import TranscriptionError
from rich.console import Console
from rich.table import Table

omnilingual_app = typer.Typer(help="Manage the Omnilingual ASR worker venv.")
console = Console()


@omnilingual_app.command("install")
def install(
    python312: str | None = typer.Option(
        None,
        "--python",
        help="Path to a Python 3.12 binary (default: first `python3.12` on PATH).",
    ),
    venv_dir: Path | None = typer.Option(
        None,
        "--venv",
        help="Where to put the venv (default: ~/.jw-core/omnilingual/venv).",
    ),
) -> None:
    """Create the dedicated 3.12 venv and install `omnilingual-asr`.

    System prerequisite: libsndfile (macOS: `brew install libsndfile`;
    Debian/Ubuntu: `apt install libsndfile1`). fairseq2 dlopen's it at import.
    """
    provider = OmnilingualProvider(venv_dir=venv_dir)
    console.print(f"[bold]Installing into[/bold] {provider.venv_dir}")
    try:
        path = provider.install(python312_executable=python312)
    except TranscriptionError as exc:
        console.print(f"[red]Install failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Done.[/green] venv at {path}")
    console.print(
        "[dim]If `jw omnilingual status` reports 'importable: no', ensure "
        "libsndfile is installed at the OS level (macOS: `brew install libsndfile`).[/dim]"
    )


@omnilingual_app.command("status")
def status(
    venv_dir: Path | None = typer.Option(None, "--venv"),
) -> None:
    """Show whether the worker venv exists and has omnilingual-asr installed."""
    provider = OmnilingualProvider(venv_dir=venv_dir)
    table = Table(show_header=False, box=None)
    table.add_row("venv dir", str(provider.venv_dir))
    table.add_row("venv python", str(provider.venv_python))
    table.add_row("python exists", "yes" if provider.venv_python.is_file() else "no")
    table.add_row("omnilingual-asr importable", "yes" if provider.is_available() else "no")
    table.add_row("default model card", provider.model_card)
    console.print(table)


@omnilingual_app.command("transcribe")
def transcribe(
    audio: Path = typer.Argument(..., exists=True, help="Audio file (WAV/FLAC/MP3)."),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language hint. ISO-639-1 (`es`) or FLORES (`spa_Latn`). Omit for auto.",
    ),
    model_card: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Omnilingual model card (default: omniASR_CTC_300M).",
    ),
) -> None:
    """Run the worker against a local audio file and print the transcript."""
    provider = OmnilingualProvider(model_card=model_card)
    try:
        result = provider.transcribe(audio, language=language)
    except TranscriptionError as exc:
        console.print(f"[red]Transcribe failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold cyan]Language:[/bold cyan] {result.language}")
    console.print(result.text)


@omnilingual_app.command("supports")
def supports(
    code: str = typer.Argument(..., help="FLORES-200 code, e.g. `quy_Latn`."),
    venv_dir: Path | None = typer.Option(None, "--venv"),
) -> None:
    """Check whether a FLORES code is in Omnilingual's supported list."""
    provider = OmnilingualProvider(venv_dir=venv_dir)
    if provider.supports_language(code):
        console.print(f"[green]yes[/green] — {code} is supported")
    else:
        console.print(f"[yellow]no[/yellow] — {code} is not in the supported list")
        raise typer.Exit(code=1)
