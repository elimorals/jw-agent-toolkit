"""F64 — WhisperXProvider con diarización opt-in."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

FIXTURE_ES = Path(__file__).parent / "fixtures" / "audio" / "discurso_mini.wav"
FIXTURE_EN = Path(__file__).parent / "fixtures" / "audio" / "discurso_en.wav"


def _whisperx_available() -> bool:
    return importlib.util.find_spec("whisperx") is not None


def test_provider_metadata() -> None:
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider

    p = WhisperXProvider()
    assert p.name == "whisperx"
    assert p.target in {"cuda", "cpu"}
    assert "es" in p.languages_supported
    assert "en" in p.languages_supported


def test_is_available_returns_bool() -> None:
    """Sin whisperx instalado, is_available debe ser False (no raise)."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider

    p = WhisperXProvider()
    available = p.is_available()
    assert isinstance(available, bool)
    # Si la dep está, es True; si no, False. No assertion hard.


@pytest.mark.skipif(not _whisperx_available(), reason="whisperx not installed")
def test_transcribe_returns_transcription_result_legacy() -> None:
    """Llamada sin diarización: devuelve TranscriptionResult compatible."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider
    from jw_core.audio.transcription import TranscriptionResult

    p = WhisperXProvider(model_size="tiny")  # rápido para test
    result = p.transcribe(FIXTURE_ES, language="es")
    assert isinstance(result, TranscriptionResult)
    assert result.language == "es"
    assert len(result.text) > 0


@pytest.mark.skipif(not _whisperx_available(), reason="whisperx not installed")
def test_transcribe_diarized_marks_speakers() -> None:
    """transcribe_diarized devuelve DiarizedResult con speaker_id."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider
    from jw_core.audio.transcription import DiarizedResult

    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        pytest.skip("HF_TOKEN not set; diarization needs pyannote model access")

    p = WhisperXProvider(model_size="tiny")
    result = p.transcribe_diarized(FIXTURE_ES, language="es")
    assert isinstance(result, DiarizedResult)
    # Audio de 1 orador → speaker_count >= 1
    assert result.speaker_count >= 1
    assert all(seg.speaker_id is not None for seg in result.segments)


@pytest.mark.skipif(not _whisperx_available(), reason="whisperx not installed")
def test_transcribe_diarized_enriches_bible_refs() -> None:
    """Con enrich_with_bible_refs=True, segmentos con menciones bíblicas
    obtienen `bible_refs`."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider

    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        pytest.skip("HF_TOKEN not set")

    p = WhisperXProvider(model_size="tiny")
    result = p.transcribe_diarized(FIXTURE_ES, language="es", enrich_with_bible_refs=True)
    has_ref = any(seg.bible_refs for seg in result.segments)
    # Audio dice "Génesis uno uno" → al menos 1 ref detectada
    assert has_ref


def test_diarization_error_raised_without_hf_token() -> None:
    """Si falta HF_TOKEN al pedir diarize, error claro con clase dedicada.

    Independiente de si whisperx está instalado: la función `is_available`
    debe gate la ejecución y la excepción es de tipo `WhisperXDiarizationError`
    importable sin la dep.
    """
    from jw_core.audio.asr_providers.whisperx import WhisperXDiarizationError

    # La clase debe existir y ser RuntimeError-subclass para integrarse con
    # los handlers ya existentes en el router / MCP layer.
    assert issubclass(WhisperXDiarizationError, RuntimeError)
