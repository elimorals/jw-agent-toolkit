"""Deterministic fakes for premium TTS providers.

Each fake writes a minimal valid WAV header so downstream code that opens the
file with `wave.open()` doesn't blow up. Length is proportional to text len.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.tts import TTSProvider


def _write_silence_wav(path: Path, duration_sec: float = 0.1, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = max(1, int(duration_sec * sample_rate))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<" + "h" * n_frames, *([0] * n_frames)))


class FakeKokoroTTS(TTSProvider):
    name = "kokoro_local"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported = {"en", "es", "pt", "fr", "de", "it", "ja", "zh"}

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        _write_silence_wav(output_path, duration_sec=0.05 + 0.01 * len(text))
        return output_path


class FakeXTTSv2(TTSProvider):
    name = "xtts"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "nvidia"
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
        "ar",
        "ru",
        "tr",
        "pl",
        "nl",
        "cs",
        "hu",
        "hi",
    }

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        _write_silence_wav(output_path, duration_sec=0.05 + 0.01 * len(text))
        return output_path


class FakeF5TTS(TTSProvider):
    name = "f5"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "nvidia"
    languages_supported = {"en"}

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        _write_silence_wav(output_path, duration_sec=0.05 + 0.01 * len(text))
        return output_path


class FakeElevenLabsTTS(TTSProvider):
    name = "elevenlabs"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "api"
    languages_supported = {"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh", "ar", "ru", "tr"}

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        # Fake an mp3 by reusing WAV; tests should not assume codec
        _write_silence_wav(output_path, duration_sec=0.05 + 0.01 * len(text))
        return output_path
