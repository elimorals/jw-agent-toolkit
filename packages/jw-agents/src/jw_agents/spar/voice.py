"""Voice mode for sparring (Fase 66 post-MVP).

Bridges F34 ASR (`transcribe_file`) + TTS (`synthesize_to_file`) into
the sparring loop. The audio never leaves the disk; the LLM receives
only the transcribed text.

Both ASR and TTS are import-guarded so the spar package stays usable
without the audio extras installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jw_agents.spar.models import PersonaTurnResponse, SparSession
from jw_agents.spar.session import get_session, take_turn
from jw_agents.spar.simulator import LLMProviderLike

logger = logging.getLogger(__name__)


class VoiceModeError(RuntimeError):
    """Raised when ASR or TTS deps are missing or fail."""


def transcribe_user_audio(
    audio_path: str,
    *,
    language: str | None = None,
    model_size: str = "base",
) -> str:
    """Run F34 Whisper on `audio_path` and return the transcribed text."""

    try:
        from jw_core.audio.transcription import transcribe_file
    except Exception as exc:
        raise VoiceModeError(
            "F34 transcription not available; install faster-whisper extra."
        ) from exc
    try:
        result = transcribe_file(
            Path(audio_path),
            language=language,
            model_size=model_size,
        )
    except Exception as exc:
        raise VoiceModeError(
            f"transcription failed for {audio_path}: {exc}"
        ) from exc
    return result.text


def synthesize_persona_reply(
    reply_text: str,
    output_path: str,
    *,
    language: str = "es",
    voice: str | None = None,
    provider: str | None = None,
) -> Path:
    """Run F34 TTS on `reply_text` and write to `output_path`."""

    try:
        from jw_core.audio.tts import synthesize_to_file
    except Exception as exc:
        raise VoiceModeError(
            "F34 TTS not available; install jw-core[tts-kokoro] or edge-tts."
        ) from exc
    try:
        return synthesize_to_file(
            reply_text,
            output_path,
            language=language,
            voice=voice,
            provider=provider,
        )
    except Exception as exc:
        raise VoiceModeError(
            f"TTS synthesis failed: {exc}"
        ) from exc


async def take_voice_turn(
    *,
    session_id: str,
    audio_in_path: str,
    audio_out_path: str,
    llm: LLMProviderLike,
    asr_language: str | None = None,
    asr_model_size: str = "base",
    tts_voice: str | None = None,
    tts_provider: str | None = None,
    transcribe_fn: Any | None = None,
    synthesize_fn: Any | None = None,
) -> tuple[str, PersonaTurnResponse, Path]:
    """End-to-end voice turn: ASR -> spar LLM -> TTS.

    Returns `(transcribed_user_text, persona_response, persona_audio_path)`.

    `transcribe_fn` and `synthesize_fn` are injection points used by tests
    to bypass F34 deps. When omitted, the real F34 callables are used.
    """

    transcribe = transcribe_fn or transcribe_user_audio
    synthesize = synthesize_fn or synthesize_persona_reply

    session: SparSession = get_session(session_id)
    user_text = transcribe(
        audio_in_path,
        language=asr_language or session.language,
        model_size=asr_model_size,
    )
    response = await take_turn(
        session_id=session_id, user_text=user_text, llm=llm
    )
    out = synthesize(
        response.reply,
        audio_out_path,
        language=session.language,
        voice=tts_voice,
        provider=tts_provider,
    )
    return user_text, response, Path(out)
