"""Voice mode tests using injected transcribe_fn / synthesize_fn (no F34 deps)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from jw_agents.spar.session import clear_sessions, start_session
from jw_agents.spar.simulator import FakeSparLLM
from jw_agents.spar.voice import (
    VoiceModeError,
    take_voice_turn,
    transcribe_user_audio,
)


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_sessions()
    yield
    clear_sessions()


@pytest.mark.asyncio
async def test_take_voice_turn_injects_transcribe_and_synthesize(
    tmp_path: Path,
) -> None:
    audio_in = tmp_path / "in.wav"
    audio_in.write_bytes(b"fake")
    audio_out = tmp_path / "out.wav"

    transcribe_calls = []
    synthesize_calls = []

    def _fake_transcribe(audio_path, *, language=None, model_size="base"):
        transcribe_calls.append((audio_path, language))
        return "Buenos días"

    def _fake_synthesize(text, out_path, *, language="es", voice=None, provider=None):
        synthesize_calls.append((text, out_path, language))
        Path(out_path).write_bytes(b"fake-audio")
        return Path(out_path)

    s = start_session(persona_key="catholic", language="es")
    user_text, response, out_path = await take_voice_turn(
        session_id=s.session_id,
        audio_in_path=str(audio_in),
        audio_out_path=str(audio_out),
        llm=FakeSparLLM(),
        transcribe_fn=_fake_transcribe,
        synthesize_fn=_fake_synthesize,
    )
    assert user_text == "Buenos días"
    assert response.reply
    assert out_path == audio_out
    assert audio_out.exists()
    assert len(transcribe_calls) == 1
    assert len(synthesize_calls) == 1
    # Synthesize should have received the persona's reply
    assert synthesize_calls[0][0] == response.reply


def test_transcribe_user_audio_raises_VoiceModeError_when_dep_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When faster-whisper isn't installed, we surface VoiceModeError cleanly."""
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"fake")

    # Force the import inside transcribe_user_audio to fail.
    import sys

    monkeypatch.setitem(sys.modules, "jw_core.audio.transcription", None)
    with pytest.raises(VoiceModeError):
        transcribe_user_audio(str(audio))
