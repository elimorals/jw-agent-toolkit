"""LLM planner stage of the doctrinal reasoner (Fase 67)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_agents.reasoner.models import ReasoningStep

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_VALID_KINDS = {"premise", "inference", "harmonization", "conclusion"}


class LLMProviderLike(Protocol):
    name: str

    async def acomplete(self, prompt: str) -> str: ...


class Planner:
    """LLM-driven planner producing a list of `ReasoningStep`."""

    def __init__(self, *, llm: LLMProviderLike, max_steps: int = 12) -> None:
        self._llm = llm
        self._max_steps = max_steps
        self._jinja = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            undefined=StrictUndefined,
        )

    async def plan(
        self,
        *,
        question_normalized: str,
        sub_questions: list[str] | None = None,
        language: str = "es",
    ) -> list[ReasoningStep]:
        template_name = f"planner_{language}.j2"
        try:
            template = self._jinja.get_template(template_name)
        except Exception:
            template = self._jinja.get_template("planner_en.j2")

        prompt = template.render(
            question_normalized=question_normalized,
            sub_questions=sub_questions or [],
            max_steps=self._max_steps,
        )
        raw = await self._llm.acomplete(prompt)
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON from planner: {exc}"
            ) from exc

        steps_raw = payload.get("steps", [])
        if len(steps_raw) > self._max_steps:
            raise ValueError(
                f"too many steps: {len(steps_raw)} > {self._max_steps}"
            )

        steps: list[ReasoningStep] = []
        ids_seen: set[str] = set()
        for s in steps_raw:
            kind = s.get("kind")
            if kind not in _VALID_KINDS:
                raise ValueError(f"invalid kind: {kind!r}")
            sid = s.get("id")
            if not sid or sid in ids_seen:
                raise ValueError(f"invalid or duplicate id: {sid!r}")
            for dep in s.get("depends_on") or []:
                if dep not in ids_seen:
                    raise ValueError(
                        f"step {sid} depends on unseen id {dep!r}"
                    )
            steps.append(
                ReasoningStep(
                    id=sid,
                    kind=kind,
                    statement=s.get("statement", ""),
                    depends_on=list(s.get("depends_on") or []),
                    rationale=s.get("rationale", ""),
                )
            )
            ids_seen.add(sid)
        return steps
