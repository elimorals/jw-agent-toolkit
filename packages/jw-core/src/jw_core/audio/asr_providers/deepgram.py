"""Deepgram ASR provider — API, streaming-ready.

SDK preferred when installed; raw httpx fallback otherwise.
Auth: DEEPGRAM_API_KEY.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar, Literal

import httpx

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.transcription import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)


class DeepgramProvider(ASRProvider):
    name = "deepgram"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "api"
    languages_supported = {
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "tr",
        "nl", "pl", "cs", "hi",
    }
    BASE_URL = "https://api.deepgram.com/v1/listen"

    def is_available(self) -> bool:
        return bool(os.getenv("DEEPGRAM_API_KEY"))

    def _use_sdk(self) -> bool:
        try:
            import deepgram  # noqa: F401  # type: ignore[import-not-found]
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
        key = os.getenv("DEEPGRAM_API_KEY")
        if not key:
            raise TranscriptionError("DEEPGRAM_API_KEY not set")
        if self._use_sdk():
            return self._transcribe_via_sdk(audio_path, key, language)
        return self._transcribe_via_http(audio_path, key, language)

    def _transcribe_via_http(
        self, audio_path: Path, key: str, language: str | None
    ) -> TranscriptionResult:
        params = {"model": "nova-2", "smart_format": "true"}
        if language:
            params["language"] = language
        else:
            params["detect_language"] = "true"

        url = self.BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        headers = {
            "Authorization": f"Token {key}",
            "Content-Type": "audio/wav",
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    url, headers=headers, content=audio_path.read_bytes()
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"Deepgram HTTP failed: {exc!r}") from exc

        return _parse_deepgram(data)

    def _transcribe_via_sdk(
        self, audio_path: Path, key: str, language: str | None
    ) -> TranscriptionResult:
        try:
            from deepgram import DeepgramClient, PrerecordedOptions  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise TranscriptionError("deepgram SDK import broken") from e
        try:
            client = DeepgramClient(api_key=key)
            opts = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                language=language,
                detect_language=language is None,
            )
            with audio_path.open("rb") as f:
                source = {"buffer": f.read(), "mimetype": "audio/wav"}
            resp = client.listen.prerecorded.v("1").transcribe_file(source, opts)
            data = resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"Deepgram SDK failed: {exc!r}") from exc
        return _parse_deepgram(data)


def _parse_deepgram(data: dict) -> TranscriptionResult:
    try:
        channel = data["results"]["channels"][0]
        alt = channel["alternatives"][0]
        text = alt.get("transcript", "")
        language = channel.get("detected_language") or "en"
        duration = float(data.get("metadata", {}).get("duration", 0.0))
        words = alt.get("words", []) or []
        segs: list[TranscriptionSegment] = []
        if words:
            segs.append(
                TranscriptionSegment(
                    start=float(words[0].get("start", 0.0)),
                    end=float(words[-1].get("end", duration)),
                    text=text,
                )
            )
        return TranscriptionResult(
            text=text, language=language, duration=duration, segments=segs
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise TranscriptionError(f"Unexpected Deepgram payload: {exc!r}") from exc
