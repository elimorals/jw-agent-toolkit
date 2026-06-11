"""F67 MCP tool integration."""

from __future__ import annotations

import asyncio


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


def test_doctrinal_reason_mcp_returns_tree_shape() -> None:
    from jw_mcp.server import doctrinal_reason

    out = _call(
        doctrinal_reason,
        question="X",
        language="es",
        max_steps=4,
        nli_mode="off",
        include_summary_prose=False,
    )
    assert isinstance(out, dict)
    assert "steps" in out
    assert "question_original" in out
