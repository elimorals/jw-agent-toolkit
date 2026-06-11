"""ReAct loop executor for the doctrinal reasoner (Fase 67).

For each `ReasoningStep` produced by the planner:
  1. Resolve a citation via a `tool_dispatcher` (configurable).
  2. Run NLI F39 on (claim=statement, premise=citation.text).
  3. Commit / warn / truncate the tree based on the configured mode.

The dispatcher signature is intentionally minimal so tests can inject a
fake. In production it routes by `tool_hint` to the apologetics tool set.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from jw_agents.reasoner.models import (
    Citation,
    NLIStatus,
    ReasoningStep,
    ReasoningTree,
)

logger = logging.getLogger(__name__)


class NLILike(Protocol):
    name: str

    def evaluate_entailment(
        self, *, claim: str, premise: str
    ) -> Any: ...


ToolDispatcher = Callable[[ReasoningStep], Awaitable[Citation | None]]


async def _no_tool_dispatcher(step: ReasoningStep) -> Citation | None:
    """Default: no tool wiring -> no citation."""
    return None


def _run_nli(
    nli: NLILike | None, *, claim: str, premise: str
) -> tuple[NLIStatus, float | None]:
    """Return (verdict, score) or ('skipped', None) if no NLI."""
    if nli is None:
        return ("skipped", None)
    try:
        verdict = nli.evaluate_entailment(claim=claim, premise=premise)
    except Exception as exc:  # noqa: BLE001
        logger.debug("reasoner: NLI raised %s; treating as skipped", exc)
        return ("skipped", None)
    v = str(getattr(verdict, "verdict", "skipped"))
    if v not in ("entails", "neutral", "contradicts"):
        v = "skipped"
    raw_score = getattr(verdict, "score", None)
    score = (
        float(raw_score)
        if isinstance(raw_score, (int, float))
        else None
    )
    return (v, score)  # type: ignore[return-value]


async def run_react_loop(
    *,
    question_original: str,
    question_normalized: str,
    steps: list[ReasoningStep],
    nli: NLILike | None = None,
    nli_mode: str = "reject",
    tool_dispatcher: ToolDispatcher | None = None,
) -> ReasoningTree:
    """Walk each step, attach citation+NLI, truncate on reject."""

    dispatcher = tool_dispatcher or _no_tool_dispatcher
    out_steps: list[ReasoningStep] = []
    truncated = False

    for step in steps:
        citation = await dispatcher(step)
        premise = citation.text if citation else ""
        if not premise:
            # No retrieval evidence; we can still keep the step but cannot
            # verify it. Mark NLI skipped and emit unchanged.
            step.citation = None
            step.nli_status = "skipped"
            out_steps.append(step)
            continue

        verdict, score = _run_nli(
            nli, claim=step.statement, premise=premise
        )
        step.citation = citation
        step.nli_status = verdict
        step.nli_score = score

        if verdict == "contradicts" and nli_mode == "reject":
            step.rejected_reason = (
                "NLI verdict contradicts retrieved premise; tree truncated."
            )
            out_steps.append(step)
            truncated = True
            break

        out_steps.append(step)

    return ReasoningTree(
        question_original=question_original,
        question_normalized=question_normalized,
        steps=out_steps,
        truncated=truncated,
        nli_provider_used=getattr(nli, "name", None) if nli else None,
    )
