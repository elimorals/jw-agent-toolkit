"""Local-first agent tracing.

Public API (incrementally expanded across tasks):
    from jw_agents.tracing import AgentTracer, get_active_tracer, set_active_tracer

The tracer is OPT-IN. Without an active tracer or with the default
`NullTraceStore` every method is a no-op.

See `docs/guias/agent-tracing.md` for usage and the spec at
`docs/superpowers/specs/2026-05-31-fase-43-agent-tracing-design.md` for the
schema contract.
"""

from jw_agents.tracing.context import (
    get_active_tracer,
    set_active_tracer,
    use_tracer,
)
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
from jw_agents.tracing.store import (
    InMemoryTraceStore,
    JsonlTraceStore,
    NullTraceStore,
    TraceStore,
)
from jw_agents.tracing.tracer import AgentTracer

__all__ = [
    "TRACE_SCHEMA_VERSION",
    "AgentTracer",
    "CustomEvent",
    "FindingDroppedEvent",
    "FindingKeptEvent",
    "InMemoryTraceStore",
    "JsonlTraceStore",
    "NullTraceStore",
    "StepEndEvent",
    "StepStartEvent",
    "Trace",
    "TraceEvent",
    "TraceEventAdapter",
    "TraceStore",
    "WarningEvent",
    "get_active_tracer",
    "set_active_tracer",
    "use_tracer",
]
