"""ElevenLabs TTS provider.

Prefers the official `elevenlabs` SDK when installed; falls back to a raw
`httpx` POST against the public REST endpoint so users don't need the SDK.

Auth: ELEVENLABS_API_KEY (required). Optional ELEVENLABS_VOICE_ID overrides
the default voice (Rachel: 21m00Tcm4TlvDq8ikWAM).

is_available() returns True iff the env key is set. We DO NOT hit the
network during availability check.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar, Literal

import httpx

from jw_core.audio.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "api"
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
    }

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def is_available(self) -> bool:
        return bool(os.getenv("ELEVENLABS_API_KEY"))

    def _use_sdk(self) -> bool:
        try:
            import elevenlabs  # noqa: F401  # type: ignore[import-not-found]
        except ImportError:
            return False
        return True

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        key = os.getenv("ELEVENLABS_API_KEY")
        if not key:
            raise TTSError("ELEVENLABS_API_KEY not set")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        voice_id = voice or os.getenv("ELEVENLABS_VOICE_ID") or self.DEFAULT_VOICE_ID

        if self._use_sdk():
            return self._synthesize_via_sdk(text, voice_id, key, output_path)
        return self._synthesize_via_http(text, voice_id, key, output_path)

    def _synthesize_via_http(self, text: str, voice_id: str, key: str, output_path: Path) -> Path:
        url = f"{self.BASE_URL}/{voice_id}"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        headers = {"xi-api-key": key, "Accept": "audio/mpeg"}
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                output_path.write_bytes(resp.content)
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"ElevenLabs HTTP synthesis failed: {exc!r}") from exc
        return output_path

    def _synthesize_via_sdk(self, text: str, voice_id: str, key: str, output_path: Path) -> Path:
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise TTSError("elevenlabs SDK present but import broken") from e
        try:
            client = ElevenLabs(api_key=key)
            audio_iter = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
            )
            with output_path.open("wb") as f:
                for chunk in audio_iter:
                    f.write(chunk)
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"ElevenLabs SDK synthesis failed: {exc!r}") from exc
        return output_path
