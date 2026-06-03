"""Omnilingual ASR provider — Meta's 1600+ language model (Apache 2.0).

## Why a subprocess instead of an in-process import

`omnilingual-asr` depends on `fairseq2`, which only publishes wheels for
CPython 3.10/3.11/3.12. The toolkit runs on Python 3.13. Rather than freeze
the entire monorepo at 3.12 because of one library, we install Omnilingual
into a **dedicated venv on Python 3.12** and drive it from a subprocess.

The runtime cost is one Python interpreter cold-start (~300 ms) per
transcription. That's acceptable for offline batch use — the dominant cost
is the model itself (seconds to minutes). It is NOT suitable for hot-path
streaming; if/when fairseq2 lands wheels for 3.13, we'll switch this to an
in-process import (the worker contract is the same JSON shape).

## Capability summary

  - 1672 languages including hundreds of low-resource (indigenous, Pacific,
    African Bantu) that Deepgram & Whisper-large-v3 don't cover.
  - Apache 2.0 weights, downloadable; runs fully offline.
  - MLX 4-bit ports (`aufklarer/*`) run on M1/M2 16 GB unified memory.

## Honest limits

  - No streaming. Batch only. 40s clip cap on base; up to 15 min on the
    `omniASR_LLM_Unlimited_*_v2` variants.
  - First call downloads the model (~600 MB to ~30 GB depending on size).

## Bootstrap

The provider needs a Python 3.12 venv with `omnilingual-asr` installed:

    jw omnilingual install
    # or, manually:
    /opt/homebrew/bin/python3.12 -m venv ~/.jw-core/omnilingual/venv
    ~/.jw-core/omnilingual/venv/bin/pip install omnilingual-asr

Override paths via env:
    JW_OMNILINGUAL_VENV=/path/to/your/python312/venv
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar, Final, Literal

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.transcription import (
    TranscriptionError,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_CARD: Final[str] = "omniASR_CTC_300M"
DEFAULT_VENV_DIR: Final[Path] = Path.home() / ".jw-core" / "omnilingual" / "venv"

# Map ISO-639-1 → FLORES-200 (`{iso639-3}_{script}`). Extend as new
# languages get exercised. The runtime-lookup path in `supports_language()`
# consults Omnilingual's own list for everything else.
_ISO1_TO_FLORES: Final[dict[str, str]] = {
    "en": "eng_Latn", "es": "spa_Latn", "pt": "por_Latn", "fr": "fra_Latn",
    "de": "deu_Latn", "it": "ita_Latn", "ja": "jpn_Jpan", "ko": "kor_Hang",
    "zh": "cmn_Hans", "ru": "rus_Cyrl", "ar": "arb_Arab", "tr": "tur_Latn",
    "nl": "nld_Latn", "pl": "pol_Latn", "cs": "ces_Latn", "hi": "hin_Deva",
    # Low-resource targets relevant for JW publication coverage:
    "qu": "quy_Latn",  # Ayacucho Quechua
    "ay": "ayr_Latn",  # Aymara
    "gn": "grn_Latn",  # Guarani
    "rw": "kin_Latn",  # Kinyarwanda
    "sw": "swh_Latn",  # Swahili
    "ln": "lin_Latn",  # Lingala
    "yo": "yor_Latn",  # Yoruba
    "ig": "ibo_Latn",  # Igbo
    "ha": "hau_Latn",  # Hausa
    "zu": "zul_Latn",  # Zulu
    "xh": "xho_Latn",  # Xhosa
}


class OmnilingualProvider(ASRProvider):
    name = "omnilingual"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported: set[str] = set()  # consulted at runtime via supports_language()

    def __init__(self, model_card: str | None = None, venv_dir: Path | None = None) -> None:
        self.model_card = model_card or os.getenv("OMNILINGUAL_MODEL_CARD", DEFAULT_MODEL_CARD)
        self.venv_dir = Path(venv_dir or os.getenv("JW_OMNILINGUAL_VENV") or DEFAULT_VENV_DIR)

    # ── availability ────────────────────────────────────────────────

    @property
    def venv_python(self) -> Path:
        """Path to the python3.12 binary inside the dedicated venv."""
        # uv-created venvs put python at venv/bin/python on POSIX,
        # venv\Scripts\python.exe on Windows. Honor both.
        candidates = [
            self.venv_dir / "bin" / "python",
            self.venv_dir / "bin" / "python3",
            self.venv_dir / "Scripts" / "python.exe",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return candidates[0]  # canonical path, used in install hints

    def is_available(self) -> bool:
        """True iff the dedicated venv exists and has omnilingual-asr installed."""
        if not self.venv_python.is_file():
            return False
        try:
            check = subprocess.run(
                [str(self.venv_python), "-c", "import omnilingual_asr"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return check.returncode == 0

    def supports_language(self, flores_code: str) -> bool:
        """Ask the worker venv whether `flores_code` is in its supported list."""
        if not self.is_available():
            return False
        try:
            out = subprocess.run(
                [
                    str(self.venv_python),
                    "-c",
                    (
                        "from omnilingual_asr.models.wav2vec2_llama.lang_ids "
                        f"import supported_langs; print('yes' if {flores_code!r} "
                        "in supported_langs else 'no')"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return out.returncode == 0 and out.stdout.strip() == "yes"

    # ── transcription ───────────────────────────────────────────────

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",  # ignored — use model_card instead
    ) -> TranscriptionResult:
        if not self.venv_python.is_file():
            raise TranscriptionError(
                f"Omnilingual venv not found at {self.venv_dir}. "
                f"Run `jw omnilingual install` to bootstrap it."
            )
        if not self.is_available():
            raise TranscriptionError(
                f"Omnilingual venv at {self.venv_dir} exists but `omnilingual_asr` "
                f"is not installed inside it. Run `jw omnilingual install`."
            )

        flores = self._normalize_language(language)
        worker = _worker_script_path()
        argv = [
            str(self.venv_python),
            str(worker),
            "--audio",
            str(audio_path),
            "--model-card",
            self.model_card,
        ]
        if flores:
            argv.extend(["--lang", flores])

        try:
            result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TranscriptionError(f"Omnilingual worker failed to start: {exc!r}") from exc
        if result.returncode != 0:
            raise TranscriptionError(
                f"Omnilingual worker exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TranscriptionError(f"Omnilingual worker emitted invalid JSON: {exc!r}") from exc

        text = payload.get("text", "")
        lang = payload.get("language", flores or "und")
        return TranscriptionResult(
            text=text,
            language=lang,
            duration=0.0,
            segments=[TranscriptionSegment(start=0.0, end=0.0, text=text)],
        )

    # ── bootstrap helper ────────────────────────────────────────────

    def install(self, python312_executable: str | None = None) -> Path:
        """Create the dedicated 3.12 venv and install omnilingual-asr.

        Looks up `python3.12` on PATH unless `python312_executable` is
        given. Idempotent: if the venv already exists, just upgrades.
        """
        py312 = python312_executable or shutil.which("python3.12")
        if not py312:
            raise TranscriptionError(
                "python3.12 not found on PATH. Install it (e.g. `brew install python@3.12`) "
                "or pass the explicit path to `install(python312_executable=...)`."
            )
        self.venv_dir.parent.mkdir(parents=True, exist_ok=True)
        if not self.venv_dir.is_dir():
            subprocess.run([py312, "-m", "venv", str(self.venv_dir)], check=True)
        pip = self.venv_dir / "bin" / "pip"
        if not pip.is_file():  # pragma: no cover - Windows fallback
            pip = self.venv_dir / "Scripts" / "pip.exe"
        subprocess.run([str(pip), "install", "--upgrade", "pip"], check=True)
        # `omnilingual-asr` doesn't pin torchaudio strictly; resolver routinely
        # picks torchaudio 2.11 against torch 2.8, which segfaults on import
        # (`Symbol not found: _torch_library_impl`). Force-align both.
        subprocess.run(
            [str(pip), "install", "omnilingual-asr", "torch==2.8.0", "torchaudio==2.8.0"],
            check=True,
        )
        return self.venv_dir

    # ── internals ───────────────────────────────────────────────────

    def _normalize_language(self, language: str | None) -> str | None:
        if language is None:
            return None
        if "_" in language:
            return language  # already FLORES
        return _ISO1_TO_FLORES.get(language.lower(), language)


def _worker_script_path() -> Path:
    return Path(__file__).with_name("omnilingual_worker.py")
