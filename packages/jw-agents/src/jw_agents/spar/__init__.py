"""jw_agents.spar - conversation sparring with simulated interlocutors (Fase 66).

Public API:
    from jw_agents.spar import (
        Persona, PersonaKey, UserTurn, PersonaTurnResponse, TurnFeedback,
        SparSession, list_personas, get_persona,
    )
"""

from __future__ import annotations

from jw_agents.spar.models import (
    Persona,
    PersonaKey,
    PersonaTurnResponse,
    SparSession,
    TurnFeedback,
    UserTurn,
)
from jw_agents.spar.personas import (
    PersonaNotFound,
    get_persona,
    list_personas,
)

__all__ = [
    "Persona",
    "PersonaKey",
    "PersonaNotFound",
    "PersonaTurnResponse",
    "SparSession",
    "TurnFeedback",
    "UserTurn",
    "get_persona",
    "list_personas",
]
