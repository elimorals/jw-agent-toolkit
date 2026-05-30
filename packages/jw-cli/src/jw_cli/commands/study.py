"""`jw study …` — preparation + lifecycle for the current study book.

Subcommands:
  lesson    Prepare a chapter (anticipation questions + key verses).
  log       Record progress (status/note/goals) for a (student, book, lesson).
  progress  Show the student's lifecycle across the book.
  goals     Print the controlled goal taxonomy.
  directory Manage the optional alias→display-name map.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from jw_agents.study_conductor import prepare_lesson
from jw_agents.study_progress import GoalKind

study_app = typer.Typer(
    name="study",
    help="Preparación de lecciones y registro de progreso del estudiante.",
    no_args_is_help=True,
)
console = Console()


@study_app.command("goals")
def goals_cmd() -> None:
    """Lista la taxonomía controlada de metas."""

    table = Table(title="Metas del estudiante (vocabulario controlado)")
    table.add_column("kind")
    table.add_column("ejemplo de uso")
    examples = {
        "attend_meetings": "Asistir a una reunión cada semana",
        "drop_addiction_smoking": "Dejar de fumar",
        "drop_addiction_alcohol": "Reducir consumo de alcohol",
        "drop_addiction_other": "Otra adicción (en nota cifrada)",
        "pray_daily": "Orar todos los días",
        "family_worship": "Iniciar adoración en familia semanal",
        "baptism": "Calificar para el bautismo",
        "other": "Cualquier otra meta (en nota cifrada)",
    }
    for k in GoalKind:
        table.add_row(k.value, examples.get(k.value, ""))
    console.print(table)


@study_app.command("lesson")
def lesson_cmd(
    pub_code: str = typer.Argument(..., help="Código de publicación (p.ej. lff)"),
    chapter: int = typer.Argument(..., help="Número de capítulo (1-based)"),
    lang: str = typer.Option("es", "--lang", "-l", help="Idioma (es/en/pt/…)"),
) -> None:
    """Prepara una lección: preguntas de anticipación y versículos clave."""

    result = prepare_lesson(pub_code, chapter=chapter, language=lang)
    if not result.findings:
        for w in result.warnings:
            console.print(f"[yellow]⚠[/yellow] {w}")
        raise typer.Exit(code=1)

    for w in result.warnings:
        console.print(f"[yellow]⚠[/yellow] {w}")

    primary = result.findings[0]
    prep = primary.metadata.get("payload")
    if prep is None:
        console.print("[red]Salida inesperada del agente.[/red]")
        raise typer.Exit(code=2)

    console.rule(f"[bold]{prep.title}[/bold]  ({prep.pub_code} ch. {prep.chapter}, {prep.language})")
    console.print(prep.summary)
    console.print(f"\n[bold]Versículos clave:[/bold] {', '.join(prep.key_verses) or '(none)'}")
    if prep.supporting_topics:
        console.print(f"[bold]Temas relacionados:[/bold] {', '.join(prep.supporting_topics)}")

    console.print("\n[bold]Preguntas de anticipación:[/bold]")
    for q in prep.questions:
        console.print(f"  · (¶{q.paragraph_index}) {q.text}")

    console.print(f"\n[dim]Fuente: {prep.source} — {primary.citation.url}[/dim]")
