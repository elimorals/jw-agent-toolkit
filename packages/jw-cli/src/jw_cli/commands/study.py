"""`jw study …` — preparation + lifecycle for the current study book.

Subcommands:
  lesson    Prepare a chapter (anticipation questions + key verses).
  log       Record progress (status/note/goals) for a (student, book, lesson).
  progress  Show the student's lifecycle across the book.
  goals     Print the controlled goal taxonomy.
  directory Manage the optional alias→display-name map.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from jw_agents.study_conductor import prepare_lesson
from jw_agents.study_progress import (
    GoalKind,
    LessonRow,
    LessonStatus,
    StudentGoal,
    StudentProgressStore,
    build_disclosure_text,
    default_salt_path,
    derive_encryptor_for_passphrase,
    looks_like_first_run,
    scan_lesson_for_crisis,
)

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


def _get_store(language: str = "es") -> StudentProgressStore:
    passphrase = os.getenv("JW_STUDY_PASSPHRASE")
    if not passphrase:
        console.print(
            "[red]Falta passphrase.[/red] "
            "Set JW_STUDY_PASSPHRASE en el entorno y vuelva a intentarlo."
        )
        raise typer.Exit(code=2)

    salt = default_salt_path()
    if looks_like_first_run(salt):
        console.print(build_disclosure_text(language=language))
        confirm = typer.confirm("¿Continuar?", default=False)
        if not confirm:
            raise typer.Exit(code=3)

    enc = derive_encryptor_for_passphrase(passphrase, salt_path=salt)
    return StudentProgressStore(encryptor=enc)


@study_app.command("log")
def log_cmd(
    student_id: str = typer.Argument(..., help="Alias del estudiante (regex [a-z0-9_-]{3,32})"),
    pub_code: str = typer.Argument(..., help="Código de publicación (lff, …)"),
    lesson: int = typer.Argument(..., help="Número de lección"),
    status: str = typer.Option("in_progress", "--status",
                                help="not_started|in_progress|completed|skipped"),
    note: str = typer.Option("", "--note", help="Nota libre (se cifra al guardar)"),
    goal: list[str] = typer.Option(None, "--goal",
                                    help="Meta de la taxonomía (repetible)"),
    target_iso: str = typer.Option(None, "--target-iso",
                                    help="ISO date (solo para --goal baptism)"),
    lang: str = typer.Option("es", "--lang", "-l"),
) -> None:
    """Registra el progreso de una lección para un estudiante."""

    try:
        row = LessonRow(
            student_id=student_id,
            book_pub=pub_code,
            lesson=lesson,
            status=LessonStatus(status),
            notes=note,
            updated_at_iso=datetime.now(timezone.utc).isoformat(),
        )
    except (ValidationError, ValueError) as e:
        console.print(f"[red]Entrada inválida:[/red] {e}")
        raise typer.Exit(code=4) from e

    if row.status == LessonStatus.IN_PROGRESS and not row.started_at_iso:
        row.started_at_iso = row.updated_at_iso
    if row.status == LessonStatus.COMPLETED and not row.completed_at_iso:
        row.completed_at_iso = row.updated_at_iso

    if goal:
        now = row.updated_at_iso
        row.goals = [
            StudentGoal(kind=GoalKind(g), set_at_iso=now,
                        target_iso=(target_iso if GoalKind(g) == GoalKind.BAPTISM else None))
            for g in goal
        ]
        if any(g.kind == GoalKind.BAPTISM for g in row.goals):
            row.baptism_target_iso = target_iso

    crisis_hits = scan_lesson_for_crisis(row, language=lang)
    if crisis_hits:
        console.print(
            "[yellow]⚠ Detectados términos de crisis "
            f"({', '.join(crisis_hits)}). Se recomienda contactar a los ancianos o un consejero.[/yellow]"
        )

    store = _get_store(language=lang)
    saved = store.upsert(row)
    console.print(f"[green]✓[/green] {saved.student_id} · {saved.book_pub} ch.{saved.lesson} → {saved.status.value}")
