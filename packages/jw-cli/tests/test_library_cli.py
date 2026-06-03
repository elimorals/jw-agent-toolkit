"""F54.3 — tests for `jw library` CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.library import library_app


def test_from_notes_builds_parseable_backup(tmp_path: Path) -> None:
    """Agent writes notes JSON → CLI builds .jwlibrary → parser reads it back."""
    notes = [
        {
            "title": "Reflection on John 3:16",
            "content": "God's love for humanity.",
            "key_symbol": "nwt",
            "book_number": 43,
            "chapter_number": 3,
            "meps_language": 0,
        },
        {
            "title": "On creation",
            "content": "Genesis 1 shows the order of creation.",
            "key_symbol": "nwt",
            "book_number": 1,
            "chapter_number": 1,
            "meps_language": 0,
        },
    ]
    notes_path = tmp_path / "notes.json"
    notes_path.write_text(json.dumps(notes))
    out_path = tmp_path / "out.jwlibrary"

    runner = CliRunner()
    result = runner.invoke(library_app, ["from-notes", str(out_path), "--notes", str(notes_path)])
    assert result.exit_code == 0, result.output
    assert out_path.is_file()

    from jw_core.parsers.jw_library_backup import parse_jw_library_backup

    parsed = parse_jw_library_backup(out_path)
    assert len(parsed.notes) == 2
    titles = sorted(n.title for n in parsed.notes)
    assert titles == ["On creation", "Reflection on John 3:16"]


def test_inspect_summarizes_archive(tmp_path: Path) -> None:
    """`jw library inspect` reports counts from a freshly-built backup."""
    notes_path = tmp_path / "notes.json"
    notes_path.write_text(json.dumps([{"title": "x", "content": "y", "key_symbol": "nwt", "book_number": 43, "chapter_number": 3}]))
    archive = tmp_path / "lib.jwlibrary"

    runner = CliRunner()
    runner.invoke(library_app, ["from-notes", str(archive), "--notes", str(notes_path)])
    result = runner.invoke(library_app, ["inspect", str(archive)])
    assert result.exit_code == 0
    assert "notes 1" in result.output


def test_re_export_with_script_modifies_backup(tmp_path: Path) -> None:
    """Run a user-supplied `modify(conn)` script during re-export."""
    notes_path = tmp_path / "notes.json"
    notes_path.write_text(json.dumps([{"title": "Original", "content": "x", "key_symbol": "nwt", "book_number": 43, "chapter_number": 3}]))
    src = tmp_path / "src.jwlibrary"
    dest = tmp_path / "dest.jwlibrary"
    runner = CliRunner()
    runner.invoke(library_app, ["from-notes", str(src), "--notes", str(notes_path)])

    script = tmp_path / "modify.py"
    script.write_text(
        "def modify(conn):\n"
        "    conn.execute('UPDATE Note SET Title = ? WHERE NoteId = 1', ('Modified',))\n"
    )
    result = runner.invoke(library_app, ["re-export", str(src), str(dest), "--script", str(script)])
    assert result.exit_code == 0, result.output

    from jw_core.parsers.jw_library_backup import parse_jw_library_backup

    parsed = parse_jw_library_backup(dest)
    assert parsed.notes[0].title == "Modified"
