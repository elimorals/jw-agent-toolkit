"""L1 — Structural eval.

Runs the agent on the case input and checks the AgentResult shape against
the expected dict. Pure CPU, no network.

Expected keys (all optional, all enforced when present):
  min_findings: int                      — len(result.findings) >= N
  must_have_source: str                  — any finding has metadata.source == X
  sources_in_order: list[str]            — result.findings[i].metadata.source matches in order
  must_have_citation: bool               — every finding has metadata.source set
  forbidden_keywords_in_findings: list   — none of these substrings in any finding.text
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from jw_eval.models import GoldenCase, LayerResult


class _AgentResultLike(Protocol):
    findings: list[Any]  # each finding has `.text` and `.metadata`


AgentCallable = Callable[[dict[str, Any]], _AgentResultLike]


def evaluate_structural(case: GoldenCase, agent: AgentCallable) -> LayerResult:
    """Evaluate one L1 case. `agent` is a callable returning an AgentResult-like object."""

    started = time.monotonic()
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l1",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    findings = list(result.findings)
    exp = case.expected

    min_n = exp.get("min_findings")
    if isinstance(min_n, int) and len(findings) < min_n:
        reasons.append(f"min_findings={min_n} but got {len(findings)}")

    must_src = exp.get("must_have_source")
    if isinstance(must_src, str) and not any(getattr(f, "metadata", {}).get("source") == must_src for f in findings):
        reasons.append(f"missing required source={must_src!r}")

    ordered = exp.get("sources_in_order")
    if isinstance(ordered, list):
        actual = [getattr(f, "metadata", {}).get("source") for f in findings[: len(ordered)]]
        if actual != ordered:
            reasons.append(f"sources_in_order expected {ordered}, got {actual}")

    if exp.get("must_have_citation") is True:
        for i, f in enumerate(findings):
            if not getattr(f, "metadata", {}).get("source"):
                reasons.append(f"finding[{i}] lacks metadata.source")

    forbidden = exp.get("forbidden_keywords_in_findings") or []
    for kw in forbidden:
        for i, f in enumerate(findings):
            text = getattr(f, "text", "") or ""
            if kw.lower() in text.lower():
                reasons.append(f"forbidden keyword {kw!r} found in finding[{i}]")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l1",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
