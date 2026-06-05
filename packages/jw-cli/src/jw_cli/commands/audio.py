"""`jw audio` — comandos de audio con diarización (F64).

`jw transcribe` (top-level) sigue existiendo y se mantiene como entrada
mínima compatible. Este sub-app expone una variante extendida que añade
diarización y enriquecimiento opcional con `BibleRef`.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

audio_app = typer.Typer(
    name="audio",
    help="Audio: transcripción con diarización + extracción de refs bíblicas (Fase 64).",
    no_args_is_help=True,
    add_completion=False,
)


@audio_app.command("transcribe")
def transcribe(
    audio_path: Path = typer.Argument(..., exists=True, help="Ruta al archivo de audio."),
    language: str = typer.Option(
        "auto",
        "--language",
        "-l",
        help="ISO code (en/es/pt/...). `auto` deja el provider detectar.",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="deepgram | whisper_turbo | whisperx | omnilingual. Default: router.",
    ),
    diarize: bool = typer.Option(
        False,
        "--diarize",
        help="Identificar oradores (requiere --provider=whisperx + HF_TOKEN).",
    ),
    bible_refs: bool = typer.Option(
        False,
        "--bible-refs",
        help="Enriquecer segmentos con BibleRef si los textos los mencionan.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Ruta de salida JSON. Si se omite, escribe a stdout.",
    ),
) -> None:
    """Transcribe un archivo de audio. Con `--diarize` identifica oradores."""
    from jw_core.audio.transcription import get_asr_provider

    lang = None if language == "auto" else language
    asr = get_asr_provider(name=provider, language=lang)

    if diarize:
        if asr.name != "whisperx":
            typer.echo(
                "--diarize requires --provider=whisperx (only WhisperXProvider "
                "supports speaker diarization).",
                err=True,
            )
            raise typer.Exit(2)
        # mypy no sabe que el ASR es WhisperXProvider; el método existe.
        result = asr.transcribe_diarized(  # type: ignore[attr-defined]
            audio_path,
            language=lang,
            enrich_with_bible_refs=bible_refs,
        )
    else:
        result = asr.transcribe(audio_path, language=lang)

    payload: dict[str, object] = {
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                **({"speaker_id": s.speaker_id} if hasattr(s, "speaker_id") else {}),
                **(
                    {"bible_refs": [r.display() for r in s.bible_refs]}
                    if hasattr(s, "bible_refs") and getattr(s, "bible_refs", ())
                    else {}
                ),
            }
            for s in result.segments
        ],
    }
    if hasattr(result, "speaker_count"):
        payload["speaker_count"] = result.speaker_count

    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output.write_text(encoded, encoding="utf-8")
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(encoded)
