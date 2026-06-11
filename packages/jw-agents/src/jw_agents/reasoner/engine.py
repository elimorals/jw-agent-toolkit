"""End-to-end doctrinal reasoner engine (Fase 67).

Pipeline:
  1. Reformulate hostile framing (opt-in).
  2. Plan reasoning steps with LLM.
  3. Run ReAct loop: dispatch tool -> attach citation -> NLI verify.
  4. Optionally generate prose summary of the tree.

The `tool_dispatcher` is injectable so the meta-orchestrator can plug in
its own retrieval. The default dispatcher is a no-op that returns no
citation; users wiring the full apologetics stack provide their own.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from jw_agents.reasoner.executor import ToolDispatcher, run_react_loop
from jw_agents.reasoner.models import (
    ReasonerConfig,
    ReasoningStep,
    ReasoningTree,
)
from jw_agents.reasoner.planner import Planner
from jw_agents.reasoner.reformulator import (
    detect_toxic_framing,
    reformulate_neutral,
)

logger = logging.getLogger(__name__)


class LLMLike(Protocol):
    name: str

    async def acomplete(self, prompt: str) -> str: ...


def _summary_prose(
    tree: ReasoningTree, *, language: str = "es"
) -> str:
    """Render a short prose summary that follows the DAG.

    Heuristic: list premises first, then inferences, then conclusion(s).
    Cites `wol_url` inline when present. No LLM required, deterministic.
    """
    sections: dict[str, list[str]] = {
        "premise": [],
        "inference": [],
        "harmonization": [],
        "conclusion": [],
    }
    for s in tree.steps:
        sections.setdefault(s.kind, []).append(s.statement)

    lead = {
        "es": "Resumen del razonamiento:",
        "en": "Reasoning summary:",
        "pt": "Resumo do raciocínio:",
    }.get(language, "Reasoning summary:")
    parts: list[str] = [lead]
    label = {
        "es": {
            "premise": "Premisas",
            "inference": "Inferencias",
            "harmonization": "Armonizaciones",
            "conclusion": "Conclusiones",
        },
        "en": {
            "premise": "Premises",
            "inference": "Inferences",
            "harmonization": "Harmonizations",
            "conclusion": "Conclusions",
        },
        "pt": {
            "premise": "Premissas",
            "inference": "Inferências",
            "harmonization": "Harmonizações",
            "conclusion": "Conclusões",
        },
    }.get(language, {})
    for kind in ("premise", "inference", "harmonization", "conclusion"):
        items = sections[kind]
        if not items:
            continue
        parts.append("")
        parts.append(f"{label.get(kind, kind.title())}:")
        for item in items:
            parts.append(f"- {item}")

    if tree.truncated:
        parts.append("")
        parts.append(
            {
                "es": "Nota: el árbol se truncó por una verificación NLI fallida.",
                "en": "Note: the tree was truncated due to a failed NLI check.",
                "pt": "Nota: a árvore foi truncada por uma verificação NLI falhada.",
            }.get(language, "Note: the tree was truncated.")
        )

    return "\n".join(parts)


async def doctrinal_reasoner(
    *,
    question: str,
    llm: LLMLike,
    config: ReasonerConfig | None = None,
    nli: Any | None = None,
    tool_dispatcher: ToolDispatcher | None = None,
    use_real_dispatcher: bool = False,
) -> ReasoningTree:
    """Top-level reasoner entry point.

    `use_real_dispatcher=True` wires the agent-backed
    `real_tool_dispatcher` when no explicit dispatcher is passed.
    Default stays False so existing tests stay hermetic.
    """

    cfg = config or ReasonerConfig()
    if tool_dispatcher is None and use_real_dispatcher:
        from jw_agents.reasoner.dispatchers import real_tool_dispatcher

        tool_dispatcher = real_tool_dispatcher
    normalized = question
    if cfg.reformulate_toxic and detect_toxic_framing(question):
        normalized = reformulate_neutral(question, language=cfg.language)

    planner = Planner(llm=llm, max_steps=cfg.max_steps)
    steps: list[ReasoningStep] = await planner.plan(
        question_normalized=normalized,
        language=cfg.language,
    )

    tree = await run_react_loop(
        question_original=question,
        question_normalized=normalized,
        steps=steps,
        nli=nli,
        nli_mode=cfg.nli_mode,
        tool_dispatcher=tool_dispatcher,
    )

    if cfg.include_summary_prose and tree.steps:
        tree.summary_prose = _summary_prose(tree, language=cfg.language)

    return tree
