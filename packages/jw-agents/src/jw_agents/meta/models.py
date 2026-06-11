"""Pydantic models for the meta-orchestrator (Fase 65)."""

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
