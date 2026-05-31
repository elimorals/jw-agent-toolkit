"""WhisperTurbo ASR provider — large-v3-turbo when VRAM allows.

Thin wrapper around the existing faster-whisper code path; the difference is
the auto-select default and the ABC compliance so it composes through the
provider chain.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.hardware import recommend_model_size
from jw_core.audio.transcription import (
    TranscriptionError,
    TranscriptionResult,
    transcribe_file,
)


def _run_faster_whisper(
    audio_path: Path,
    *,
    model_size: str,
    language: str | None,
    device: str,
    beam_size: int,
) -> TranscriptionResult:
    """Indirection so tests can monkeypatch without touching transcribe_file."""

    return transcribe_file(
        audio_path,
        model_size=model_size,
        language=language,
        device=device,
        beam_size=beam_size,
    )


class WhisperTurboProvider(ASRProvider):
    name = "whisper_turbo"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported = {
        "en",
        "es",
        "pt",
        "fr",
        "de",
        "it",
        "ja",
        "ko",
        "zh",
        "ru",
        "ar",
        "tr",
        "nl",
        "pl",
        "cs",
        "hu",
        "hi",
    }

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401  # type: ignore[import-not-found]
        except ImportError:
            return False
        return True

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult:
        if not self.is_available():
            raise TranscriptionError("faster-whisper not installed. Install jw-core[asr-turbo].")
        resolved = recommend_model_size() if model_size == "auto" else model_size
        return _run_faster_whisper(
            audio_path,
            model_size=resolved,
            language=language,
            device="auto",
            beam_size=5,
        )
