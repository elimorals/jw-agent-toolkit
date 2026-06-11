"""Markdown export tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from jw_agents.spar.export import to_markdown
from jw_agents.spar.feedback import score_session
from jw_agents.spar.session import (
    clear_sessions,
    close_session,
    get_session,
    start_session,
    take_turn,
)
from jw_agents.spar.simulator import FakeSparLLM


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_sessions()
    yield
    clear_sessions()


def _make_session() -> str:
    s = start_session(persona_key="catholic", language="es")
    llm = FakeSparLLM()
    asyncio.run(
        take_turn(session_id=s.session_id, user_text="Buenos días", llm=llm)
    )
    asyncio.run(
        take_turn(
            session_id=s.session_id,
            user_text="Según w23.04 p. 12, ...",
            llm=llm,
        )
    )
    close_session(session_id=s.session_id)
    score_session(get_session(s.session_id))
    return s.session_id


def test_to_markdown_renders_header_and_turns() -> None:
    sid = _make_session()
    session = get_session(sid)
    md = to_markdown(session)
    assert "# Sparring session" in md
    assert "PRÁCTICA - esto NO es una visita real" in md
    assert "### Turno 1" in md
    assert "### Turno 2" in md
    assert "**Visitante**: Buenos días" in md
    assert "## Score summary" in md
    assert "## Feedback" in md


def test_to_markdown_includes_persona_display_name() -> None:
    sid = _make_session()
    md = to_markdown(get_session(sid))
    # María is the catholic display name
    assert "María" in md


def test_to_markdown_handles_session_without_feedback() -> None:
    s = start_session(persona_key="atheist", language="es")
    md = to_markdown(s)
    assert "# Sparring session" in md
    assert "## Score summary" not in md
    assert "## Feedback" not in md
