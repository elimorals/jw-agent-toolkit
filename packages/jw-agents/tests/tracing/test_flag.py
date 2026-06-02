"""Tests for the shared --trace flag installer and the Typer integration."""

from __future__ import annotations

from pathlib import Path

import typer
from jw_agents.tracing._flag import (
    DEFAULT_TRACE_DIR_ENV,
    resolve_trace_target,
    tracer_from_target,
)
from jw_agents.tracing.store import JsonlTraceStore, NullTraceStore
from typer.testing import CliRunner


def test_resolve_target_none_returns_none() -> None:
    assert resolve_trace_target(None) is None


def test_resolve_target_dash_returns_stdout_sentinel() -> None:
    assert resolve_trace_target("-") == "-"


def test_resolve_target_explicit_path(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    out = resolve_trace_target(str(p))
    assert out == p


def test_resolve_target_default_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(DEFAULT_TRACE_DIR_ENV, str(tmp_path))
    out = resolve_trace_target("DEFAULT", agent="apologetics")
    assert isinstance(out, Path)
    assert out.parent == tmp_path
    assert out.name.startswith("apologetics-")
    assert out.suffix == ".jsonl"


def test_tracer_from_target_none_is_null() -> None:
    tr = tracer_from_target(None, agent="x")
    assert isinstance(tr.store, NullTraceStore)


def test_tracer_from_target_path_is_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    tr = tracer_from_target(p, agent="x")
    assert isinstance(tr.store, JsonlTraceStore)


def test_typer_flag_integration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(DEFAULT_TRACE_DIR_ENV, str(tmp_path))
    app = typer.Typer()

    @app.command()
    def demo(
        question: str,
        trace: str = typer.Option(None, "--trace"),
    ) -> None:
        target = (
            resolve_trace_target(trace, agent="demo") if trace is not None else None
        )
        tr = tracer_from_target(target, agent="demo")
        with tr.run(input_kwargs={"question": question}), tr.step("noop"):
            pass

    runner = CliRunner()
    res = runner.invoke(app, ["x", "--trace", "DEFAULT"])
    assert res.exit_code == 0, res.output
    written = list(tmp_path.glob("demo-*.jsonl"))
    assert written, f"no jsonl in {tmp_path}: {list(tmp_path.iterdir())}"
