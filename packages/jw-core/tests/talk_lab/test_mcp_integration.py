"""Verify the three Fase 68 MCP tools are exposed."""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path


def _call(tool_obj, **kwargs):
    """fastmcp wraps tools so the original callable is on `.fn`."""
    fn = getattr(tool_obj, "fn", tool_obj)
    return asyncio.run(fn(**kwargs))


def test_talklab_list_counsel_points_returns_payload() -> None:
    from jw_mcp.server import talklab_list_counsel_points

    out = _call(talklab_list_counsel_points, language="es")
    assert isinstance(out, dict)
    assert "points" in out
    assert any(p["id"] == "cp-01" for p in out["points"])


def test_talklab_list_counsel_points_filters_by_kind() -> None:
    from jw_mcp.server import talklab_list_counsel_points

    out = _call(
        talklab_list_counsel_points,
        part_kind="watchtower_comment",
        language="es",
    )
    by_id = {p["id"]: p for p in out["points"]}
    assert by_id["cp-01"]["applies"] is True
    assert by_id["cp-06"]["applies"] is False


def test_talklab_analyze_silence(tmp_path: Path) -> None:
    from jw_mcp.server import talklab_analyze

    wav = tmp_path / "x.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)

    out = _call(
        talklab_analyze,
        recording_path=str(wav),
        part_kind="bible_reading",
        language="es",
        llm_judge=False,
    )
    assert isinstance(out, dict)
    assert "counsel_results" in out
    assert "prosody" in out
