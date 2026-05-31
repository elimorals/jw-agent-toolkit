"""`jw news digest` — print a markdown digest of new jw.org content.

Usage:
    jw news digest                                  # last_run, all channels, default langs
    jw news digest --since 2026-05-23
    jw news digest --since epoch --no-update
    jw news digest --languages en,es --channels publications,programs --out digest.md
    jw news digest --json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from jw_agents.news_monitor import (
    DEFAULT_CHANNELS,
    DEFAULT_LANGUAGES,
    news_monitor,
)
from rich.console import Console

news_app = typer.Typer(
    name="news",
    help="Monitor de novedades jw.org (publicaciones, broadcasting, programas).",
    no_args_is_help=True,
    add_completion=False,
)


@news_app.callback()
def _callback() -> None:
    """JW.org news monitor — publicaciones, broadcasting, programas."""
    # Forces Typer to keep `digest` as a subcommand even when it's the only one.


console = Console()
err_console = Console(stderr=True)


def _csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return list(default)
    return [v.strip() for v in value.split(",") if v.strip()]


@news_app.command("digest")
def digest_cmd(
    since: str = typer.Option(
        "last_run",
        "--since",
        help='"last_run" (default), "epoch", or ISO date 2026-05-23.',
    ),
    languages: str = typer.Option(
        "",
        "--languages",
        "-l",
        help=f"CSV of ISO codes. Default: {','.join(DEFAULT_LANGUAGES)}.",
    ),
    channels: str = typer.Option(
        "",
        "--channels",
        "-c",
        help=f"CSV of channel names. Default: {','.join(DEFAULT_CHANNELS)}.",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write digest to file."),
    no_update: bool = typer.Option(
        False,
        "--no-update",
        help="Do not mark seen items or advance last_run (dry mode).",
    ),
    json_format: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON envelope instead of markdown.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Print a digest of new jw.org content."""

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    langs = _csv(languages, DEFAULT_LANGUAGES)
    chans = _csv(channels, DEFAULT_CHANNELS)
    invalid = [c for c in chans if c not in DEFAULT_CHANNELS]
    if invalid:
        err_console.print(f"[red]Unknown channels: {invalid}. Valid: {DEFAULT_CHANNELS}[/red]")
        raise typer.Exit(2)

    try:
        result = asyncio.run(
            news_monitor(
                since=since,
                languages=langs,
                channels=chans,
                update=not no_update,
            )
        )
    except ValueError as exc:
        err_console.print(f"[red]Invalid argument: {exc}[/red]")
        raise typer.Exit(2) from exc

    if json_format:
        payload = {
            "agent_name": result.agent_name,
            "stats": result.metadata.get("stats", {}),
            "markdown": result.metadata.get("markdown", ""),
            "warnings": result.warnings,
            "findings": [
                {
                    "summary": f.summary,
                    "url": f.citation.url,
                    "metadata": f.metadata,
                }
                for f in result.findings
            ],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = result.metadata.get("markdown", "(empty digest)")

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        err_console.print(f"[green]Wrote digest to {out}[/green]")
    console.print(text)

    if result.warnings:
        err_console.print(f"[yellow]{len(result.warnings)} warnings:[/yellow]")
        for w in result.warnings:
            err_console.print(f"  - {w}")
