"""Persona LLM simulator (Fase 66).

Produces a `PersonaTurnResponse` given a `Persona`, the conversation
history, and the user's current turn. Uses an LLM provider with the
`acomplete(prompt: str) -> str` shape (same as F65's planner).

Includes a deterministic `FakeSparLLM` that cycles canned replies
indexed by `(persona_key, turn_index)`. This is what keeps tests
offline and what `JW_SPAR_LLM=fake` resolves to in production.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_agents.spar.models import Persona, PersonaTurnResponse, UserTurn

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


class LLMProviderLike(Protocol):
    name: str

    async def acomplete(self, prompt: str) -> str: ...


def _render_prompt(
    *,
    persona: Persona,
    history: list[tuple[str, str]],
    current_user_turn: str,
    language: str,
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        undefined=StrictUndefined,
    )
    template_name = f"persona_{language}.j2"
    try:
        template = env.get_template(template_name)
    except Exception:
        template = env.get_template("persona_en.j2")
    turns = [{"user": u, "persona": p} for u, p in history]
    return template.render(
        persona=persona,
        profile_md=persona.profile_md,
        turns=turns,
        current_user_turn=current_user_turn,
    )


async def simulate_persona_turn(
    *,
    persona: Persona,
    history: list[tuple[str, str]],
    user_turn: UserTurn,
    llm: LLMProviderLike,
    language: str = "es",
) -> PersonaTurnResponse:
    """Ask `llm` for the persona's reply. Falls back to a safe stub on parse error."""

    prompt = _render_prompt(
        persona=persona,
        history=history,
        current_user_turn=user_turn.text,
        language=language,
    )
    raw = await llm.acomplete(prompt)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "spar: persona LLM returned non-JSON (%s); using safe stub.",
            exc,
        )
        return PersonaTurnResponse(reply=raw.strip()[:500] or "...")
    return PersonaTurnResponse(
        reply=str(payload.get("reply", "")),
        hidden_doubts=list(payload.get("hidden_doubts") or []),
        references_cited=list(payload.get("references_cited") or []),
        needs_followup=bool(payload.get("needs_followup", False)),
    )


class FakeSparLLM:
    """Deterministic fake LLM cycling canned replies for offline tests."""

    name = "fake"

    _CANNED: dict[str, list[dict]] = {
        "catholic": [
            {
                "reply": (
                    "Buenos días. Mire, ya tengo mi religión, pero "
                    "cuénteme: ¿de qué quiere hablar?"
                ),
                "hidden_doubts": ["¿qué quiere de mí?"],
                "references_cited": [],
                "needs_followup": True,
            },
            {
                "reply": (
                    "Eso de los 144.000... eso siempre me ha sonado raro."
                ),
                "hidden_doubts": ["¿solo 144.000 al cielo?"],
                "references_cited": [],
                "needs_followup": True,
            },
        ],
        "evangelical": [
            {
                "reply": "Hermano, conozco la Biblia. ¿En qué pasaje se basa?",
                "hidden_doubts": ["¿cita Biblia o doctrina propia?"],
                "references_cited": [],
                "needs_followup": True,
            }
        ],
        "atheist": [
            {
                "reply": (
                    "No creo en eso, gracias. Pero si tiene un argumento "
                    "racional, escucho."
                ),
                "hidden_doubts": ["¿evidencia o solo fe?"],
                "references_cited": [],
                "needs_followup": False,
            }
        ],
        "muslim": [
            {
                "reply": "Ya tengo mi fe. Pero respeto la conversación.",
                "hidden_doubts": ["¿reconoce al profeta?"],
                "references_cited": [],
                "needs_followup": False,
            }
        ],
        "nominal": [
            {
                "reply": "Creo en Dios pero no en religiones organizadas.",
                "hidden_doubts": ["¿por qué tantas religiones?"],
                "references_cited": [],
                "needs_followup": True,
            }
        ],
        "young_skeptic": [
            {
                "reply": (
                    "Mira, no creo en la religión así, pero soy curiosa."
                ),
                "hidden_doubts": ["¿esto aplica a mi vida?"],
                "references_cited": [],
                "needs_followup": True,
            }
        ],
    }

    # Detection markers from display_name / tone so the fake routes to the
    # right canned response without needing the persona key in the prompt.
    # Order matters: longer / more specific markers win first.
    _DETECT: tuple[tuple[str, str], ...] = (
        ("pastor carlos", "evangelical"),
        ("pentecostal", "evangelical"),
        ("evangelical", "evangelical"),
        ("ahmed", "muslim"),
        ("musulmán", "muslim"),
        ("muslim", "muslim"),
        ("roberto", "nominal"),
        ("nominal", "nominal"),
        ("luna", "young_skeptic"),
        ("escéptica", "young_skeptic"),
        ("young_skeptic", "young_skeptic"),
        ("ana", "atheist"),
        ("atea", "atheist"),
        ("atheist", "atheist"),
        ("maría", "catholic"),
        ("católica", "catholic"),
        ("catholic", "catholic"),
    )

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    @classmethod
    def _detect_persona(cls, prompt: str) -> str:
        """Pick a persona by matching markers on whole words.

        Word-boundary lookup so "ana" does NOT match "practic*ana*te" inside
        catholic's display_name "(católica practicante)". Matching is
        case-insensitive and Unicode-aware via re's \\b on the lowercased prompt.
        """
        import re

        lowered = prompt.lower()
        for marker, key in cls._DETECT:
            if re.search(rf"\b{re.escape(marker)}\b", lowered):
                return key
        return "catholic"

    async def acomplete(self, prompt: str) -> str:
        persona_key = self._detect_persona(prompt)
        canned = self._CANNED[persona_key]
        idx = self._counters.get(persona_key, 0)
        payload = canned[idx % len(canned)]
        self._counters[persona_key] = idx + 1
        return json.dumps(payload)
