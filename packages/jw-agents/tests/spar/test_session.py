"""SparSession manager tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.memory.fake import FakeMemoryStore
from jw_agents.spar.session import (
    clear_sessions,
    close_session,
    get_session,
    list_active_sessions,
    start_session,
    take_turn,
)
from jw_agents.spar.simulator import FakeSparLLM


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_sessions()
    yield
    clear_sessions()


def test_start_session_creates_session_id() -> None:
    s = start_session(persona_key="catholic", language="es")
    assert s.session_id.startswith("spar-")
    assert s.persona.key == "catholic"
    assert s.closed is False


def test_start_session_with_unknown_persona_raises() -> None:
    with pytest.raises(KeyError):
        start_session(persona_key="zoroastrian", language="es")


def test_start_session_records_to_memory_store() -> None:
    store = FakeMemoryStore()
    s = start_session(
        persona_key="catholic", language="es", store=store
    )
    recalled = store.recall(session_id=s.session_id, limit=10)
    assert recalled
    assert any("persona=catholic" in r.content for r in recalled)


@pytest.mark.asyncio
async def test_take_turn_appends_user_and_persona_turns() -> None:
    s = start_session(persona_key="catholic", language="es")
    llm = FakeSparLLM()
    response = await take_turn(
        session_id=s.session_id, user_text="Buenos días", llm=llm
    )
    session = get_session(s.session_id)
    assert response.reply
    assert len(session.user_turns) == 1
    assert len(session.persona_turns) == 1
    assert session.user_turns[0].turn_index == 0


@pytest.mark.asyncio
async def test_take_turn_records_user_and_persona_into_memory() -> None:
    store = FakeMemoryStore()
    s = start_session(
        persona_key="atheist", language="es", store=store
    )
    llm = FakeSparLLM()
    await take_turn(
        session_id=s.session_id,
        user_text="Hola",
        llm=llm,
        store=store,
    )
    recalled = store.recall(session_id=s.session_id, limit=10)
    kinds = {r.kind for r in recalled}
    assert "question" in kinds
    assert "answer" in kinds


@pytest.mark.asyncio
async def test_take_turn_respects_max_turns_cap() -> None:
    s = start_session(persona_key="muslim", language="es")
    llm = FakeSparLLM()
    await take_turn(
        session_id=s.session_id, user_text="t1", llm=llm, max_turns=2
    )
    await take_turn(
        session_id=s.session_id, user_text="t2", llm=llm, max_turns=2
    )
    with pytest.raises(RuntimeError, match="max_turns"):
        await take_turn(
            session_id=s.session_id, user_text="t3", llm=llm, max_turns=2
        )


@pytest.mark.asyncio
async def test_take_turn_after_close_raises() -> None:
    s = start_session(persona_key="evangelical", language="es")
    close_session(session_id=s.session_id)
    llm = FakeSparLLM()
    with pytest.raises(RuntimeError, match="closed"):
        await take_turn(session_id=s.session_id, user_text="x", llm=llm)


def test_list_active_sessions_excludes_closed() -> None:
    a = start_session(persona_key="catholic", language="es")
    b = start_session(persona_key="atheist", language="es")
    close_session(session_id=b.session_id)
    active = list_active_sessions()
    assert a.session_id in active
    assert b.session_id not in active


def test_take_turn_unknown_session_raises() -> None:
    import asyncio

    llm = FakeSparLLM()
    with pytest.raises(KeyError):
        asyncio.run(
            take_turn(
                session_id="nonexistent", user_text="x", llm=llm
            )
        )
