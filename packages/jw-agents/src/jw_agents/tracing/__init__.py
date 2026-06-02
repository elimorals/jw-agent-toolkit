"""Local-first agent tracing.

Public API (incrementally expanded across tasks):
    from jw_agents.tracing import AgentTracer, get_active_tracer, set_active_tracer

The tracer is OPT-IN. Without an active tracer or with the default
`NullTraceStore` every method is a no-op.

See `docs/guias/agent-tracing.md` for usage and the spec at
`docs/superpowers/specs/2026-05-31-fase-43-agent-tracing-design.md` for the
schema contract.
"""

from jw_agents.tracing.schema import (
    TRACE_SCHEMA_VERSION,
    CustomEvent,
    FindingDroppedEvent,
    FindingKeptEvent,
    StepEndEvent,
    StepStartEvent,
    Trace,
    TraceEvent,
    TraceEventAdapter,
    WarningEvent,
)

__all__ = [
    "TRACE_SCHEMA_VERSION",
    "CustomEvent",
    "FindingDroppedEvent",
    "FindingKeptEvent",
    "StepEndEvent",
    "StepStartEvent",
    "Trace",
    "TraceEvent",
    "TraceEventAdapter",
    "WarningEvent",
]
