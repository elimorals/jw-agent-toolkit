"""`jw translate` — translate text preserving Bible references.

Uses the NLLB-200 provider (200 languages, non-commercial). Bible refs are
masked before translation and restored in the target language.
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from jw_core.translation import translate_preserving_references
from jw_core.translation_providers import TranslationError, get_translation_provider

console = Console()


def translate_cmd(
    text: str = typer.Argument(
        None,
        help="Source text. If omitted, reads from stdin.",
    ),
    source: str = typer.Option(
        ...,
        "--from",
        "-s",
        help="Source language: ISO-639-1 (`es`) or FLORES (`spa_Latn`).",
    ),
    target: str = typer.Option(
        ...,
        "--to",
        "-t",
        help="Target language: ISO-639-1 (`en`) or FLORES (`eng_Latn`).",
    ),
    commercial: bool = typer.Option(
        False,
        "--commercial",
        help="Require a commercial-safe provider (skips NLLB CC-BY-NC).",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Force a specific provider (`nllb-200`). Default = auto.",
    ),
) -> None:
    """Translate text, keeping Bible references like `Juan 3:16` intact."""
    body = text or sys.stdin.read()
    if not body.strip():
        console.print("[red]No input text.[/red]")
        raise typer.Exit(code=1)

    try:
        prov = get_translation_provider(provider, source=source, target=target, commercial=commercial)
    except TranslationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not prov.is_commercial_safe:
        console.print(
            f"[yellow]⚠ Using {prov.name} (CC-BY-NC; non-commercial only).[/yellow]",
            highlight=False,
        )
    out = translate_preserving_references(body, source=source, target=target, provider=prov)
    console.print(out, highlight=False)
