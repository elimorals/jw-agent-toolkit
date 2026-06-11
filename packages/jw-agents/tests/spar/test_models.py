"""Spar Pydantic models."""

from __future__ import annotations

import pytest

from jw_agents.spar.models import (
    Persona,
    PersonaTurnResponse,
    SparSession,
    TurnFeedback,
    UserTurn,
)


def test_persona_minimal() -> None:
    p = Persona(
        key="catholic",
        display_name="María (católica)",
        language="es",
        tone="warm",
    )
    assert p.core_beliefs == []
    assert p.typical_doubts == []


def test_persona_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        Persona(
            key="zoroastrian",  # type: ignore[arg-type]
            display_name="x",
            language="es",
            tone="warm",
        )


def test_user_turn_round_trip() -> None:
    t = UserTurn(text="Buenos días", turn_index=0)
    dumped = t.model_dump()
    rehydrated = UserTurn.model_validate(dumped)
    assert rehydrated.turn_index == 0
    assert rehydrated.voice_audio_path is None


def test_persona_turn_response_defaults() -> None:
    r = PersonaTurnResponse(reply="Hola")
    assert r.hidden_doubts == []
    assert r.needs_followup is False


def test_turn_feedback_minimal() -> None:
    fb = TurnFeedback(user_turn_index=0, citation_quality="missing")
    assert fb.nli_verdict == "skipped"
    assert fb.nli_score is None


def test_turn_feedback_rejects_out_of_range_nli() -> None:
    with pytest.raises(ValueError):
        TurnFeedback(
            user_turn_index=0,
            citation_quality="strong",
            nli_score=1.5,
            nli_verdict="entails",
        )


def test_spar_session_round_trip() -> None:
    p = Persona(
        key="atheist",
        display_name="Ana",
        language="es",
        tone="skeptical",
    )
    s = SparSession(
        session_id="sess-1",
        persona=p,
        language="es",
        started_at="2026-06-11T15:00:00",
    )
    dumped = s.model_dump()
    rehydrated = SparSession.model_validate(dumped)
    assert rehydrated.session_id == "sess-1"
    assert rehydrated.persona.key == "atheist"
