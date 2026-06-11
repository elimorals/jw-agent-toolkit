"""Verify the three Fase 65 MCP tools are exposed and callable."""

from __future__ import annotations

import asyncio


def test_meta_list_tools_returns_payload() -> None:
    from jw_mcp.server import meta_list_tools

    coro = meta_list_tools.fn() if hasattr(meta_list_tools, "fn") else meta_list_tools()
    out = asyncio.run(coro)
    assert isinstance(out, dict)
    assert "tools" in out
    assert any(t["name"] == "research.topic" for t in out["tools"])


def test_meta_plan_goal_returns_dict() -> None:
    from jw_mcp.server import meta_plan_goal

    coro = (
        meta_plan_goal.fn(goal="x", language="es")
        if hasattr(meta_plan_goal, "fn")
        else meta_plan_goal(goal="x", language="es")
    )
    out = asyncio.run(coro)
    assert isinstance(out, dict)
    assert "goal" in out
    assert "steps" in out


def test_meta_run_plan_returns_orchestration_result_dict() -> None:
    from jw_mcp.server import meta_run_plan

    coro = (
        meta_run_plan.fn(goal="x", language="es", max_replans=0)
        if hasattr(meta_run_plan, "fn")
        else meta_run_plan(goal="x", language="es", max_replans=0)
    )
    out = asyncio.run(coro)
    assert isinstance(out, dict)
    assert "plan" in out
    assert "critique" in out
