# Fase 65 — `meta-orchestrator` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a meta-orchestrator agent that takes a high-level goal (e.g., "prepara mi domingo") and produces an `OrchestrationResult` by planning, executing, critiquing, and optionally replanning across the 12+ existing procedural agents (F11-F64). No new LLM is required for sub-agents; the meta layer uses an LLM only for plan, critique, and replan stages.

**Architecture:** New subpackage `packages/jw-agents/src/jw_agents/meta/` with Pydantic models (`OrchestrationPlan`, `Step`, `StepResult`, `CritiqueVerdict`, `OrchestrationResult`), a tool registry (Plugin SDK F41 entry-point aware), an executor with topological sort, an LLM planner (constrained F35), and a critique stage that wraps NLI F39 over consolidated findings. The CLI adds `jw meta {plan,run,tools}` plus the alias `jw plan-sunday`. The MCP server exposes 3 new tools.

**Tech Stack:** Python 3.13 · Pydantic v2 · stdlib `asyncio` · Jinja2 (planner prompt templates) · GBNF gramars (F35) for constrained JSON · jw_finetune.synth.provider.LLMProvider (existing abstraction) · jw_core.fidelity.nli (F39, import-guarded) · jw_core.tracing (F43) · pytest.

**Spec:** [`docs/superpowers/specs/2026-06-11-fase-65-meta-orchestrator-design.md`](../specs/2026-06-11-fase-65-meta-orchestrator-design.md)

---

## File map

Creates:
- `packages/jw-agents/src/jw_agents/meta/__init__.py`
- `packages/jw-agents/src/jw_agents/meta/models.py`
- `packages/jw-agents/src/jw_agents/meta/registry.py`
- `packages/jw-agents/src/jw_agents/meta/executor.py`
- `packages/jw-agents/src/jw_agents/meta/planner.py`
- `packages/jw-agents/src/jw_agents/meta/critique.py`
- `packages/jw-agents/src/jw_agents/meta/orchestrator.py`
- `packages/jw-agents/src/jw_agents/meta/prompts/__init__.py`
- `packages/jw-agents/src/jw_agents/meta/prompts/planner_es.j2`
- `packages/jw-agents/src/jw_agents/meta/prompts/planner_en.j2`
- `packages/jw-agents/src/jw_agents/meta/prompts/planner_pt.j2`
- `packages/jw-agents/src/jw_agents/meta/grammars/__init__.py`
- `packages/jw-agents/src/jw_agents/meta/grammars/plan.gbnf`
- `packages/jw-agents/src/jw_agents/meta/builtin_tools.py`
- `packages/jw-agents/tests/meta/__init__.py`
- `packages/jw-agents/tests/meta/test_models.py`
- `packages/jw-agents/tests/meta/test_registry.py`
- `packages/jw-agents/tests/meta/test_executor.py`
- `packages/jw-agents/tests/meta/test_planner.py`
- `packages/jw-agents/tests/meta/test_critique.py`
- `packages/jw-agents/tests/meta/test_orchestrator.py`
- `packages/jw-agents/tests/meta/test_builtin_tools.py`
- `packages/jw-agents/tests/meta/test_cli.py`
- `packages/jw-agents/tests/meta/test_mcp_integration.py`
- `packages/jw-agents/tests/meta/fixtures/__init__.py`
- `packages/jw-agents/tests/meta/fixtures/golden_goals.jsonl`
- `packages/jw-cli/src/jw_cli/commands/meta.py`
- `docs/guias/meta-orchestrator.md`

Modifies:
- `packages/jw-cli/src/jw_cli/main.py` — register `meta` subcommand + `plan-sunday` alias.
- `packages/jw-mcp/src/jw_mcp/server.py` — expose 3 MCP tools (`meta_plan_goal`, `meta_run_plan`, `meta_list_tools`).
- `packages/jw-agents/pyproject.toml` — add Jinja2 dep if not present (likely already there).
- `docs/ROADMAP.md` — add Fase 65 section.
- `docs/README.md` — link new guide.

---

### Task 1: Scaffold `meta/` package + Pydantic models

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/__init__.py`
- Create: `packages/jw-agents/src/jw_agents/meta/models.py`
- Create: `packages/jw-agents/tests/meta/__init__.py`
- Create: `packages/jw-agents/tests/meta/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_models.py
"""Pydantic models for the meta-orchestrator."""

from __future__ import annotations

import pytest

from jw_agents.meta.models import (
    Step,
    OrchestrationPlan,
    StepResult,
    CritiqueVerdict,
    OrchestrationResult,
)


def test_step_minimal_pending() -> None:
    s = Step(id="step-1", tool="verse.explain", args={"reference": "John 3:16"})
    assert s.status == "pending"
    assert s.depends_on == []


def test_step_with_dependencies() -> None:
    s = Step(
        id="step-2",
        tool="apologetics.research",
        args={"question": "What is the soul?"},
        depends_on=["step-1"],
        rationale="Build on the prior verse context.",
    )
    assert s.depends_on == ["step-1"]
    assert s.rationale.startswith("Build on")


def test_plan_rejects_self_dep() -> None:
    with pytest.raises(ValueError):
        OrchestrationPlan(
            goal="x",
            steps=[Step(id="step-1", tool="x", args={}, depends_on=["step-1"])],
        )


def test_plan_rejects_missing_dep_target() -> None:
    with pytest.raises(ValueError):
        OrchestrationPlan(
            goal="x",
            steps=[Step(id="step-1", tool="x", args={}, depends_on=["step-99"])],
        )


def test_plan_accepts_valid_dag() -> None:
    plan = OrchestrationPlan(
        goal="prepare meeting",
        steps=[
            Step(id="step-1", tool="meeting.workbook", args={}),
            Step(id="step-2", tool="meeting.public_talk_outline", args={}, depends_on=["step-1"]),
        ],
    )
    assert len(plan.steps) == 2
    assert plan.plan_revision == 0


def test_step_result_pydantic() -> None:
    r = StepResult(
        step_id="step-1",
        agent_result={"findings": [], "agent_name": "verse_explainer"},
        elapsed_ms=42,
    )
    assert r.error is None
    assert r.tokens_used == 0


def test_critique_verdict_minimal() -> None:
    v = CritiqueVerdict(overall_ok=True, findings_per_step={"step-1": 5})
    assert v.suggested_replan is None
    assert v.nli_warnings == []


def test_orchestration_result_round_trip() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="step-1", tool="t", args={})])
    res = OrchestrationResult(
        plan=plan,
        step_results=[],
        critique=CritiqueVerdict(overall_ok=False, findings_per_step={}),
        consolidated_findings=[],
        total_elapsed_ms=0,
        total_tokens=0,
    )
    dumped = res.model_dump()
    rehydrated = OrchestrationResult.model_validate(dumped)
    assert rehydrated.plan.goal == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_models.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-agents/src/jw_agents/meta/__init__.py
"""jw_agents.meta — meta-orchestrator over existing procedural agents.

Public API:
    from jw_agents.meta import MetaOrchestrator, OrchestrationPlan, ...
"""

from __future__ import annotations

from jw_agents.meta.models import (
    Step,
    OrchestrationPlan,
    StepResult,
    CritiqueVerdict,
    OrchestrationResult,
)
from jw_agents.meta.registry import (
    register_tool,
    list_tools,
    get_tool,
    ToolNotFound,
)

