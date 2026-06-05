"""jw meeting CLI subcommands."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from jw_meeting_media.downloader import Downloader
from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MeetingKind
from jw_meeting_media.program_client import MeetingProgramClient
from jw_meeting_media.storage import MeetingStorage

app = typer.Typer(name="meeting", help="Reunión-en-vivo: discover / download / present")


def _default_cache_root() -> Path:
    return Path("~/.jw-agent-toolkit/meetings").expanduser()


@app.command("discover")
def discover(
    language: str = typer.Option(..., "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
    output: Path | None = typer.Option(None, "--output"),
    save: bool = typer.Option(True, "--save/--no-save"),
) -> None:
    """Descubre el programa semanal y opcionalmente lo guarda en sqlite local."""

    async def _run() -> None:
        client = MeetingProgramClient()
        program = await client.fetch_week(language=language, year=year, week=week, kind=kind)
        await client.aclose()
        if save:
            storage = MeetingStorage(_default_cache_root() / "meetings.db")
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
    language: str = typer.Option(..., "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
) -> None:
    """Descarga toda la media del programa para esa semana al cache local."""

    async def _run() -> None:
        storage = MeetingStorage(_default_cache_root() / "meetings.db")
        program = storage.load_program(language=language, year=year, week=week, kind=kind)
        if program is None:
            typer.echo("No program saved. Run 'discover' first.", err=True)
            raise typer.Exit(1)

        resolver = MediaResolver()
        dl = Downloader(cache_root=_default_cache_root() / "media")

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
                            resolved, language=language, year=year, week=week
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
def list_programs() -> None:
    """Lista programas guardados localmente."""
    storage_path = _default_cache_root() / "meetings.db"
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
