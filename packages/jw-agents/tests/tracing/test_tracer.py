"""Tests for the AgentTracer context manager + helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_agents.tracing.schema import (
    StepEndEvent,
    StepStartEvent,
    Trace,
    WarningEvent,
)
from jw_agents.tracing.store import InMemoryTraceStore, JsonlTraceStore
from jw_agents.tracing.tracer import AgentTracer


def test_tracer_emits_events_in_order() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="apologetics", store=store)
    with tr.run(input_kwargs={"question": "x"}, language="en"):
        with tr.step("topic_index_lookup", input_digest={"q_len": 1}) as step:
            tr.kept(
                source="topic_index",
                citation_url="https://x",
                score=0.9,
                reason="primary",
            )
            tr.dropped(source="rag", reason="duplicate")
            step.note_hits(2)
            step.note_kept(1)
            step.note_dropped(1)
    types = [type(e).__name__ for e in store.events]
    assert types == [
        "StepStartEvent",
        "FindingKeptEvent",
        "FindingDroppedEvent",
        "StepEndEvent",
    ]
    assert all(store.events[i].seq == i for i in range(len(store.events)))
    assert store.envelope is not None
    assert isinstance(store.envelope, Trace)
    assert store.envelope.findings_in == 2
    assert store.envelope.findings_out == 1
    assert store.envelope.warnings_count == 0


def test_tracer_warns_increments_envelope_counter() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="apologetics", store=store)
    with tr.run(input_kwargs={}):
        tr.warn("topic timed out", step="topic_index_lookup")
        tr.warn("another")
    assert store.envelope is not None
    assert store.envelope.warnings_count == 2
    assert [
        type(e).__name__ for e in store.events if isinstance(e, WarningEvent)
    ] == ["WarningEvent", "WarningEvent"]


def test_tracer_step_records_error_on_exception() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="x", store=store)
    with tr.run(input_kwargs={}):
        with pytest.raises(RuntimeError):
            with tr.step("explode"):
                raise RuntimeError("boom")
    ends = [e for e in store.events if isinstance(e, StepEndEvent)]
    assert len(ends) == 1
    assert ends[0].error is not None and "boom" in ends[0].error


def test_tracer_envelope_contains_trace_id() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="x", store=store)
    with tr.run(input_kwargs={"k": "v"}):
        pass
    assert store.envelope is not None
    assert str(tr.trace_id) == str(store.envelope.trace_id)
    assert store.envelope.input == {"k": "v"}


def test_tracer_writes_to_jsonl_store(tmp_path: Path) -> None:
    target = tmp_path / "t.jsonl"
    tr = AgentTracer(agent="apologetics", store=JsonlTraceStore(path=target))
    with tr.run(input_kwargs={"question": "x"}):
        with tr.step("s"):
            tr.kept(source="t", citation_url="https://x", reason="ok")
    text = target.read_text(encoding="utf-8")
    assert "step_start" in text
    assert "finding_kept" in text
    assert "step_end" in text
    assert "trace_complete" in text


def test_nested_steps_keep_independent_counters() -> None:
    store = InMemoryTraceStore()
    tr = AgentTracer(agent="x", store=store)
    with tr.run(input_kwargs={}):
        with tr.step("outer"):
            with tr.step("inner"):
                tr.kept(source="x", citation_url="https://x", reason="r")
    starts = [e.name for e in store.events if isinstance(e, StepStartEvent)]
    ends = [e.name for e in store.events if isinstance(e, StepEndEvent)]
    assert starts == ["outer", "inner"]
    assert ends == ["inner", "outer"]  # LIFO
