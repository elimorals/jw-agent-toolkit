"""Verify the 4 F66 MCP tools are exposed and callable."""

from __future__ import annotations

import asyncio

import pytest

from jw_agents.spar.session import clear_sessions


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_sessions()
    yield
    clear_sessions()


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


def test_spar_list_personas_returns_six() -> None:
    from jw_mcp.server import spar_list_personas

    out = _call(spar_list_personas)
    assert isinstance(out, dict)
    keys = {p["key"] for p in out["personas"]}
    assert keys == {
        "catholic",
        "evangelical",
        "atheist",
        "muslim",
        "nominal",
        "young_skeptic",
    }


def test_spar_start_returns_session() -> None:
    from jw_mcp.server import spar_start

    out = _call(spar_start, persona="catholic", language="es")
    assert isinstance(out, dict)
    assert out["session_id"].startswith("spar-")
    assert out["persona"]["key"] == "catholic"


def test_spar_turn_and_close_round_trip() -> None:
    from jw_mcp.server import spar_close, spar_start, spar_turn

    start = _call(spar_start, persona="atheist", language="es")
    sid = start["session_id"]
    reply = _call(spar_turn, session_id=sid, text="Hola, ¿podemos hablar?")
    assert isinstance(reply, dict)
    assert reply["reply"]
    closed = _call(spar_close, session_id=sid)
    assert closed["closed"] is True
    assert closed["score_summary"] is not None
