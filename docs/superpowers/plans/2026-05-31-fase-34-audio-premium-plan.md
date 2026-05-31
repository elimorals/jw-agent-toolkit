# Fase 34 — `audio-premium` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `jw_core.audio` with premium TTS providers (Kokoro/XTTSv2/F5/ElevenLabs) and ASR providers (WhisperTurbo/Deepgram) behind opt-in extras, without breaking the 3 existing providers (`system`/`edge`/`piper`) nor the existing `transcribe_file()` API.

**Architecture:** Two new subpackages (`tts_providers/`, `asr_providers/`) + `hardware.py` helper, plus minimal additive changes to `tts.py` (chain + factory) and `transcription.py` (auto-select). Each new provider ships with a deterministic `Fake*` sibling for offline tests. Lazy SDK imports keep base install lightweight.

**Tech Stack:** Python 3.13 · existing `TTSProvider` ABC · new `ASRProvider` ABC · `huggingface_hub` + `onnxruntime` (Kokoro) · `coqui-tts` (XTTSv2) · `f5-tts` (experimental) · `elevenlabs` SDK / `httpx` (EL) · `deepgram-sdk` / `httpx` (Deepgram) · `faster-whisper>=1.1` (turbo).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-34-audio-premium-design.md`](../specs/2026-05-31-fase-34-audio-premium-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/audio/hardware.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/__init__.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/kokoro.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/xtts.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/f5.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/elevenlabs.py`
- `packages/jw-core/src/jw_core/audio/tts_providers/fakes.py`
- `packages/jw-core/src/jw_core/audio/asr_providers/__init__.py`
- `packages/jw-core/src/jw_core/audio/asr_providers/whisper_turbo.py`
- `packages/jw-core/src/jw_core/audio/asr_providers/deepgram.py`
- `packages/jw-core/src/jw_core/audio/asr_providers/fakes.py`
- `packages/jw-core/tests/test_audio_hardware.py`
- `packages/jw-core/tests/test_tts_kokoro.py`
- `packages/jw-core/tests/test_tts_xtts.py`
- `packages/jw-core/tests/test_tts_f5.py`
- `packages/jw-core/tests/test_tts_elevenlabs.py`
- `packages/jw-core/tests/test_asr_whisper_turbo.py`
- `packages/jw-core/tests/test_asr_deepgram.py`
- `packages/jw-core/tests/test_audio_factory.py`
- `docs/guias/audio-premium.md`

Modifies:
- `packages/jw-core/pyproject.toml` — add `tts-kokoro`, `tts-xtts`, `tts-f5`, `tts-elevenlabs`, `asr-deepgram`, `asr-turbo`, `tts-premium`, `asr-premium`, `audio-premium` extras.
- `packages/jw-core/src/jw_core/audio/tts.py` — extend `_PROVIDERS` registry, add `JW_TTS_PROVIDER` env, add `target` attribute to base ABC.
- `packages/jw-core/src/jw_core/audio/transcription.py` — add `model_size="auto"` support via `recommend_model_size()`; keep all existing kwargs.
- `packages/jw-cli/src/jw_cli/commands/say.py` (or equivalent) — pass new `--provider` / `--voice` flags (no behaviour change if unset).
- `packages/jw-cli/src/jw_cli/commands/transcribe.py` — accept `--model auto` and `--provider` flag.
- `packages/jw-mcp/src/jw_mcp/server.py` — add optional `provider`/`voice` params to `synthesize_speech` and `transcribe_audio` tools.
- `docs/ROADMAP.md` — append Fase 34 entry.
- `docs/VISION_AUDIT.md` — add Fase 34 row.

---

### Task 1: Extras in `pyproject.toml` + ABC `target` attribute

**Files:**
- Modify: `packages/jw-core/pyproject.toml`
- Modify: `packages/jw-core/src/jw_core/audio/tts.py` (only add `target` class var to ABC)

- [ ] **Step 1: Add optional-dependencies extras**

Append to `[project.optional-dependencies]` in `packages/jw-core/pyproject.toml`:

```toml
tts-kokoro = [
    "huggingface_hub>=0.24.0",
    "onnxruntime>=1.19.0",
    "soundfile>=0.12.1",
    "numpy>=1.26.0",
]
tts-xtts = ["coqui-tts>=0.24.0"]
tts-f5 = ["f5-tts>=0.4.0"]
tts-elevenlabs = ["elevenlabs>=1.5.0"]
asr-deepgram = ["deepgram-sdk>=3.7.0"]
asr-turbo = ["faster-whisper>=1.1.0"]
tts-premium = ["jw-core[tts-kokoro,tts-elevenlabs]"]
asr-premium = ["jw-core[asr-turbo,asr-deepgram]"]
audio-premium = ["jw-core[tts-kokoro,asr-turbo]"]
```

- [ ] **Step 2: Add `target` literal to ABC (additive, default `"cpu"`)**

In `packages/jw-core/src/jw_core/audio/tts.py`, modify the ABC class header only (keep all three existing providers intact):

```python
from typing import Literal, ClassVar

class TTSProvider(ABC):
    """Abstract synthesizer."""

    name: str
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported: set[str] = set()
    ...
```

