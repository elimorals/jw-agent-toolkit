"""Premium ASR providers (opt-in)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.transcription import TranscriptionResult


class ASRProvider(ABC):
    name: str
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported: set[str] = set()

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult: ...


from jw_core.audio.asr_providers.fakes import FakeDeepgram, FakeWhisperTurbo  # noqa: E402

__all__ = ["ASRProvider", "FakeDeepgram", "FakeWhisperTurbo"]
