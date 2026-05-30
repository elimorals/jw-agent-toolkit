"""Pluggable TTS layer.

Three built-in providers, all OPTIONAL:

  - `system`    → `say` on macOS, `espeak` / `espeak-ng` on Linux, PowerShell
                  System.Speech on Windows. Zero install, lowest quality.
  - `edge`      → Microsoft Edge TTS (uses the public `edge-tts` Python pkg
                  if installed). Free, no API key, high quality.
  - `piper`     → Local Piper TTS (offline). Requires `piper-tts` binary +
                  a voice .onnx model.

We auto-detect availability. Callers ask `get_tts_provider(name=None)` and
get whatever works on this machine.

This keeps the toolkit free of mandatory ML dependencies while still
shipping VISION.md item #3 ("TTS para escuchar texto bíblico/artículos
en cualquier idioma soportado").
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSError(RuntimeError):
    pass


class TTSProvider(ABC):
    """Abstract synthesizer."""

    name: str
    languages_supported: set[str] = set()

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        """Synthesize `text` to `output_path` (typically .wav or .mp3)."""


# ── System TTS (no deps) ─────────────────────────────────────────────────


class SystemTTSProvider(TTSProvider):
    name = "system"
    languages_supported = {"en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh"}

    def is_available(self) -> bool:
        return any(shutil.which(b) for b in ("say", "espeak-ng", "espeak", "powershell"))

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if shutil.which("say"):  # macOS
            cmd = ["say", "-o", str(output_path)]
            if voice:
                cmd.extend(["-v", voice])
            cmd.append(text)
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            binary = "espeak-ng" if shutil.which("espeak-ng") else "espeak"
            cmd = [binary, "-w", str(output_path), "-v", voice or language, text]
        elif shutil.which("powershell"):
            ps_script = (
                "Add-Type -AssemblyName System.Speech;"
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                f"$s.SetOutputToWaveFile('{output_path}');"
                f"$s.Speak('{text.replace(chr(39), chr(39) * 2)}');"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
        else:
            raise TTSError("No system TTS binary available")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise TTSError(f"system TTS failed: {e.stderr.decode(errors='ignore')}") from e
        return output_path


# ── Edge TTS (cloud, free, no API key) ──────────────────────────────────


class EdgeTTSProvider(TTSProvider):
    name = "edge"
    languages_supported = {
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "tr",
    }

    DEFAULT_VOICES: dict[str, str] = {
        "en": "en-US-AvaNeural",
        "es": "es-MX-DaliaNeural",
        "pt": "pt-BR-FranciscaNeural",
        "fr": "fr-FR-DeniseNeural",
        "de": "de-DE-KatjaNeural",
        "it": "it-IT-IsabellaNeural",
        "ja": "ja-JP-NanamiNeural",
        "ko": "ko-KR-SunHiNeural",
        "zh": "zh-CN-XiaoxiaoNeural",
    }

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        try:
            import asyncio

            import edge_tts
        except ImportError as e:  # pragma: no cover
            raise TTSError("edge-tts is not installed. `pip install edge-tts`") from e
        output_path.parent.mkdir(parents=True, exist_ok=True)
        voice_id = voice or self.DEFAULT_VOICES.get(language, "en-US-AvaNeural")

        async def _run() -> None:
            communicate = edge_tts.Communicate(text, voice_id)
            await communicate.save(str(output_path))

        try:
            asyncio.get_event_loop().run_until_complete(_run())
        except RuntimeError:
            asyncio.run(_run())
        return output_path


# ── Piper TTS (local, offline) ───────────────────────────────────────────


class PiperTTSProvider(TTSProvider):
    name = "piper"
    languages_supported = {"en", "es", "pt", "fr", "de", "it"}

    def is_available(self) -> bool:
        return shutil.which("piper") is not None

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        binary = shutil.which("piper")
        if not binary:
            raise TTSError("piper binary not found. Install from https://github.com/rhasspy/piper")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model_path = voice or os.getenv("JW_PIPER_MODEL")
        if not model_path:
            raise TTSError(
                "Piper requires a voice model. Pass via `voice` parameter or "
                "set JW_PIPER_MODEL=/path/to/voice.onnx"
            )
        try:
            subprocess.run(
                [binary, "--model", model_path, "--output_file", str(output_path)],
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise TTSError(f"piper failed: {e.stderr.decode(errors='ignore')}") from e
        return output_path


# ── Registry + factory ──────────────────────────────────────────────────


_PROVIDERS: list[type[TTSProvider]] = [PiperTTSProvider, EdgeTTSProvider, SystemTTSProvider]


def list_tts_providers() -> list[dict[str, object]]:
    return [
        {
            "name": cls.name,
            "available": cls().is_available(),
            "languages": sorted(cls.languages_supported),
        }
        for cls in _PROVIDERS
    ]


def get_tts_provider(name: str | None = None) -> TTSProvider:
    """Return the first available provider, or `name` if explicitly requested."""
    if name is not None:
        for cls in _PROVIDERS:
            if cls.name == name:
                instance = cls()
                if not instance.is_available():
                    raise TTSError(f"Provider {name!r} is registered but not available on this machine.")
                return instance
        raise TTSError(f"Unknown TTS provider {name!r}. Available: {[c.name for c in _PROVIDERS]}")
    for cls in _PROVIDERS:
        instance = cls()
        if instance.is_available():
            return instance
    raise TTSError("No TTS provider available. Install edge-tts (`pip install edge-tts`) or piper-tts.")


def synthesize_to_file(
    text: str,
    output_path: Path | str,
    *,
    language: str = "en",
    voice: str | None = None,
    provider: str | None = None,
) -> Path:
    """High-level convenience: pick a provider and synthesize.

    >>> synthesize_to_file("Hello world", "out.wav", language="en")
    PosixPath('out.wav')
    """
    p = get_tts_provider(provider)
    return p.synthesize(text, voice=voice, language=language, output_path=Path(output_path))