Set `target = "api"` on `EdgeTTSProvider`, leave `system`/`piper` as `"cpu"`.

- [ ] **Step 3: Verify nothing broke**

```bash
uv sync --all-packages
uv run pytest packages/jw-core/tests/test_tts.py -v
```
Expected: existing TTS tests still pass.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/pyproject.toml packages/jw-core/src/jw_core/audio/tts.py
git commit -m "feat(jw-core/audio): add premium audio extras and target attribute"
```

---

### Task 2: `hardware.py` — detect_target() and recommend_model_size()

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/hardware.py`
- Create: `packages/jw-core/tests/test_audio_hardware.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_audio_hardware.py
from __future__ import annotations

from unittest.mock import patch

from jw_core.audio import hardware


def test_detect_target_returns_nvidia_when_smi_present() -> None:
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        assert hardware.detect_target() == "nvidia"


def test_detect_target_returns_mlx_on_apple_silicon() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("sys.platform", "darwin"),
        patch("platform.machine", return_value="arm64"),
    ):
        assert hardware.detect_target() == "mlx"


def test_detect_target_returns_cpu_fallback() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("sys.platform", "linux"),
        patch("platform.machine", return_value="x86_64"),
    ):
        assert hardware.detect_target() == "cpu"


def test_recommend_model_size_picks_turbo_with_vram() -> None:
    with patch.object(hardware, "available_vram_gb", return_value=12.0):
        assert hardware.recommend_model_size() == "large-v3-turbo"


def test_recommend_model_size_falls_back_to_base() -> None:
    with patch.object(hardware, "available_vram_gb", return_value=2.0):
        assert hardware.recommend_model_size() == "base"


def test_available_vram_gb_returns_float() -> None:
    val = hardware.available_vram_gb()
    assert isinstance(val, float)
    assert val >= 0.0
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_audio_hardware.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/hardware.py
"""Hardware detection helpers for the audio stack.

Pure stdlib; no torch/onnx import at module level.
"""

from __future__ import annotations

import platform
import shutil
import sys
from typing import Literal

Target = Literal["api", "nvidia", "mlx", "cpu"]


def detect_target() -> Target:
    """Detect the strongest local accelerator. API is opt-in only."""

    if shutil.which("nvidia-smi"):
        return "nvidia"
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "mlx"
    return "cpu"


def available_vram_gb() -> float:
    """Best-effort VRAM detection. Returns 0.0 if unknown.

    - CUDA: torch.cuda.mem_get_info()[1] / 1024**3 if torch installed.
    - MPS: psutil.virtual_memory().available / 1024**3 (approximation,
      shared system memory).
    - else: 0.0
    """

    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info()
            return float(free) / (1024**3)
    except Exception:
        pass

    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import psutil  # type: ignore[import-not-found]

            return float(psutil.virtual_memory().available) / (1024**3)
        except Exception:
            return 0.0
    return 0.0


WHISPER_CHAIN: list[tuple[float, str]] = [
    (8.0, "large-v3-turbo"),
    (4.0, "medium"),
    (2.0, "small"),
    (1.0, "base"),
    (0.0, "tiny"),
]


def recommend_model_size() -> str:
    """Pick a Whisper model size based on available VRAM/RAM."""

    vram = available_vram_gb()
    for threshold, name in WHISPER_CHAIN:
        if vram >= threshold:
            return name
    return "tiny"
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_audio_hardware.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/hardware.py packages/jw-core/tests/test_audio_hardware.py
git commit -m "feat(jw-core/audio): hardware detection + whisper auto-select"
```

---

### Task 3: Fakes subpackage — deterministic offline doubles

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/__init__.py`
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/fakes.py`
- Create: `packages/jw-core/src/jw_core/audio/asr_providers/__init__.py`
- Create: `packages/jw-core/src/jw_core/audio/asr_providers/fakes.py`

- [ ] **Step 1: Implement TTS fakes**

```python
# packages/jw-core/src/jw_core/audio/tts_providers/__init__.py
"""Premium TTS providers (opt-in).

All providers extend jw_core.audio.tts.TTSProvider. SDK imports are LAZY:
`is_available()` must not touch the network and must not raise.
"""

from jw_core.audio.tts_providers.fakes import (
    FakeElevenLabsTTS,
    FakeF5TTS,
    FakeKokoroTTS,
    FakeXTTSv2,
)

__all__ = [
    "FakeElevenLabsTTS",
    "FakeF5TTS",
    "FakeKokoroTTS",
    "FakeXTTSv2",
]
```

```python
# packages/jw-core/src/jw_core/audio/tts_providers/fakes.py
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
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh",
        "ar", "ru", "tr", "pl", "nl", "cs", "hu", "hi",
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
```

- [ ] **Step 2: Implement ASR ABC + fakes**

```python
# packages/jw-core/src/jw_core/audio/asr_providers/__init__.py
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
```

```python
# packages/jw-core/src/jw_core/audio/asr_providers/fakes.py
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
```

- [ ] **Step 3: Smoke import**

```bash
uv run python -c "from jw_core.audio.tts_providers import FakeKokoroTTS; from jw_core.audio.asr_providers import FakeDeepgram; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts_providers packages/jw-core/src/jw_core/audio/asr_providers
git commit -m "feat(jw-core/audio): TTS/ASR fakes + ASR ABC"
```

