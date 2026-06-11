"""Executor tests — topological sort + dispatch + error handling."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.meta.executor import Executor, ExecutorTimeout, _topological_sort
from jw_agents.meta.models import OrchestrationPlan, Step
from jw_agents.meta.registry import clear_registry, register_tool


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


async def _ok_tool(text: str = "ok") -> dict:
    return {"agent_name": "ok_tool", "findings": [{"text": text}]}


async def _err_tool(**_: object) -> dict:
    raise RuntimeError("boom")


async def _slow_tool(**_: object) -> dict:
    import asyncio

    await asyncio.sleep(5)
    return {"agent_name": "slow"}


def _register_ok() -> None:
    register_tool(
        name="ok",
        callable_=_ok_tool,
        description="ok",
        args_schema={"text": "str"},
    )


def _register_err() -> None:
    register_tool(
        name="err", callable_=_err_tool, description="err", args_schema={}
    )


def _register_slow() -> None:
    register_tool(
        name="slow", callable_=_slow_tool, description="slow", args_schema={}
    )


# --- topological sort ---


def test_topological_sort_linear() -> None:
    steps = [
        Step(id="a", tool="ok", args={}),
        Step(id="b", tool="ok", args={}, depends_on=["a"]),
        Step(id="c", tool="ok", args={}, depends_on=["b"]),
    ]
    order = _topological_sort(steps)
    assert order == ["a", "b", "c"]


def test_topological_sort_diamond() -> None:
    steps = [
        Step(id="a", tool="ok", args={}),
        Step(id="b", tool="ok", args={}, depends_on=["a"]),
        Step(id="c", tool="ok", args={}, depends_on=["a"]),
        Step(id="d", tool="ok", args={}, depends_on=["b", "c"]),
    ]
    order = _topological_sort(steps)
    assert order[0] == "a" and order[-1] == "d"
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


# --- execution ---


@pytest.mark.asyncio
async def test_execute_linear_plan() -> None:
    _register_ok()
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(id="a", tool="ok", args={"text": "first"}),
            Step(id="b", tool="ok", args={"text": "second"}, depends_on=["a"]),
        ],
    )
    ex = Executor()
    results = await ex.run(plan)
    assert len(results) == 2
    assert results[0].error is None
    assert results[0].agent_result["findings"][0]["text"] == "first"


@pytest.mark.asyncio
async def test_execute_with_failing_step_propagates_error_not_crash() -> None:
    _register_ok()
    _register_err()
    plan = OrchestrationPlan(
        goal="x",
        steps=[
            Step(id="a", tool="err", args={}),
            Step(
                id="b",
                tool="ok",
                args={"text": "after err"},
                depends_on=["a"],
            ),
        ],
    )
    ex = Executor()
    results = await ex.run(plan)
    by_id = {r.step_id: r for r in results}
    assert by_id["a"].error is not None
    assert "boom" in by_id["a"].error
    # Downstream step is skipped because upstream failed.
    assert by_id["b"].error is not None
    assert "skipped" in by_id["b"].error


@pytest.mark.asyncio
async def test_execute_respects_timeout() -> None:
    _register_slow()
    plan = OrchestrationPlan(
        goal="x",
        steps=[Step(id="a", tool="slow", args={})],
    )
    ex = Executor(timeout_s=0.5)
    with pytest.raises(ExecutorTimeout):
        await ex.run(plan)


@pytest.mark.asyncio
async def test_execute_unknown_tool_marks_step_failed() -> None:
    plan = OrchestrationPlan(
        goal="x",
        steps=[Step(id="a", tool="nope", args={})],
    )
    ex = Executor()
    results = await ex.run(plan)
    assert results[0].error is not None
    assert "nope" in results[0].error