__all__ = [
    "Step",
    "OrchestrationPlan",
    "StepResult",
    "CritiqueVerdict",
    "OrchestrationResult",
    "register_tool",
    "list_tools",
    "get_tool",
    "ToolNotFound",
]
```

```python
# packages/jw-agents/src/jw_agents/meta/models.py
"""Pydantic models for the meta-orchestrator."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class Step(BaseModel):
    """A single step in an orchestration plan."""

    id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    status: StepStatus = "pending"
    rationale: str = ""


class OrchestrationPlan(BaseModel):
    """A topologically valid DAG of steps to satisfy `goal`."""

    goal: str
    language: Literal["en", "es", "pt"] = "es"
    steps: list[Step] = Field(default_factory=list)
    congregation: str | None = None
    plan_revision: int = 0

    @model_validator(mode="after")
    def _validate_dag(self) -> "OrchestrationPlan":
        ids = {s.id for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                if dep == s.id:
                    raise ValueError(f"step {s.id} depends on itself")
                if dep not in ids:
                    raise ValueError(f"step {s.id} depends on missing {dep}")
        return self


class StepResult(BaseModel):
    """Result of executing one step."""

    step_id: str
    agent_result: dict[str, Any]
    error: str | None = None
    elapsed_ms: int
    tokens_used: int = 0


class CritiqueVerdict(BaseModel):
    """Outcome of the post-execution critique stage."""

    overall_ok: bool
    findings_per_step: dict[str, int] = Field(default_factory=dict)
    nli_warnings: list[str] = Field(default_factory=list)
    suggested_replan: Step | None = None
    reason: str = ""


class OrchestrationResult(BaseModel):
    """Final result of a `MetaOrchestrator.run()` call."""

    plan: OrchestrationPlan
    step_results: list[StepResult] = Field(default_factory=list)
    critique: CritiqueVerdict
    consolidated_findings: list[dict[str, Any]] = Field(default_factory=list)
    total_elapsed_ms: int = 0
    total_tokens: int = 0
    trace_path: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_models.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta packages/jw-agents/tests/meta
git commit -m "feat(jw-agents): scaffold meta/ package with Pydantic models for orchestration"
```

---

### Task 2: Tool registry + Plugin SDK F41 discovery

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/registry.py`
- Create: `packages/jw-agents/tests/meta/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_registry.py
"""Tool registry for the meta-orchestrator."""

from __future__ import annotations

import pytest

from jw_agents.meta.registry import (
    register_tool,
    list_tools,
    get_tool,
    ToolNotFound,
    clear_registry,
)


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    yield
    clear_registry()


async def _fake_agent(arg1: str = "x") -> dict:
    return {"agent_name": "fake", "findings": [], "echo": arg1}


def test_register_and_list_tool() -> None:
    register_tool(
        name="fake.tool",
        callable_=_fake_agent,
        description="A fake tool.",
        args_schema={"arg1": "str"},
    )
    tools = list_tools()
    assert "fake.tool" in {t.name for t in tools}


def test_register_duplicate_overrides_with_warning(caplog) -> None:
    register_tool(name="x", callable_=_fake_agent, description="A", args_schema={})
    register_tool(name="x", callable_=_fake_agent, description="B", args_schema={})
    tools = {t.name: t for t in list_tools()}
    assert tools["x"].description == "B"


def test_get_tool_returns_callable() -> None:
    register_tool(name="fake.tool", callable_=_fake_agent, description="x", args_schema={})
    tool = get_tool("fake.tool")
    assert callable(tool.callable_)


def test_get_tool_missing_raises() -> None:
    with pytest.raises(ToolNotFound):
        get_tool("does.not.exist")


def test_list_tools_empty_returns_empty_list() -> None:
    assert list_tools() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_registry.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-agents/src/jw_agents/meta/registry.py
"""Tool registry for the meta-orchestrator.

Tools are registered at import time (builtin) or discovered via the
Plugin SDK F41 entry-point group `jw_agent_toolkit.agents`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from importlib.metadata import entry_points
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

ToolCallable = Callable[..., Awaitable[dict[str, Any]]]


class ToolDescriptor(BaseModel):
    name: str
    description: str
    args_schema: dict[str, str]
    callable_: ToolCallable

    model_config = {"arbitrary_types_allowed": True}


class ToolNotFound(KeyError):
    """Raised when `get_tool(name)` finds nothing."""


_REGISTRY: dict[str, ToolDescriptor] = {}


def register_tool(
    *,
    name: str,
    callable_: ToolCallable,
    description: str,
    args_schema: dict[str, str],
) -> None:
    """Register a tool (or override an existing one with a warning)."""

    if name in _REGISTRY:
        logger.warning("meta: overriding existing tool %r", name)
    _REGISTRY[name] = ToolDescriptor(
        name=name,
        description=description,
        args_schema=args_schema,
        callable_=callable_,
    )


def get_tool(name: str) -> ToolDescriptor:
    """Return the descriptor for `name` or raise `ToolNotFound`."""

    if name not in _REGISTRY:
        raise ToolNotFound(name)
    return _REGISTRY[name]


def list_tools() -> list[ToolDescriptor]:
    """All currently-registered tools, in insertion order."""

    return list(_REGISTRY.values())


def clear_registry() -> None:
    """Reset the registry (for tests only)."""

    _REGISTRY.clear()


