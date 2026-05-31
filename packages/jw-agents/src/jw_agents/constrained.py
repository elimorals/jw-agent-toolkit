r"""run_with_citations — compose procedural agent + LLM under grammar control.

This is the public, single-call API for constrained decoding.

    result = await run_with_citations(prompt, agent=verse_explainer)

Guarantees on the returned AgentResult:
  - Every `finding.citation.url` matches `^https://wol\.jw\.org/...`.
  - Every URL exists in the procedural result (no forgery).
  - The shape is `AgentResultModel`-valid (Pydantic v2).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from jw_core.grammar.factory import ConstrainedCaller, get_default_constrained_caller
from jw_core.grammar.schemas import AgentResultModel
from pydantic import ValidationError

from jw_agents.base import AgentResult


class CitationForgeryError(RuntimeError):
    """Raised when the LLM emits a citation URL not present in procedural findings."""


AgentCallable = Callable[[dict[str, Any]], Awaitable[AgentResult] | AgentResult]


async def run_with_citations(
    prompt: str,
    agent: AgentCallable,
    caller: ConstrainedCaller | None = None,
    *,
    schema: type = AgentResultModel,
    language: str = "en",
    temperature: float = 0.3,
) -> AgentResult:
    """Run agent procedurally first, then constrain an LLM with its findings."""

    procedural = await _maybe_await(agent({"question": prompt, "language": language}))
    if not procedural.findings:
        procedural.warnings.append("constrained: no procedural findings to anchor citations")
        return procedural

    caller = caller or get_default_constrained_caller()
    enriched_prompt = _build_prompt(prompt, procedural)
    raw = await caller.generate(enriched_prompt, json_schema=schema, temperature=temperature)

    try:
        model = AgentResultModel.model_validate_json(raw)
    except ValidationError as exc:
        raise CitationForgeryError(f"LLM emitted shape that fails schema: {exc}") from exc

    procedural_urls = {f.citation.url for f in procedural.findings}
    for f in model.findings:
        if f.citation.url not in procedural_urls:
            raise CitationForgeryError(f"LLM emitted URL not in procedural findings: {f.citation.url}")

    return model.to_dataclass()


def _build_prompt(user_prompt: str, procedural: AgentResult) -> str:
    """Inline the procedural findings so the LLM cannot invent new URLs and pass reconciliation."""

    lines = [
        "User question:",
        user_prompt.strip(),
        "",
        "Verified sources (use ONLY these URLs in `citation.url`):",
    ]
    for i, f in enumerate(procedural.findings):
        lines.append(f"{i + 1}. url={f.citation.url} title={f.citation.title!r} summary={f.summary[:200]!r}")
    lines.append("")
    lines.append(
        "Emit a single JSON object matching the AgentResult schema. Every citation.url MUST appear in the list above."
    )
    return "\n".join(lines)


async def _maybe_await(value: Awaitable[AgentResult] | AgentResult) -> AgentResult:
    if inspect.isawaitable(value):
        return await value  # type: ignore[no-any-return]
    return value  # type: ignore[return-value]
