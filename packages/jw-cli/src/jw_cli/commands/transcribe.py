"""`jw transcribe` — automatic speech recognition over a local audio file.

Defaults to the local `whisper_turbo` provider with auto-selected model size.
Pass `--provider deepgram` to use the Deepgram API (requires DEEPGRAM_API_KEY).
"""

from __future__ import annotations

from pathlib import Path

import typer


def transcribe_cmd(
    audio: Path = typer.Argument(..., exists=True, help="Audio file (WAV/MP3/M4A/FLAC)."),
    model: str = typer.Option(
        "auto",
        "--model",
        help="auto | tiny | base | small | medium | large-v3 | large-v3-turbo",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="ISO language hint; omit for auto-detect.",
    ),
    provider: str = typer.Option(
        "whisper_turbo",
        "--provider",
        help="whisper_turbo (local) | deepgram (API)",
    ),
) -> None:
    """Print the transcript of `audio`."""

    if provider == "deepgram":
        from jw_core.audio.asr_providers.deepgram import DeepgramProvider

        p = DeepgramProvider()
    else:
        from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider

        p = WhisperTurboProvider()
    result = p.transcribe(audio, language=language, model_size=model)
    typer.echo(result.text)