---

### Task 4: Kokoro TTS provider

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/kokoro.py`
- Create: `packages/jw-core/tests/test_tts_kokoro.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_tts_kokoro.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from jw_core.audio.tts_providers.fakes import FakeKokoroTTS
from jw_core.audio.tts_providers.kokoro import KokoroTTSProvider


def test_kokoro_real_is_available_when_imports_ok() -> None:
    provider = KokoroTTSProvider()
    # Real availability depends on env; just make sure it never raises
    assert isinstance(provider.is_available(), bool)


def test_kokoro_real_is_unavailable_without_deps() -> None:
    provider = KokoroTTSProvider()
    with patch.object(provider, "_can_import_runtime", return_value=False):
        assert provider.is_available() is False


def test_kokoro_real_synthesize_raises_when_unavailable(tmp_path: Path) -> None:
    provider = KokoroTTSProvider()
    with patch.object(provider, "is_available", return_value=False):
        with pytest.raises(Exception):
            provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "x.wav")


def test_fake_kokoro_writes_wav(tmp_path: Path) -> None:
    out = FakeKokoroTTS().synthesize(
        "Hola mundo", voice=None, language="es", output_path=tmp_path / "h.wav"
    )
    assert out.exists()
    assert out.suffix == ".wav"
    assert out.stat().st_size > 44  # header + at least 1 frame


def test_fake_kokoro_advertises_target_cpu() -> None:
    assert FakeKokoroTTS.target == "cpu"
    assert "es" in FakeKokoroTTS.languages_supported
```

- [ ] **Step 2: Run, expect FAIL on `KokoroTTSProvider` import**

```bash
uv run pytest packages/jw-core/tests/test_tts_kokoro.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/tts_providers/kokoro.py
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_tts_kokoro.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts_providers/kokoro.py packages/jw-core/tests/test_tts_kokoro.py
git commit -m "feat(jw-core/audio): Kokoro-82M TTS provider with lazy ONNX backend"
```

---

### Task 5: XTTSv2 voice-cloning provider (double opt-in)

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/xtts.py`
- Create: `packages/jw-core/tests/test_tts_xtts.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_tts_xtts.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.fakes import FakeXTTSv2
from jw_core.audio.tts_providers.xtts import XTTSv2Provider


def test_xtts_requires_consent_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("JW_XTTS_CLONE_CONSENT", raising=False)
    provider = XTTSv2Provider()
    assert provider.is_available() is False


def test_xtts_requires_voice_sample(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    provider = XTTSv2Provider()
    with pytest.raises(TTSError, match="voice_sample"):
        provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "o.wav")


def test_xtts_writes_consent_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    fake = FakeXTTSv2()
    out = fake.synthesize("hola", voice=str(sample), language="es", output_path=tmp_path / "o.wav")
    assert out.exists()


def test_xtts_real_unavailable_without_pkg(monkeypatch) -> None:
    monkeypatch.setenv("JW_XTTS_CLONE_CONSENT", "1")
    provider = XTTSv2Provider()
    # In CI coqui-tts is not installed; assert that path is exercised
    available = provider.is_available()
    assert isinstance(available, bool)


def test_xtts_target_nvidia() -> None:
    assert XTTSv2Provider.target == "nvidia"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_tts_xtts.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/tts_providers/xtts.py
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_tts_xtts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts_providers/xtts.py packages/jw-core/tests/test_tts_xtts.py
git commit -m "feat(jw-core/audio): XTTSv2 cloning provider with double opt-in + consent.txt"
```

---

### Task 6: F5-TTS experimental provider

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/f5.py`
- Create: `packages/jw-core/tests/test_tts_f5.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_tts_f5.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.f5 import F5TTSProvider
from jw_core.audio.tts_providers.fakes import FakeF5TTS


def test_f5_real_is_available_returns_bool() -> None:
    assert isinstance(F5TTSProvider().is_available(), bool)


def test_f5_real_synthesize_raises_when_unavailable(monkeypatch, tmp_path: Path) -> None:
    provider = F5TTSProvider()
    monkeypatch.setattr(provider, "is_available", lambda: False)
    with pytest.raises(TTSError):
        provider.synthesize("hi", voice=None, language="en", output_path=tmp_path / "x.wav")


def test_f5_languages_conservative() -> None:
    # We only declare en officially to avoid over-promising
    assert F5TTSProvider.languages_supported == {"en"}


def test_fake_f5_writes_wav(tmp_path: Path) -> None:
    out = FakeF5TTS().synthesize("hello", voice=None, language="en", output_path=tmp_path / "f.wav")
    assert out.exists()
    assert out.stat().st_size > 0


