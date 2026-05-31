"""Pydantic models for the eval suite.

A GoldenCase is one row in the suite. It declares which agent to run, what
input to give it, and what the expected output looks like — shape of
`expected` depends on the layer.

A LayerResult is the verdict for one (case, layer) pair.

A SuiteReport is the aggregate of all LayerResults plus metadata.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LayerName = Literal["l1", "l2", "l3"]
Verdict = Literal["pass", "fail", "skip", "error"]


class GoldenCase(BaseModel):
    """One Golden Q&A case."""

    id: str
    agent: str
    layer: LayerName
    input: dict[str, Any]
    expected: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayerResult(BaseModel):
    """Verdict of evaluating one case at one layer."""

    case_id: str
    layer: LayerName
    verdict: Verdict
    score: float | None = None  # 0..1 for L3; None for L1/L2
    reasons: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class SuiteReport(BaseModel):
    """Aggregate report for a Suite run."""

    started_at: datetime
    finished_at: datetime
    layers_run: list[str]
    results: list[LayerResult]
    summary: dict[str, dict[str, int]] = Field(default_factory=dict)
    diff_vs_baseline: dict[str, Any] | None = None

    @staticmethod
    def summarize(results: list[LayerResult]) -> dict[str, dict[str, int]]:
        """Roll up verdict counts per layer."""

        agg: dict[str, dict[str, int]] = defaultdict(
            lambda: {"pass": 0, "fail": 0, "skip": 0, "error": 0}
        )
        for r in results:
            agg[r.layer][r.verdict] += 1
        return dict(agg)
