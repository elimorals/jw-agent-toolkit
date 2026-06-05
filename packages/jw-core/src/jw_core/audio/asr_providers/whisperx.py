"""WhisperX provider: word-level timestamps + speaker diarization (Fase 64).

Carga la dep pesada (`whisperx`, ~3 GB con modelos) solo cuando se
instancia un job real, no en module import.

Modelo de diarización (`pyannote/speaker-diarization-3.1`) requiere:

1. Token HF accesible via env `HF_TOKEN` o `HUGGING_FACE_HUB_TOKEN`.
2. Aceptación de términos de uso en HuggingFace UI (una vez por cuenta).

El provider expone dos puntos de entrada:

- `transcribe(audio_path, ...)` — devuelve `TranscriptionResult` legacy
  (compatible con el `ASRProvider` Protocol).
- `transcribe_diarized(audio_path, ..., enrich_with_bible_refs=False)` —
  devuelve `DiarizedResult` con `speaker_id` por segmento y, opcionalmente,
  `BibleRef`s extraídas vía `parse_all_references()`.

Decisión clave: NO se añade a `DEFAULT_ASR_CHAIN` para no forzar la
descarga del modelo (~2 GB) en usuarios que no lo piden explícitamente.
Se selecciona con `JW_ASR_PROVIDER=whisperx` o `get_asr_provider(name="whisperx")`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.transcription import (
    DiarizedResult,
    DiarizedSegment,
    TranscriptionResult,
    TranscriptionSegment,
)


class WhisperXDiarizationError(RuntimeError):
    """Diarización pidió un recurso (token HF) que no está disponible."""


def _detect_target() -> Literal["cuda", "cpu"]:
    """CUDA si está disponible, CPU en otro caso. Sin import pesado al cargar."""
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return "cpu"
    try:
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001 — defensivo: torch puede explotar al checkear cuda
        return "cpu"


class WhisperXProvider(ASRProvider):
    """ASR provider con diarización + word-level timestamps."""

    name = "whisperx"
    # `target` es declarativo en ASRProvider; el valor real se pisa en __init__
    # para reflejar la GPU disponible en runtime sin forzar torch import top-level.
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu"]] = "cpu"
    languages_supported = {
        "en",
        "es",
        "pt",
        "fr",
        "de",
        "it",
        "ru",
        "zh",
        "ja",
        "ko",
        "nl",
        "tr",
        "pl",
        "uk",
        "cs",
        "ar",
        "hi",
        "vi",
        "th",
    }

    def __init__(self, model_size: str = "large-v3") -> None:
        self.model_size = model_size
        # Sobreescribimos el ClassVar en la instancia con "cuda"/"cpu" reales.
        # Usamos setattr para evitar que mypy se queje del estrechamiento de tipo.
        object.__setattr__(self, "target", _detect_target())
        self._asr_model = None
        self._align_model: tuple[object, str, object] | None = None
        self._diarize_model = None

    def is_available(self) -> bool:
        try:
            import whisperx  # noqa: F401  # type: ignore[import-not-found]
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
        """Transcripción rápida sin diarización (compatible con Protocol)."""
        return self._transcribe_impl(
            audio_path,
            language=language,
            model_size=model_size,
            diarize=False,
        )  # type: ignore[return-value]

    def transcribe_diarized(
        self,
        audio_path: Path | str,
        *,
        language: str | None = None,
        model_size: str = "auto",
        enrich_with_bible_refs: bool = False,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> DiarizedResult:
        """Transcripción + diarización + opcional enrichment con BibleRef."""
        result = self._transcribe_impl(
            audio_path,
            language=language,
            model_size=model_size,
            diarize=True,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        if not isinstance(result, DiarizedResult):
            raise RuntimeError("Expected DiarizedResult; got " + type(result).__name__)
        if enrich_with_bible_refs:
            result = self._enrich_bible_refs(result)
        return result

    # ── Internals ──────────────────────────────────────────────────────

    def _transcribe_impl(
        self,
        audio_path: Path | str,
        *,
        language: str | None,
        model_size: str,
        diarize: bool,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> TranscriptionResult | DiarizedResult:
        import whisperx  # type: ignore[import-not-found]

        actual_size = self.model_size if model_size == "auto" else model_size
        device = self.target
        # int8 en CPU, float16 en CUDA — defaults razonables.
        compute_type = "int8" if device == "cpu" else "float16"

        if self._asr_model is None:
            self._asr_model = whisperx.load_model(
                actual_size, device, compute_type=compute_type
            )

        audio = whisperx.load_audio(str(audio_path))
        asr_out = self._asr_model.transcribe(audio, language=language)
        detected_lang = asr_out.get("language", language or "en")

        # Word-level alignment: reusa modelo si el idioma no cambió.
        needs_align = self._align_model is None or self._align_model[1] != detected_lang
        if needs_align:
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_lang, device=device
            )
            self._align_model = (model_a, detected_lang, metadata)
        assert self._align_model is not None
        aligned = whisperx.align(
            asr_out["segments"],
            self._align_model[0],
            self._align_model[2],
            audio,
            device,
            return_char_alignments=False,
        )

        duration = audio.shape[0] / 16000.0

        if not diarize:
            segments = [
                TranscriptionSegment(start=s["start"], end=s["end"], text=s["text"])
                for s in aligned["segments"]
            ]
            return TranscriptionResult(
                text=" ".join(s.text for s in segments).strip(),
                language=detected_lang,
                duration=duration,
                segments=segments,
            )

        # Diarización: gate sobre HF token.
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get(
            "HUGGING_FACE_HUB_TOKEN"
        )
        if not hf_token:
            raise WhisperXDiarizationError(
                "Diarization requires a HuggingFace token. Set HF_TOKEN "
                "env var and accept terms at "
                "https://hf.co/pyannote/speaker-diarization-3.1"
            )
        if self._diarize_model is None:
            self._diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=hf_token, device=device
            )
        diarize_segments = self._diarize_model(
            audio, min_speakers=min_speakers, max_speakers=max_speakers
        )
        result_with_speakers = whisperx.assign_word_speakers(diarize_segments, aligned)

        segments_diarized: list[DiarizedSegment] = []
        for s in result_with_speakers["segments"]:
            segments_diarized.append(
                DiarizedSegment(
                    start=s["start"],
                    end=s["end"],
                    text=s["text"],
                    speaker_id=s.get("speaker"),
                )
            )
        speaker_ids = {seg.speaker_id for seg in segments_diarized if seg.speaker_id}
        return DiarizedResult(
            text=" ".join(s.text for s in segments_diarized).strip(),
            language=detected_lang,
            duration=duration,
            segments=segments_diarized,
            speaker_count=len(speaker_ids),
        )

    @staticmethod
    def _enrich_bible_refs(result: DiarizedResult) -> DiarizedResult:
        """Para cada segmento, extrae todas las BibleRef si el texto las menciona."""
        from jw_core.parsers.reference import parse_all_references

        enriched: list[DiarizedSegment] = []
        for seg in result.segments:
            refs = parse_all_references(seg.text)
            enriched.append(
                DiarizedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker_id=seg.speaker_id,
                    bible_refs=tuple(refs) if refs else (),
                )
            )
        return DiarizedResult(
            text=result.text,
            language=result.language,
            duration=result.duration,
            segments=enriched,
            speaker_count=result.speaker_count,
        )
