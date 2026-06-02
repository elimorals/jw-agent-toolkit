"""Tests for the contextvars-based ambient tracer."""

from __future__ import annotations

import asyncio

import pytest

from jw_agents.tracing.context import (
    get_active_tracer,
    set_active_tracer,
    use_tracer,
)
from jw_agents.tracing.store import InMemoryTraceStore
from jw_agents.tracing.tracer import AgentTracer


def _make() -> AgentTracer:
    return AgentTracer(agent="x", store=InMemoryTraceStore())


def test_default_active_tracer_is_noop() -> None:
    tr = get_active_tracer()
    tr.warn("just checking")
    assert tr.agent in {"_null", "x"}


def test_set_active_tracer_returns_token_and_restores() -> None:
    base = get_active_tracer()
    new = _make()
    token = set_active_tracer(new)
    try:
        assert get_active_tracer() is new
    finally:
        from jw_agents.tracing.context import _active

        _active.reset(token)
    assert get_active_tracer() is base


def test_use_tracer_context_manager() -> None:
    base = get_active_tracer()
    new = _make()
    with use_tracer(new):
        assert get_active_tracer() is new
    assert get_active_tracer() is base


@pytest.mark.asyncio
async def test_concurrent_tasks_isolate_tracers() -> None:
    a = _make()
    b = _make()

    seen: dict[str, AgentTracer] = {}

    async def run(name: str, tracer: AgentTracer) -> None:
        with use_tracer(tracer):
            await asyncio.sleep(0)
            seen[name] = get_active_tracer()

    await asyncio.gather(run("a", a), run("b", b))
    assert seen["a"] is a
    assert seen["b"] is b
