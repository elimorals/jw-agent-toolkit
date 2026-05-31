"""`jw eval` — run the doctrinal eval suite."""

from __future__ import annotations

from pathlib import Path

import typer
from jw_eval.cli import run_from_cli
from jw_eval.models import LayerName
from jw_eval.report import to_json, to_markdown


def eval_cmd(
    layer: str = typer.Option("1,2", "--layer", help="Comma-separated layer numbers: 1, 2, 3"),
    cases_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/golden_qa"),
        "--cases",
        help="Path to golden_qa root.",
    ),
    snapshots_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/wol_snapshots"),
        "--snapshots",
        help="Path to wol HTML snapshots.",
    ),
    live: bool = typer.Option(False, "--live", help="Use live HTTP for L2 instead of snapshots."),
    agent_filter: str | None = typer.Option(None, "--filter-agent", help="Run only cases for this agent."),
    report: str = typer.Option("md", "--report", help="md | json"),
    out: Path | None = typer.Option(None, "--out", help="Write report to file instead of stdout."),
) -> None:
    layers: list[LayerName] = []
    for ch in layer.split(","):
        n = int(ch.strip())
        layers.append(f"l{n}")  # type: ignore[arg-type]

    suite_report = run_from_cli(
        cases_root=cases_root,
        snapshots_root=snapshots_root,
        layers=layers,
        agent_filter=agent_filter,
        live=live,
    )

    text = to_markdown(suite_report) if report == "md" else to_json(suite_report)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(text)

    # Exit code = number of failures (caps at 125 to keep within POSIX bounds).
    failures = sum(1 for r in suite_report.results if r.verdict in {"fail", "error"})
    raise typer.Exit(code=min(failures, 125))