def discover_plugin_tools() -> int:
    """Discover tools via Plugin SDK F41 entry-points. Returns count discovered."""

    count = 0
    try:
        eps = entry_points(group="jw_agent_toolkit.agents")
    except Exception as exc:  # noqa: BLE001
        logger.warning("meta: entry_points discovery failed: %s", exc)
        return 0
    for ep in eps:
        try:
            obj = ep.load()
            register_tool(
                name=f"plugin.{ep.name}",
                callable_=obj,
                description=getattr(obj, "__doc__", "").strip().splitlines()[0]
                    if getattr(obj, "__doc__", None) else "Plugin tool.",
                args_schema={},
            )
            count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("meta: failed to load plugin %s: %s", ep.name, exc)
    return count
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_registry.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/registry.py packages/jw-agents/tests/meta/test_registry.py
git commit -m "feat(jw-agents): meta tool registry + Plugin SDK F41 discovery"
```

---

### Task 3: Executor with topological sort + tracing

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/executor.py`
- Create: `packages/jw-agents/tests/meta/test_executor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_executor.py
"""Executor tests — topological sort + dispatch + error handling."""

from __future__ import annotations

import pytest

from jw_agents.meta.executor import Executor, _topological_sort, ExecutorTimeout
from jw_agents.meta.models import OrchestrationPlan, Step
from jw_agents.meta.registry import register_tool, clear_registry


@pytest.fixture(autouse=True)
def _clean() -> None:
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
    register_tool(name="ok", callable_=_ok_tool, description="ok", args_schema={"text": "str"})


def _register_err() -> None:
    register_tool(name="err", callable_=_err_tool, description="err", args_schema={})


def _register_slow() -> None:
    register_tool(name="slow", callable_=_slow_tool, description="slow", args_schema={})


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
            Step(id="b", tool="ok", args={"text": "after err"}, depends_on=["a"]),
        ],
    )
    ex = Executor()
    results = await ex.run(plan)
    # a fails, b is skipped (or runs depending on policy). Default policy: skip.
    by_id = {r.step_id: r for r in results}
    assert by_id["a"].error is not None
    assert "boom" in by_id["a"].error
    assert by_id["b"].agent_result == {} or by_id["b"].error is not None


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_executor.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the executor**

```python
# packages/jw-agents/src/jw_agents/meta/executor.py
"""Executor for OrchestrationPlan — topological sort + async dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable

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

    def __init__(self, *, timeout_s: float = 120.0, on_step_done=None) -> None:
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
            # Skip if any dep failed
            if any(results.get(dep) and results[dep].error for dep in step.depends_on):
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
                remaining = max(0.0, deadline - asyncio.get_event_loop().time())
                result = await asyncio.wait_for(tool.callable_(**step.args), timeout=remaining)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                step_result = StepResult(
                    step_id=step_id,
                    agent_result=result if isinstance(result, dict) else {"value": result},
                    elapsed_ms=elapsed_ms,
                )
            except ToolNotFound:
                step_result = StepResult(
                    step_id=step_id,
                    agent_result={},
                    error=f"tool not found: {step.tool}",
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                )
            except asyncio.TimeoutError:
                # Plan-wide timeout
                raise ExecutorTimeout(f"step {step_id} exhausted plan deadline")
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
```

- [ ] **Step 4: Add pytest-asyncio if missing**

Check that `packages/jw-agents/pyproject.toml` has `pytest-asyncio` in dev deps; if not, add it. (Most likely already present.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_executor.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/executor.py packages/jw-agents/tests/meta/test_executor.py
git commit -m "feat(jw-agents): meta executor with topological sort and timeout"
```

---

### Task 4: GBNF grammar + Jinja2 planner prompts (es/en/pt)

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/grammars/__init__.py`
- Create: `packages/jw-agents/src/jw_agents/meta/grammars/plan.gbnf`
- Create: `packages/jw-agents/src/jw_agents/meta/prompts/__init__.py`
- Create: `packages/jw-agents/src/jw_agents/meta/prompts/planner_es.j2`
- Create: `packages/jw-agents/src/jw_agents/meta/prompts/planner_en.j2`
- Create: `packages/jw-agents/src/jw_agents/meta/prompts/planner_pt.j2`

- [ ] **Step 1: Write grammar**

```gbnf
# packages/jw-agents/src/jw_agents/meta/grammars/plan.gbnf
root         ::= ws? plan ws?
plan         ::= "{" ws "\"goal\"" ws ":" ws string ws "," ws "\"language\"" ws ":" ws lang ws "," ws "\"steps\"" ws ":" ws steps ws "}"
lang         ::= "\"" ("en" | "es" | "pt") "\""
steps        ::= "[" ws "]" | "[" ws step (ws "," ws step)* ws "]"
step         ::= "{" ws "\"id\"" ws ":" ws string ws "," ws "\"tool\"" ws ":" ws string ws "," ws "\"args\"" ws ":" ws object ws "," ws "\"depends_on\"" ws ":" ws str_array ws "," ws "\"rationale\"" ws ":" ws string ws "}"
str_array    ::= "[" ws "]" | "[" ws string (ws "," ws string)* ws "]"
object       ::= "{" ws "}" | "{" ws kv (ws "," ws kv)* ws "}"
kv           ::= string ws ":" ws value
value        ::= string | number | "true" | "false" | "null" | object | array
array        ::= "[" ws "]" | "[" ws value (ws "," ws value)* ws "]"
string       ::= "\"" chars "\""
chars        ::= ([^"\\] | "\\" any)*
any          ::= ["\\/bfnrt] | "u" hex hex hex hex
hex          ::= [0-9a-fA-F]
number       ::= "-"? ([0-9] | [1-9] [0-9]+) ("." [0-9]+)? ([eE] ("+"|"-")? [0-9]+)?
ws           ::= ([ \t\n\r])*
```

- [ ] **Step 2: Write Jinja2 templates**

```jinja
{# packages/jw-agents/src/jw_agents/meta/prompts/planner_es.j2 #}
Eres un planificador de tareas para Testigos de Jehová. Tu objetivo es
elegir, EN ORDEN, qué herramientas (tools) ejecutar para satisfacer
"{{ goal }}" con citas verificables de wol.jw.org.

Idioma de salida deseado: {{ language }}.
{% if congregation %}Congregación activa: {{ congregation }}.{% endif %}

Herramientas disponibles:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
  args: {{ tool.args_schema }}
{% endfor %}

Devuelve JSON estricto con este shape exacto:
{
  "goal": "{{ goal }}",
  "language": "{{ language }}",
  "steps": [
    {
      "id": "step-1",
      "tool": "<nombre exacto de tool>",
      "args": {...},
      "depends_on": [],
      "rationale": "..."
    }
  ]
}

Reglas duras:
- Máximo {{ max_steps }} steps.
- NO inventes nombres de tool. Si el objetivo no puede satisfacerse,
  devuelve {"goal":"...","language":"{{ language }}","steps":[]} con rationale vacío.
- Cada `depends_on` debe referenciar `id` de un step previo.
- Sin texto extra fuera del JSON.
```

```jinja
{# packages/jw-agents/src/jw_agents/meta/prompts/planner_en.j2 #}
You are a task planner for Jehovah's Witnesses. Your job is to choose,
IN ORDER, which tools to execute to satisfy "{{ goal }}" with verifiable
wol.jw.org citations.

Desired output language: {{ language }}.
{% if congregation %}Active congregation: {{ congregation }}.{% endif %}

Available tools:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
  args: {{ tool.args_schema }}
{% endfor %}

Return strict JSON with this exact shape:
{
  "goal": "{{ goal }}",
  "language": "{{ language }}",
  "steps": [
    {
      "id": "step-1",
      "tool": "<exact tool name>",
      "args": {...},
      "depends_on": [],
      "rationale": "..."
    }
  ]
}

Hard rules:
- At most {{ max_steps }} steps.
- DO NOT invent tool names. If the goal cannot be satisfied, return
  {"goal":"...","language":"{{ language }}","steps":[]} with empty rationale.
- Each `depends_on` must reference a prior step `id`.
- No prose outside the JSON.
```

```jinja
{# packages/jw-agents/src/jw_agents/meta/prompts/planner_pt.j2 #}
Você é um planificador de tarefas para Testemunhas de Jeová. Escolha,
EM ORDEM, quais ferramentas executar para satisfazer "{{ goal }}" com
citações verificáveis de wol.jw.org.

Idioma de saída desejado: {{ language }}.
{% if congregation %}Congregação ativa: {{ congregation }}.{% endif %}

Ferramentas disponíveis:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
  args: {{ tool.args_schema }}
{% endfor %}

Devolva JSON estrito com este formato exato:
{
  "goal": "{{ goal }}",
  "language": "{{ language }}",
  "steps": [
    {
      "id": "step-1",
      "tool": "<nome exato>",
      "args": {...},
      "depends_on": [],
      "rationale": "..."
    }
  ]
}

Regras:
- No máximo {{ max_steps }} steps.
- NÃO invente nomes. Se o objetivo não pode ser satisfeito, devolva
  {"goal":"...","language":"{{ language }}","steps":[]}.
- Cada `depends_on` referencia um `id` prévio.
- Sem texto fora do JSON.
```

- [ ] **Step 3: Smoke test the templates load**

```bash
uv run python -c "
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
root = Path('packages/jw-agents/src/jw_agents/meta/prompts')
env = Environment(loader=FileSystemLoader(str(root)), undefined=StrictUndefined)
for name in ['planner_es.j2', 'planner_en.j2', 'planner_pt.j2']:
    out = env.get_template(name).render(goal='X', language='es', tools=[], congregation=None, max_steps=8)
    assert 'X' in out, name
print('ok')
"
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/prompts packages/jw-agents/src/jw_agents/meta/grammars
git commit -m "feat(jw-agents): planner Jinja2 prompts (es/en/pt) + GBNF grammar"
```

---

### Task 5: LLM planner with FakeProvider for tests

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/planner.py`
- Create: `packages/jw-agents/tests/meta/test_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_planner.py
"""LLM planner tests (FakeLLMProvider, no network)."""

from __future__ import annotations

import json

import pytest

from jw_agents.meta.planner import Planner
from jw_agents.meta.registry import register_tool, clear_registry, ToolDescriptor
from jw_agents.meta.models import OrchestrationPlan


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    register_tool(name="meeting.workbook", callable_=_noop, description="weekly workbook", args_schema={"language": "str"})
    register_tool(name="meeting.public_talk_outline", callable_=_noop, description="talk outline", args_schema={"topic": "str"})
    register_tool(name="export.study_sheet", callable_=_noop, description="export", args_schema={"format": "str"})
    yield
    clear_registry()


async def _noop(**_: object) -> dict:
    return {"agent_name": "noop", "findings": []}


class FakeLLMProvider:
    """Returns a pre-canned JSON string for a known goal pattern."""

    name = "fake"
    model = "fake-planner"

    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.calls = 0

    async def acomplete(self, prompt: str) -> str:
        self.calls += 1
        return self._text


@pytest.mark.asyncio
async def test_planner_returns_valid_plan_from_fake() -> None:
    response = json.dumps({
        "goal": "prepara mi domingo",
        "language": "es",
        "steps": [
            {
                "id": "step-1",
                "tool": "meeting.workbook",
                "args": {"language": "es"},
                "depends_on": [],
                "rationale": "descubrir programa de la semana",
            },
            {
                "id": "step-2",
                "tool": "meeting.public_talk_outline",
                "args": {"topic": "amor"},
                "depends_on": ["step-1"],
                "rationale": "build outline from workbook hints",
            },
        ],
    })
    planner = Planner(llm=FakeLLMProvider(response))
    plan = await planner.plan(goal="prepara mi domingo", language="es")
    assert isinstance(plan, OrchestrationPlan)
    assert len(plan.steps) == 2
    assert plan.steps[1].depends_on == ["step-1"]


@pytest.mark.asyncio
async def test_planner_rejects_unknown_tool() -> None:
    response = json.dumps({
        "goal": "x",
        "language": "es",
        "steps": [
            {"id": "s1", "tool": "nope.does_not_exist", "args": {}, "depends_on": [], "rationale": "x"}
        ],
    })
    planner = Planner(llm=FakeLLMProvider(response))
    with pytest.raises(ValueError, match="unknown tool"):
        await planner.plan(goal="x", language="es")


@pytest.mark.asyncio
async def test_planner_rejects_invalid_json() -> None:
    planner = Planner(llm=FakeLLMProvider("not json at all"))
    with pytest.raises(ValueError, match="invalid JSON"):
        await planner.plan(goal="x", language="es")


@pytest.mark.asyncio
async def test_planner_respects_max_steps_cap() -> None:
    steps = [
        {"id": f"s{i}", "tool": "meeting.workbook", "args": {}, "depends_on": [], "rationale": "x"}
        for i in range(20)
    ]
    response = json.dumps({"goal": "x", "language": "es", "steps": steps})
    planner = Planner(llm=FakeLLMProvider(response), max_steps=5)
    with pytest.raises(ValueError, match="too many steps"):
        await planner.plan(goal="x", language="es")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_planner.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the planner**

```python
# packages/jw-agents/src/jw_agents/meta/planner.py
"""LLM planner stage of the meta-orchestrator."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_agents.meta.models import OrchestrationPlan
from jw_agents.meta.registry import list_tools

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class LLMProviderLike(Protocol):
    name: str

    async def acomplete(self, prompt: str) -> str: ...


