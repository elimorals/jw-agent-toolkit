"""F51 — round-trip tests for the `.jwlibrary` writer.

Build a synthetic userData.db, package it via `write_backup`, re-parse via
the existing parser, and verify hashes + counts. Also exercise the
`update_backup` callback path: extract → mutate → repack → re-read.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from jw_core.parsers.jw_library_backup import parse_jw_library_backup
from jw_core.writers.jw_library_backup import BackupWriteError, update_backup, write_backup


def _build_user_data_db(db_path: Path, *, with_last_modified: bool = True) -> None:
    """Synthesize a tiny but parser-compatible userData.db at `db_path`.

    Mirrors what the parser's own tests build internally. Sets `PRAGMA
    user_version=16` so the writer reports the modern schema number.
    """
    conn = sqlite3.connect(db_path)
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
            INSERT INTO Location VALUES (1, 43, 3, NULL, NULL, NULL, 'nwt', 0, 2, 'John 3');
            INSERT INTO Note VALUES (1, 'guid-1', NULL, 1, 'Test', 'body', '2026-06-02', '2026-06-02', 0, NULL);
            PRAGMA user_version = 16;
            """
        )
        if with_last_modified:
            conn.executescript(
                """
                CREATE TABLE LastModified (LastModified TEXT);
                INSERT INTO LastModified VALUES ('2020-01-01T00:00:00Z');
                """
            )
        conn.commit()
    finally:
        conn.close()


def test_write_backup_produces_parseable_archive(tmp_path: Path) -> None:
    db_path = tmp_path / "userData.db"
    _build_user_data_db(db_path)
    out = write_backup(tmp_path / "backup.jwlibrary", user_data_db_path=db_path)

    # Reads back through the existing parser.
    parsed = parse_jw_library_backup(out)
    assert parsed.manifest.schema_version == 16
    assert parsed.manifest.database_name == "userData.db"
    assert len(parsed.notes) == 1
    assert parsed.notes[0].title == "Test"


def test_write_backup_hash_matches_db(tmp_path: Path) -> None:
    db_path = tmp_path / "userData.db"
    _build_user_data_db(db_path)
    out = write_backup(tmp_path / "backup.jwlibrary", user_data_db_path=db_path)

    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        db_bytes = zf.read("userData.db")
    expected_hash = hashlib.sha256(db_bytes).hexdigest()
    assert manifest["userDataBackup"]["hash"] == expected_hash


def test_write_backup_stamps_last_modified(tmp_path: Path) -> None:
    """The LastModified table should be refreshed to the writer's timestamp."""
    db_path = tmp_path / "userData.db"
    _build_user_data_db(db_path, with_last_modified=True)
    out = write_backup(tmp_path / "backup.jwlibrary", user_data_db_path=db_path)

    # Reopen the embedded DB and check the LastModified row.
    with zipfile.ZipFile(out) as zf:
        db_bytes = zf.read("userData.db")
    extract_path = tmp_path / "extract.db"
    extract_path.write_bytes(db_bytes)
    conn = sqlite3.connect(extract_path)
    try:
        row = conn.execute("SELECT LastModified FROM LastModified").fetchone()
    finally:
        conn.close()
    assert row is not None
    # We can't know the exact instant, but it should NOT be the original 2020 stamp.
    assert row[0] != "2020-01-01T00:00:00Z"


def test_write_backup_handles_db_without_last_modified(tmp_path: Path) -> None:
    """No LastModified table = no crash; manifest still produced."""
    db_path = tmp_path / "userData.db"
    _build_user_data_db(db_path, with_last_modified=False)
    out = write_backup(tmp_path / "backup.jwlibrary", user_data_db_path=db_path)

    parsed = parse_jw_library_backup(out)
    assert parsed.manifest.schema_version == 16  # PRAGMA still works.


def test_update_backup_round_trip(tmp_path: Path) -> None:
    """Extract → modify → repack: a new note inserted via callback survives."""
    src_db = tmp_path / "userData.db"
    _build_user_data_db(src_db)
    src_archive = write_backup(tmp_path / "src.jwlibrary", user_data_db_path=src_db)

    def add_a_note(conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO Note (NoteId, Guid, LocationId, Title, Content, LastModified, Created, BlockType) "
            "VALUES (2, 'guid-2', 1, 'Second', 'second body', '2026-06-02', '2026-06-02', 0)"
        )

    dest = update_backup(src_archive, tmp_path / "dest.jwlibrary", modify_fn=add_a_note)
    parsed = parse_jw_library_backup(dest)
    titles = sorted(n.title for n in parsed.notes)
    assert titles == ["Second", "Test"]


def test_update_backup_without_callback_restamps_manifest(tmp_path: Path) -> None:
    src_db = tmp_path / "userData.db"
    _build_user_data_db(src_db)
    src_archive = write_backup(tmp_path / "src.jwlibrary", user_data_db_path=src_db, device_name="A")
    dest = update_backup(src_archive, tmp_path / "dest.jwlibrary", device_name="B")

    parsed = parse_jw_library_backup(dest)
    assert parsed.manifest.device_name == "B"


def test_write_backup_missing_db_raises(tmp_path: Path) -> None:
    with pytest.raises(BackupWriteError):
        write_backup(tmp_path / "out.jwlibrary", user_data_db_path=tmp_path / "nope.db")


def test_update_backup_missing_archive_raises(tmp_path: Path) -> None:
    with pytest.raises(BackupWriteError):
        update_backup(tmp_path / "nope.jwlibrary", tmp_path / "out.jwlibrary")


def test_update_backup_bad_zip_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jwlibrary"
    bad.write_bytes(b"not a zip")
    with pytest.raises(BackupWriteError):
        update_backup(bad, tmp_path / "out.jwlibrary")
