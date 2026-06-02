"""Ambient tracer propagation via contextvars.

Most agents accept an explicit `trace: AgentTracer | None = None` kwarg, but
plugin authors and downstream tools (CLI / MCP / pytest fixtures) need to
inject a tracer without modifying every signature. `contextvars.ContextVar`
gives us async-task-safe, per-context propagation.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from jw_agents.tracing.tracer import AgentTracer

_active: ContextVar["AgentTracer | None"] = ContextVar(
    "jw_active_tracer", default=None
)
_NULL: "AgentTracer | None" = None


def _null_singleton() -> "AgentTracer":
    global _NULL
    if _NULL is None:
        from jw_agents.tracing.store import NullTraceStore
        from jw_agents.tracing.tracer import AgentTracer

        _NULL = AgentTracer(agent="_null", store=NullTraceStore())
    return _NULL


def get_active_tracer() -> "AgentTracer":
    """Return the ambient tracer; falls back to the shared NO-OP singleton."""

    tr = _active.get()
    if tr is None:
        return _null_singleton()
    return tr


def set_active_tracer(tracer: "AgentTracer") -> Token["AgentTracer | None"]:
    """Set the ambient tracer for the current context.

    Returns a Token. Callers MUST `token.reset()` to restore the previous
    value (or use the `use_tracer` context manager).
    """

    return _active.set(tracer)


@contextmanager
def use_tracer(tracer: "AgentTracer") -> Iterator["AgentTracer"]:
    """Bind `tracer` as the ambient tracer for the duration of the block."""

    token = _active.set(tracer)
    try:
        yield tracer
    finally:
        _active.reset(token)
