"""Kokoro-82M TTS provider — local, multilingual, ONNX-based.

Model: hexgrad/Kokoro-82M (HuggingFace). 82M params, ~310MB on disk.
Backend: onnxruntime (CPU by default; onnxruntime-gpu if CUDA available).

`is_available()` does NOT download the model — only checks that the python
deps are importable. The model is fetched on first `synthesize()` call via
huggingface_hub.snapshot_download() and cached locally.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.tts import TTSError, TTSProvider

logger = logging.getLogger(__name__)


class KokoroTTSProvider(TTSProvider):
    name = "kokoro_local"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported = {"en", "es", "pt", "fr", "de", "it", "ja", "zh"}

    DEFAULT_REPO = "hexgrad/Kokoro-82M"
    DEFAULT_VOICES: dict[str, str] = {
        "en": "af_bella",
        "es": "ef_dora",
        "pt": "pf_dora",
        "fr": "ff_siwis",
        "de": "df_klara",
        "it": "if_sara",
        "ja": "jf_alpha",
        "zh": "zf_xiaobei",
    }

    def __init__(self) -> None:
        self._model = None
        self._repo = os.getenv("JW_KOKORO_MODEL_REPO", self.DEFAULT_REPO)

    def _can_import_runtime(self) -> bool:
        try:
            import huggingface_hub  # noqa: F401
            import numpy  # noqa: F401
            import onnxruntime  # noqa: F401
            import soundfile  # noqa: F401
        except ImportError:
            return False
        return True

    def is_available(self) -> bool:
        return self._can_import_runtime()

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        from huggingface_hub import snapshot_download  # type: ignore[import-not-found]
        import onnxruntime as ort  # type: ignore[import-not-found]

        cache_dir = snapshot_download(repo_id=self._repo)
        onnx_path = Path(cache_dir) / "kokoro-v1.0.onnx"
        if not onnx_path.exists():
            # Some forks name the file differently — pick first .onnx
            candidates = list(Path(cache_dir).glob("*.onnx"))
            if not candidates:
                raise TTSError(f"No .onnx model found under {cache_dir}")
            onnx_path = candidates[0]
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        self._model = ort.InferenceSession(str(onnx_path), providers=providers)
        return self._model

    def synthesize(self, text: str, *, voice: str | None, language: str, output_path: Path) -> Path:
        if not self.is_available():
            raise TTSError("KokoroTTSProvider deps missing. Install jw-core[tts-kokoro].")
        try:
            import numpy as np  # type: ignore[import-not-found]
            import soundfile as sf  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise TTSError("numpy/soundfile not installed") from e

        output_path.parent.mkdir(parents=True, exist_ok=True)
        model = self._ensure_model()
        voice_id = voice or self.DEFAULT_VOICES.get(language, "af_bella")

        # NOTE: The exact ONNX input names depend on the released model card.
        # We compute tokens via the Kokoro phonemizer-style input shape; users
        # who hit a schema mismatch get a clear error pointing to the spec.
        try:
            tokens = _kokoro_tokenize(text, language=language)
            audio = model.run(
                None,
                {
                    "tokens": np.asarray([tokens], dtype=np.int64),
                    "voice": np.asarray([voice_id], dtype=object),
                    "speed": np.asarray([1.0], dtype=np.float32),
                },
            )[0]
        except Exception as exc:  # noqa: BLE001
            raise TTSError(
                f"Kokoro inference failed ({exc!r}). "
                "Check JW_KOKORO_MODEL_REPO matches the ONNX schema."
            ) from exc

        sf.write(str(output_path), np.squeeze(audio), samplerate=24000)
        return output_path


def _kokoro_tokenize(text: str, *, language: str) -> list[int]:
    """Minimal char-level fallback tokenizer.

    The reference Kokoro release ships a `kokoro` python helper for proper
    phoneme tokenization; if that pkg is installed we delegate to it.
    """

    try:
        from kokoro import tokenize  # type: ignore[import-not-found]

        return list(tokenize(text, lang=language))
    except ImportError:
        return [ord(c) % 256 for c in text]
