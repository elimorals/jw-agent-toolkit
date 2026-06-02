"""get_trace returns envelope + events for a recently completed trace."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from jw_agents.tracing.store import JsonlTraceStore
from jw_agents.tracing.tracer import AgentTracer


@pytest.mark.asyncio
async def test_get_trace_finds_recent_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_TRACE_DIR", str(tmp_path))

    target = tmp_path / f"apologetics-2026-05-31-{uuid4().hex[:8]}.jsonl"
    tracer = AgentTracer(
        agent="apologetics", store=JsonlTraceStore(path=target)
    )
    with tracer.run(input_kwargs={"question": "x"}, language="en"), tracer.step("noop"):
        tracer.kept(source="t", citation_url="https://x", reason="ok")

    from jw_mcp.server import get_trace

    out = await get_trace(str(tracer.trace_id))
    assert "events" in out and "envelope" in out
    assert out["envelope"]["trace_id"] == str(tracer.trace_id)
    assert any(e.get("type") == "step_start" for e in out["events"])


@pytest.mark.asyncio
async def test_get_trace_rejects_non_uuid() -> None:
    from jw_mcp.server import get_trace

    with pytest.raises(ValueError):
        await get_trace("not-a-uuid")
