"""`jw letter --kind {letter|phone|cart} --topic ... --audience ...`.

Renders the structured scaffold returned by `letter_composer` as a
Rich table. The actual prose belongs to the publisher — this is a
calibrated starting point.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_agents.letter_composer import KINDS, letter_composer

console = Console()


def letter_cmd(
    kind: str = typer.Option(
        "letter",
        "--kind", "-k",
        help="Modality: letter | phone | cart.",
    ),
    topic: str = typer.Option(
        ...,
        "--topic", "-t",
        help="Free-form topic or question for the witnessing scaffold.",
    ),
    audience: str = typer.Option(
        "default",
        "--audience", "-a",
        help="Audience profile: default | new | religious | atheist | "
             "grieving | young | parents.",
    ),
    lang: str = typer.Option(
        "es",
        "--lang", "-l",
        help="Language code: en, es, or pt.",
    ),
    territory: str | None = typer.Option(
        None,
        "--territory",
        help="Optional cosmetic territory hint inserted in the opener.",
    ),
    jw_link: str | None = typer.Option(
        None,
        "--jw-link",
        help="Optional jw.org URL to use in the closing (overrides default).",
    ),
) -> None:
    """Compose a witnessing scaffold (letter / phone / cart)."""

    if kind not in KINDS:
        console.print(
            f"[red]Unknown kind {kind!r}. Allowed: {', '.join(KINDS)}[/red]"
        )
        raise typer.Exit(code=2)

    result = asyncio.run(
        letter_composer(
            kind=kind,  # type: ignore[arg-type]
            language=lang,
            topic_or_question=topic,
            audience=audience,
            territory_hint=territory,
            jw_link=jw_link,
        )
    )

    md = result.metadata
    header_lines = [
        f"[bold]Kind:[/bold] {md['kind']}",
        f"[bold]Audience:[/bold] {md['audience']}",
        f"[bold]Topic family:[/bold] {md['topic_family']}",
        f"[bold]Language:[/bold] {md['language']}",
    ]
    if md.get("time_target_seconds"):
        header_lines.append(
            f"[bold]Time target:[/bold] ~{md['time_target_seconds']}s"
        )
    if md.get("word_count_target"):
        header_lines.append(
            f"[bold]Word count target:[/bold] ~{md['word_count_target']}"
        )
    if md.get("territory_hint"):
        header_lines.append(
            f"[bold]Territory hint:[/bold] {md['territory_hint']}"
        )
    console.print(Panel("\n".join(header_lines), title="letter_composer"))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Section", style="bold")
    table.add_column("Content")
    for f in result.findings:
        section = (f.metadata.get("section") or "—").upper()
        table.add_row(section, f.summary)
    console.print(table)

    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  - {w}")

    console.print(
        f"\n[blue underline]{md['jw_link_suggested']}[/blue underline]"
    )
