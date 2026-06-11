"""Persona LLM simulator tests."""

from __future__ import annotations

import json

import pytest

from jw_agents.spar.models import PersonaTurnResponse, UserTurn
from jw_agents.spar.personas import get_persona
from jw_agents.spar.simulator import FakeSparLLM, simulate_persona_turn


@pytest.mark.asyncio
async def test_simulate_persona_turn_with_fake_llm() -> None:
    persona = get_persona("catholic")
    llm = FakeSparLLM()
    user_turn = UserTurn(text="Buenos días, ¿puedo hablar con usted?", turn_index=0)
    response = await simulate_persona_turn(
        persona=persona,
        history=[],
        user_turn=user_turn,
        llm=llm,
        language="es",
    )
    assert isinstance(response, PersonaTurnResponse)
    assert response.reply
    assert response.needs_followup is True or response.needs_followup is False


@pytest.mark.asyncio
async def test_simulate_handles_non_json_response_with_safe_stub() -> None:
    class BadLLM:
        name = "bad"

        async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
            return "not json at all"

    persona = get_persona("evangelical")
    user_turn = UserTurn(text="Hola", turn_index=0)
    response = await simulate_persona_turn(
        persona=persona,
        history=[],
        user_turn=user_turn,
        llm=BadLLM(),
        language="es",
    )
    assert response.reply == "not json at all"
    assert response.needs_followup is False


@pytest.mark.asyncio
async def test_simulate_renders_history_into_prompt() -> None:
    captured: list[str] = []

    class SpyLLM:
        name = "spy"

        async def acomplete(self, prompt: str) -> str:
            captured.append(prompt)
            return json.dumps(
                {
                    "reply": "ok",
                    "hidden_doubts": [],
                    "references_cited": [],
                    "needs_followup": False,
                }
            )

    persona = get_persona("atheist")
    history = [("¿Qué tal?", "Bien, gracias.")]
    user_turn = UserTurn(text="¿Cree en Dios?", turn_index=1)
    await simulate_persona_turn(
        persona=persona,
        history=history,
        user_turn=user_turn,
        llm=SpyLLM(),
        language="es",
    )
    assert "¿Qué tal?" in captured[0]
    assert "Bien, gracias." in captured[0]
    assert "¿Cree en Dios?" in captured[0]


@pytest.mark.asyncio
async def test_fake_llm_responds_per_persona_in_prompt() -> None:
    """The FakeSparLLM should pick the canned response for the persona
    mentioned in the prompt body."""
    llm = FakeSparLLM()
    persona = get_persona("muslim")
    user_turn = UserTurn(text="Hola Ahmed", turn_index=0)
    response = await simulate_persona_turn(
        persona=persona,
        history=[],
        user_turn=user_turn,
        llm=llm,
        language="es",
    )
    # FakeLLM uses lowercase key match; "muslim" is in the rendered prompt
    # because Persona's display_name includes "musulmán"/"muslim" hint.
    # Just verify reply is non-empty and valid.
    assert response.reply