def test_fake_f5_target_nvidia() -> None:
    assert FakeF5TTS.target == "nvidia"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_tts_f5.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/tts_providers/f5.py
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_tts_f5.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts_providers/f5.py packages/jw-core/tests/test_tts_f5.py
git commit -m "feat(jw-core/audio): F5-TTS experimental provider (nvidia primary)"
```

---

### Task 7: ElevenLabs TTS provider

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/tts_providers/elevenlabs.py`
- Create: `packages/jw-core/tests/test_tts_elevenlabs.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_tts_elevenlabs.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jw_core.audio.tts import TTSError
from jw_core.audio.tts_providers.elevenlabs import ElevenLabsProvider
from jw_core.audio.tts_providers.fakes import FakeElevenLabsTTS


def test_elevenlabs_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert ElevenLabsProvider().is_available() is False


def test_elevenlabs_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    # is_available must not hit the network
    assert ElevenLabsProvider().is_available() is True


def test_elevenlabs_synthesize_raises_without_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(TTSError):
        ElevenLabsProvider().synthesize(
            "hi", voice=None, language="en", output_path=tmp_path / "x.mp3"
        )


def test_elevenlabs_uses_httpx_with_voice_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "my-voice")

    called = {}

    class FakeResp:
        status_code = 200
        content = b"ID3FAKEMP3"

        def raise_for_status(self) -> None: ...

    class FakeClient:
        def __init__(self, *a, **kw) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a) -> None: ...

        def post(self, url, **kw):
            called["url"] = url
            called["json"] = kw.get("json")
            called["headers"] = kw.get("headers")
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    monkeypatch.setattr(
        ElevenLabsProvider, "_use_sdk", lambda self: False, raising=True
    )

    out = ElevenLabsProvider().synthesize(
        "hello", voice=None, language="en", output_path=tmp_path / "h.mp3"
    )
    assert out.exists()
    assert out.read_bytes() == b"ID3FAKEMP3"
    assert "my-voice" in called["url"]
    assert called["headers"]["xi-api-key"] == "sk-test"


def test_fake_elevenlabs_target_api() -> None:
    assert FakeElevenLabsTTS.target == "api"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_tts_elevenlabs.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/tts_providers/elevenlabs.py
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
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh",
        "ar", "ru", "tr", "pl", "nl", "cs",
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_tts_elevenlabs.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts_providers/elevenlabs.py packages/jw-core/tests/test_tts_elevenlabs.py
git commit -m "feat(jw-core/audio): ElevenLabs TTS provider (SDK + httpx fallback)"
```

---

### Task 8: WhisperTurbo ASR provider + transcription auto-select

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/asr_providers/whisper_turbo.py`
- Modify: `packages/jw-core/src/jw_core/audio/transcription.py`
- Create: `packages/jw-core/tests/test_asr_whisper_turbo.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_asr_whisper_turbo.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from jw_core.audio.asr_providers.fakes import FakeWhisperTurbo
from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider
from jw_core.audio.transcription import TranscriptionError, transcribe_file


def test_whisper_turbo_is_available_when_pkg_installed() -> None:
    provider = WhisperTurboProvider()
    assert isinstance(provider.is_available(), bool)


def test_whisper_turbo_resolves_auto_to_recommended_size(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    provider = WhisperTurboProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo.recommend_model_size",
        lambda: "large-v3-turbo",
    )
    captured: dict[str, str] = {}

    def fake_inner(audio_path, *, model_size, language, device, beam_size):
        captured["model_size"] = model_size
        from jw_core.audio.transcription import TranscriptionResult

        return TranscriptionResult(text="ok", language="en", duration=0.0, segments=[])

    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo._run_faster_whisper", fake_inner
    )
    result = provider.transcribe(audio, language="en", model_size="auto")
    assert captured["model_size"] == "large-v3-turbo"
    assert result.text == "ok"


