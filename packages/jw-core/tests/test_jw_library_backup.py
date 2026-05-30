"""Tests for jw_core.parsers.jw_library_backup (Layer 2).

We synthesise a `.jwlibrary` archive on the fly using the documented v14
schema. The tests assert (a) the happy-path projection across all tables,
(b) graceful degradation when columns or whole tables are missing, and
(c) defensive handling of bad ZIPs / bad manifests.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from jw_core.parsers.jw_library_backup import (
    JWLibraryBackupError,
    notes_for_chapter,
    parse_jw_library_backup,
)


# ── Fixture: build a backup archive from a dict spec ────────────────────


def _build_backup(
    tmp_path: Path,
    *,
    manifest: dict | None = None,
    locations: list[dict] | None = None,
    notes: list[dict] | None = None,
    user_marks: list[dict] | None = None,
    block_ranges: list[dict] | None = None,
    bookmarks: list[dict] | None = None,
    tags: list[dict] | None = None,
    tag_maps: list[dict] | None = None,
    input_fields: list[dict] | None = None,
    skip_tables: set[str] | None = None,
    db_name: str = "userData.db",
) -> Path:
    skip = skip_tables or set()
    db_path = tmp_path / db_name
    conn = sqlite3.connect(db_path)
    try:
        if "Location" not in skip:
            conn.execute(
                """
                CREATE TABLE Location (
                    LocationId INTEGER PRIMARY KEY,
                    BookNumber INTEGER,
                    ChapterNumber INTEGER,
                    DocumentId INTEGER,
                    Track INTEGER,
                    IssueTagNumber INTEGER,
                    KeySymbol TEXT,
                    MepsLanguage INTEGER,
                    Type INTEGER,
                    Title TEXT
                )
                """
            )
            for loc in locations or []:
                conn.execute(
                    "INSERT INTO Location VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [
                        loc.get("LocationId"),
                        loc.get("BookNumber"),
                        loc.get("ChapterNumber"),
                        loc.get("DocumentId"),
                        loc.get("Track"),
                        loc.get("IssueTagNumber"),
                        loc.get("KeySymbol"),
                        loc.get("MepsLanguage"),
                        loc.get("Type"),
                        loc.get("Title"),
                    ],
                )
        if "UserMark" not in skip:
            conn.execute(
                """
                CREATE TABLE UserMark (
                    UserMarkId INTEGER PRIMARY KEY,
                    ColorIndex INTEGER,
                    LocationId INTEGER,
                    StyleIndex INTEGER,
                    UserMarkGuid TEXT,
                    Version INTEGER
                )
                """
            )
            for m in user_marks or []:
                conn.execute(
                    "INSERT INTO UserMark VALUES (?,?,?,?,?,?)",
                    [
                        m.get("UserMarkId"),
                        m.get("ColorIndex", 0),
                        m.get("LocationId"),
                        m.get("StyleIndex", 0),
                        m.get("UserMarkGuid", ""),
                        m.get("Version", 1),
                    ],
                )
        if "BlockRange" not in skip:
            conn.execute(
                """
                CREATE TABLE BlockRange (
                    BlockRangeId INTEGER PRIMARY KEY,
                    BlockType INTEGER,
                    Identifier INTEGER,
                    StartToken INTEGER,
                    EndToken INTEGER,
                    UserMarkId INTEGER
                )
                """
            )
            for br in block_ranges or []:
                conn.execute(
                    "INSERT INTO BlockRange VALUES (?,?,?,?,?,?)",
                    [
                        br.get("BlockRangeId"),
                        br.get("BlockType"),
                        br.get("Identifier"),
                        br.get("StartToken"),
                        br.get("EndToken"),
                        br.get("UserMarkId"),
                    ],
                )
        if "Note" not in skip:
            conn.execute(
                """
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
                )
                """
            )
            for n in notes or []:
                conn.execute(
                    "INSERT INTO Note VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [
                        n.get("NoteId"),
                        n.get("Guid", ""),
                        n.get("UserMarkId"),
                        n.get("LocationId"),
                        n.get("Title", ""),
                        n.get("Content", ""),
                        n.get("LastModified", ""),
                        n.get("Created", ""),
                        n.get("BlockType"),
                        n.get("BlockIdentifier"),
                    ],
                )
        if "Bookmark" not in skip:
            conn.execute(
                """
                CREATE TABLE Bookmark (
                    BookmarkId INTEGER PRIMARY KEY,
                    LocationId INTEGER,
                    PublicationLocationId INTEGER,
                    Slot INTEGER,
                    Title TEXT,
                    Snippet TEXT,
                    BlockType INTEGER,
                    BlockIdentifier INTEGER
                )
                """
            )
            for b in bookmarks or []:
                conn.execute(
                    "INSERT INTO Bookmark VALUES (?,?,?,?,?,?,?,?)",
                    [
                        b.get("BookmarkId"),
                        b.get("LocationId"),
                        b.get("PublicationLocationId"),
                        b.get("Slot", 0),
                        b.get("Title", ""),
                        b.get("Snippet", ""),
                        b.get("BlockType"),
                        b.get("BlockIdentifier"),
                    ],
                )
        if "Tag" not in skip:
            conn.execute(
                "CREATE TABLE Tag (TagId INTEGER PRIMARY KEY, Type INTEGER, Name TEXT)"
            )
            for t in tags or []:
                conn.execute(
                    "INSERT INTO Tag VALUES (?,?,?)",
                    [t.get("TagId"), t.get("Type", 1), t.get("Name", "")],
                )
        if "TagMap" not in skip:
            conn.execute(
                """
                CREATE TABLE TagMap (
                    TagMapId INTEGER PRIMARY KEY,
                    PlaylistItemId INTEGER,
                    LocationId INTEGER,
                    NoteId INTEGER,
                    TagId INTEGER,
                    Position INTEGER
                )
                """
            )
            for tm in tag_maps or []:
                conn.execute(
                    "INSERT INTO TagMap VALUES (?,?,?,?,?,?)",
                    [
                        tm.get("TagMapId"),
                        tm.get("PlaylistItemId"),
                        tm.get("LocationId"),
                        tm.get("NoteId"),
                        tm.get("TagId"),
                        tm.get("Position", 0),
                    ],
                )
        if "InputField" not in skip:
            conn.execute(
                """
                CREATE TABLE InputField (
                    LocationId INTEGER,
                    TextTag TEXT,
                    Value TEXT
                )
                """
            )
            for f in input_fields or []:
                conn.execute(
                    "INSERT INTO InputField VALUES (?,?,?)",
                    [f.get("LocationId"), f.get("TextTag", ""), f.get("Value", "")],
                )
        conn.commit()
    finally:
        conn.close()

    manifest_obj = manifest or {
        "name": "UserDataBackup_test.jwlibrary",
        "creationDate": "2024-11-15",
        "version": 1,
        "type": 0,
        "hash": "deadbeef",
        "userDataBackup": {
            "lastModifiedDate": "2024-11-15T20:00:00+00:00",
            "deviceName": "Test Device",
            "databaseName": db_name,
            "hash": "deadbeef",
            "schemaVersion": 14,
        },
    }

    archive = tmp_path / "test.jwlibrary"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest_obj))
        zf.write(db_path, db_name)
    db_path.unlink()
    return archive


# ── Manifest ─────────────────────────────────────────────────────────────


def test_parses_manifest_fields(tmp_path: Path) -> None:
    archive = _build_backup(tmp_path)
    backup = parse_jw_library_backup(archive)
    assert backup.manifest.name == "UserDataBackup_test.jwlibrary"
    assert backup.manifest.creation_date == "2024-11-15"
    assert backup.manifest.device_name == "Test Device"
    assert backup.manifest.schema_version == 14
    assert backup.manifest.hash == "deadbeef"


def test_manifest_preserves_unknown_fields(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        manifest={
            "name": "x.jwlibrary",
            "creationDate": "2024-12-01",
            "version": 1,
            "type": 0,
            "hash": "h",
            "userDataBackup": {"databaseName": "userData.db"},
            "futureField": {"v": 42},
        },
    )
    backup = parse_jw_library_backup(archive)
    assert backup.manifest.extra == {"futureField": {"v": 42}}


def test_missing_manifest_raises(tmp_path: Path) -> None:
    archive = tmp_path / "broken.jwlibrary"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nothing.txt", "x")
    with pytest.raises(JWLibraryBackupError, match="manifest"):
        parse_jw_library_backup(archive)


def test_non_zip_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "plain.jwlibrary"
    bogus.write_bytes(b"not a zip")
    with pytest.raises(JWLibraryBackupError, match="ZIP"):
        parse_jw_library_backup(bogus)


def test_nonexistent_path_raises(tmp_path: Path) -> None:
    with pytest.raises(JWLibraryBackupError, match="not found"):
        parse_jw_library_backup(tmp_path / "missing.jwlibrary")


# ── Locations ────────────────────────────────────────────────────────────


def test_locations_parsed(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[
            {
                "LocationId": 1,
                "BookNumber": 43,
                "ChapterNumber": 3,
                "KeySymbol": "nwtsty",
                "MepsLanguage": 0,
                "Type": 2,
                "Title": "John 3",
            },
            {
                "LocationId": 2,
                "DocumentId": 1102021201,
                "KeySymbol": "w24",
                "IssueTagNumber": 20240401,
                "Type": 0,
                "Title": "Watchtower 2024/04 Article 1",
            },
        ],
    )
    backup = parse_jw_library_backup(archive)
    assert backup.counts["locations"] == 2
    bible_loc = next(loc for loc in backup.locations if loc.is_bible)
    assert bible_loc.book_number == 43
    pub_loc = next(loc for loc in backup.locations if not loc.is_bible)
    assert pub_loc.document_id == 1102021201
    assert pub_loc.key_symbol == "w24"


# ── Notes ────────────────────────────────────────────────────────────────


def test_notes_joined_with_location_and_tags(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 10,
                "Guid": "g-1",
                "LocationId": 1,
                "Title": "El amor de Dios",
                "Content": "Juan 3:16 enseña…",
                "LastModified": "2024-11-15T20:00:00",
                "Created": "2024-11-10T10:00:00",
            }
        ],
        tags=[{"TagId": 1, "Type": 1, "Name": "Favorito"}, {"TagId": 2, "Type": 1, "Name": "Sermón"}],
        tag_maps=[
            {"TagMapId": 1, "NoteId": 10, "TagId": 1, "Position": 0},
            {"TagMapId": 2, "NoteId": 10, "TagId": 2, "Position": 1},
        ],
    )
    backup = parse_jw_library_backup(archive)
    assert len(backup.notes) == 1
    note = backup.notes[0]
    assert note.title == "El amor de Dios"
    assert note.location is not None
    assert note.location.book_number == 43
    assert sorted(note.tags) == ["Favorito", "Sermón"]


def test_notes_for_chapter_filter(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[
            {"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2},
            {"LocationId": 2, "BookNumber": 43, "ChapterNumber": 4, "Type": 2},
        ],
        notes=[
            {"NoteId": 1, "LocationId": 1, "Title": "n1"},
            {"NoteId": 2, "LocationId": 2, "Title": "n2"},
            {"NoteId": 3, "LocationId": 1, "Title": "n3"},
        ],
    )
    backup = parse_jw_library_backup(archive)
    matches = notes_for_chapter(backup, book_num=43, chapter=3)
    assert {n.title for n in matches} == {"n1", "n3"}


def test_orphan_note_kept_with_no_location(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        # LocationId 99 points nowhere — note keeps location=None.
        notes=[{"NoteId": 1, "LocationId": 99, "Title": "orphan"}],
    )
    backup = parse_jw_library_backup(archive)
    assert backup.notes[0].location is None


# ── Highlights ───────────────────────────────────────────────────────────


def test_highlights_with_block_ranges(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        user_marks=[
            {
                "UserMarkId": 100,
                "ColorIndex": 4,
                "LocationId": 1,
                "StyleIndex": 1,
                "UserMarkGuid": "guid-100",
            }
        ],
        block_ranges=[
            {"BlockRangeId": 1, "BlockType": 1, "Identifier": 16, "StartToken": 0, "EndToken": 5, "UserMarkId": 100},
            {"BlockRangeId": 2, "BlockType": 1, "Identifier": 16, "StartToken": 6, "EndToken": 10, "UserMarkId": 100},
        ],
    )
    backup = parse_jw_library_backup(archive)
    assert len(backup.highlights) == 1
    h = backup.highlights[0]
    assert h.color_index == 4
    assert h.location.book_number == 43
    assert len(h.block_ranges) == 2
    assert h.block_ranges[0]["start_token"] == 0


def test_highlight_orphan_location_skipped(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        user_marks=[{"UserMarkId": 1, "LocationId": 999}],
    )
    backup = parse_jw_library_backup(archive)
    assert backup.highlights == []


# ── Bookmarks ────────────────────────────────────────────────────────────


def test_bookmarks_parsed(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        bookmarks=[
            {
                "BookmarkId": 1,
                "LocationId": 1,
                "Slot": 0,
                "Title": "Juan 3:16",
                "Snippet": "Porque tanto amó Dios…",
            }
        ],
    )
    backup = parse_jw_library_backup(archive)
    assert len(backup.bookmarks) == 1
    bm = backup.bookmarks[0]
    assert bm.title == "Juan 3:16"
    assert bm.location.chapter_number == 3


# ── Input fields ─────────────────────────────────────────────────────────


def test_input_fields_with_location(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 5, "KeySymbol": "mwb24.04", "Type": 0}],
        input_fields=[{"LocationId": 5, "TextTag": "q1", "Value": "Respuesta del estudiante"}],
    )
    backup = parse_jw_library_backup(archive)
    assert len(backup.input_fields) == 1
    f = backup.input_fields[0]
    assert f.value == "Respuesta del estudiante"
    assert f.location.key_symbol == "mwb24.04"


# ── Schema resilience ────────────────────────────────────────────────────


def test_missing_optional_tables_returns_empty_lists(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        skip_tables={"Note", "Bookmark", "InputField", "BlockRange"},
        locations=[{"LocationId": 1, "BookNumber": 1, "ChapterNumber": 1}],
    )
    backup = parse_jw_library_backup(archive)
    assert backup.counts["locations"] == 1
    assert backup.counts["notes"] == 0
    assert backup.counts["bookmarks"] == 0
    assert backup.counts["input_fields"] == 0


def test_empty_database_parses_without_errors(tmp_path: Path) -> None:
    archive = _build_backup(tmp_path)
    backup = parse_jw_library_backup(archive)
    assert all(v == 0 for v in backup.counts.values())


def test_counts_property_exposed(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 1, "ChapterNumber": 1}],
        notes=[{"NoteId": 1, "LocationId": 1}],
    )
    backup = parse_jw_library_backup(archive)
    assert backup.counts == {
        "locations": 1,
        "notes": 1,
        "highlights": 0,
        "bookmarks": 0,
        "tags": 0,
        "input_fields": 0,
    }
