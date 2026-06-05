"""jw meeting CLI subcommands."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer

from jw_meeting_media.congregation import (
    Congregation,
    load_registry,
    remove_congregation,
    resolve_congregation,
    save_congregation,
)
from jw_meeting_media.downloader import Downloader
from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MeetingKind
from jw_meeting_media.program_client import MeetingProgramClient
from jw_meeting_media.storage import MeetingStorage

app = typer.Typer(name="meeting", help="Reunión-en-vivo: discover / download / present")
congregation_app = typer.Typer(
    name="congregation",
    help="Gestiona múltiples congregaciones (F57.16).",
)
app.add_typer(congregation_app, name="congregation")


def _meeting_home() -> Path:
    """Base directory shared by all congregations."""
    return Path(
        os.environ.get("JW_MEETING_HOME", "~/.jw-agent-toolkit/meetings")
    ).expanduser()


def _default_cache_root() -> Path:
    """Legacy single-cache root (kept for backwards compat / monkeypatching)."""
    return _meeting_home()


def _cache_root_for(congregation_name: str = "default") -> Path:
    """Cache root for a given congregation.

    For ``"default"`` (the implicit congregation when no registry exists)
    we return the legacy ``$JW_MEETING_HOME`` path directly so pre-F57.16
    installs keep finding their saved programs without migration. For any
    other congregation, we namespace under a per-congregation subdirectory.
    """
    base = _meeting_home()
    if congregation_name == "default":
        return base
    return base / congregation_name


# ── meeting commands ────────────────────────────────────────────────────


@app.command("discover")
def discover(
    language: str | None = typer.Option(None, "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
    output: Path | None = typer.Option(None, "--output"),
    save: bool = typer.Option(True, "--save/--no-save"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
) -> None:
    """Descubre el programa semanal y opcionalmente lo guarda en sqlite local."""

    try:
        cong = resolve_congregation(name=congregation)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    actual_language = language if language else cong.language

    async def _run() -> None:
        client = MeetingProgramClient()
        program = await client.fetch_week(
            language=actual_language, year=year, week=week, kind=kind
        )
        await client.aclose()
        if save:
            storage = MeetingStorage(_cache_root_for(cong.name) / "meetings.db")
            storage.save_program(program)
        payload = json.loads(program.model_dump_json())
        if output:
            output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            typer.echo(f"Wrote {output}")
        else:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))

    asyncio.run(_run())


@app.command("download")
def download(
    language: str | None = typer.Option(None, "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
) -> None:
    """Descarga toda la media del programa para esa semana al cache local."""

    try:
        cong = resolve_congregation(name=congregation)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    actual_language = language if language else cong.language
    cache_root = _cache_root_for(cong.name)

    async def _run() -> None:
        storage = MeetingStorage(cache_root / "meetings.db")
        program = storage.load_program(
            language=actual_language, year=year, week=week, kind=kind
        )
        if program is None:
            typer.echo("No program saved. Run 'discover' first.", err=True)
            raise typer.Exit(1)

        resolver = MediaResolver()
        dl = Downloader(cache_root=cache_root / "media")

        total = 0
        succeeded = 0
        for sec in program.sections:
            for item in sec.items:
                for ref in item.media_refs:
                    total += 1
                    try:
                        resolved = await resolver.resolve(ref)
                        if not resolved.url:
                            typer.echo(f"  - unresolved: {ref.title}", err=True)
                            continue
                        local = await dl.download(
                            resolved,
                            language=actual_language,
                            year=year,
                            week=week,
                        )
                        storage.mark_downloaded(resolved, local_path=local)
                        succeeded += 1
                        typer.echo(f"  + {ref.title} -> {local}")
                    except Exception as exc:
                        typer.echo(f"  - {ref.title}: {exc}", err=True)
        typer.echo(f"\nDone: {succeeded}/{total} media downloaded")
        await dl.aclose()

    asyncio.run(_run())


@app.command("list")
def list_programs(
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
) -> None:
    """Lista programas guardados localmente."""
    try:
        cong = resolve_congregation(name=congregation)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    storage_path = _cache_root_for(cong.name) / "meetings.db"
    if not storage_path.exists():
        typer.echo("No programs saved yet.")
        return
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(storage_path)) as conn:
        rows = conn.execute(
            "SELECT language, year, week, kind, saved_at FROM programs "
            "ORDER BY year DESC, week DESC"
        ).fetchall()
    for r in rows:
        typer.echo(f"  {r[1]}/{r[2]:02d} [{r[0]}] {r[3]} (saved {r[4][:10]})")


# ── congregation subcommands ────────────────────────────────────────────


@congregation_app.command("add")
def cli_cong_add(
    name: str = typer.Argument(..., help="Identificador (filesystem-safe)"),
    language: str = typer.Option(..., "--language", "-l"),
    notes: str = typer.Option("", "--notes"),
) -> None:
    """Registra una congregación nueva en el registry TOML."""
    save_congregation(Congregation(name=name, language=language, notes=notes))
    typer.echo(f"Added congregation: {name} ({language})")


@congregation_app.command("list")
def cli_cong_list() -> None:
    """Lista las congregaciones registradas."""
    registry = load_registry()
    if not registry:
        typer.echo(
            "No congregations registered. "
            "Add one with: jw meeting congregation add NAME --language es"
        )
        return
    for cong in registry.values():
        notes_tail = f" — {cong.notes}" if cong.notes else ""
        typer.echo(f"  {cong.name} [{cong.language}]{notes_tail}")


@congregation_app.command("remove")
def cli_cong_remove(
    name: str = typer.Argument(..., help="Nombre de la congregación a eliminar"),
) -> None:
    """Elimina una congregación del registry."""
    n = remove_congregation(name)
    if n:
        typer.echo(f"Removed: {name}")
    else:
        typer.echo(f"Not found: {name}", err=True)
        raise typer.Exit(1)


@congregation_app.command("default")
def cli_cong_default(
    congregation: str | None = typer.Option(None, "--congregation", "-c"),
) -> None:
    """Muestra qué congregación se resolvería por defecto.

    Útil para confirmar la selección automática cuando hay 0/1/N registradas.
    """
    try:
        cong = resolve_congregation(name=congregation)
    except (KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    notes_tail = f" — {cong.notes}" if cong.notes else ""
    typer.echo(f"{cong.name} [{cong.language}]{notes_tail}")
