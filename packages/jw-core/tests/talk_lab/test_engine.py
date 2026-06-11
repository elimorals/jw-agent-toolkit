"""End-to-end engine tests over synthetic silence (no WhisperX needed)."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from jw_core.talk_lab.engine import TalkLabConfig, analyze_recording
from jw_core.talk_lab.models import TalkLabReport


def _write_silent_wav(
    path: Path, duration_s: float = 5.0, sr: int = 16000
) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(duration_s * sr))


@pytest.mark.asyncio
async def test_analyze_recording_silence_produces_valid_report(
    tmp_path: Path,
) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=2.0)
    rpt = await analyze_recording(
        recording_path=str(wav),
        config=TalkLabConfig(
            part_kind="bible_reading", language="es", llm_judge=False
        ),
    )
    assert isinstance(rpt, TalkLabReport)
    assert rpt.language == "es"
    assert rpt.duration_s == pytest.approx(2.0, abs=0.1)
    # No transcript -> pronunciation score should be 0
    assert any(
        r.point_id == "cp-01" and r.score == 0
        for r in rpt.counsel_results
    )


@pytest.mark.asyncio
async def test_analyze_recording_returns_top_and_focus(
    tmp_path: Path,
) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=2.0)
    rpt = await analyze_recording(
        recording_path=str(wav),
        config=TalkLabConfig(
            part_kind="bible_reading", language="es", llm_judge=False
        ),
    )
    assert isinstance(rpt.summary_top_3, list)
    assert isinstance(rpt.summary_focus_3, list)


@pytest.mark.asyncio
async def test_analyze_recording_marks_non_applicable_points(
    tmp_path: Path,
) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=2.0)
    rpt = await analyze_recording(
        recording_path=str(wav),
        config=TalkLabConfig(
            part_kind="watchtower_comment", language="es", llm_judge=False
        ),
    )
    # cp-04, cp-05, cp-06 do NOT apply to watchtower_comment per catalog
    applies_map = {r.point_id: r.applies for r in rpt.counsel_results}
    assert applies_map["cp-01"] is True
    assert applies_map["cp-06"] is False
