"""``jw spar`` - conversation sparring with simulated interlocutors (Fase 66).

CLI surface for `jw_agents.spar`:
  - `jw spar personas` - list the 6 builtin personas
  - `jw spar start --persona catholic` - open a new session, prints session_id
  - `jw spar turn <sid> "<text>"` - send one user turn, prints persona reply
  - `jw spar show <sid>` - dump the session JSON
  - `jw spar close <sid>` - close the session and produce feedback
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from jw_agents.spar.feedback import score_session
from jw_agents.spar.personas import list_personas
from jw_agents.spar.session import (
    close_session,
    get_session,
    start_session,
    take_turn,
)
from jw_agents.spar.simulator import FakeSparLLM

spar_app = typer.Typer(
    help="Sparring conversacional (Fase 66).",
    no_args_is_help=True,
)

console = Console()


def _build_llm() -> Any:
    """Resolve the LLM provider from JW_SPAR_LLM (defaults to fake).

    Real Claude / Ollama bindings are wired in F65's llm_factory; here we
    reuse that adapter so the same env conventions apply. Any failure
    degrades to FakeSparLLM with a warning so the CLI never crashes.
    """

    backend = os.environ.get("JW_SPAR_LLM", "fake").lower()
    if backend in ("", "fake"):
        return FakeSparLLM()
    try:
        from jw_agents.meta.llm_factory import build_llm_from_env

        # F65's factory reads JW_META_LLM. We bridge JW_SPAR_LLM -> JW_META_LLM
        # in-process so the same providers are reachable.
        os.environ.setdefault("JW_META_LLM", backend)
        return build_llm_from_env()
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[yellow]spar: LLM backend {backend!r} unavailable ({exc}); "
            "using fake.[/]"
        )
        return FakeSparLLM()


@spar_app.command("personas")
def cmd_personas() -> None:
    """List the 6 builtin personas."""

    table = Table(title="Spar personas (builtin)")
    table.add_column("Key")
    table.add_column("Display name")
    table.add_column("Lang")
    table.add_column("Tone")
    for p in list_personas():
        table.add_row(p.key, p.display_name, p.language, p.tone)
    console.print(table)


@spar_app.command("start")
def cmd_start(
    persona: str = typer.Option(..., "--persona", "-p"),
    language: str = typer.Option("es", "--language", "-l"),
) -> None:
    """Start a new sparring session. Prints the new session_id."""

    session = start_session(persona_key=persona, language=language)
    console.print(
        f"[green]session started[/]: {session.session_id} "
        f"(persona={persona}, lang={language})"
    )
    console.print(
        "[dim]PRACTICA - esto NO es una visita real. Sin guardado remoto.[/]"
    )


@spar_app.command("turn")
def cmd_turn(
    session_id: str = typer.Argument(...),
    text: str = typer.Argument(..., help="User turn text"),
) -> None:
    """Send one user turn and print the persona's reply."""

    llm = _build_llm()
    response = asyncio.run(
        take_turn(session_id=session_id, user_text=text, llm=llm)
    )
    console.print_json(response.model_dump_json())


@spar_app.command("show")
def cmd_show(
    session_id: str = typer.Argument(...),
    export_md: str | None = typer.Option(
        None,
        "--export",
        help="Write the transcript as Markdown to this path instead of JSON.",
    ),
) -> None:
    """Dump the current SparSession state (JSON or Markdown via --export)."""

    from pathlib import Path

    from jw_agents.spar.export import to_markdown

    session = get_session(session_id)
    if export_md:
        out = Path(export_md).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(session))
        console.print(f"[dim]transcript saved to[/] {out}")
        return
    console.print_json(session.model_dump_json())


@spar_app.command("close")
def cmd_close(
    session_id: str = typer.Argument(...),
    no_feedback: bool = typer.Option(
        False, "--no-feedback", help="Skip post-session feedback."
    ),
    export_md: str | None = typer.Option(
        None,
        "--export",
        help="Also write the transcript as Markdown to this path.",
    ),
) -> None:
    """Close a session and produce formative feedback (citation_quality + NLI)."""

    from pathlib import Path

    from jw_agents.spar.export import to_markdown

    session = close_session(session_id=session_id)
    if not no_feedback:
        score_session(session)
    console.print_json(session.model_dump_json())
    if export_md:
        out = Path(export_md).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(session))
        console.print(f"[dim]transcript saved to[/] {out}")


@spar_app.command("voice-turn")
def cmd_voice_turn(
    session_id: str = typer.Argument(...),
    audio_in: str = typer.Option(
        ..., "--audio-in", "-i", help="WAV/MP3/M4A/FLAC user turn audio."
    ),
    audio_out: str = typer.Option(
        ..., "--audio-out", "-o", help="Output path for persona reply audio."
    ),
    asr_model: str = typer.Option(
        "base",
        "--asr-model",
        help="Whisper model size: tiny|base|small|medium|large-v3|auto.",
    ),
    tts_voice: str | None = typer.Option(
        None, "--tts-voice", help="Voice id (provider-dependent)."
    ),
    tts_provider: str | None = typer.Option(
        None,
        "--tts-provider",
        help="kokoro|edge|piper|system (auto-select if omitted).",
    ),
) -> None:
    """One voice turn: ASR your audio -> persona LLM reply -> TTS output."""

    import asyncio

    from jw_agents.spar.voice import VoiceModeError, take_voice_turn

    llm = _build_llm()
    try:
        user_text, response, out_path = asyncio.run(
            take_voice_turn(
                session_id=session_id,
                audio_in_path=audio_in,
                audio_out_path=audio_out,
                llm=llm,
                asr_model_size=asr_model,
                tts_voice=tts_voice,
                tts_provider=tts_provider,
            )
        )
    except VoiceModeError as exc:
        console.print(f"[red]voice-turn failed:[/] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        {
            "user_text": user_text,
            "reply": response.reply,
            "audio_out": str(out_path),
        }
    )