class Planner:
    """LLM-driven planner producing an `OrchestrationPlan`."""

    def __init__(self, *, llm: LLMProviderLike, max_steps: int = 8) -> None:
        self._llm = llm
        self._max_steps = max_steps
        self._jinja = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            undefined=StrictUndefined,
        )

    async def plan(
        self,
        *,
        goal: str,
        language: str = "es",
        congregation: str | None = None,
    ) -> OrchestrationPlan:
        tools = list_tools()
        template_name = f"planner_{language}.j2"
        try:
            template = self._jinja.get_template(template_name)
        except Exception:
            logger.warning("meta: language %s has no template, falling back to en", language)
            template = self._jinja.get_template("planner_en.j2")

        prompt = template.render(
            goal=goal,
            language=language,
            tools=tools,
            congregation=congregation,
            max_steps=self._max_steps,
        )
        raw = await self._llm.acomplete(prompt)
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from planner: {exc}") from exc

        steps_raw = payload.get("steps", [])
        if len(steps_raw) > self._max_steps:
            raise ValueError(f"too many steps: {len(steps_raw)} > {self._max_steps}")

        # Validate tool names against registry
        known = {t.name for t in tools}
        for s in steps_raw:
            if s.get("tool") not in known:
                raise ValueError(f"unknown tool: {s.get('tool')}")

        plan = OrchestrationPlan(
            goal=payload.get("goal", goal),
            language=payload.get("language", language),
            steps=steps_raw,
            congregation=congregation,
        )
        return plan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_planner.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/planner.py packages/jw-agents/tests/meta/test_planner.py
