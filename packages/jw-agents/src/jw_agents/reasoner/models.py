"""Pydantic models for the doctrinal reasoner (Fase 67)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

StepKind = Literal["premise", "inference", "harmonization", "conclusion"]
NLIStatus = Literal["entails", "neutral", "contradicts", "skipped"]
SourceKind = Literal[
    "verse",
    "study_note",
    "cross_ref",
    "topic_index",
    "topic_subheading",
    "cdn_search",
    "rag",
]


class Citation(BaseModel):
    text: str
    wol_url: str
    source_kind: SourceKind


class ReasoningStep(BaseModel):
    id: str
    kind: StepKind
    statement: str
    depends_on: list[str] = Field(default_factory=list)
    rationale: str = ""
    citation: Citation | None = None
    nli_status: NLIStatus = "skipped"
    nli_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rejected_reason: str | None = None


class ReasoningTree(BaseModel):
    question_original: str
    question_normalized: str
    sub_questions: list[str] = Field(default_factory=list)
    steps: list[ReasoningStep]
    truncated: bool = False
    summary_prose: str = ""
    trace_path: str | None = None
    nli_provider_used: str | None = None

    @model_validator(mode="after")
    def _validate_dag(self) -> "ReasoningTree":
        ids = {s.id for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                if dep == s.id:
                    raise ValueError(f"step {s.id} depends on itself")
                if dep not in ids:
                    raise ValueError(
                        f"step {s.id} depends on missing {dep}"
                    )
        return self


class ReasonerConfig(BaseModel):
    language: Literal["en", "es", "pt"] = "es"
    max_steps: int = Field(default=12, ge=1, le=50)
    nli_mode: Literal["off", "warn", "reject"] = "reject"
    reformulate_toxic: bool = True
    include_summary_prose: bool = True
