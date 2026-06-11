"""Pydantic models for conversation sparring (Fase 66)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PersonaKey = Literal[
    "catholic",
    "evangelical",
    "atheist",
    "muslim",
    "nominal",
    "young_skeptic",
]


class Persona(BaseModel):
    key: PersonaKey
    display_name: str
    language: Literal["en", "es", "pt"]
    core_beliefs: list[str] = Field(default_factory=list)
    typical_doubts: list[str] = Field(default_factory=list)
    tone: Literal["warm", "neutral", "skeptical", "guarded"]
    profile_md: str = ""


class UserTurn(BaseModel):
    text: str
    voice_audio_path: str | None = None
    turn_index: int


class PersonaTurnResponse(BaseModel):
    reply: str
    hidden_doubts: list[str] = Field(default_factory=list)
    references_cited: list[str] = Field(default_factory=list)
    needs_followup: bool = False


class TurnFeedback(BaseModel):
    user_turn_index: int
    nli_verdict: Literal[
        "entails", "neutral", "contradicts", "skipped"
    ] = "skipped"
    nli_score: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_quality: Literal["strong", "weak", "missing"]
    suggested_source: str | None = None
    suggested_phrasing: str | None = None


class SparSession(BaseModel):
    session_id: str
    persona: Persona
    language: Literal["en", "es", "pt"]
    started_at: str
    user_turns: list[UserTurn] = Field(default_factory=list)
    persona_turns: list[PersonaTurnResponse] = Field(default_factory=list)
    feedback: list[TurnFeedback] = Field(default_factory=list)
    resolved_objections: list[str] = Field(default_factory=list)
    closed: bool = False
    score_summary: dict[str, float] | None = None
