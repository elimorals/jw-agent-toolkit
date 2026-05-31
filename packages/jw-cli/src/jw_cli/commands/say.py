"""`jw say` — high-quality text-to-speech via the configured TTS chain.

Defaults to auto-selecting the best available provider (Kokoro local if
installed, falling back through edge/system/ElevenLabs/Piper). Pass
`--provider` to force a specific one and `--voice` to choose a voice ID or
voice-clone sample WAV.
"""

from __future__ import annotations

from pathlib import Path

import typer


def say_cmd(
    text: str = typer.Argument(..., help="Text to synthesize."),
    out: Path = typer.Option(..., "--out", "-o", help="Output audio path."),
    language: str = typer.Option("en", "--language", "-l", help="ISO language code."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="kokoro|edge|system|elevenlabs|piper|xtts|f5",
    ),
    voice: str | None = typer.Option(
        None,
        "--voice",
        help="Provider-specific voice ID or path to a voice sample WAV.",
    ),
) -> None:
    """Synthesize `text` to `out`."""

    from jw_core.audio.tts import synthesize_to_file

    synthesize_to_file(text, out, language=language, provider=provider, voice=voice)
    typer.echo(f"wrote {out}")
