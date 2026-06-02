"""Tests for jw_agents.tracing.schema (event union + envelope)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from jw_agents.tracing.schema import (
    TRACE_SCHEMA_VERSION,
    CustomEvent,
    FindingDroppedEvent,
    FindingKeptEvent,
    StepEndEvent,
    StepStartEvent,
    Trace,
    TraceEventAdapter,
    WarningEvent,
)
from pydantic import ValidationError


def _now() -> datetime:
    return datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)


def test_step_start_minimal() -> None:
    e = StepStartEvent(ts=_now(), seq=0, name="topic_index_lookup")
    assert e.type == "step_start"
    assert e.input_digest is None


def test_step_end_carries_counts() -> None:
    e = StepEndEvent(
        ts=_now(), seq=1, name="x", duration_ms=10, hits=5, kept=2, dropped=3
    )
    assert e.kept == 2 and e.dropped == 3


def test_finding_kept_serialization_round_trip() -> None:
    e = FindingKeptEvent(
        ts=_now(),
        seq=2,
        source="topic_index",
        citation_url="https://wol.jw.org/x",
        score=0.91,
        rank=0,
        reason="primary match",
    )
    raw = e.model_dump_json()
    back = TraceEventAdapter.validate_json(raw)
    assert isinstance(back, FindingKeptEvent)
    assert back.citation_url == "https://wol.jw.org/x"


def test_finding_dropped_minimal() -> None:
    e = FindingDroppedEvent(ts=_now(), seq=3, source="rag", reason="duplicate")
    assert e.citation_url is None


def test_warning_event() -> None:
    e = WarningEvent(
        ts=_now(), seq=4, message="topic timed out", step="topic_index_lookup"
    )
    assert e.message == "topic timed out"


def test_custom_event_payload_arbitrary() -> None:
    e = CustomEvent(
        ts=_now(), seq=5, name="plugin.foo", payload={"a": 1, "b": [1, 2]}
    )
    assert e.payload["b"] == [1, 2]


def test_event_union_discriminates_by_type() -> None:
    raw = json.dumps(
        {
            "type": "step_start",
            "ts": _now().isoformat(),
            "seq": 0,
            "name": "x",
        }
    )
    parsed = TraceEventAdapter.validate_json(raw)
    assert isinstance(parsed, StepStartEvent)


def test_event_union_rejects_unknown_type() -> None:
    raw = json.dumps({"type": "wat", "ts": _now().isoformat(), "seq": 0})
    with pytest.raises(ValidationError):
        TraceEventAdapter.validate_json(raw)


def test_trace_envelope_has_schema_version() -> None:
    tid = uuid4()
    t = Trace(
        trace_id=tid,
        agent="apologetics",
        language="en",
        started_at=_now(),
        finished_at=_now(),
        duration_ms=42,
        input={"question": "x"},
        findings_in=10,
        findings_out=3,
        warnings_count=0,
        events_path="apologetics-2026-05-31.jsonl",
    )
    assert t.schema_version == TRACE_SCHEMA_VERSION
    assert t.trace_id == tid


def test_trace_envelope_serializes_uuid() -> None:
    tid = uuid4()
    t = Trace(
        trace_id=tid,
        agent="apologetics",
        started_at=_now(),
        finished_at=_now(),
        duration_ms=0,
        input={},
        findings_in=0,
        findings_out=0,
        warnings_count=0,
        events_path="x.jsonl",
    )
    data = json.loads(t.model_dump_json())
    assert data["trace_id"] == str(tid)
    assert data["schema_version"] == TRACE_SCHEMA_VERSION
