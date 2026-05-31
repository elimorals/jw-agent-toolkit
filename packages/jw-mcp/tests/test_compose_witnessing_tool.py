"""Smoke test for the compose_witnessing MCP tool."""

from __future__ import annotations

import asyncio


def test_compose_witnessing_tool_returns_dict() -> None:
    from jw_mcp.server import compose_witnessing as _tool  # noqa: PLC0415

    result = asyncio.run(
        _tool(
            kind="letter",
            language="es",
            topic="esperanza",
            audience="default",
        )
    )
    assert isinstance(result, dict)
    assert result["agent_name"] == "letter_composer"
    assert len(result["findings"]) >= 4
    sections = [f["metadata"]["section"] for f in result["findings"][:4]]
    assert sections == ["opener", "bridge", "scripture", "closing"]


def test_compose_witnessing_tool_passes_territory_hint() -> None:
    from jw_mcp.server import compose_witnessing as _tool  # noqa: PLC0415

    result = asyncio.run(
        _tool(
            kind="phone",
            language="es",
            topic="paz",
            territory_hint="Madrid",
        )
    )
    assert result["metadata"]["territory_hint"] == "Madrid"
