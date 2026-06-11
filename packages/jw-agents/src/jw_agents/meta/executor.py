"""Executor for OrchestrationPlan — topological sort + async dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from jw_agents.meta.models import OrchestrationPlan, Step, StepResult
from jw_agents.meta.registry import ToolNotFound, get_tool

logger = logging.getLogger(__name__)


class ExecutorTimeout(TimeoutError):
    """Raised when the whole plan exceeds the wall-clock cap."""


def _topological_sort(steps: list[Step]) -> list[str]:
    """Kahn's algorithm. Raises ValueError on cycles."""

    in_degree: dict[str, int] = {s.id: len(s.depends_on) for s in steps}
    children: dict[str, list[str]] = {s.id: [] for s in steps}
    for s in steps:
        for dep in s.depends_on:
            children[dep].append(s.id)
    queue: list[str] = [sid for sid, deg in in_degree.items() if deg == 0]
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for child in children[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    if len(order) != len(steps):
        raise ValueError("cycle detected in plan")
    return order


class Executor:
    """Run an `OrchestrationPlan` step by step, respecting deps and timeout."""

    def __init__(
        self,
        *,
        timeout_s: float = 120.0,
        on_step_done: Callable[[Step, StepResult], None] | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._on_step_done = on_step_done

    async def run(self, plan: OrchestrationPlan) -> list[StepResult]:
        order = _topological_sort(plan.steps)
        by_id = {s.id: s for s in plan.steps}
        results: dict[str, StepResult] = {}
        deadline = asyncio.get_event_loop().time() + self._timeout_s

        for step_id in order:
            if asyncio.get_event_loop().time() > deadline:
                raise ExecutorTimeout(f"plan exceeded {self._timeout_s}s")

            step = by_id[step_id]
            if any(
                results.get(dep) and results[dep].error for dep in step.depends_on
            ):
                results[step_id] = StepResult(
                    step_id=step_id,
                    agent_result={},
                    error=f"skipped: upstream {step.depends_on} failed",
                    elapsed_ms=0,
                )
                continue

            t0 = time.perf_counter()
            try:
                tool = get_tool(step.tool)
                remaining = max(
                    0.0, deadline - asyncio.get_event_loop().time()
                )
                result = await asyncio.wait_for(
                    tool.callable_(**step.args), timeout=remaining
                )
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                agent_result = (
                    result if isinstance(result, dict) else {"value": result}
                )
                step_result = StepResult(
                    step_id=step_id,
                    agent_result=agent_result,
                    elapsed_ms=elapsed_ms,
                )
            except ToolNotFound:
                step_result = StepResult(
                    step_id=step_id,
                    agent_result={},
                    error=f"tool not found: {step.tool}",
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                )
            except asyncio.TimeoutError as exc:
                raise ExecutorTimeout(
                    f"step {step_id} exhausted plan deadline"
                ) from exc
            except Exception as exc:  # noqa: BLE001
                step_result = StepResult(
                    step_id=step_id,
                    agent_result={},
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                )

            results[step_id] = step_result
            if self._on_step_done is not None:
                self._on_step_done(step, step_result)

        return [results[sid] for sid in order]
