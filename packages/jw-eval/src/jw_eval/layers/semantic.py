"""L3 — semantic Q&A eval.

Pipeline:
  1) Run agent on case.input.
  2) Concatenate finding.text into `candidate`.
  3) Compute cosine(embedder(candidate), embedder(golden_answer)).
  4) Apply expected_keywords_any / expected_keywords_none — any miss is a fail
     regardless of cosine.
  5) Classify cosine: pass / review / fail.
     - pass -> verdict pass
     - fail -> verdict fail
     - review -> escalate to LLM judge if available; else mark as 'review' (treated as fail).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from jw_eval.judges.embeddings import EmbeddingsJudge
from jw_eval.models import GoldenCase, LayerResult


class LLMJudgeLike(Protocol):
    def judge(
        self,
        golden: str,
        candidate: str,
        keywords_any: list[str],
        keywords_none: list[str],
    ) -> tuple[str, str]: ...


def _join_findings(result: Any) -> str:
    parts: list[str] = []
    for f in getattr(result, "findings", []) or []:
        t = getattr(f, "text", "") or getattr(f, "summary", "") or ""
        if t:
            parts.append(t)
    return "\n".join(parts)


def evaluate_semantic(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    embeddings_judge: EmbeddingsJudge,
    llm_judge: LLMJudgeLike | None = None,
) -> LayerResult:
    started = time.monotonic()
    exp = case.expected
    golden = str(exp.get("golden_answer") or "")
    kw_any: list[str] = list(exp.get("expected_keywords_any") or [])
    kw_none: list[str] = list(exp.get("expected_keywords_none") or [])
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l3",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    candidate = _join_findings(result)

    # Keyword gates run BEFORE cosine — they're hard rules.
    cand_lower = candidate.lower()
    if kw_any and not any(k.lower() in cand_lower for k in kw_any):
        reasons.append(f"none of expected_keywords_any present: {kw_any}")
    for k in kw_none:
        if k.lower() in cand_lower:
            reasons.append(f"forbidden keyword present: {k!r}")

    score = embeddings_judge.cosine(candidate, golden) if golden else 0.0
    bucket = embeddings_judge.classify(score)

    if reasons:
        verdict = "fail"
    elif bucket == "pass":
        verdict = "pass"
    elif bucket == "fail":
        verdict = "fail"
        reasons.append(f"cosine={score:.3f} below threshold")
    else:  # review
        if llm_judge is None:
            verdict = "fail"
            reasons.append(f"cosine={score:.3f} in review band, no LLM judge configured")
        else:
            v, why = llm_judge.judge(golden=golden, candidate=candidate, keywords_any=kw_any, keywords_none=kw_none)
            verdict = v if v in {"pass", "fail"} else "error"
            reasons.append(f"escalated to LLM: {why}")

    return LayerResult(
        case_id=case.id,
        layer="l3",
        verdict=verdict,
        score=score,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
