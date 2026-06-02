"""Pydantic event schema for the tracing layer.

A trace is a sequence of JSON Lines events. Each event is one of the
discriminated variants below. The Trace envelope is written as the FINAL
line of the JSONL file to mark completion.

The schema is semverable via TRACE_SCHEMA_VERSION; breaking changes bump
the major component.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

TRACE_SCHEMA_VERSION = "1.0"


class _BaseEvent(BaseModel):
    ts: datetime
    seq: int


class StepStartEvent(_BaseEvent):
    type: Literal["step_start"] = "step_start"
    name: str
    input_digest: dict[str, Any] | None = None


class StepEndEvent(_BaseEvent):
    type: Literal["step_end"] = "step_end"
    name: str
    duration_ms: int
    hits: int | None = None
    kept: int | None = None
    dropped: int | None = None
    error: str | None = None


class FindingKeptEvent(_BaseEvent):
    type: Literal["finding_kept"] = "finding_kept"
    source: str
    citation_url: str
    score: float | None = None
    rank: int | None = None
    reason: str = ""


class FindingDroppedEvent(_BaseEvent):
    type: Literal["finding_dropped"] = "finding_dropped"
    source: str
    citation_url: str | None = None
    reason: str
    score: float | None = None


class WarningEvent(_BaseEvent):
    type: Literal["warning"] = "warning"
    message: str
    step: str | None = None


class CustomEvent(_BaseEvent):
    type: Literal["custom"] = "custom"
    name: str
    payload: dict[str, Any]


TraceEvent = Annotated[
    StepStartEvent
    | StepEndEvent
    | FindingKeptEvent
    | FindingDroppedEvent
    | WarningEvent
    | CustomEvent,
    Field(discriminator="type"),
]

TraceEventAdapter: TypeAdapter[TraceEvent] = TypeAdapter(TraceEvent)


class Trace(BaseModel):
    """Envelope written as the FINAL line of the JSONL file."""

    schema_version: str = TRACE_SCHEMA_VERSION
    trace_id: UUID
    agent: str
    language: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    input: dict[str, Any]
    findings_in: int
    findings_out: int
    warnings_count: int
    events_path: str
