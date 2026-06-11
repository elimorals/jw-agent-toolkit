"""Smoke tests for the `jw talklab` CLI commands."""

from __future__ import annotations

import json
import wave
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.talklab import talklab_app

runner = CliRunner()


def _write_silent_wav(
    path: Path, duration_s: float = 1.0, sr: int = 16000
) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(duration_s * sr))


def test_cli_counsel_points_default_lang() -> None:
    result = runner.invoke(talklab_app, ["counsel-points"])
    assert result.exit_code == 0
    assert "cp-01" in result.stdout


def test_cli_counsel_points_es_with_kind() -> None:
    result = runner.invoke(
        talklab_app, ["counsel-points", "-l", "es", "-k", "bible_reading"]
    )
    assert result.exit_code == 0
    assert "Pronunciación clara" in result.stdout


def test_cli_analyze_silence_produces_json(tmp_path: Path) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=1.0)
    result = runner.invoke(
        talklab_app, ["analyze", str(wav), "-k", "bible_reading", "-l", "es"]
    )
    assert result.exit_code == 0
    assert '"counsel_results"' in result.stdout
    assert '"prosody"' in result.stdout


def test_cli_analyze_with_export_md_writes_file(tmp_path: Path) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=1.0)
    md = tmp_path / "report.md"
    result = runner.invoke(
        talklab_app,
        ["analyze", str(wav), "-k", "bible_reading", "--export", str(md)],
    )
    assert result.exit_code == 0
    assert md.exists()
    assert "TalkLab report" in md.read_text()
