"""Real tool dispatchers for the doctrinal reasoner (Fase 67 post-MVP).

Resolves each `ReasoningStep` to a `Citation` by calling the closest
matching procedural agent: verse_explainer, research_topic,
apologetics, life_topics. The dispatcher is best-effort: if the agent
returns nothing usable it falls through to None and the step stays
without citation (`nli_status` will become `skipped`).
"""

from __future__ import annotations

import logging
from typing import Any

from jw_agents.reasoner.models import Citation, ReasoningStep

logger = logging.getLogger(__name__)

# Map of tool_hint substrings to dispatcher routes
_HINT_ROUTES: tuple[tuple[str, str], ...] = (
    ("bible.get_verse", "verse"),
    ("verse_explainer", "verse"),
    ("topic_index.search", "topic"),
    ("topic_index", "topic"),
    ("rag.semantic_search", "rag"),
    ("rag", "rag"),
    ("apologetics", "apologetics"),
    ("life_topics", "life_topics"),
)


def _extract_first_finding_with_url(result: Any) -> dict | None:
    """Return the first finding with a citation.url from an AgentResult-like."""
    findings_attr = None
    if isinstance(result, dict):
        findings_attr = result.get("findings")
    else:
        findings_attr = getattr(result, "findings", None)
    if not findings_attr:
        return None
    for raw in findings_attr:
        if isinstance(raw, dict):
            cit = raw.get("citation") or {}
            url = (
                cit.get("url")
                if isinstance(cit, dict)
                else getattr(cit, "url", None)
            )
            text = raw.get("excerpt") or raw.get("summary") or ""
            kind = raw.get("kind") or "rag"
        else:
            cit = getattr(raw, "citation", None)
            url = getattr(cit, "url", None) if cit is not None else None
            text = (
                getattr(raw, "excerpt", "")
                or getattr(raw, "summary", "")
            )
            kind = getattr(raw, "kind", "rag")
        if url and text:
            return {"text": text, "url": url, "kind": kind}
    return None


_KIND_TO_SOURCE: dict[str, str] = {
    "verse": "verse",
    "study_note": "study_note",
    "topic_subject": "topic_index",
    "topic_subheading": "topic_subheading",
    "cdn_search": "cdn_search",
    "rag": "rag",
}


def _wrap_citation(data: dict | None) -> Citation | None:
    if data is None:
        return None
    return Citation(
        text=data["text"][:600],
        wol_url=data["url"],
        source_kind=_KIND_TO_SOURCE.get(data["kind"], "rag"),  # type: ignore[arg-type]
    )


def _route_for(step: ReasoningStep) -> str:
    """Pick a route key from rationale + statement (no tool_hint field today)."""
    hay = f"{step.rationale} {step.statement}".lower()
    for marker, route in _HINT_ROUTES:
        if marker in hay:
            return route
    # Default heuristic: if the statement mentions a Bible book name, try verse.
    return "topic"


async def real_tool_dispatcher(step: ReasoningStep) -> Citation | None:
    """Default dispatcher wired to the 12 builtin agents.

    Best-effort: any exception falls through to `None` so the reasoner
    can continue with NLI skipped on that step.
    """
    route = _route_for(step)

    try:
        if route == "verse":
            from jw_agents.verse_explainer import verse_explainer

            agent_result = await verse_explainer(
                step.statement, language="es"
            )
            return _wrap_citation(
                _extract_first_finding_with_url(agent_result)
            )

        if route == "topic":
            from jw_agents.research_topic import research_topic

            agent_result = await research_topic(
                step.statement, language="E"
            )
            return _wrap_citation(
                _extract_first_finding_with_url(agent_result)
            )

        if route == "apologetics":
            from jw_agents.apologetics import apologetics

            agent_result = await apologetics(
                step.statement, language="E"
            )
            return _wrap_citation(
                _extract_first_finding_with_url(agent_result)
            )

        if route == "life_topics":
            from jw_agents.life_topics import life_topics

            agent_result = await life_topics(
                step.statement, language="es"
            )
            return _wrap_citation(
                _extract_first_finding_with_url(agent_result)
            )

        # rag fallback: try apologetics which itself queries the RAG store
        from jw_agents.apologetics import apologetics

        agent_result = await apologetics(step.statement, language="E")
        return _wrap_citation(
            _extract_first_finding_with_url(agent_result)
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("reasoner dispatcher %s raised: %s", route, exc)
        return None
