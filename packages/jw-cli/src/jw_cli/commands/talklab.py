"""``jw talklab`` - coach of public speaking CLI (Fase 68)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jw_core.talk_lab.counsel_points.loader import applies_to, load_catalog
from jw_core.talk_lab.engine import TalkLabConfig, analyze_recording
from jw_core.talk_lab.history import SessionHistory
from jw_core.talk_lab.models import TalkLabReport

talklab_app = typer.Typer(
    help="Talk-lab - coach of public speaking (Fase 68).",
    no_args_is_help=True,
)
console = Console()


def _history_path() -> Path:
    return Path("~/.jw-agent-toolkit/talklab/history.sqlite").expanduser()


def _markdown(report: TalkLabReport) -> str:
    lines = [
        f"# TalkLab report - {report.part_kind}",
        f"- Language: {report.language}",
        f"- Duration: {report.duration_s:.1f}s",
        "",
        "## Prosody",
        f"- Speech rate: {report.prosody.speech_rate_wpm:.0f} wpm",
        f"- Pause count: {report.prosody.pause_count} "
        f"(total {report.prosody.pause_total_s:.1f}s)",
        f"- Fillers/min: {report.prosody.filler_per_minute:.1f}",
        "",
        "## Top 3 strengths",
        *[f"- {pid}" for pid in report.summary_top_3],
        "",
        "## 3 focus areas",
        *[f"- {pid}" for pid in report.summary_focus_3],
        "",
        "## All counsel points",
    ]
    for r in report.counsel_results:
        if not r.applies:
            continue
        lines.append(
            f"- **{r.point_id} {r.title_localized}**: "
            f"{r.score}/3 - {r.suggestion}"
        )
    return "\n".join(lines)


@talklab_app.command("analyze")
def cmd_analyze(
    recording: str = typer.Argument(..., help="Path to .wav recording"),
    kind: str = typer.Option("bible_reading", "--kind", "-k"),
    language: str = typer.Option("es", "--language", "-l"),
    llm_judge: bool = typer.Option(False, "--llm-judge"),
    track_history: bool = typer.Option(False, "--track-history"),
    export_md: str | None = typer.Option(
        None, "--export", help="Export the report as Markdown to this path."
    ),
    export_svg: str | None = typer.Option(
        None,
        "--svg",
        help="Export the report timeline as a self-contained SVG.",
    ),
    export_pdf: str | None = typer.Option(
        None,
        "--pdf",
        help="Export the report as a styled PDF (requires [pdf] extra).",
    ),
) -> None:
    """Analyze a recording and print the TalkLabReport JSON."""

    cfg = TalkLabConfig(
        part_kind=kind,  # type: ignore[arg-type]
        language=language,
        llm_judge=llm_judge,
    )
    rpt = asyncio.run(
        analyze_recording(recording_path=recording, config=cfg)
    )
    console.print_json(rpt.model_dump_json())

    if track_history:
        h = SessionHistory(_history_path())
        scores = {
            r.point_id: r.score for r in rpt.counsel_results if r.applies
        }
        h.track(
            recording_hash=hashlib.sha256(
                Path(recording).read_bytes()
            ).hexdigest()[:16],
            report_id=hashlib.sha256(
                rpt.model_dump_json().encode()
            ).hexdigest()[:12],
            scores=scores,
            part_kind=rpt.part_kind,
            language=rpt.language,
        )
        console.print("[dim]tracked to local history.sqlite[/]")

    if export_md:
        out = Path(export_md).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_markdown(rpt))
        console.print(f"[dim]exported to {out}[/]")

    if export_svg:
        from jw_core.talk_lab.svg import report_to_svg

        out_svg = Path(export_svg).expanduser()
        out_svg.parent.mkdir(parents=True, exist_ok=True)
        out_svg.write_text(report_to_svg(rpt))
        console.print(f"[dim]svg exported to {out_svg}[/]")

    if export_pdf:
        from jw_core.talk_lab.pdf_export import export_talk_lab_pdf

        out_pdf = Path(export_pdf).expanduser()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        try:
            export_talk_lab_pdf(rpt, out=out_pdf)
            console.print(f"[dim]pdf exported to {out_pdf}[/]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]pdf export failed:[/] {exc}")


@talklab_app.command("history")
def cmd_history() -> None:
    """Show local TalkLab history."""

    h = SessionHistory(_history_path())
    table = Table(title="TalkLab history")
    table.add_column("Report")
    table.add_column("Kind")
    table.add_column("Lang")
    table.add_column("Top scores")
    for row in h.list():
        top = ", ".join(
            f"{pid}={s}"
            for pid, s in sorted(
                row.scores.items(), key=lambda kv: -kv[1]
            )[:3]
        )
        table.add_row(row.report_id, row.part_kind, row.language, top)
    console.print(table)


@talklab_app.command("compare")
def cmd_compare(
    report_id_a: str = typer.Argument(...),
    report_id_b: str = typer.Argument(...),
) -> None:
    """Print delta of counsel scores between two tracked reports."""

    h = SessionHistory(_history_path())
    deltas = h.compare(report_id_a, report_id_b)
    console.print_json(json.dumps(deltas))


@talklab_app.command("counsel-points")
def cmd_counsel_points(
    language: str = typer.Option("es", "--language", "-l"),
    kind: str | None = typer.Option(None, "--kind", "-k"),
) -> None:
    """List counsel points (optionally filtered by kind)."""

    catalog = load_catalog(language)
    applicable = applies_to(kind) if kind else {p.id for p in catalog}
    title = (
        f"Counsel points ({language}, kind={kind})"
        if kind
        else f"Counsel points ({language})"
    )
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Category")
    table.add_column("Applies")
    for p in catalog:
        table.add_row(
            p.id,
            p.title_localized,
            p.category,
            "yes" if p.id in applicable else "no",
        )
    console.print(table)
