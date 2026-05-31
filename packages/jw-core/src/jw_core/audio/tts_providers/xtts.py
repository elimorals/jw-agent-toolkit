"""XTTSv2 voice-cloning provider — STRICT double opt-in.

Requires:
  1. `coqui-tts` python package installed (extra: jw-core[tts-xtts]).
  2. Env JW_XTTS_CLONE_CONSENT=1 set in the calling process.
  3. A `voice_sample_path` (6-10s clip) passed as the `voice` arg.

On successful synthesis we also drop a `consent.txt` next to the output
documenting the consent flag and the source sample. This is enforced by
Política #6 of the Fase 33-38 overview: nothing that can be confused with a
brother's real voice without explicit, archivable consent.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)


class XTTSv2Provider(TTSProvider):
    name = "xtts"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "nvidia"
    languages_supported = {
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh",
        "ar", "ru", "tr", "pl", "nl", "cs", "hu", "hi",
    }

    DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self) -> None:
        self._tts = None

    def _consent_granted(self) -> bool:
        return os.getenv("JW_XTTS_CLONE_CONSENT") == "1"

    def _can_import(self) -> bool:
        try:
            from TTS.api import TTS  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return False
        return True

    def is_available(self) -> bool:
        return self._consent_granted() and self._can_import()

    def _write_consent(self, output_path: Path, sample_path: str) -> None:
        consent_path = output_path.with_name(output_path.stem + ".consent.txt")
        consent_path.write_text(
            "XTTSv2 voice cloning consent\n"
            f"timestamp_utc: {datetime.now(UTC).isoformat()}\n"
            f"output: {output_path.name}\n"
            f"voice_sample: {sample_path}\n"
            "consent_env: JW_XTTS_CLONE_CONSENT=1\n",
            encoding="utf-8",
        )

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        if not self._consent_granted():
            raise TTSError(
                "XTTSv2 cloning requires explicit consent. "
                "Set JW_XTTS_CLONE_CONSENT=1 to acknowledge."
            )
        if not voice:
            raise TTSError(
                "XTTSv2 needs a voice_sample (6-10s WAV) passed as the `voice` arg."
            )
        sample_path = Path(voice)
        if not sample_path.exists():
            raise TTSError(f"voice_sample not found: {sample_path}")
        if not self._can_import():
            raise TTSError("coqui-tts not installed. Install jw-core[tts-xtts].")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        from TTS.api import TTS  # type: ignore[import-not-found]

        if self._tts is None:
            self._tts = TTS(self.DEFAULT_MODEL)
        try:
            self._tts.tts_to_file(
                text=text,
                speaker_wav=str(sample_path),
                language=language,
                file_path=str(output_path),
            )
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"XTTSv2 synthesis failed: {exc!r}") from exc

        self._write_consent(output_path, str(sample_path))
        return output_path