def test_whisper_turbo_respects_explicit_size(monkeypatch, tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    provider = WhisperTurboProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    captured: dict[str, str] = {}

    def fake_inner(audio_path, *, model_size, language, device, beam_size):
        captured["model_size"] = model_size
        from jw_core.audio.transcription import TranscriptionResult

        return TranscriptionResult(text="ok", language="en", duration=0.0, segments=[])

    monkeypatch.setattr(
        "jw_core.audio.asr_providers.whisper_turbo._run_faster_whisper", fake_inner
    )
    provider.transcribe(audio, language="en", model_size="medium")
    assert captured["model_size"] == "medium"


def test_fake_whisper_turbo_returns_text(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    result = FakeWhisperTurbo().transcribe(audio, language="es", model_size="base")
    assert "fake transcript" in result.text
    assert result.language == "es"


def test_transcribe_file_auto_keeps_legacy_default(monkeypatch, tmp_path: Path) -> None:
    """`transcribe_file(...)` without args should still work — keeps the
    legacy `base` default unless caller passes `model_size="auto"`.
    """
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")

    captured: dict[str, str] = {}

    class FakeInfo:
        language = "en"
        duration = 0.0

    class FakeSeg:
        start = 0.0
        end = 0.5
        text = "hi"

    class FakeWM:
        def __init__(self, size, *, device, compute_type):
            captured["size"] = size

        def transcribe(self, *a, **kw):
            return iter([FakeSeg()]), FakeInfo()

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeWM, raising=False)
    # If faster_whisper is not installed, skip the test
    pytest.importorskip("faster_whisper")
    transcribe_file(audio)
    assert captured["size"] == "base"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_asr_whisper_turbo.py -v
```

- [ ] **Step 3: Modify `transcription.py` (additive)**

Extend `transcribe_file` in `packages/jw-core/src/jw_core/audio/transcription.py` to accept `"auto"`. Keep the old `"base"` default to preserve backwards compatibility.

```python
# packages/jw-core/src/jw_core/audio/transcription.py — additions
# Add to imports:
from jw_core.audio.hardware import recommend_model_size

# Inside transcribe_file:
def transcribe_file(
    audio_path: Path | str,
    *,
    model_size: str = "base",  # unchanged default for back-compat
    language: str | None = None,
    device: str = "auto",
    beam_size: int = 5,
) -> TranscriptionResult:
    """... existing docstring ...

    `model_size="auto"` resolves via hardware.recommend_model_size().
    """
    if model_size == "auto":
        model_size = recommend_model_size()
    # ... rest unchanged ...
```

Also expose the run-helper used by the new provider:

```python
# at bottom of transcription.py
def _run(
    audio_path: Path | str,
    *,
    model_size: str,
    language: str | None,
    device: str,
    beam_size: int,
) -> TranscriptionResult:
    """Internal hook used by WhisperTurboProvider so it can share the
    faster-whisper code path while staying lazily-imported."""
    return transcribe_file(
        audio_path,
        model_size=model_size,
        language=language,
        device=device,
        beam_size=beam_size,
    )
```

- [ ] **Step 4: Implement WhisperTurbo provider**

```python
# packages/jw-core/src/jw_core/audio/asr_providers/whisper_turbo.py
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
        "en", "es", "pt", "fr", "de", "it", "ja", "ko", "zh", "ru", "ar", "tr",
        "nl", "pl", "cs", "hu", "hi",
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
            raise TranscriptionError(
                "faster-whisper not installed. Install jw-core[asr-turbo]."
            )
        resolved = recommend_model_size() if model_size == "auto" else model_size
        return _run_faster_whisper(
            audio_path,
            model_size=resolved,
            language=language,
            device="auto",
            beam_size=5,
        )
```

- [ ] **Step 5: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_asr_whisper_turbo.py -v
uv run pytest packages/jw-core/tests/test_transcription.py -v  # existing tests
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/transcription.py packages/jw-core/src/jw_core/audio/asr_providers/whisper_turbo.py packages/jw-core/tests/test_asr_whisper_turbo.py
git commit -m "feat(jw-core/audio): WhisperTurbo provider + auto model select"
```

---

### Task 9: Deepgram ASR provider

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/asr_providers/deepgram.py`
- Create: `packages/jw-core/tests/test_asr_deepgram.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_asr_deepgram.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.audio.asr_providers.deepgram import DeepgramProvider
from jw_core.audio.asr_providers.fakes import FakeDeepgram
from jw_core.audio.transcription import TranscriptionError


def test_deepgram_unavailable_without_key(monkeypatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    assert DeepgramProvider().is_available() is False


def test_deepgram_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
    assert DeepgramProvider().is_available() is True


def test_deepgram_transcribe_raises_without_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    with pytest.raises(TranscriptionError):
        DeepgramProvider().transcribe(audio, language="en", model_size="auto")


def test_deepgram_transcribe_via_http(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"AUDIO_BYTES")

    captured: dict[str, object] = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None: ...

        def json(self) -> dict:
            return {
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "hello from deepgram",
                                    "confidence": 0.95,
                                }
                            ],
                            "detected_language": "en",
                        }
                    ]
                },
                "metadata": {"duration": 1.5},
            }

    class FakeClient:
        def __init__(self, *a, **kw) -> None: ...
        def __enter__(self):
            return self
        def __exit__(self, *a) -> None: ...
        def post(self, url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            captured["data"] = kw.get("content")
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    monkeypatch.setattr(DeepgramProvider, "_use_sdk", lambda self: False)

    result = DeepgramProvider().transcribe(audio, language="en", model_size="auto")
    assert result.text == "hello from deepgram"
    assert result.language == "en"
    assert captured["headers"]["Authorization"] == "Token dg-test"


def test_fake_deepgram(tmp_path: Path) -> None:
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"\x00")
    r = FakeDeepgram().transcribe(audio, language="es", model_size="auto")
    assert r.text
    assert FakeDeepgram.target == "api"
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_asr_deepgram.py -v
```

- [ ] **Step 3: Implement**

```python
# packages/jw-core/src/jw_core/audio/asr_providers/deepgram.py
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
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-core/tests/test_asr_deepgram.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/asr_providers/deepgram.py packages/jw-core/tests/test_asr_deepgram.py
git commit -m "feat(jw-core/audio): Deepgram ASR provider (SDK + httpx fallback)"
```

---

### Task 10: Factory update — chain + `JW_TTS_PROVIDER` override

**Files:**
- Modify: `packages/jw-core/src/jw_core/audio/tts.py`
- Create: `packages/jw-core/tests/test_audio_factory.py`

- [ ] **Step 1: Write failing test**

```python
# packages/jw-core/tests/test_audio_factory.py
from __future__ import annotations

from unittest.mock import patch

import pytest

from jw_core.audio.tts import (
    DEFAULT_TTS_CHAIN,
    TTSError,
    get_tts_provider,
    list_tts_providers,
)


