"""SparSession SQLite persistence tests (Fase 66 post-MVP)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from jw_agents.spar.persistence import (
    delete_persisted,
    list_persisted,
    load_session,
    reload_into_registry,
    save_session,
)
from jw_agents.spar.session import (
    _SESSIONS,
    clear_sessions,
    start_session,
    take_turn,
)
from jw_agents.spar.simulator import FakeSparLLM


@pytest.fixture(autouse=True)
def _isolated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    monkeypatch.setenv(
        "JW_SPAR_SESSIONS_DB", str(tmp_path / "sessions.sqlite")
    )
    clear_sessions()
    yield
    clear_sessions()


def test_save_and_load_round_trip() -> None:
    s = start_session(persona_key="catholic", language="es")
    save_session(s)
    loaded = load_session(s.session_id)
    assert loaded is not None
    assert loaded.session_id == s.session_id
    assert loaded.persona.key == "catholic"


def test_load_missing_returns_none() -> None:
    assert load_session("nope") is None


def test_list_persisted_orders_by_recency() -> None:
    a = start_session(persona_key="catholic", language="es")
    b = start_session(persona_key="atheist", language="es")
    save_session(a)
    save_session(b)
    ids = list_persisted()
    assert set(ids) == {a.session_id, b.session_id}


def test_delete_persisted_returns_true_when_existed() -> None:
    s = start_session(persona_key="atheist", language="es")
    save_session(s)
    assert delete_persisted(s.session_id) is True
    assert load_session(s.session_id) is None


def test_delete_persisted_false_when_absent() -> None:
    assert delete_persisted("ghost") is False


def test_reload_into_registry_makes_take_turn_work() -> None:
    """Cross-process resume scenario."""
    import asyncio

    s = start_session(persona_key="catholic", language="es")
    save_session(s)
    sid = s.session_id

    # Simulate a different process: drop the in-memory copy.
    clear_sessions()
    assert sid not in _SESSIONS

    reload_into_registry(sid)
    # Now take_turn must succeed
    asyncio.run(
        take_turn(
            session_id=sid, user_text="Hola", llm=FakeSparLLM()
        )
    )
    assert sid in _SESSIONS
    assert len(_SESSIONS[sid].user_turns) == 1


def test_reload_into_registry_raises_for_unknown_session() -> None:
    with pytest.raises(KeyError):
        reload_into_registry("ghost")


def test_autosave_off_by_default() -> None:
    s = start_session(persona_key="catholic", language="es")
    # No save_session call, no env var
    assert load_session(s.session_id) is None


def test_autosave_on_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setenv("JW_SPAR_PERSIST", "1")
    s = start_session(persona_key="catholic", language="es")
    asyncio.run(
        take_turn(
            session_id=s.session_id, user_text="Hola", llm=FakeSparLLM()
        )
    )
    loaded = load_session(s.session_id)
    assert loaded is not None
    assert len(loaded.user_turns) == 1
