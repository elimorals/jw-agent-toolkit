"""Deterministic ASR fakes for offline tests."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.transcription import TranscriptionResult, TranscriptionSegment


def _fake_result(audio_path: Path, language: str | None) -> TranscriptionResult:
    text = f"[fake transcript of {audio_path.name}]"
    return TranscriptionResult(
        text=text,
        language=language or "en",
        duration=1.0,
        segments=[TranscriptionSegment(start=0.0, end=1.0, text=text)],
    )


class FakeWhisperTurbo(ASRProvider):
    name = "whisper_turbo"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported = {"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh"}

    def is_available(self) -> bool:
        return True

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult:
        result = _fake_result(audio_path, language)
        result.text = f"[whisper_turbo:{model_size}] {result.text}"
        return result


class FakeDeepgram(ASRProvider):
    name = "deepgram"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "api"
    languages_supported = {"en", "es", "pt", "fr", "de", "it"}

    def is_available(self) -> bool:
        return True

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult:
        return _fake_result(audio_path, language)
