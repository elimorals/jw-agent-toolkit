from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from jw_core.audio.asr_providers.fakes import FakeWhisperTurbo
from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider
from jw_core.audio.transcription import TranscriptionError, transcribe_file


def test_whisper_turbo_is_available_when_pkg_installed() -> None:
    provider = WhisperTurboProvider()
    assert isinstance(provider.is_available(), bool)


def test_whisper_turbo_resolves_auto_to_recommended_size(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    provider = WhisperTurboProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo.recommend_model_size",
        lambda: "large-v3-turbo",
    )
    captured: dict[str, str] = {}

    def fake_inner(audio_path, *, model_size, language, device, beam_size):
        captured["model_size"] = model_size
        from jw_core.audio.transcription import TranscriptionResult

        return TranscriptionResult(text="ok", language="en", duration=0.0, segments=[])

    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo._run_faster_whisper", fake_inner
    )
    result = provider.transcribe(audio, language="en", model_size="auto")
    assert captured["model_size"] == "large-v3-turbo"
    assert result.text == "ok"


def test_whisper_turbo_respects_explicit_size(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    provider = WhisperTurboProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    captured: dict[str, str] = {}

    def fake_inner(audio_path, *, model_size, language, device, beam_size):
        captured["model_size"] = model_size
        from jw_core.audio.transcription import TranscriptionResult

        return TranscriptionResult(text="ok", language="en", duration=0.0, segments=[])

    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo._run_faster_whisper", fake_inner
    )
    provider.transcribe(audio, language="en", model_size="medium")
    assert captured["model_size"] == "medium"


def test_fake_whisper_turbo_returns_text(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    result = FakeWhisperTurbo().transcribe(audio, language="es", model_size="base")
    assert "fake transcript" in result.text
    assert result.language == "es"


def test_transcribe_file_auto_keeps_legacy_default(monkeypatch, tmp_path: Path) -> None:
    """`transcribe_file(...)` without args should still work — keeps the
    legacy `base` default unless caller passes `model_size="auto"`.
    """
    # If faster_whisper is not installed, skip the test (must come *before*
    # any setattr against the module path so monkeypatch can resolve it).
    pytest.importorskip("faster_whisper")

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")

    captured: dict[str, str] = {}

    class FakeInfo:
        language = "en"
        duration = 0.0

    class FakeSeg:
        start = 0.0
        end = 0.5
        text = "hi"

    class FakeWM:
        def __init__(self, size, *, device, compute_type):
            captured["size"] = size

        def transcribe(self, *a, **kw):
            return iter([FakeSeg()]), FakeInfo()

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWM, raising=False)
    transcribe_file(audio)
    assert captured["size"] == "base"
