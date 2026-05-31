"""`jw report` — log hours / studies / meetings, then render the monthly report."""

from __future__ import annotations

import os
import sys
from datetime import date as _date
from pathlib import Path

import typer
from rich.console import Console

from jw_core.ministry.exporters import render_csv, render_markdown
from jw_core.ministry.field_report import (
    FieldReportStore,
    HoursEntry,
    StudyEntry,
    aggregate_monthly_report,
)

console = Console()
report_app = typer.Typer(name="report", help="Informe mensual de precursor (local).")


def _warn_no_encryption() -> None:
    if os.getenv("JW_PRIVACY_KEY"):
        return
    if os.getenv("JW_FIELD_DISABLE_ENCRYPTION") == "1":
        return
    console.print(
        "[yellow][!] Cifrado deshabilitado (no se encontró JW_PRIVACY_KEY).\n"
        "    Tus notas y alias se guardarán en cleartext en "
        "~/.jw-agent-toolkit/field_service.db.\n"
        "    Para habilitarlo: export JW_PRIVACY_KEY=$(jw keygen)\n"
        "    Para silenciar este aviso: export JW_FIELD_DISABLE_ENCRYPTION=1[/yellow]"
    )


def _today() -> _date:
    return _date.today()


class _RevisitsAdapter:
    """Best-effort, read-only adapter over jw_agents.RevisitStore.

    Returns 0 (and never raises) if the revisit DB is absent — keeps the
    report renderable on a fresh install.
    """

    def count_in_range(self, start: _date, end: _date) -> int:
        try:
            from jw_agents.revisit_tracker import RevisitStore
        except ImportError:
            return 0
        try:
            with RevisitStore() as store:
                rows = store.list_all()
        except Exception:  # noqa: BLE001
            return 0
        # Revisit timestamps live in `next_visit_iso` and `updated_at_unix`.
        # We use `updated_at_unix` as proxy for "interaction date" — accepted
        # by VISION.md (a revisit is a touchpoint we logged).
        import datetime as _dt

        n = 0
        for r in rows:
            ts = r.updated_at_unix or 0
            if not ts:
                continue
            d = _dt.date.fromtimestamp(ts)
            if start <= d <= end:
                n += 1
        return n


@report_app.command("log-hours")
def log_hours_cmd(
    hours: float = typer.Option(..., "--hours", "-h", help="Horas decimales (ej. 1.25)."),
    date: str = typer.Option("", "--date", "-d", help="ISO yyyy-mm-dd. Por omisión, hoy."),
    tag: str = typer.Option("", "--tag", "-t"),
    note: str = typer.Option("", "--note", "-n"),
) -> None:
    """Registrar una entrada de horas."""

    _warn_no_encryption()
    d = _date.fromisoformat(date) if date else _today()
    with FieldReportStore() as store:
        e = store.add_hours(
            HoursEntry(entry_id="", date=d, hours_decimal=hours, tag=tag or None, note=note)
        )
    console.print(f"[green]+ {e.hours_decimal}h[/green] el {e.date} (tag={e.tag}) id={e.entry_id[:8]}")


@report_app.command("log-study")
def log_study_cmd(
    student_alias: str = typer.Option(..., "--student-alias", "-s"),
    started: str = typer.Option("", "--started"),
    close: bool = typer.Option(False, "--close", help="Cerrar el estudio."),
    closed: str = typer.Option("", "--closed"),
    note: str = typer.Option("", "--note", "-n"),
) -> None:
    """Crear o cerrar un curso bíblico."""

    _warn_no_encryption()
    with FieldReportStore() as store:
        if close:
            n = store.close_study(
                student_id=student_alias,
                closed_at=_date.fromisoformat(closed) if closed else _today(),
            )
            console.print(f"[green]✓ cerrado(s) {n} estudio(s) de {student_alias}[/green]")
        else:
            s = store.upsert_study(
                StudyEntry(
                    study_id="",
                    student_id=student_alias,
                    started_at=_date.fromisoformat(started) if started else _today(),
                    note=note,
                )
            )
            console.print(f"[green]+ estudio[/green] {s.student_id} desde {s.started_at} id={s.study_id[:8]}")


@report_app.command("met-today")
def met_today_cmd(
    student_alias: str = typer.Option(..., "--student-alias", "-s"),
    date: str = typer.Option("", "--date", "-d"),
) -> None:
    """Marcar que se reunió con un estudiante hoy (o en --date)."""

    _warn_no_encryption()
    d = _date.fromisoformat(date) if date else _today()
    with FieldReportStore() as store:
        store.mark_met(student_id=student_alias, met_date=d)
    console.print(f"[green]✓ reunión con {student_alias} el {d}[/green]")


@report_app.command("show")
def show_cmd(
    month: str = typer.Option(..., "--month", "-m"),
    detail: bool = typer.Option(False, "--detail"),
) -> None:
    """Listar entradas crudas del mes."""

    with FieldReportStore() as store:
        rows = store.list_hours(month=month)
    if not rows:
        console.print(f"[dim]sin entradas en {month}[/dim]")
        return
    for r in rows:
        if detail:
            console.print(f"{r.date} {r.hours_decimal:>5.2f}h tag={r.tag or '-':<14} {r.note}")
        else:
            console.print(f"{r.date} {r.hours_decimal:>5.2f}h tag={r.tag or '-'}")


@report_app.callback(invoke_without_command=True)
def report_root(
    ctx: typer.Context,
    month: str = typer.Option("", "--month", "-m"),
    format: str = typer.Option("md", "--format", "-f", help="md|csv|pdf"),
    out: str = typer.Option("", "--out", "-o"),
) -> None:
    """Generar el informe del mes (default markdown a stdout)."""

    if ctx.invoked_subcommand is not None:
        return
    if not month:
        console.print("[red]--month YYYY-MM es requerido cuando no se usa subcomando[/red]")
        raise typer.Exit(code=2)

    with FieldReportStore() as store:
        report = aggregate_monthly_report(store, month, revisits=_RevisitsAdapter())

    if format == "md":
        body = render_markdown(report)
    elif format == "csv":
        body = render_csv(report)
    elif format == "pdf":
        out_path = Path(out or f"informe-{month}.pdf").expanduser()
        from jw_core.ministry.exporters import render_pdf

        render_pdf(report, out_path=out_path)
        console.print(f"[green]✓ PDF escrito en {out_path}[/green]")
        return
    else:
        console.print(f"[red]formato desconocido: {format}[/red]")
        raise typer.Exit(code=2)

    if out:
        Path(out).expanduser().write_text(body, encoding="utf-8")
        console.print(f"[green]✓ {format} escrito en {out}[/green]")
    else:
        sys.stdout.write(body)
