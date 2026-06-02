"""Tests for the trace viewer / list / gc CLI."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from jw_agents.tracing.viewer import app as trace_app
from typer.testing import CliRunner


def _write_trace(
    path: Path, *, agent: str = "apologetics", trace_id: str | None = None
) -> str:
    tid = str(trace_id or uuid4())
    events = [
        {
            "type": "step_start",
            "ts": "2026-05-31T12:00:00+00:00",
            "seq": 0,
            "name": "topic_index_lookup",
        },
        {
            "type": "finding_kept",
            "ts": "2026-05-31T12:00:00+00:00",
            "seq": 1,
            "source": "topic_index",
            "citation_url": "https://wol.jw.org/x",
            "score": 0.91,
            "reason": "primary",
        },
        {
            "type": "finding_dropped",
            "ts": "2026-05-31T12:00:00+00:00",
            "seq": 2,
            "source": "rag",
            "reason": "duplicate",
        },
        {
            "type": "step_end",
            "ts": "2026-05-31T12:00:00+00:00",
            "seq": 3,
            "name": "topic_index_lookup",
            "duration_ms": 12,
            "hits": 3,
            "kept": 1,
            "dropped": 2,
        },
        {
            "type": "trace_complete",
            "schema_version": "1.0",
            "trace_id": tid,
            "agent": agent,
            "language": "en",
            "started_at": "2026-05-31T12:00:00+00:00",
            "finished_at": "2026-05-31T12:00:01+00:00",
            "duration_ms": 1000,
            "input": {"question": "demo"},
            "findings_in": 3,
            "findings_out": 1,
            "warnings_count": 0,
            "events_path": str(path),
        },
    ]
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    return tid


def test_view_renders_summary_and_events(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    _write_trace(p)
    runner = CliRunner()
    res = runner.invoke(trace_app, ["view", str(p)])
    assert res.exit_code == 0, res.output
    assert "apologetics" in res.output
    assert "topic_index_lookup" in res.output
    assert "kept=1" in res.output or "1 kept" in res.output


def test_list_filters_by_agent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TRACE_DIR", str(tmp_path))
    _write_trace(
        tmp_path / "apologetics-2026-05-31-aaaa.jsonl", agent="apologetics"
    )
    _write_trace(
        tmp_path / "research_topic-2026-05-31-bbbb.jsonl", agent="research_topic"
    )
    runner = CliRunner()
    res = runner.invoke(trace_app, ["list", "--agent", "apologetics"])
    assert res.exit_code == 0
    assert "apologetics-2026-05-31-aaaa" in res.output
    assert "research_topic" not in res.output


def test_gc_deletes_old_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JW_TRACE_DIR", str(tmp_path))
    old = tmp_path / "apologetics-2026-04-01-aaaa.jsonl"
    new = tmp_path / "apologetics-2026-05-31-bbbb.jsonl"
    _write_trace(old)
    _write_trace(new)
    past = datetime.now(UTC) - timedelta(days=90)
    os.utime(old, (past.timestamp(), past.timestamp()))
    runner = CliRunner()
    res = runner.invoke(trace_app, ["gc", "--older-than", "30d"])
    assert res.exit_code == 0
    assert not old.exists()
    assert new.exists()


def test_view_handles_missing_envelope(tmp_path: Path) -> None:
    p = tmp_path / "partial.jsonl"
    p.write_text(
        json.dumps(
            {
                "type": "step_start",
                "ts": "2026-05-31T12:00:00+00:00",
                "seq": 0,
                "name": "x",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    res = runner.invoke(trace_app, ["view", str(p)])
    assert res.exit_code == 0
    assert (
        "incomplete" in res.output.lower() or "no envelope" in res.output.lower()
    )
