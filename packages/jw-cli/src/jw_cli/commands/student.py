"""`jw student <kind> <topic_or_ref>` — compose a 4-section script for a
student assignment in Life and Ministry.

Examples:
    jw student bible_reading "Juan 3:16" --lang es
    jw student conversation  "creation" --audience atheist --lang en
    jw student revisit       "John 3:16" --lang en
    jw student study         "esperanza de resurrección" --audience new --lang es
"""

from __future__ import annotations

import asyncio
import json

import typer
from jw_agents import student_part_helper
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


_KIND_ALIAS = {
    "reading": "bible_reading",
    "bible_reading": "bible_reading",
    "conversation": "starting_conversation",
    "conv": "starting_conversation",
    "starting_conversation": "starting_conversation",
    "revisit": "return_visit",
    "return_visit": "return_visit",
    "study": "bible_study",
    "bible_study": "bible_study",
}


def student_command(
    kind: str = typer.Argument(..., help="bible_reading | conversation | revisit | study"),
    topic_or_ref: str = typer.Argument(..., help="Bible reference, topic, or 'this week'"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
    audience: str = typer.Option("default", "--audience", "-a", help="default | new | religious | atheist"),
    point: int | None = typer.Option(
        None, "--point", "-p", help="Override oratory point 1..50 (default: auto by month)"
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty Rich output"),
) -> None:
    """Compose a student-part script."""

    normalized_kind = _KIND_ALIAS.get(kind, kind)

    result = asyncio.run(
        student_part_helper(
            kind=normalized_kind,
            topic_or_ref=topic_or_ref,
            language=language,
            oratory_point=point,
            audience=audience,
        )
    )

    if as_json:
        console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    op = result.metadata.get("oratory_point_applied", {})
    header = (
        f"[bold]{normalized_kind}[/bold] · "
        f"audience=[cyan]{result.metadata.get('audience_used', '?')}[/cyan] · "
        f"target=[cyan]{result.metadata.get('time_target_seconds', '?')}s[/cyan] · "
        f"point=[cyan]{op.get('number', '?')} — {op.get('key_phrase', '?')}[/cyan]"
    )
    console.print(Panel(header, title="jw student", border_style="cyan"))

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]⚠[/yellow] {w}")

    table = Table(title="Script", show_lines=True)
    table.add_column("Section", style="bold")
    table.add_column("Text")
    for f in result.findings:
        table.add_row(f.metadata.get("section", "?"), f.excerpt)
    console.print(table)

    ref = result.metadata.get("resolved_reference")
    if ref:
        url = result.findings[0].citation.url if result.findings else ""
        console.print(f"[dim]Scripture:[/dim] {ref}  [link={url}]{url}[/link]")
