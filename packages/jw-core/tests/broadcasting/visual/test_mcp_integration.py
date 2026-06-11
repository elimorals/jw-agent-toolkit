"""MCP tool integration (Fase 69)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


@pytest.fixture(autouse=True)
def _isolated_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_VISUAL_INDEX_ROOT", str(tmp_path / "visual"))


def test_mcp_stats_empty() -> None:
    from jw_mcp.server import broadcasting_visual_stats

    out = _call(broadcasting_visual_stats)
    assert isinstance(out, dict)
    assert out["videos_indexed"] == 0


def test_mcp_index_then_search(tmp_path: Path) -> None:
    from jw_mcp.server import (
        broadcasting_visual_index,
        broadcasting_visual_search,
    )

    video = tmp_path / "v.mp4"
    video.write_bytes(b"fake")
    stats = _call(
        broadcasting_visual_index,
        video_path=str(video),
        video_id="test",
        no_ffmpeg=True,
    )
    assert stats["videos_indexed"] == 1

    out = _call(broadcasting_visual_search, query="image", top_k=3)
    assert isinstance(out, dict)
    assert "hits" in out