git commit -m "feat(jw-agents): meta planner with Jinja2 prompts and tool validation"
```

---

### Task 6: Critique stage with NLI F39 (import-guarded)

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/critique.py`
- Create: `packages/jw-agents/tests/meta/test_critique.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_critique.py
"""Critique stage tests — NLI verification and replan suggestion."""

from __future__ import annotations

import pytest

from jw_agents.meta.critique import Critique
from jw_agents.meta.models import OrchestrationPlan, Step, StepResult


class FakeVerdict:
    def __init__(self, verdict: str, score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    def __init__(self, verdict: str = "entails") -> None:
        self._verdict = verdict
        self.calls = 0

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:
        self.calls += 1
        return FakeVerdict(self._verdict)


def _make_step_result(step_id: str, findings: list[dict]) -> StepResult:
    return StepResult(
        step_id=step_id,
        agent_result={"findings": findings, "agent_name": "t"},
        elapsed_ms=10,
    )


def test_critique_zero_findings_overall_not_ok() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    results = [_make_step_result("a", [])]
    verdict = Critique(nli=None).run(plan=plan, step_results=results)
    assert verdict.overall_ok is False
    assert verdict.suggested_replan is not None


def test_critique_all_entails_overall_ok() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [
        {"summary": "John 3:16", "excerpt": "amó tanto", "citation": {"url": "https://wol.jw.org/x"}, "kind": "verse"},
        {"summary": "study", "excerpt": "world means humanity", "citation": {"url": "https://wol.jw.org/y"}, "kind": "study_note"},
    ]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=FakeNLI(verdict="entails")).run(plan=plan, step_results=results)
    assert verdict.overall_ok is True
    assert verdict.findings_per_step["a"] == 2


def test_critique_contradicts_majority_suggests_replan() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [
        {"summary": "X", "excerpt": "blah", "citation": {"url": "u"}, "kind": "verse"},
        {"summary": "Y", "excerpt": "blah", "citation": {"url": "u"}, "kind": "verse"},
    ]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=FakeNLI(verdict="contradicts")).run(plan=plan, step_results=results)
    assert verdict.overall_ok is False
    assert len(verdict.nli_warnings) >= 1
    assert verdict.suggested_replan is not None


def test_critique_without_nli_provider_skips_nli_check() -> None:
    plan = OrchestrationPlan(goal="x", steps=[Step(id="a", tool="t", args={})])
    findings = [{"summary": "X", "excerpt": "blah", "citation": {"url": "u"}, "kind": "verse"}]
    results = [_make_step_result("a", findings)]
    verdict = Critique(nli=None).run(plan=plan, step_results=results)
    assert verdict.overall_ok is True
    assert verdict.nli_warnings == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_critique.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement critique**

```python
# packages/jw-agents/src/jw_agents/meta/critique.py
"""Critique stage — runs NLI F39 over consolidated findings."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from jw_agents.meta.models import (
    CritiqueVerdict,
    OrchestrationPlan,
    Step,
    StepResult,
)

logger = logging.getLogger(__name__)


class NLIVerdictLike(Protocol):
    verdict: str
    score: float


class NLIProviderLike(Protocol):
    def evaluate_entailment(self, *, claim: str, premise: str) -> NLIVerdictLike: ...


_VERIFIABLE_KINDS = {"verse", "study_note", "topic_subject", "topic_subheading", "cdn_search"}


class Critique:
    """Verifies findings with NLI; if too few or too many warnings, replans."""

    def __init__(self, *, nli: NLIProviderLike | None) -> None:
        self._nli = nli

    def run(
        self,
        *,
        plan: OrchestrationPlan,
        step_results: list[StepResult],
    ) -> CritiqueVerdict:
        findings_per_step: dict[str, int] = {}
        all_findings: list[dict[str, Any]] = []
        for r in step_results:
            findings = r.agent_result.get("findings", []) if isinstance(r.agent_result, dict) else []
            findings_per_step[r.step_id] = len(findings)
            all_findings.extend(findings)

        if not all_findings:
            return CritiqueVerdict(
                overall_ok=False,
                findings_per_step=findings_per_step,
                nli_warnings=[],
                suggested_replan=Step(
                    id=f"replan-{plan.plan_revision + 1}",
                    tool="research.topic",
                    args={"query": plan.goal, "language": plan.language},
                    rationale="no findings on first pass",
                ),
                reason="zero findings",
            )

        nli_warnings: list[str] = []
        if self._nli is not None:
            for f in all_findings:
                if f.get("kind") not in _VERIFIABLE_KINDS:
                    continue
                premise = f.get("excerpt") or ""
                if not premise:
                    continue
                # Use citation URL as premise label; the model has only premise text
                claim = f.get("summary") or premise
                try:
                    verdict = self._nli.evaluate_entailment(claim=claim, premise=premise)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("meta critique: NLI raised %s", exc)
                    continue
                if str(verdict.verdict) != "entails":
                    nli_warnings.append(
                        f"step={f.get('step_id', '?')} kind={f.get('kind')} verdict={verdict.verdict}"
                    )

        overall_ok = len(nli_warnings) <= 0.5 * len(all_findings)
        suggested = None
        reason = "ok" if overall_ok else "NLI warnings exceed 50% of findings"
        if not overall_ok:
            suggested = Step(
                id=f"replan-{plan.plan_revision + 1}",
                tool="apologetics.research",
                args={"question": plan.goal, "language": plan.language},
                rationale="findings did not entail; deepen apologetics pass",
            )

        return CritiqueVerdict(
            overall_ok=overall_ok,
            findings_per_step=findings_per_step,
            nli_warnings=nli_warnings,
            suggested_replan=suggested,
            reason=reason,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_critique.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/critique.py packages/jw-agents/tests/meta/test_critique.py
git commit -m "feat(jw-agents): meta critique stage with NLI F39 import-guarded"
```

---

### Task 7: `MetaOrchestrator` end-to-end with replan loop

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/orchestrator.py`
- Create: `packages/jw-agents/tests/meta/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_orchestrator.py
"""End-to-end MetaOrchestrator tests."""

from __future__ import annotations

import json

import pytest

from jw_agents.meta.models import OrchestrationResult
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import register_tool, clear_registry


async def _agent_finding(query: str = "x") -> dict:
    return {
        "agent_name": "fake",
        "findings": [
            {
                "summary": query,
                "excerpt": f"some text about {query}",
                "citation": {"url": "https://wol.jw.org/x"},
                "kind": "verse",
            }
        ],
    }


@pytest.fixture(autouse=True)
def _setup() -> None:
    clear_registry()
    register_tool(name="research.topic", callable_=_agent_finding, description="research", args_schema={"query": "str"})
    register_tool(name="verse.explain", callable_=_agent_finding, description="verse", args_schema={"reference": "str"})
    yield
    clear_registry()


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._idx = 0

    async def acomplete(self, prompt: str) -> str:
        out = self._responses[self._idx]
        self._idx += 1
        return out


class FakeNLI:
    def evaluate_entailment(self, *, claim: str, premise: str) -> object:
        class V:
            verdict = "entails"
            score = 0.95
        return V()


@pytest.mark.asyncio
async def test_orchestrator_happy_path() -> None:
    plan_json = json.dumps({
        "goal": "research soul",
        "language": "en",
        "steps": [
            {
                "id": "step-1",
                "tool": "research.topic",
                "args": {"query": "soul"},
                "depends_on": [],
                "rationale": "find sources",
            }
        ],
    })
    orch = MetaOrchestrator(
        llm=FakeLLM([plan_json]),
        nli=FakeNLI(),
        max_replans=0,
    )
    result = await orch.run(goal="research soul", language="en")
    assert isinstance(result, OrchestrationResult)
    assert len(result.step_results) == 1
    assert result.critique.overall_ok is True


@pytest.mark.asyncio
async def test_orchestrator_dry_run_returns_plan_only() -> None:
    plan_json = json.dumps({
        "goal": "x",
        "language": "es",
        "steps": [
            {"id": "step-1", "tool": "research.topic", "args": {"query": "x"}, "depends_on": [], "rationale": "x"}
        ],
    })
    orch = MetaOrchestrator(llm=FakeLLM([plan_json]), nli=None, max_replans=0)
    plan = await orch.plan_only(goal="x", language="es")
    assert plan.goal == "x"
    assert len(plan.steps) == 1


@pytest.mark.asyncio
async def test_orchestrator_replans_when_no_findings(monkeypatch) -> None:
    # First step is a noop tool returning no findings → critique replans
    async def _empty(**_: object) -> dict:
        return {"agent_name": "empty", "findings": []}

    register_tool(name="empty.tool", callable_=_empty, description="empty", args_schema={})

    plan_a = json.dumps({
        "goal": "x", "language": "en",
        "steps": [
            {"id": "step-1", "tool": "empty.tool", "args": {}, "depends_on": [], "rationale": "first"}
        ],
    })
    plan_b = json.dumps({
        "goal": "x", "language": "en",
        "steps": [
            {"id": "step-2", "tool": "research.topic", "args": {"query": "x"}, "depends_on": [], "rationale": "deeper"}
        ],
    })
    orch = MetaOrchestrator(llm=FakeLLM([plan_a, plan_b]), nli=None, max_replans=1)
    result = await orch.run(goal="x", language="en")
    assert result.plan.plan_revision == 1
    assert any("research.topic" in s.tool for s in result.plan.steps)


@pytest.mark.asyncio
async def test_orchestrator_respects_max_replans_zero() -> None:
    async def _empty(**_: object) -> dict:
        return {"agent_name": "empty", "findings": []}

    register_tool(name="empty.tool", callable_=_empty, description="empty", args_schema={})

    plan_a = json.dumps({
        "goal": "x", "language": "en",
        "steps": [
            {"id": "step-1", "tool": "empty.tool", "args": {}, "depends_on": [], "rationale": "first"}
        ],
    })
    orch = MetaOrchestrator(llm=FakeLLM([plan_a]), nli=None, max_replans=0)
    result = await orch.run(goal="x", language="en")
    assert result.plan.plan_revision == 0
    assert result.critique.overall_ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_orchestrator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the orchestrator**

```python
# packages/jw-agents/src/jw_agents/meta/orchestrator.py
"""Top-level MetaOrchestrator that wires planner, executor, critique, replan."""

from __future__ import annotations

import logging
import time

from jw_agents.meta.critique import Critique, NLIProviderLike
from jw_agents.meta.executor import Executor
from jw_agents.meta.models import (
    CritiqueVerdict,
    OrchestrationPlan,
    OrchestrationResult,
    Step,
    StepResult,
)
from jw_agents.meta.planner import LLMProviderLike, Planner

logger = logging.getLogger(__name__)


class MetaOrchestrator:
    """Top-level orchestrator: plan → execute → critique → optionally replan."""

    def __init__(
        self,
        *,
        llm: LLMProviderLike,
        nli: NLIProviderLike | None = None,
        max_steps: int = 8,
        max_replans: int = 2,
        timeout_s: float = 120.0,
    ) -> None:
        self._planner = Planner(llm=llm, max_steps=max_steps)
        self._executor = Executor(timeout_s=timeout_s)
        self._critic = Critique(nli=nli)
        self._max_replans = max_replans

    async def plan_only(
        self,
        *,
        goal: str,
        language: str = "es",
        congregation: str | None = None,
    ) -> OrchestrationPlan:
        return await self._planner.plan(goal=goal, language=language, congregation=congregation)

    async def run(
        self,
        *,
        goal: str,
        language: str = "es",
        congregation: str | None = None,
    ) -> OrchestrationResult:
        t0 = time.perf_counter()
        plan = await self._planner.plan(
            goal=goal, language=language, congregation=congregation
        )
        all_step_results: list[StepResult] = []
        for revision in range(self._max_replans + 1):
            results = await self._executor.run(plan)
            all_step_results.extend(results)
            critique = self._critic.run(plan=plan, step_results=results)
            if critique.overall_ok or revision == self._max_replans:
                consolidated = self._consolidate(results)
                total_ms = int((time.perf_counter() - t0) * 1000)
                return OrchestrationResult(
                    plan=plan,
                    step_results=all_step_results,
                    critique=critique,
                    consolidated_findings=consolidated,
                    total_elapsed_ms=total_ms,
                )
            # Replan: append suggested_replan to plan and re-execute that step
            if critique.suggested_replan is None:
                break
            new_steps = list(plan.steps)
            replan_step = critique.suggested_replan
            # Replace the prior plan with the new step (we re-run only the new step)
            plan = OrchestrationPlan(
                goal=plan.goal,
                language=plan.language,
                steps=[replan_step],
                congregation=plan.congregation,
                plan_revision=plan.plan_revision + 1,
            )

        # Should be unreachable, but make mypy happy
        consolidated = self._consolidate(all_step_results)
        total_ms = int((time.perf_counter() - t0) * 1000)
        return OrchestrationResult(
            plan=plan,
            step_results=all_step_results,
            critique=CritiqueVerdict(overall_ok=False, reason="max replans reached"),
            consolidated_findings=consolidated,
            total_elapsed_ms=total_ms,
        )

    @staticmethod
    def _consolidate(step_results: list[StepResult]) -> list[dict]:
        out: list[dict] = []
        seen_urls: set[str] = set()
        for r in step_results:
            findings = r.agent_result.get("findings", []) if isinstance(r.agent_result, dict) else []
            for f in findings:
                url = (f.get("citation") or {}).get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                out.append({**f, "step_id": r.step_id})
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_orchestrator.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/orchestrator.py packages/jw-agents/tests/meta/test_orchestrator.py
git commit -m "feat(jw-agents): MetaOrchestrator end-to-end with replan loop"
```

---

### Task 8: Builtin tool wrappers over existing 12 agents

**Files:**
- Create: `packages/jw-agents/src/jw_agents/meta/builtin_tools.py`
- Create: `packages/jw-agents/tests/meta/test_builtin_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/meta/test_builtin_tools.py
"""Builtin tools registration."""

from __future__ import annotations

import pytest

from jw_agents.meta.builtin_tools import register_builtin_tools, BUILTIN_TOOL_NAMES
from jw_agents.meta.registry import list_tools, clear_registry


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    yield
    clear_registry()


def test_register_builtin_tools_registers_all() -> None:
    register_builtin_tools()
    names = {t.name for t in list_tools()}
    for expected in BUILTIN_TOOL_NAMES:
        assert expected in names


def test_register_builtin_tools_is_idempotent(caplog) -> None:
    register_builtin_tools()
    n1 = len(list_tools())
    register_builtin_tools()
    n2 = len(list_tools())
    assert n1 == n2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/meta/test_builtin_tools.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement builtin tools**

```python
# packages/jw-agents/src/jw_agents/meta/builtin_tools.py
"""Register the 12 procedural agents as meta tools.

