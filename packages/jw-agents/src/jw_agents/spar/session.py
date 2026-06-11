"""Spar session manager (Fase 66).

Holds in-process `SparSession` objects keyed by `session_id` and
optionally mirrors every turn into a `MemoryStore` (F61) so the
conversation can be recovered across processes.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from jw_agents.memory.protocol import MemoryRecord, MemoryStore
from jw_agents.spar.models import (
    Persona,
    PersonaTurnResponse,
    SparSession,
    UserTurn,
)
from jw_agents.spar.personas import get_persona
from jw_agents.spar.simulator import LLMProviderLike, simulate_persona_turn

logger = logging.getLogger(__name__)


# In-process registry so the CLI / MCP can address sessions by id.
_SESSIONS: dict[str, SparSession] = {}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _record_turn(
    store: MemoryStore | None,
    *,
    session_id: str,
    kind: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if store is None:
        return
    try:
        store.record(
            MemoryRecord(
                session_id=session_id,
                timestamp=datetime.now(UTC),
                kind=kind,  # type: ignore[arg-type]
                content=content,
                metadata=metadata or {},
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("spar: memory store record failed: %s", exc)


def _maybe_persist(session: SparSession) -> None:
    """Autosave the session to SQLite when `JW_SPAR_PERSIST=1`."""
    if os.environ.get("JW_SPAR_PERSIST", "0").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        from jw_agents.spar.persistence import save_session

        save_session(session)
    except Exception as exc:  # noqa: BLE001
        logger.debug("spar: autosave failed: %s", exc)


def start_session(
    *,
    persona_key: str,
    language: str = "es",
    store: MemoryStore | None = None,
    session_id: str | None = None,
) -> SparSession:
    """Create a new SparSession and register it in-process."""

    persona: Persona = get_persona(persona_key)
    sid = session_id or f"spar-{uuid.uuid4().hex[:8]}"
    session = SparSession(
        session_id=sid,
        persona=persona,
        language=language,  # type: ignore[arg-type]
        started_at=_now_iso(),
    )
    _SESSIONS[sid] = session
    _record_turn(
        store,
        session_id=sid,
        kind="preference",
        content=f"persona={persona_key} language={language}",
        metadata={"persona": persona_key, "language": language},
    )
    return session


async def take_turn(
    *,
    session_id: str,
    user_text: str,
    llm: LLMProviderLike,
    store: MemoryStore | None = None,
    max_turns: int = 20,
) -> PersonaTurnResponse:
    """Record one user turn, ask the LLM for the persona reply."""

    if session_id not in _SESSIONS:
        raise KeyError(f"unknown session {session_id!r}")
    session = _SESSIONS[session_id]
    if session.closed:
        raise RuntimeError(f"session {session_id} is closed")
    if len(session.user_turns) >= max_turns:
        raise RuntimeError(
            f"session {session_id} reached max_turns={max_turns}"
        )

    turn_index = len(session.user_turns)
    user_turn = UserTurn(text=user_text, turn_index=turn_index)
    session.user_turns.append(user_turn)
    _record_turn(
        store,
        session_id=session_id,
        kind="question",
        content=user_text,
        metadata={"turn_index": turn_index},
    )

    history = [
        (u.text, p.reply)
        for u, p in zip(
            session.user_turns[:-1], session.persona_turns, strict=False
        )
    ]
    response = await simulate_persona_turn(
        persona=session.persona,
        history=history,
        user_turn=user_turn,
        llm=llm,
        language=session.language,
    )
    session.persona_turns.append(response)
    _record_turn(
        store,
        session_id=session_id,
        kind="answer",
        content=response.reply,
        metadata={
            "turn_index": turn_index,
            "needs_followup": response.needs_followup,
        },
    )
    _maybe_persist(session)
    return response


def close_session(
    *,
    session_id: str,
    score_fn: Callable[[SparSession], Awaitable[SparSession]] | None = None,
    store: MemoryStore | None = None,
) -> SparSession:
    """Mark a session closed. `score_fn` is the post-session feedback hook."""

    if session_id not in _SESSIONS:
        raise KeyError(f"unknown session {session_id!r}")
    session = _SESSIONS[session_id]
    session.closed = True
    if store is not None:
        _record_turn(
            store,
            session_id=session_id,
            kind="fact_recalled",
            content=f"session closed after {len(session.user_turns)} turns",
            metadata={"user_turns": len(session.user_turns)},
        )
    _maybe_persist(session)
    return session


def get_session(session_id: str) -> SparSession:
    if session_id not in _SESSIONS:
        raise KeyError(f"unknown session {session_id!r}")
    return _SESSIONS[session_id]


def list_active_sessions() -> list[str]:
    return [sid for sid, s in _SESSIONS.items() if not s.closed]


def clear_sessions() -> None:
    """Reset in-process registry (tests only)."""
    _SESSIONS.clear()
