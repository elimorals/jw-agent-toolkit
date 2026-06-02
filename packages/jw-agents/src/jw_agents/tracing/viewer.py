"""Typer CLI for inspecting trace files.

    jw trace view <path>            pretty-print one trace
    jw trace list --agent X         list traces in $JW_TRACE_DIR
    jw trace gc --older-than 30d    delete old trace files

The viewer reads JSONL line-by-line; the last `trace_complete` line is the
envelope. Older schema versions are tolerated (extra fields ignored).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from pathlib import Path

import typer

from jw_agents.tracing._flag import _default_root

app = typer.Typer(
    help="Inspect agent trace files (Fase 43).", no_args_is_help=True
)


_DUR_RE = re.compile(r"^(\d+)\s*([smhd])$")


def _parse_duration(s: str) -> float:
    m = _DUR_RE.match(s.strip().lower())
    if not m:
        raise typer.BadParameter(f"unparseable duration: {s!r}")
    n = int(m.group(1))
    unit = m.group(2)
    factor = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return float(n * factor)


def _iter_lines(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _format_event(evt: dict) -> str:
    t = evt.get("type")
    if t == "step_start":
        return f"  > {evt.get('name')}  start"
    if t == "step_end":
        bits = []
        if evt.get("hits") is not None:
            bits.append(f"hits={evt['hits']}")
        if evt.get("kept") is not None:
            bits.append(f"kept={evt['kept']}")
        if evt.get("dropped") is not None:
            bits.append(f"dropped={evt['dropped']}")
        bits.append(f"{evt.get('duration_ms', 0)}ms")
        return f"  < {evt.get('name')}  " + " ".join(bits)
    if t == "finding_kept":
        score = (
            f" score={evt['score']:.2f}" if evt.get("score") is not None else ""
        )
        return (
            f"    + kept   [{evt.get('source')}]{score}  "
            f"{evt.get('citation_url', '')}  ({evt.get('reason', '')})"
        )
    if t == "finding_dropped":
        score = (
            f" score={evt['score']:.2f}" if evt.get("score") is not None else ""
        )
        url = evt.get("citation_url") or "(no-url)"
        return (
            f"    - drop   [{evt.get('source')}]{score}  {url}  "
            f"({evt.get('reason')})"
        )
    if t == "warning":
        return f"    ! warn   {evt.get('message')}"
    if t == "custom":
        return f"    * custom {evt.get('name')}  {evt.get('payload')}"
    return f"    ? {t}"


@app.command("view")
def view(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Pretty-print one trace file."""

    events: list[dict] = []
    envelope: dict | None = None
    for obj in _iter_lines(path):
        if obj.get("type") == "trace_complete":
            envelope = obj
        else:
            events.append(obj)

    if envelope is None:
        typer.echo(f"# {path}")
        typer.echo("(trace incomplete — no envelope)\n")
    else:
        typer.echo(
            f"# {envelope.get('agent', '?')} "
            f"({envelope.get('language') or '-'})"
        )
        typer.echo(f"  trace_id   : {envelope.get('trace_id')}")
        typer.echo(f"  duration   : {envelope.get('duration_ms')}ms")
        typer.echo(
            f"  findings   : {envelope.get('findings_out')} kept / "
            f"{envelope.get('findings_in')} total"
        )
        typer.echo(f"  warnings   : {envelope.get('warnings_count')}")
        typer.echo(f"  input      : {envelope.get('input')}\n")

    for evt in events:
        typer.echo(_format_event(evt))


@app.command("list")
def list_(
    agent: str | None = typer.Option(None, "--agent"),
    last: int = typer.Option(10, "--last"),
) -> None:
    """List trace files under $JW_TRACE_DIR."""

    root = _default_root()
    if not root.exists():
        typer.echo(f"(no trace dir at {root})")
        return
    files = sorted(
        root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if agent:
        files = [p for p in files if p.name.startswith(f"{agent}-")]
    for p in files[:last]:
        typer.echo(p.name)


@app.command("gc")
def gc(
    older_than: str = typer.Option("30d", "--older-than"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Delete trace files older than the given duration."""

    secs = _parse_duration(older_than)
    threshold = time.time() - secs
    root = _default_root()
    if not root.exists():
        typer.echo("(nothing to GC)")
        return
    n = 0
    for p in root.glob("*.jsonl"):
        if p.stat().st_mtime < threshold:
            if dry_run:
                typer.echo(f"would delete {p.name}")
            else:
                p.unlink()
            n += 1
    typer.echo(f"deleted {n} trace file(s).")


if __name__ == "__main__":
    app()
