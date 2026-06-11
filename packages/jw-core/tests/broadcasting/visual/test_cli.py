"""CLI smoke tests (Fase 69)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.commands.broadcasting_visual import broadcasting_visual_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_VISUAL_INDEX_ROOT", str(tmp_path / "visual"))


def test_cli_stats_on_empty_index(tmp_path: Path) -> None:  # noqa: ARG001
    result = runner.invoke(broadcasting_visual_app, ["stats"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.stdout)
    assert parsed["videos_indexed"] == 0


def test_cli_index_with_no_ffmpeg_then_search(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"fake")
    # Index with the fake sampler
    idx = runner.invoke(
        broadcasting_visual_app,
        ["index", str(video), "--no-ffmpeg", "--video-id", "test"],
    )
    assert idx.exit_code == 0, idx.output
    stats = json.loads(idx.stdout)
    assert stats["videos_indexed"] == 1

    # Now search
    search = runner.invoke(
        broadcasting_visual_app, ["search", "image", "-k", "3"]
    )
    assert search.exit_code == 0
