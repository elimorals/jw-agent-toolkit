"""Top-level MetaOrchestrator that wires planner, executor, critique, replan."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

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
    """Top-level orchestrator: plan -> execute -> critique -> optionally replan."""

    def __init__(
        self,
        *,
        llm: LLMProviderLike,
        nli: NLIProviderLike | None = None,
        max_steps: int = 8,
        max_replans: int = 2,
        timeout_s: float = 120.0,
        tracer: Any | None = None,
    ) -> None:
        self._planner = Planner(llm=llm, max_steps=max_steps)
        self._tracer = tracer
        on_step_done = self._emit_step if tracer is not None else None
        self._executor = Executor(
            timeout_s=timeout_s, on_step_done=on_step_done
        )
        self._critic = Critique(nli=nli)
        self._max_replans = max_replans

    async def plan_only(
        self,
        *,
        goal: str,
        language: str = "es",
        congregation: str | None = None,
    ) -> OrchestrationPlan:
        return await self._planner.plan(
            goal=goal, language=language, congregation=congregation
        )

    async def run_plan(
        self,
        plan: OrchestrationPlan,
    ) -> OrchestrationResult:
        """Execute a pre-built plan (skips the planner stage).

        Useful for replaying a saved plan from disk: load JSON, validate
        through Pydantic, then call this directly. The critique +
        replan loop still applies, so a stale plan may still be revised.
        """
        t0 = time.perf_counter()
        self._emit_plan(plan)
        all_step_results: list[StepResult] = []
        current_plan = plan
        for revision in range(self._max_replans + 1):
            results = await self._executor.run(current_plan)
            all_step_results.extend(results)
            critique = self._critic.run(plan=current_plan, step_results=results)
            self._emit_critique(critique)
            if critique.overall_ok or revision == self._max_replans:
                consolidated = self._consolidate(results)
                total_ms = int((time.perf_counter() - t0) * 1000)
                return OrchestrationResult(
                    plan=current_plan,
                    step_results=all_step_results,
                    critique=critique,
                    consolidated_findings=consolidated,
                    total_elapsed_ms=total_ms,
                    trace_path=self._tracer_path(),
                )
            if critique.suggested_replan is None:
                break
            replan_step = critique.suggested_replan
            current_plan = OrchestrationPlan(
                goal=current_plan.goal,
                language=current_plan.language,
                steps=[replan_step],
                congregation=current_plan.congregation,
                plan_revision=current_plan.plan_revision + 1,
            )

        consolidated = self._consolidate(all_step_results)
        total_ms = int((time.perf_counter() - t0) * 1000)
        return OrchestrationResult(
            plan=current_plan,
            step_results=all_step_results,
            critique=CritiqueVerdict(
                overall_ok=False, reason="max replans reached"
            ),
            consolidated_findings=consolidated,
            total_elapsed_ms=total_ms,
            trace_path=self._tracer_path(),
        )

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
        self._emit_plan(plan)
        all_step_results: list[StepResult] = []
        for revision in range(self._max_replans + 1):
            results = await self._executor.run(plan)
            all_step_results.extend(results)
            critique = self._critic.run(plan=plan, step_results=results)
            self._emit_critique(critique)
            if critique.overall_ok or revision == self._max_replans:
                consolidated = self._consolidate(results)
                total_ms = int((time.perf_counter() - t0) * 1000)
                return OrchestrationResult(
                    plan=plan,
                    step_results=all_step_results,
                    critique=critique,
                    consolidated_findings=consolidated,
                    total_elapsed_ms=total_ms,
                    trace_path=self._tracer_path(),
                )
            if critique.suggested_replan is None:
                break
            replan_step = critique.suggested_replan
            plan = OrchestrationPlan(
                goal=plan.goal,
                language=plan.language,
                steps=[replan_step],
                congregation=plan.congregation,
                plan_revision=plan.plan_revision + 1,
            )

        consolidated = self._consolidate(all_step_results)
        total_ms = int((time.perf_counter() - t0) * 1000)
        return OrchestrationResult(
            plan=plan,
            step_results=all_step_results,
            critique=CritiqueVerdict(
                overall_ok=False, reason="max replans reached"
            ),
            consolidated_findings=consolidated,
            total_elapsed_ms=total_ms,
            trace_path=self._tracer_path(),
        )

    # ---- tracing helpers (F43 bridge) ----

    def _tracer_path(self) -> str | None:
        if self._tracer is None:
            return None
        store = getattr(self._tracer, "store", None)
        path = getattr(store, "_path", None)
        return str(path) if path else None

    def _emit(self, name: str, payload: dict[str, Any]) -> None:
        if self._tracer is None:
            return
        try:
            from jw_agents.tracing.schema import CustomEvent

            self._tracer.store.append(
                CustomEvent(
                    ts=datetime.now(UTC),
                    seq=self._tracer._next_seq(),
                    name=name,
                    payload=payload,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("meta: tracing emit failed (%s); continuing.", exc)

    def _emit_plan(self, plan: OrchestrationPlan) -> None:
        self._emit(
            "meta_plan",
            {
                "goal": plan.goal,
                "language": plan.language,
                "plan_revision": plan.plan_revision,
                "step_ids": [s.id for s in plan.steps],
                "tools": [s.tool for s in plan.steps],
            },
        )

    def _emit_step(self, step: Step, step_result: StepResult) -> None:
        agent_result = step_result.agent_result or {}
        n_findings = (
            len(agent_result.get("findings", []))
            if isinstance(agent_result, dict)
            else 0
        )
        self._emit(
            "meta_step",
            {
                "step_id": step.id,
                "tool": step.tool,
                "status": "error" if step_result.error else "ok",
                "elapsed_ms": step_result.elapsed_ms,
                "error": step_result.error,
                "n_findings": n_findings,
            },
        )

    def _emit_critique(self, critique: CritiqueVerdict) -> None:
        self._emit(
            "meta_critique",
            {
                "overall_ok": critique.overall_ok,
                "findings_per_step": critique.findings_per_step,
                "nli_warnings_count": len(critique.nli_warnings),
                "suggested_replan_tool": (
                    critique.suggested_replan.tool
                    if critique.suggested_replan
                    else None
                ),
                "reason": critique.reason,
            },
        )

    @staticmethod
    def _consolidate(step_results: list[StepResult]) -> list[dict]:
        out: list[dict] = []
        seen_urls: set[str] = set()
        for r in step_results:
            findings = (
                r.agent_result.get("findings", [])
                if isinstance(r.agent_result, dict)
                else []
            )
            for f in findings:
                url = (f.get("citation") or {}).get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                out.append({**f, "step_id": r.step_id})
        return out
