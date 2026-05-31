"""F5-TTS provider — experimental.

Target primary: NVIDIA CUDA. MLX builds exist (mlx-f5-tts) but are tracked
as experimental — we don't enable MLX path unless the user opts in via
JW_TTS_TARGET=mlx.

Languages: officially en only. Community fine-tunes exist for es/pt but we
do not advertise them to avoid over-promising.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)


class F5TTSProvider(TTSProvider):
    name = "f5"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "nvidia"
    languages_supported = {"en"}

    def __init__(self) -> None:
        self._model = None

    def _can_import(self) -> bool:
        try:
            import f5_tts  # noqa: F401  # type: ignore[import-not-found]
        except ImportError:
            return False
        return True

    def is_available(self) -> bool:
        return self._can_import()

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        if not self.is_available():
            raise TTSError(
                "F5TTSProvider unavailable. Install jw-core[tts-f5] and ensure CUDA. "
                "Experimental: not recommended for production."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_override = os.getenv("JW_TTS_TARGET")

        try:
            from f5_tts.api import F5TTS  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise TTSError("f5-tts API not found") from e

        if self._model is None:
            device = "mlx" if target_override == "mlx" else "cuda"
            self._model = F5TTS(device=device)

        try:
            self._model.infer(
                gen_text=text,
                ref_audio=voice,
                file_wave=str(output_path),
            )
        except Exception as exc:  # noqa: BLE001
            raise TTSError(f"F5-TTS inference failed: {exc!r}") from exc

        return output_path
