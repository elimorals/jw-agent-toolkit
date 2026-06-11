"""LLM planner stage of the meta-orchestrator."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_agents.meta.models import OrchestrationPlan
from jw_agents.meta.registry import list_tools

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class LLMProviderLike(Protocol):
    name: str

    async def acomplete(self, prompt: str) -> str: ...


class Planner:
    """LLM-driven planner producing an `OrchestrationPlan`."""

    def __init__(self, *, llm: LLMProviderLike, max_steps: int = 8) -> None:
        self._llm = llm
        self._max_steps = max_steps
        self._jinja = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            undefined=StrictUndefined,
        )

    async def plan(
        self,
        *,
        goal: str,
        language: str = "es",
        congregation: str | None = None,
    ) -> OrchestrationPlan:
        tools = list_tools()
        template_name = f"planner_{language}.j2"
        try:
            template = self._jinja.get_template(template_name)
        except Exception:
            logger.warning(
                "meta: language %s has no template, falling back to en",
                language,
            )
            template = self._jinja.get_template("planner_en.j2")

        prompt = template.render(
            goal=goal,
            language=language,
            tools=tools,
            congregation=congregation,
            max_steps=self._max_steps,
        )
        raw = await self._llm.acomplete(prompt)
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from planner: {exc}") from exc

        steps_raw = payload.get("steps", [])
        if len(steps_raw) > self._max_steps:
            raise ValueError(
                f"too many steps: {len(steps_raw)} > {self._max_steps}"
            )

        known = {t.name for t in tools}
        for s in steps_raw:
            if s.get("tool") not in known:
                raise ValueError(f"unknown tool: {s.get('tool')}")

        plan = OrchestrationPlan(
            goal=payload.get("goal", goal),
            language=payload.get("language", language),
            steps=steps_raw,
            congregation=congregation,
        )
        return plan