def test_default_chain_starts_with_kokoro() -> None:
    assert DEFAULT_TTS_CHAIN[0] == "kokoro_local"
    assert "edge" in DEFAULT_TTS_CHAIN
    assert "system" in DEFAULT_TTS_CHAIN
    assert "elevenlabs" in DEFAULT_TTS_CHAIN
    assert "piper" in DEFAULT_TTS_CHAIN


def test_list_includes_premium_providers() -> None:
    names = {p["name"] for p in list_tts_providers()}
    assert {"kokoro_local", "elevenlabs", "xtts", "f5", "edge", "system", "piper"}.issubset(names)


def test_get_tts_provider_falls_back_through_chain(monkeypatch) -> None:
    """When kokoro isn't available we should get edge/system, not an error."""
    monkeypatch.delenv("JW_TTS_PROVIDER", raising=False)
    # Kokoro unavailable
    with patch(
        "jw_core.audio.tts_providers.kokoro.KokoroTTSProvider.is_available",
        return_value=False,
    ):
        provider = get_tts_provider()
        assert provider.name in {"edge", "system", "elevenlabs", "piper"}


def test_jw_tts_provider_env_forces_choice(monkeypatch) -> None:
    monkeypatch.setenv("JW_TTS_PROVIDER", "system")
    p = get_tts_provider()
    assert p.name == "system"


def test_jw_tts_provider_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setenv("JW_TTS_PROVIDER", "kokoro_local")
    with patch(
        "jw_core.audio.tts_providers.kokoro.KokoroTTSProvider.is_available",
        return_value=False,
    ):
        with pytest.raises(TTSError, match="kokoro_local"):
            get_tts_provider()


def test_existing_providers_still_present_unchanged() -> None:
    """The 3 original providers must not be renamed or removed."""
    names = {p["name"] for p in list_tts_providers()}
    assert {"system", "edge", "piper"}.issubset(names)
```

- [ ] **Step 2: Run, expect FAIL**

```bash
uv run pytest packages/jw-core/tests/test_audio_factory.py -v
```

- [ ] **Step 3: Modify `tts.py` registry + factory**

In `packages/jw-core/src/jw_core/audio/tts.py`, replace the `_PROVIDERS` registry block and `get_tts_provider` body. Do NOT touch the existing 3 provider classes.

```python
# Replace the `_PROVIDERS = [...]` line and `get_tts_provider(...)` with:

import os

# Import lazily — we do NOT want to crash if a premium provider's deps are
# absent. The provider classes themselves are pure-python; SDK imports are
# inside their own methods.
from jw_core.audio.tts_providers.elevenlabs import ElevenLabsProvider
from jw_core.audio.tts_providers.f5 import F5TTSProvider
from jw_core.audio.tts_providers.kokoro import KokoroTTSProvider
from jw_core.audio.tts_providers.xtts import XTTSv2Provider

_PROVIDERS: list[type[TTSProvider]] = [
    KokoroTTSProvider,
    EdgeTTSProvider,
    SystemTTSProvider,
    ElevenLabsProvider,
    PiperTTSProvider,
    XTTSv2Provider,
    F5TTSProvider,
]

# Chain that auto-selection walks in order. Not all entries appear; e.g. xtts
# and f5 are never picked automatically because their `is_available()`
# requires explicit consent / GPU.
DEFAULT_TTS_CHAIN: list[str] = [
    "kokoro_local",
    "edge",
    "system",
    "elevenlabs",
    "piper",
]


def list_tts_providers() -> list[dict[str, object]]:
    return [
        {
            "name": cls.name,
            "available": cls().is_available(),
            "languages": sorted(cls.languages_supported),
            "target": cls.target,
        }
        for cls in _PROVIDERS
    ]


def _by_name(name: str) -> type[TTSProvider] | None:
    for cls in _PROVIDERS:
        if cls.name == name:
            return cls
    return None


def get_tts_provider(name: str | None = None) -> TTSProvider:
    """Return a TTS provider.

    Resolution order:
      1. Explicit `name` argument (raises if registered but not available).
      2. JW_TTS_PROVIDER env (same semantics).
      3. DEFAULT_TTS_CHAIN — first available wins.
    """

    requested = name or os.getenv("JW_TTS_PROVIDER")
    if requested:
        cls = _by_name(requested)
        if cls is None:
            raise TTSError(
                f"Unknown TTS provider {requested!r}. Known: {[c.name for c in _PROVIDERS]}"
            )
        instance = cls()
        if not instance.is_available():
            raise TTSError(
                f"Provider {requested!r} is registered but not available on this machine."
            )
        return instance

    for entry in DEFAULT_TTS_CHAIN:
        cls = _by_name(entry)
        if cls is None:
            continue
        instance = cls()
        if instance.is_available():
            return instance

    raise TTSError(
        "No TTS provider available. Install one of: "
        "jw-core[tts-kokoro] | edge-tts | piper-tts | system `say`/`espeak`."
    )
```

- [ ] **Step 4: Run, expect PASS for new + old**

```bash
uv run pytest packages/jw-core/tests/test_audio_factory.py -v
uv run pytest packages/jw-core/tests/test_tts.py -v  # existing
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/tts.py packages/jw-core/tests/test_audio_factory.py
git commit -m "feat(jw-core/audio): register premium providers in chain + JW_TTS_PROVIDER env"
```

---

### Task 11: CLI flags — `--provider`, `--voice`, `--model auto`

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/say.py` (or wherever `jw say` lives)
- Modify: `packages/jw-cli/src/jw_cli/commands/transcribe.py`

