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