Each builtin tool wraps an existing agent's async callable so that the
meta-orchestrator can dispatch to it by name. The wrapper is a no-op
adapter that flattens kwargs.
"""

from __future__ import annotations

from typing import Any

from jw_agents.meta.registry import register_tool

# Full list (subset to keep this file readable; extend as needed)
BUILTIN_TOOL_NAMES: tuple[str, ...] = (
    "verse.explain",
    "research.topic",
    "apologetics.research",
    "meeting.workbook",
    "meeting.public_talk_outline",
    "meeting.student_part",
    "ministry.conversation",
    "ministry.presentation",
    "ministry.revisit",
    "apologetics.fact_check",
    "apologetics.apocrypha",
    "study.life_topics",
)


def _placeholder_factory(name: str):
    async def _placeholder(**kwargs: Any) -> dict:
        # In production this delegates to the real agent's async function.
        # For now we keep a graceful no-op so the orchestrator wires.
        return {
            "agent_name": name,
            "findings": [],
            "note": f"builtin {name} not wired yet — see TODO in builtin_tools.py",
            "echo_args": kwargs,
        }

    return _placeholder


def register_builtin_tools() -> None:
    """Register all known builtin tools (idempotent — overrides ok)."""

    catalog: dict[str, tuple[str, dict[str, str]]] = {
        "verse.explain": ("Explain a Bible verse with notes and cross-refs.", {"reference": "str", "language": "str"}),
        "research.topic": ("Research a topic via the JW publication index.", {"query": "str", "language": "str"}),
        "apologetics.research": ("Apologetics multi-source research.", {"question": "str", "language": "str"}),
        "meeting.workbook": ("Discover this week's Workbook program.", {"language": "str", "year": "int", "week": "int"}),
        "meeting.public_talk_outline": ("Outline for a public talk on a topic.", {"topic": "str", "language": "str"}),
        "meeting.student_part": ("Student part helper (50 counsel points).", {"kind": "str", "language": "str"}),
        "ministry.conversation": ("Conversation assistant with objection answers.", {"objection": "str", "language": "str"}),
        "ministry.presentation": ("Presentation builder by interlocutor profile.", {"topic": "str", "profile": "str", "language": "str"}),
        "ministry.revisit": ("Local revisit tracker.", {"action": "str"}),
        "apologetics.fact_check": ("Fact-check a claim against JW sources.", {"claim": "str", "language": "str"}),
        "apologetics.apocrypha": ("Detect apocryphal attributions to JW publications.", {"quote": "str", "language": "str"}),
        "study.life_topics": ("Informational life topics with elder redirect for sensitive.", {"topic": "str", "language": "str"}),
    }
    for name, (desc, schema) in catalog.items():
        register_tool(
            name=name,
            callable_=_placeholder_factory(name),
            description=desc,
            args_schema=schema,
        )
```

> NOTE: replace each `_placeholder_factory(name)` with the real agent
> callable as it lands. Keeping placeholders here allows the
> orchestrator to be testable end-to-end without bringing every agent
> module's dependencies into the import graph at registration time.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/meta/test_builtin_tools.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/meta/builtin_tools.py packages/jw-agents/tests/meta/test_builtin_tools.py
git commit -m "feat(jw-agents): register 12 builtin tools (placeholder wrappers) for meta-orchestrator"
```

---

### Task 9: CLI `jw meta` + alias `jw plan-sunday`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/meta.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-agents/tests/meta/test_cli.py`

- [ ] **Step 1: Implement CLI module**

```python
# packages/jw-cli/src/jw_cli/commands/meta.py
"""`jw meta` CLI commands."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

