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
    def evaluate_entailment(
        self, *, claim: str, premise: str
    ) -> NLIVerdictLike: ...


_VERIFIABLE_KINDS = {
    "verse",
    "study_note",
    "topic_subject",
    "topic_subheading",
    "cdn_search",
}


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
            findings = (
                r.agent_result.get("findings", [])
                if isinstance(r.agent_result, dict)
                else []
            )
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
                claim = f.get("summary") or premise
                try:
                    verdict = self._nli.evaluate_entailment(
                        claim=claim, premise=premise
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("meta critique: NLI raised %s", exc)
                    continue
                if str(verdict.verdict) != "entails":
                    nli_warnings.append(
                        f"step={f.get('step_id', '?')} "
                        f"kind={f.get('kind')} verdict={verdict.verdict}"
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
