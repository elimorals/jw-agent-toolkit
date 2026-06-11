"""``jw voiceclone`` - consented family-voice TTS (Fase 76).

The training wizard is NOT exposed via MCP. CLI registers a
non-interactive variant for testing; the real wizard belongs to a
separate UI surface.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jw_core.audio.voice_clone.license_gate import LicenseGateError
from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    TrainingSample,
    VoiceProfile,
)
from jw_core.audio.voice_clone.registry import (
    VoiceNotFoundError,
    delete_voice,
    get_voice,
    list_voices,
    register,
    revoke_consent,
)
from jw_core.audio.voice_clone.synthesizer import synthesize_with_voice

voiceclone_app = typer.Typer(
    help="TTS con voz familiar consentida (Fase 76).",
    no_args_is_help=True,
)
console = Console()


@voiceclone_app.command("register-from-consent")
def cmd_register_from_consent(
    name: str = typer.Argument(..., help="Voice name (deny list applies)."),
    consent_file: str = typer.Option(
        ..., "--consent-file", help="Path to consent.json"
    ),
    weights_path: str = typer.Option(
        "/tmp/fake.bin",
        "--weights-path",
        help="Path to the trained weights (provider-dependent).",
    ),
    provider: str = typer.Option(
        "fake", "--provider", help="fake | f5tts | xttsv2"
    ),
) -> None:
    """Register a voice from an existing consent.json + weights.

    The full training wizard is intentionally NOT here — that surface
    captures mic input and live consent. This command is for
    importing already-trained profiles.
    """

    consent_dict = json.loads(Path(consent_file).expanduser().read_text())
    consent = ConsentRecord(**consent_dict)
    profile = VoiceProfile(
        name=name,
        provider=provider,  # type: ignore[arg-type]
        consent=consent,
        weights_path=weights_path,
        created_at=datetime.now(UTC),
    )
    register(profile)
    console.print(f"[green]registered:[/] {name}")


@voiceclone_app.command("list")
def cmd_list() -> None:
    """List registered voices."""

    table = Table(title="Registered voices")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("License")
    table.add_column("Consent revoked?")
    table.add_column("Uses")
    for v in list_voices():
        table.add_row(
            v.name,
            v.provider,
            v.license,
            "yes" if v.consent.revoked else "no",
            str(v.use_count),
        )
    console.print(table)


@voiceclone_app.command("show")
def cmd_show(
    name: str = typer.Argument(...),
) -> None:
    """Show a voice profile JSON."""

    try:
        profile = get_voice(name)
    except VoiceNotFoundError:
        console.print(f"[red]not found:[/] {name}")
        raise typer.Exit(code=1)
    console.print_json(profile.model_dump_json())


@voiceclone_app.command("revoke")
def cmd_revoke(
    name: str = typer.Argument(...),
    reason: str = typer.Option(
        "", "--reason", help="Optional reason recorded with the revocation."
    ),
) -> None:
    """Mark a voice profile's consent as revoked."""

    try:
        revoke_consent(name, reason=reason or None)
        console.print(f"[yellow]revoked:[/] {name}")
    except VoiceNotFoundError:
        console.print(f"[red]not found:[/] {name}")
        raise typer.Exit(code=1)


@voiceclone_app.command("delete")
def cmd_delete(
    name: str = typer.Argument(...),
    confirm: bool = typer.Option(
        False, "--confirm", help="Required to actually delete."
    ),
) -> None:
    """Delete a voice profile (consent + metadata; weights stay on disk)."""

    if not confirm:
        console.print(
            "[yellow]error:[/] pass --confirm to delete the profile."
        )
        raise typer.Exit(code=1)
    try:
        delete_voice(name)
    except VoiceNotFoundError:
        console.print(f"[red]not found:[/] {name}")
        raise typer.Exit(code=1)
    console.print(f"[dim]deleted:[/] {name}")


@voiceclone_app.command("say")
def cmd_say(
    name: str = typer.Argument(...),
    text: str = typer.Argument(...),
    output: str = typer.Option(
        ..., "--output", "-o", help="Output WAV path."
    ),
) -> None:
    """Synthesize `text` with voice `name` into the output path."""

    try:
        out = synthesize_with_voice(name, text, output)
    except VoiceNotFoundError:
        console.print(f"[red]not found:[/] {name}")
        raise typer.Exit(code=1)
    except LicenseGateError as exc:
        console.print(f"[red]license gate:[/] {exc}")
        raise typer.Exit(code=2)
    console.print(f"[green]wrote:[/] {out}")