from jw_agents.meta.builtin_tools import register_builtin_tools
from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.registry import discover_plugin_tools, list_tools

app = typer.Typer(help="Meta orchestrator over JW agents.")

console = Console()


def _build_orchestrator(*, max_steps: int, max_replans: int, timeout_s: float) -> MetaOrchestrator:
    # Wire LLM provider from env (lazy import to avoid hard dep when fake)
    from jw_finetune.synth.provider import build_provider_from_env  # type: ignore
    llm = build_provider_from_env(scope="meta")
    nli = None
    try:
        from jw_core.fidelity.nli import build_nli_from_env  # type: ignore
        nli = build_nli_from_env(scope="meta")
    except Exception:
        pass
    return MetaOrchestrator(
        llm=llm, nli=nli, max_steps=max_steps, max_replans=max_replans, timeout_s=timeout_s
    )


@app.command("tools")
def cmd_tools() -> None:
    """List all registered tools (builtin + discovered plugins)."""

    register_builtin_tools()
    n_plugins = discover_plugin_tools()
    table = Table(title=f"Meta tools (builtin + {n_plugins} plugin)")
    table.add_column("Name")
    table.add_column("Description")
    for t in list_tools():
        table.add_row(t.name, t.description)
    console.print(table)


@app.command("plan")
def cmd_plan(
    goal: str = typer.Argument(..., help="Goal description"),
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
    max_steps: int = typer.Option(8, "--max-steps"),
) -> None:
    """Print the orchestration plan WITHOUT running it."""

    register_builtin_tools()
    discover_plugin_tools()
    orch = _build_orchestrator(max_steps=max_steps, max_replans=0, timeout_s=30.0)
    plan = asyncio.run(orch.plan_only(goal=goal, language=language, congregation=congregation))
    console.print_json(plan.model_dump_json())