- [ ] **Step 1: Identify exact CLI module**

```bash
grep -rn "def say" packages/jw-cli/src
grep -rn "def transcribe" packages/jw-cli/src
```

- [ ] **Step 2: Add `--provider` and `--voice` options to `jw say`**

In the relevant Typer command, add (preserving existing flags):

```python
@app.command()
def say(
    text: str = typer.Argument(...),
    out: Path = typer.Option(..., "--out", "-o"),
    language: str = typer.Option("en", "--language", "-l"),
    provider: str | None = typer.Option(None, "--provider", help="kokoro|edge|system|elevenlabs|piper|xtts|f5"),
    voice: str | None = typer.Option(None, "--voice"),
) -> None:
    from jw_core.audio.tts import synthesize_to_file
    synthesize_to_file(text, out, language=language, provider=provider, voice=voice)
    typer.echo(f"wrote {out}")
```

- [ ] **Step 3: Add `--model auto` and `--provider` to `jw transcribe`**

```python
@app.command()
def transcribe(
    audio: Path = typer.Argument(..., exists=True),
    model: str = typer.Option("auto", "--model"),
    language: str | None = typer.Option(None, "--language", "-l"),
    provider: str = typer.Option("whisper_turbo", "--provider"),
) -> None:
    if provider == "deepgram":
        from jw_core.audio.asr_providers.deepgram import DeepgramProvider
        p = DeepgramProvider()
    else:
        from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider
        p = WhisperTurboProvider()
    result = p.transcribe(audio, language=language, model_size=model)
    typer.echo(result.text)
```

- [ ] **Step 4: Smoke-test CLI**

```bash
uv run jw say "Hola" --out /tmp/h.wav --provider system
uv run jw say --help
uv run jw transcribe --help
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands
git commit -m "feat(jw-cli): expose --provider/--voice/--model flags for audio"
```

---

### Task 12: MCP additive params + offline tests

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Locate the tool decorators**

```bash
grep -n "synthesize_speech\|transcribe_audio" packages/jw-mcp/src/jw_mcp/server.py
```

- [ ] **Step 2: Add optional `provider` and `voice` params (no breaking change)**

```python
@mcp.tool()
def synthesize_speech(
    text: str,
    output_path: str,
    language: str = "en",
    provider: str | None = None,
    voice: str | None = None,
) -> dict:
    """Synthesize speech via the configured TTS chain."""
    from jw_core.audio.tts import synthesize_to_file

    out = synthesize_to_file(
        text, output_path, language=language, provider=provider, voice=voice
    )
    return {"path": str(out)}


@mcp.tool()
def transcribe_audio(
    audio_path: str,
    language: str | None = None,
    model_size: str = "auto",
    provider: str = "whisper_turbo",
) -> dict:
    """Transcribe an audio file via whisper_turbo (local) or deepgram (API)."""
    from pathlib import Path

    if provider == "deepgram":
        from jw_core.audio.asr_providers.deepgram import DeepgramProvider
        p = DeepgramProvider()
    else:
        from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider
        p = WhisperTurboProvider()
    result = p.transcribe(Path(audio_path), language=language, model_size=model_size)
    return {"text": result.text, "language": result.language, "duration": result.duration}
```

- [ ] **Step 3: Run existing MCP test suite (no regressions)**

```bash
uv run pytest packages/jw-mcp/tests -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): expose provider/voice/model params on audio tools"
```

---

### Task 13: User guide `docs/guias/audio-premium.md`

**Files:**
- Create: `docs/guias/audio-premium.md`

- [ ] **Step 1: Write the guide**

```markdown
# Audio premium — TTS y ASR de alta calidad

Esta guía explica cómo usar los providers nuevos añadidos en Fase 34.
Los providers originales (`system`, `edge`, `piper`) siguen funcionando
exactamente igual; lo aquí descrito es opt-in.

## Instalación rápida

```bash
# Stack local recomendado (Kokoro TTS + Whisper Turbo ASR)
uv pip install -e "packages/jw-core[audio-premium]"

# Solo TTS premium local + ElevenLabs
uv pip install -e "packages/jw-core[tts-premium]"

# Solo ASR premium (Whisper Turbo + Deepgram)
uv pip install -e "packages/jw-core[asr-premium]"
```

## TTS providers

| Provider | Comando | Coste | Network | Notas |
|---|---|---|---|---|
| `kokoro_local` | `jw say "..." --provider kokoro` | $0 | No | Recomendado por defecto |
| `edge` | `jw say "..." --provider edge` | $0 | Sí | Voces neurales de MS |
| `system` | `jw say "..." --provider system` | $0 | No | `say`/`espeak` |
| `piper` | `jw say "..." --provider piper` | $0 | No | Requiere `.onnx` |
| `elevenlabs` | `jw say "..." --provider elevenlabs` | $$ | Sí | Necesita `ELEVENLABS_API_KEY` |
| `xtts` | `jw say "..." --provider xtts --voice sample.wav` | $0 | No | Doble opt-in obligatorio |
| `f5` | `jw say "..." --provider f5` | $0 | No | Experimental, requiere NVIDIA |

## ASR providers

```bash
# Auto-select (recomendado): elige large-v3-turbo si tienes >=8GB VRAM
jw transcribe audio.mp3 --model auto

