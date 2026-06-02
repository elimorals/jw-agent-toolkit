"""Tests for the TraceStore implementations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from jw_agents.tracing.schema import (
    FindingKeptEvent,
    StepEndEvent,
    StepStartEvent,
    Trace,
)
from jw_agents.tracing.store import (
    InMemoryTraceStore,
    JsonlTraceStore,
    NullTraceStore,
)


def _now() -> datetime:
    return datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def _envelope(tid) -> Trace:
    return Trace(
        trace_id=tid,
        agent="x",
        started_at=_now(),
        finished_at=_now(),
        duration_ms=0,
        input={},
        findings_in=0,
        findings_out=0,
        warnings_count=0,
        events_path="x.jsonl",
    )


def test_null_store_accepts_everything_and_persists_nothing() -> None:
    store = NullTraceStore()
    store.append(StepStartEvent(ts=_now(), seq=0, name="x"))
    store.complete(_envelope(uuid4()))


def test_inmemory_store_round_trips_events() -> None:
    store = InMemoryTraceStore()
    e1 = StepStartEvent(ts=_now(), seq=0, name="topic")
    e2 = FindingKeptEvent(
        ts=_now(),
        seq=1,
        source="topic_index",
        citation_url="https://x",
        reason="r",
    )
    store.append(e1)
    store.append(e2)
    env = _envelope(uuid4())
    store.complete(env)
    assert len(store.events) == 2
    assert store.envelope is env


def test_jsonl_store_writes_events_in_order(tmp_path: Path) -> None:
    target = tmp_path / "t.jsonl"
    store = JsonlTraceStore(path=target)
    store.append(StepStartEvent(ts=_now(), seq=0, name="a"))
    store.append(
        FindingKeptEvent(
            ts=_now(),
            seq=1,
            source="rag",
            citation_url="https://x",
            score=0.9,
            reason="hit",
        )
    )
    store.append(
        StepEndEvent(
            ts=_now(), seq=2, name="a", duration_ms=10, hits=1, kept=1, dropped=0
        )
    )
    store.complete(_envelope(uuid4()))

    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # 3 events + 1 envelope
    types = [json.loads(line)["type"] for line in lines[:3]]
    assert types == ["step_start", "finding_kept", "step_end"]
    last = json.loads(lines[-1])
    assert last["type"] == "trace_complete"
    assert "trace_id" in last and "schema_version" in last


def test_jsonl_store_flush_on_complete(tmp_path: Path) -> None:
    target = tmp_path / "t.jsonl"
    store = JsonlTraceStore(path=target, buffer_size=64)
    store.append(StepStartEvent(ts=_now(), seq=0, name="a"))
    # Before complete the file MAY be empty due to buffering — that's allowed.
    store.complete(_envelope(uuid4()))
    # After complete it MUST contain at least the envelope.
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "trace_complete" in content


def test_jsonl_store_accepts_stdout_sentinel(
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = JsonlTraceStore(path=None)  # sentinel: stdout
    store.append(StepStartEvent(ts=_now(), seq=0, name="a"))
    store.complete(_envelope(uuid4()))
    out = capsys.readouterr().out
    assert "step_start" in out
    assert "trace_complete" in out


def test_jsonl_store_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "t.jsonl"
    store = JsonlTraceStore(path=target)
    store.complete(_envelope(uuid4()))
    assert target.exists()