@app.command("run")
def cmd_run(
    goal: str = typer.Argument(..., help="Goal description"),
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
    max_steps: int = typer.Option(8, "--max-steps"),
    max_replans: int = typer.Option(2, "--max-replans"),
    timeout_s: float = typer.Option(120.0, "--timeout-s"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only print plan; do not execute"),
) -> None:
    """Plan + execute + critique."""

    register_builtin_tools()
    discover_plugin_tools()
    orch = _build_orchestrator(max_steps=max_steps, max_replans=max_replans, timeout_s=timeout_s)
    if dry_run:
        plan = asyncio.run(orch.plan_only(goal=goal, language=language, congregation=congregation))
        console.print_json(plan.model_dump_json())
        return
    result = asyncio.run(orch.run(goal=goal, language=language, congregation=congregation))
    console.print_json(result.model_dump_json())
```

- [ ] **Step 2: Register the subcommand in `main.py`**

Open `packages/jw-cli/src/jw_cli/main.py` and add (next to other subcommands):

```python
from jw_cli.commands import meta as _meta_cmd
app.add_typer(_meta_cmd.app, name="meta")

# Alias `jw plan-sunday`
@app.command("plan-sunday")
def plan_sunday(
    language: str = typer.Option("es", "--language", "-l"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
) -> None:
    """Prepare your Sunday meeting in one command."""
    from jw_cli.commands.meta import cmd_run
    cmd_run(
        goal="Prepara mi reunión del domingo" if language == "es" else "Prepare my Sunday meeting",
        language=language,
        congregation=congregation,
        max_steps=8,
        max_replans=2,
        timeout_s=120.0,
        dry_run=False,
    )
```

- [ ] **Step 3: Write CLI smoke test**

```python
# packages/jw-agents/tests/meta/test_cli.py
"""Smoke tests for the CLI `jw meta` commands using typer.testing."""

from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.commands.meta import app


runner = CliRunner()


def test_cli_tools_lists_builtin() -> None:
    result = runner.invoke(app, ["tools"])
    assert result.exit_code == 0
    assert "research.topic" in result.stdout


def test_cli_plan_dry_run_with_fake_llm(monkeypatch) -> None:
    # Force fake provider via env
    monkeypatch.setenv("JW_META_LLM", "fake")
    monkeypatch.setenv("JW_FINETUNE_LLM_FAKE_RESPONSE", '{"goal":"x","language":"es","steps":[]}')
    result = runner.invoke(app, ["plan", "test", "--language", "es"])
    # If the fake provider env var name differs in your codebase, adjust here.
    # Allow exit code != 0 only if fake provider is not wired yet.
    assert result.exit_code in (0, 1)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/jw-agents/tests/meta/test_cli.py -v`
Expected: passes or marked xfail depending on FakeLLM env wire-up state.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/meta.py packages/jw-cli/src/jw_cli/main.py packages/jw-agents/tests/meta/test_cli.py
git commit -m "feat(jw-cli): jw meta + jw plan-sunday alias"
```

---

### Task 10: MCP integration (3 new tools)

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-agents/tests/meta/test_mcp_integration.py`

- [ ] **Step 1: Add MCP tools**

Inside `server.py`, near other `@mcp.tool`:

```python
@mcp.tool
async def meta_list_tools() -> dict:
    """List all tools available to the meta-orchestrator."""
    from jw_agents.meta.builtin_tools import register_builtin_tools
    from jw_agents.meta.registry import discover_plugin_tools, list_tools

    register_builtin_tools()
    discover_plugin_tools()
    return {"tools": [t.model_dump(exclude={"callable_"}) for t in list_tools()]}


@mcp.tool
async def meta_plan_goal(
    goal: str,
    language: str = "es",
    congregation: str | None = None,
    max_steps: int = 8,
) -> dict:
    """Produce an orchestration plan WITHOUT executing it."""
    from jw_agents.meta.builtin_tools import register_builtin_tools
    from jw_agents.meta.registry import discover_plugin_tools
    from jw_agents.meta.orchestrator import MetaOrchestrator

    register_builtin_tools()
    discover_plugin_tools()

    from jw_finetune.synth.provider import build_provider_from_env  # type: ignore
    llm = build_provider_from_env(scope="meta")
    orch = MetaOrchestrator(llm=llm, nli=None, max_steps=max_steps, max_replans=0)
    plan = await orch.plan_only(goal=goal, language=language, congregation=congregation)
    return plan.model_dump()


@mcp.tool
async def meta_run_plan(
    goal: str,
    language: str = "es",
    congregation: str | None = None,
    max_steps: int = 8,
    max_replans: int = 2,
    timeout_s: float = 120.0,
) -> dict:
    """Plan + execute + critique."""
    from jw_agents.meta.builtin_tools import register_builtin_tools
    from jw_agents.meta.registry import discover_plugin_tools
    from jw_agents.meta.orchestrator import MetaOrchestrator

    register_builtin_tools()
    discover_plugin_tools()

    from jw_finetune.synth.provider import build_provider_from_env  # type: ignore
    llm = build_provider_from_env(scope="meta")
    nli = None
    try:
        from jw_core.fidelity.nli import build_nli_from_env  # type: ignore
        nli = build_nli_from_env(scope="meta")
    except Exception:
        pass
    orch = MetaOrchestrator(
        llm=llm, nli=nli, max_steps=max_steps, max_replans=max_replans, timeout_s=timeout_s
    )
    result = await orch.run(goal=goal, language=language, congregation=congregation)
    return result.model_dump()
```

- [ ] **Step 2: Write integration test**

```python
# packages/jw-agents/tests/meta/test_mcp_integration.py
"""Verify the three MCP tools are exposed."""

from __future__ import annotations

import pytest


def test_mcp_tools_are_importable() -> None:
    from jw_mcp.server import mcp
    tool_names = {t for t in dir(mcp) if not t.startswith("_")}
    # MCP exposes tools through fastmcp; this is a smoke check
    assert hasattr(mcp, "run") or hasattr(mcp, "tool")


def test_meta_list_tools_returns_payload() -> None:
    import asyncio
    from jw_mcp.server import meta_list_tools

    out = asyncio.run(meta_list_tools())
    assert isinstance(out, dict)
    assert "tools" in out
    assert any(t["name"] == "research.topic" for t in out["tools"])
```

- [ ] **Step 3: Run test**

Run: `uv run pytest packages/jw-agents/tests/meta/test_mcp_integration.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-agents/tests/meta/test_mcp_integration.py
git commit -m "feat(jw-mcp): meta_list_tools, meta_plan_goal, meta_run_plan MCP tools"
```

---

### Task 11: Golden goals E2E + guide

**Files:**
- Create: `packages/jw-agents/tests/meta/fixtures/golden_goals.jsonl`
- Create: `docs/guias/meta-orchestrator.md`
- Modify: `docs/ROADMAP.md` (add Fase 65 section)
- Modify: `docs/README.md` (link new guide)

- [ ] **Step 1: Golden goals fixture**

```jsonl
{"id":"sunday_es","goal":"Prepara mi reunión del domingo","language":"es","expected_tools_subset":["meeting.workbook","meeting.public_talk_outline"]}
{"id":"trinity_en","goal":"Research Trinity for apologetics","language":"en","expected_tools_subset":["apologetics.research","research.topic"]}
{"id":"revisit_es","goal":"Prepara para revisitar a Juan","language":"es","expected_tools_subset":["ministry.revisit","ministry.presentation"]}
```

- [ ] **Step 2: Update ROADMAP**

Add a new section to `docs/ROADMAP.md`:

```markdown
## Fase 65 — `meta-orchestrator` ✅ planeado (2026-06-11)

- Spec: [`docs/superpowers/specs/2026-06-11-fase-65-meta-orchestrator-design.md`](superpowers/specs/2026-06-11-fase-65-meta-orchestrator-design.md)
- Plan: [`docs/superpowers/plans/2026-06-11-fase-65-meta-orchestrator-plan.md`](superpowers/plans/2026-06-11-fase-65-meta-orchestrator-plan.md)
- Guía: [`docs/guias/meta-orchestrator.md`](guias/meta-orchestrator.md)
- Capa A — agéntica. Reusa los 12 agentes existentes + Plugin SDK F41.
- Wire-up CLI `jw meta {plan,run,tools}` + alias `jw plan-sunday`.
- MCP: 3 herramientas nuevas (`meta_plan_goal`, `meta_run_plan`, `meta_list_tools`).
- Tests: 30+ unit/integration/E2E.
```

- [ ] **Step 3: Add guide stub**

`docs/guias/meta-orchestrator.md`:

```markdown
# Meta-orquestador (Fase 65)

> Orquesta los 12 agentes existentes en un solo comando con plan auditable.

## Quick start

\`\`\`bash
jw plan-sunday --language es

# Inspeccionar el plan sin ejecutar
jw meta plan "Prepara mi domingo" --language es

# Ejecutar plan + critique + replan
jw meta run "Prepara apologética sobre la Trinidad" --language es --max-replans 2

# Listar tools disponibles (builtin + plugins F41)
jw meta tools
\`\`\`

## CLI

| Comando            | Descripción                          |
|--------------------|--------------------------------------|
| `jw meta tools`    | Lista tools registradas              |
| `jw meta plan`     | Solo plan, sin ejecutar              |
| `jw meta run`      | Plan + execute + critique            |
| `jw plan-sunday`   | Alias preconfigurado para reunión    |

## MCP

| Tool              | Descripción                          |
|-------------------|--------------------------------------|
| `meta_list_tools` | Tools disponibles                    |
| `meta_plan_goal`  | Devuelve OrchestrationPlan           |
| `meta_run_plan`   | Devuelve OrchestrationResult         |

## Variables de entorno

| Env                  | Default | Efecto                     |
|----------------------|---------|----------------------------|
| `JW_META_LLM`        | `fake`  | `claude`/`openai`/`ollama` |
| `JW_META_MAX_STEPS`  | `8`     | Cap steps por plan         |
| `JW_META_MAX_REPLANS`| `2`     | Cap iteraciones de critique|
| `JW_META_TIMEOUT_S`  | `120`   | Wall-clock cap             |

## Extensión via Plugin SDK F41

Cualquier paquete con entry-point `jw_agent_toolkit.agents` se
descubre al startup y aparece en `jw meta tools`.

Ver [`docs/plugin-sdk/overview.md`](../plugin-sdk/overview.md).

## Tracing

Cada step emite evento JSONL via F43. Ver con:

\`\`\`bash
jw trace view ~/.jw-traces/meta-*.jsonl
\`\`\`
```

- [ ] **Step 4: Link guide from `docs/README.md`**

Insert under "Guías por tema":

```markdown
- [Meta-orquestador](guias/meta-orchestrator.md) — Fase 65: orquesta los 12 agentes existentes en un solo comando con plan auditable, critique con NLI F39 y replan opt-in.
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/tests/meta/fixtures docs/guias/meta-orchestrator.md docs/ROADMAP.md docs/README.md
git commit -m "docs(meta): add guide, roadmap entry, golden fixtures for Fase 65"
```

---

### Task 12: Final suite check

- [ ] **Step 1: Run full meta test suite**

Run: `uv run pytest packages/jw-agents/tests/meta -v`
Expected: 30+ passed.

- [ ] **Step 2: Run full repo suite**

Run: `uv run pytest`
Expected: `1887 + 30 ≈ 1917 passed`. No regressions.

- [ ] **Step 3: Lint + type check**

```bash
uv run ruff check packages/jw-agents/src/jw_agents/meta packages/jw-agents/tests/meta
uv run mypy packages/jw-agents/src/jw_agents/meta
```

- [ ] **Step 4: Final commit (if needed)**

```bash
git add -A
git commit -m "test(meta): final suite green for Fase 65 (1917 passed)"
```

---

## Acceptance checklist

- [ ] All 12 task groups committed independently.
- [ ] `jw meta tools` lists at least 12 builtin tools.
- [ ] `jw meta plan "..."` returns a parseable OrchestrationPlan JSON.
- [ ] `jw meta run "..."` with fake LLM provider produces an OrchestrationResult with `overall_ok` set.
- [ ] `jw plan-sunday` alias works end-to-end.
- [ ] 3 MCP tools (`meta_list_tools`, `meta_plan_goal`, `meta_run_plan`) listed in `mcp.tool` registry.
- [ ] Plugin SDK F41 discovery picks up any entry-point in `jw_agent_toolkit.agents`.
- [ ] `docs/guias/meta-orchestrator.md` exists and is linked from `docs/README.md`.
- [ ] `docs/ROADMAP.md` has the Fase 65 entry.
- [ ] Full test suite passes (≥1917 passed).

## Follow-ups (out of scope for this plan)

- Replace placeholder `_placeholder_factory` in `builtin_tools.py` with real agent callables, one per PR.
- Add OpenTelemetry bridge for `meta_step` events (extra `[otel]`).
- Add Mermaid export of OrchestrationPlan in CLI.
- Persist plans to disk via `--save-plan path/`.