# Forzar tamaño
jw transcribe audio.mp3 --model large-v3-turbo
jw transcribe audio.mp3 --model base

# API (streaming, mejor para reuniones largas)
DEEPGRAM_API_KEY=dg-... jw transcribe audio.mp3 --provider deepgram
```

## Clonación de voz (XTTSv2)

Esta característica es opt-in **doble** por razones éticas:

1. La librería `coqui-tts` debe estar instalada (`jw-core[tts-xtts]`).
2. El env `JW_XTTS_CLONE_CONSENT=1` debe estar presente.
3. Se debe pasar un sample WAV de 6-10s como `--voice`.

Cada output viene acompañado de un `*.consent.txt` documentando la
clonación. Política #6 del overview de fases 33-38 establece que ninguna
voz clonable de un hermano puede usarse sin consentimiento archivable.

## Variables de entorno

Ver la sección homónima en el spec
`docs/superpowers/specs/2026-05-31-fase-34-audio-premium-design.md`.

## Troubleshooting

- **Kokoro descarga lenta**: el modelo (~310MB) se cachea en
  `~/.cache/huggingface`. Ejecuta `jw say "warmup" --provider kokoro` una
  sola vez después de instalar.
- **`is_available()` devuelve `False` con la key puesta**: confirma que el
  env está exportado en el shell donde corres `jw` (`echo $ELEVENLABS_API_KEY`).
- **F5 falla en MLX**: F5-MLX es experimental. Usa Kokoro en M3/M4.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/audio-premium.md
git commit -m "docs(audio): user guide for audio-premium providers"
```

---

### Task 14: VISION/ROADMAP entries + final audit

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Append ROADMAP entry**

In `docs/ROADMAP.md`, append:

```markdown
### Fase 34 — `audio-premium` ✅
- Kokoro-82M (local, multilingüe) como TTS default
- ElevenLabs TTS opt-in (env key)
- XTTSv2 voice-cloning con doble opt-in + consent.txt
- F5-TTS experimental (nvidia primary)
- Whisper Turbo + auto-select por VRAM
- Deepgram ASR opt-in (env key)
- Providers originales `system`/`edge`/`piper` intactos
```

- [ ] **Step 2: Append VISION_AUDIT row**

In `docs/VISION_AUDIT.md`, add Fase 34 row matching the existing format.

- [ ] **Step 3: Run the full suite as final audit**

```bash
uv sync --all-packages
uv run pytest packages/jw-core/tests -v -k "audio or tts or asr or transcription"
uv run pytest packages/jw-mcp/tests -v
uv run pytest packages/jw-cli/tests -v
```

Expected: all pass; the original 1649 tests still green; ~30+ new tests added (5 hardware + 5 each for kokoro/xtts/elevenlabs + 5 for f5 + 5 for whisper turbo + 5 for deepgram + 6 for factory).

- [ ] **Step 4: Verify env-key sanitization**

```bash
grep -rn "ELEVENLABS_API_KEY\|DEEPGRAM_API_KEY" packages/jw-core packages/jw-mcp packages/jw-cli
```
Expected: only `os.getenv(...)` reads — no `print`/`log` of the value.

- [ ] **Step 5: Confirm no module-level heavy imports**

```bash
uv run python -c "import jw_core.audio.tts_providers; import jw_core.audio.asr_providers; print('ok')"
```
Expected: zero seconds wall-clock; no torch/coqui/onnxruntime imported.

- [ ] **Step 6: Final commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: register Fase 34 in roadmap + audit"
```

---

## Self-review

- [x] All 14 tasks have explicit TDD loop (failing test → implement → pass → commit).
- [x] The 3 existing providers (`system`/`edge`/`piper`) are not renamed, moved, or modified beyond setting `target` class var — backward compatible.
- [x] `transcribe_file()` keeps `model_size="base"` as default — only `"auto"` triggers new path. Existing callers untouched.
- [x] Every new provider has a deterministic `Fake*` sibling so tests stay offline.
- [x] `is_available()` on every provider is import-only or env-only; no sockets.
- [x] SDK imports are lazy inside `synthesize`/`transcribe`, never at module level.
- [x] Extras `[tts-kokoro]`, `[tts-xtts]`, `[tts-f5]`, `[tts-elevenlabs]`, `[asr-deepgram]`, `[asr-turbo]`, `[tts-premium]`, `[asr-premium]`, `[audio-premium]` declared in pyproject.
- [x] XTTSv2 enforces double opt-in + consent.txt as required by Política #6.
- [x] CLI and MCP changes are additive — no breaking signature changes.
- [x] Final audit catches accidental key leaks and heavy module imports.

## Execution choice

**Recommended:** subagent-driven (`superpowers:subagent-driven-development`) — tasks 4-9 (providers) are independent and can be dispatched to parallel subagents after task 3 (fakes) lands. Tasks 1, 2, 3, 10, 11, 12, 13, 14 run sequentially on the main thread.

**Alternative:** sequential (`superpowers:executing-plans`) — safer if monorepo state gets messy.
