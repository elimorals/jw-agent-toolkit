"""`jw library` — export/import `.jwlibrary` backups (F54.3).

Two ways to author a backup:

  - `jw library re-export <src.jwlibrary> <dest.jwlibrary>` —
    open an existing backup, optionally let an agent edit it via
    `--script <python_file>`, then write a new one. This is the round-trip
    case (extract → modify → repack) and uses `writers.jw_library_backup`.

  - `jw library export-empty <out.jwlibrary>` —
    build a brand-new backup from scratch with no notes/highlights. Useful
    as a starting template for agents that add notes programmatically.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import typer
from jw_core.parsers.jw_library_backup import parse_jw_library_backup
from jw_core.writers.jw_library_backup import BackupWriteError, update_backup, write_backup
from rich.console import Console

library_app = typer.Typer(help="Export/import JW Library backups (.jwlibrary).")
console = Console()


@library_app.command("inspect")
def inspect(
    archive: Path = typer.Argument(..., exists=True, help="Existing .jwlibrary archive."),
) -> None:
    """Print a summary of a `.jwlibrary` archive (notes/highlights/bookmarks counts)."""
    parsed = parse_jw_library_backup(archive)
    console.print(f"[bold]name[/bold] {parsed.manifest.name}")
    console.print(f"[bold]device[/bold] {parsed.manifest.device_name}")
    console.print(f"[bold]schema[/bold] v{parsed.manifest.schema_version}")
    console.print(f"[bold]locations[/bold] {len(parsed.locations)}")
    console.print(f"[bold]notes[/bold] {len(parsed.notes)}")
    console.print(f"[bold]highlights[/bold] {len(parsed.highlights)}")
    console.print(f"[bold]bookmarks[/bold] {len(parsed.bookmarks)}")
    console.print(f"[bold]tags[/bold] {len(parsed.tags)}")


@library_app.command("re-export")
def re_export(
    src: Path = typer.Argument(..., exists=True, help="Source .jwlibrary archive."),
    dest: Path = typer.Argument(..., help="Destination .jwlibrary archive."),
    device_name: str | None = typer.Option(
        None,
        "--device",
        help="Device name stamped into the new manifest.",
    ),
    script: Path | None = typer.Option(
        None,
        "--script",
        help="Optional Python file with a `modify(conn)` function that mutates the userData.db.",
    ),
) -> None:
    """Read a `.jwlibrary`, optionally modify via a script, write a fresh archive."""
    modify_fn = None
    if script:
        modify_fn = _load_modify_fn(script)
    try:
        out = update_backup(src, dest, modify_fn=modify_fn, device_name=device_name)
    except BackupWriteError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Wrote[/green] {out}")


@library_app.command("from-notes")
def from_notes(
    out: Path = typer.Argument(..., help="Destination .jwlibrary archive."),
    notes_json: Path = typer.Option(
        ...,
        "--notes",
        exists=True,
        help="JSON file with a list of {title, content, key_symbol, doc_id, lang} objects.",
    ),
    device_name: str = typer.Option("jw-core-agent", "--device", help="Device stamp."),
) -> None:
    """Build a `.jwlibrary` from a JSON list of notes.

    This is the "agent writes notes → user imports into JW Library" flow.
    JSON shape per item:

        {
          "title": "Reflection on John 3:16",
          "content": "...",
          "key_symbol": "nwt",
          "doc_id": 0,                  // or null for chapter-level
          "book_number": 43,            // for Bible locations
          "chapter_number": 3,
          "meps_language": 0
        }
    """
    import json
    import tempfile

    items = json.loads(notes_json.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        console.print("[red]--notes JSON must be a list of note objects.[/red]")
        raise typer.Exit(code=1)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "userData.db"
        _build_userdata_db(db_path, items)
        try:
            written = write_backup(out, user_data_db_path=db_path, device_name=device_name)
        except BackupWriteError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    console.print(f"[green]Wrote[/green] {written} ({len(items)} notes)")


# ── helpers ─────────────────────────────────────────────────────────────


def _load_modify_fn(script: Path):  # type: ignore[no-untyped-def]
    """Load a Python file that exposes `modify(conn: sqlite3.Connection)`."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("user_modify", script)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"could not load {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "modify", None)
    if not callable(fn):
        raise typer.BadParameter(f"{script} must define `def modify(conn): ...`")
    return fn


def _build_userdata_db(path: Path, notes: list[dict]) -> None:
    """Construct a minimal userData.db schema-v16 holding `notes`.

    Mirrors the v14+ shape the parser accepts. Skips tables the agent doesn't
    touch (TagMap, Bookmark, etc.) — the parser is tolerant of missing tables.
    """
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE Location (
                LocationId INTEGER PRIMARY KEY,
                BookNumber INTEGER, ChapterNumber INTEGER,
                DocumentId INTEGER, Track INTEGER,
                IssueTagNumber INTEGER, KeySymbol TEXT,
                MepsLanguage INTEGER, Type INTEGER, Title TEXT
            );
            CREATE TABLE Note (
                NoteId INTEGER PRIMARY KEY,
                Guid TEXT,
                UserMarkId INTEGER,
                LocationId INTEGER,
                Title TEXT,
                Content TEXT,
                LastModified TEXT,
                Created TEXT,
                BlockType INTEGER,
                BlockIdentifier INTEGER
            );
            CREATE TABLE LastModified (LastModified TEXT);
            INSERT INTO LastModified VALUES (datetime('now'));
            PRAGMA user_version = 16;
            """
        )
        for i, note in enumerate(notes, start=1):
            loc_type = 2 if note.get("book_number") else 0  # 2 = Bible, 0 = publication
            conn.execute(
                "INSERT INTO Location VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    i,
                    note.get("book_number"),
                    note.get("chapter_number"),
                    note.get("doc_id"),
                    None,
                    note.get("issue_tag_number"),
                    note.get("key_symbol", ""),
                    note.get("meps_language", 0),
                    loc_type,
                    note.get("location_title", note.get("title", "")),
                ),
            )
            conn.execute(
                "INSERT INTO Note (NoteId, Guid, LocationId, Title, Content, LastModified, Created, BlockType) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?)",
                (
                    i,
                    f"jw-core-{i:04d}",
                    i,
                    note["title"],
                    note["content"],
                    0,
                ),
            )
        conn.commit()
    finally:
        conn.close()
