"""Transcription — faster-whisper (default), Deepgram, Omnilingual (1672 langs).

Original VISION.md item: "Whisper local para dictar notas durante estudio
personal". Phase 54.1 adds a provider registry + auto-router: callers can
request a transcription by language and the toolkit picks the best provider
that supports it.

Routing logic (in `get_asr_provider`):

  1. Explicit `name` argument wins.
  2. `JW_ASR_PROVIDER` env var (same semantics).
  3. If the requested `language` is in a provider's `languages_supported`,
     prefer that provider.
  4. Fallback chain: Deepgram → Whisper → Omnilingual.

The fallback chain places Omnilingual last (heaviest) but it's the ONLY
provider that covers the long tail of 1600+ languages JW publishes in.
For any language Deepgram doesn't claim, the router prefers Omnilingual.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from jw_core.audio.hardware import recommend_model_size

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration: float = 0.0
    segments: list[TranscriptionSegment] = field(default_factory=list)


def transcribe_file(
    audio_path: Path | str,
    *,
    model_size: str = "base",
    language: str | None = None,
    device: str = "auto",
    beam_size: int = 5,
) -> TranscriptionResult:
    """Run Whisper on `audio_path`.

    Args:
        audio_path: WAV/MP3/M4A/FLAC.
        model_size: 'tiny', 'base' (default), 'small', 'medium', 'large-v3',
            'large-v3-turbo', or 'auto' (resolves via hardware.recommend_model_size()).
        language: optional ISO-639 hint; None = auto-detect.
        device: 'auto', 'cpu', or 'cuda'.
        beam_size: decoder beam size (higher = better, slower).
    """
    if model_size == "auto":
        model_size = recommend_model_size()
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise TranscriptionError("faster-whisper is not installed. `pip install faster-whisper`") from e

    model = WhisperModel(model_size, device=device, compute_type="int8")
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
    )

    segments: list[TranscriptionSegment] = []
    text_parts: list[str] = []
    for seg in segments_iter:
        segments.append(TranscriptionSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
        text_parts.append(seg.text.strip())
    return TranscriptionResult(
        text=" ".join(text_parts),
        language=info.language,
        duration=info.duration,
        segments=segments,
    )


# ── Provider registry + router (F54.1) ─────────────────────────────────


def _all_providers() -> list[type]:
    """Lazy import to avoid loading optional deps at module-level.

    Cada provider se importa con try/except aislado para que un import
    error no tumbe el registry entero.
    """
    from jw_core.audio.asr_providers import ASRProvider  # noqa: F401

    out: list[type] = []
    try:
        from jw_core.audio.asr_providers.deepgram import DeepgramProvider

        out.append(DeepgramProvider)
    except ImportError:
        pass
    try:
        from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider

        out.append(WhisperTurboProvider)
    except ImportError:
        pass
    try:
        # F64: whisperX provider (lazy: la dep `whisperx` se valida en is_available()).
        # El módulo en sí no importa `whisperx` al cargar — sólo a la hora de transcribir.
        from jw_core.audio.asr_providers.whisperx import WhisperXProvider

        out.append(WhisperXProvider)
    except ImportError:
        pass
    try:
        from jw_core.audio.asr_providers.omnilingual import OmnilingualProvider

        out.append(OmnilingualProvider)
    except ImportError:
        pass
    return out


DEFAULT_ASR_CHAIN: list[str] = ["deepgram", "whisper-turbo", "omnilingual"]


def _provider_by_name(name: str) -> type | None:
    for cls in _all_providers():
        if cls.name == name:
            return cls
    return None


def get_asr_provider(name: str | None = None, *, language: str | None = None):  # type: ignore[no-untyped-def]
    """Return an available ASR provider.

    Resolution:
      1. Explicit `name`.
      2. `JW_ASR_PROVIDER` env.
      3. By `language` (provider whose `languages_supported` covers it,
         with Deepgram preferred for high-resource for latency).
      4. DEFAULT_ASR_CHAIN — first available wins.
    """
    requested = name or os.getenv("JW_ASR_PROVIDER")
    if requested:
        cls = _provider_by_name(requested)
        if cls is None:
            known = [c.name for c in _all_providers()]
            raise TranscriptionError(f"Unknown ASR provider {requested!r}. Known: {known}")
        instance = cls()
        if not instance.is_available():
            raise TranscriptionError(f"Provider {requested!r} not available on this machine.")
        return instance

    # Language-aware routing: if the language is mainstream → Deepgram;
    # otherwise → Omnilingual (covers the long tail).
    if language:
        lang_iso = language.split("_")[0].lower()
        for entry_name in DEFAULT_ASR_CHAIN:
            cls = _provider_by_name(entry_name)
            if cls is None:
                continue
            if lang_iso in cls.languages_supported:
                instance = cls()
                if instance.is_available():
                    return instance
        # Omnilingual is the catch-all when nobody else claims the lang.
        omni_cls = _provider_by_name("omnilingual")
        if omni_cls is not None:
            omni = omni_cls()
            if omni.is_available():
                return omni

    for entry_name in DEFAULT_ASR_CHAIN:
        cls = _provider_by_name(entry_name)
        if cls is None:
            continue
        instance = cls()
        if instance.is_available():
            return instance

    raise TranscriptionError(
        "No ASR provider available. Options: DEEPGRAM_API_KEY for Deepgram, "
        "`pip install faster-whisper`, or `jw omnilingual install` for 1672 languages."
    )


def list_asr_providers() -> list[dict[str, object]]:
    return [
        {
            "name": cls.name,
            "available": cls().is_available(),
            "languages_supported_count": len(cls.languages_supported),
            "target": getattr(cls, "target", "cpu"),
        }
        for cls in _all_providers()
    ]


def estimate_real_time_factor(model_size: str) -> float:
    """Rough CPU-only Real-Time Factor (RTF) per model size on M2/M3.

    Lower is faster. Returned values are guidance, not guarantees.
    """
    return {
        "tiny": 0.1,
        "base": 0.2,
        "small": 0.4,
        "medium": 0.9,
        "large-v3": 2.0,
    }.get(model_size, 1.0)


# ── F64: diarization (whisperX) — extiende sin modificar ─────────────────


@dataclass
class DiarizedSegment(TranscriptionSegment):
    """Segmento con identificación de orador y refs bíblicas opcionales.

    Subclase backwards-compatible de `TranscriptionSegment`: el código
    que recibe la base sigue funcionando. La importación de `BibleRef`
    se hace lazy en `field(default_factory=tuple)` para evitar ciclos.
    """

    # IMPORTANTE: la importación de BibleRef se hace en el módulo (top-level)
    # debajo de esta clase para no introducir ciclos con jw_core.models
    # (que sólo depende de jw_core.types/data). Si BibleRef llega a depender
    # de jw_core.audio en el futuro, mover este import dentro del provider.
    speaker_id: str | None = None
    bible_refs: tuple[BibleRef, ...] = field(default_factory=tuple)


@dataclass
class DiarizedResult(TranscriptionResult):
    """Result de transcripción con diarización.

    Subclase backwards-compatible de `TranscriptionResult`: código que
    espera la base sigue funcionando. `segments` se redeclara con tipo
    más estrecho `list[DiarizedSegment]`; dataclass tolera el override
    porque ambos campos tienen `default_factory`.
    """

    segments: list[DiarizedSegment] = field(default_factory=list)  # type: ignore[assignment]
    speaker_count: int = 0


# Lazy import para resolver el forward-ref `"BibleRef"` en DiarizedSegment.
# Se hace al final para evitar cualquier ciclo durante la carga del módulo.
from jw_core.models import BibleRef  # noqa: E402  (intentional late import)
