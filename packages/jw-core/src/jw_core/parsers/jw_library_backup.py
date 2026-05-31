"""Parser for `.jwlibrary` backup archives (user data only).

A `.jwlibrary` file is a ZIP that the official app produces when the user
hits "Export Backup". It contains:

    manifest.json   — backup metadata (creation date, device, schema version)
    userData.db     — SQLite with the user's notes, marks, bookmarks, tags

It does **not** contain any publication text — only references into
publications the user has installed. The schema evolves between JW Library
versions; we read it defensively (PRAGMA table_info → skip missing columns,
fall back on missing tables).

Read-only: this parser never writes to a backup or to the live app DB.
Mutating the live `userData.db` while the app is running corrupts the cloud
sync. We expose the result so callers can ingest it into their own stores.

Schema reference (community-documented for JW Library v12-14):

    Location      — addresses (Bible verse OR publication+paragraph)
    UserMark      — a colored highlight pointing at a Location
    BlockRange    — character offsets inside the marked block
    Note          — title + body attached to a UserMark or Location
    Bookmark      — quick-jump entry in the user's Bookmarks panel
    Tag           — user-defined label (also includes built-in "Favorite")
    TagMap        — many-to-many between Tags and (Notes | Locations)
    InputField    — answers typed into publication form fields (workbook, etc.)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

__all__ = [
    "BackupContents",
    "BackupManifest",
    "Bookmark",
    "InputField",
    "JWLibraryBackupError",
    "Location",
    "Tag",
    "UserHighlight",
    "UserNote",
    "notes_for_chapter",
    "parse_jw_library_backup",
    "parse_user_data_db",
]


class JWLibraryBackupError(RuntimeError):
    """Raised when a `.jwlibrary` archive can't be parsed."""


# ── Models ───────────────────────────────────────────────────────────────


class BackupManifest(BaseModel):
    """Metadata from the archive's `manifest.json`.

    All fields are optional because the manifest layout has shifted between
    JW Library releases; the parser keeps whatever it finds and surfaces
    the unknown keys under `extra` for inspection.
    """

    name: str = ""
    creation_date: str = ""
    device_name: str = ""
    schema_version: int | None = None
    last_modified_date: str = ""
    database_name: str = "userData.db"
    hash: str = ""
    type: int | None = None
    version: int | None = None
    extra: dict = Field(default_factory=dict)


class Location(BaseModel):
    """A single addressable position inside the user's library.

    For Bible references, `book_number` + `chapter_number` are set.
    For publications, `key_symbol` (e.g. 'w24', 'bh') + `meps_language`
    + `document_id` + `issue_tag_number` are set.
    """

    location_id: int
    book_number: int | None = None
    chapter_number: int | None = None
    document_id: int | None = None
    track: int | None = None
    issue_tag_number: int | None = None
    key_symbol: str = ""
    meps_language: int | None = None
    type: int | None = None
    title: str = ""

    @property
    def is_bible(self) -> bool:
        return self.book_number is not None and self.chapter_number is not None


class UserHighlight(BaseModel):
    """One colored highlight in the user's library."""

    user_mark_id: int
    color_index: int = 0
    style_index: int = 0
    user_mark_guid: str = ""
    location: Location
    block_ranges: list[dict] = Field(
        default_factory=list,
        description="BlockRange rows (BlockType/Identifier/StartToken/EndToken)",
    )


class UserNote(BaseModel):
    """A note authored by the user. May or may not be attached to a UserMark."""

    note_id: int
    guid: str = ""
    title: str = ""
    content: str = ""
    last_modified: str = ""
    created: str = ""
    block_type: int | None = None
    block_identifier: int | None = None
    location: Location | None = None
    user_mark_id: int | None = None
    tags: list[str] = Field(default_factory=list)


class Bookmark(BaseModel):
    """One bookmarked position (max 10 per publication in JW Library)."""

    bookmark_id: int
    slot: int = 0
    title: str = ""
    snippet: str = ""
    block_type: int | None = None
    block_identifier: int | None = None
    location: Location


class Tag(BaseModel):
    """A user-defined tag (or the built-in 'Favorite' tag, type=1)."""

    tag_id: int
    name: str
    type: int = 1


class InputField(BaseModel):
    """Answer typed into a publication form field (workbook, study aids)."""

    location_id: int
    text_tag: str = ""
    value: str = ""
    location: Location | None = None


class BackupContents(BaseModel):
    """Top-level result: everything we could pull out of the archive."""

    source_path: str
    manifest: BackupManifest
    locations: list[Location] = Field(default_factory=list)
    notes: list[UserNote] = Field(default_factory=list)
    highlights: list[UserHighlight] = Field(default_factory=list)
    bookmarks: list[Bookmark] = Field(default_factory=list)
    tags: list[Tag] = Field(default_factory=list)
    input_fields: list[InputField] = Field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "locations": len(self.locations),
            "notes": len(self.notes),
            "highlights": len(self.highlights),
            "bookmarks": len(self.bookmarks),
            "tags": len(self.tags),
            "input_fields": len(self.input_fields),
        }


# ── Public API ───────────────────────────────────────────────────────────


def parse_jw_library_backup(path: Path | str) -> BackupContents:
    """Open a `.jwlibrary` archive and return all user data we can read.

    Raises:
        JWLibraryBackupError: When the file is missing, not a ZIP, or lacks
            both `manifest.json` and `userData.db`. Per-row decode errors
            are logged and skipped rather than raising.
    """
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise JWLibraryBackupError(f"Backup file not found: {source}")
    if not zipfile.is_zipfile(source):
        raise JWLibraryBackupError(f"Not a ZIP archive: {source}")

    with zipfile.ZipFile(source) as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise JWLibraryBackupError("Backup is missing manifest.json")
        manifest = _parse_manifest(zf.read("manifest.json"))
        db_name = manifest.database_name or "userData.db"
        if db_name not in names:
            raise JWLibraryBackupError(f"Backup is missing {db_name}")

        with _extract_to_tempfile(zf, db_name) as db_path:
            return _read_user_data(db_path, manifest, str(source))


def parse_user_data_db(
    db_path: Path | str,
    *,
    manifest: BackupManifest | None = None,
    source: str = "",
) -> BackupContents:
    """Read a standalone `userData.db` (without the ZIP wrapper).

    Use this when you have the SQLite file directly — for example when
    reading the live container on macOS via Full Disk Access. The schema
    is the same that ships inside `.jwlibrary` archives.
    """
    p = Path(db_path).expanduser()
    if not p.is_file():
        raise JWLibraryBackupError(f"userData.db not found: {p}")
    return _read_user_data(
        p,
        manifest or BackupManifest(database_name=p.name),
        source or str(p),
    )


def notes_for_chapter(
    backup: BackupContents,
    *,
    book_num: int,
    chapter: int,
) -> list[UserNote]:
    """Filter notes whose Location addresses the given Bible chapter."""
    return [
        n
        for n in backup.notes
        if n.location is not None and n.location.book_number == book_num and n.location.chapter_number == chapter
    ]


# ── Internals ────────────────────────────────────────────────────────────


_KNOWN_MANIFEST_FIELDS = {
    "name",
    "creationDate",
    "userDataBackup",
    "version",
    "type",
    "hash",
}


def _parse_manifest(blob: bytes) -> BackupManifest:
    try:
        data = json.loads(blob.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise JWLibraryBackupError(f"manifest.json is not valid JSON: {e}") from e

    udb = data.get("userDataBackup") or {}
    extra = {k: v for k, v in data.items() if k not in _KNOWN_MANIFEST_FIELDS}
    return BackupManifest(
        name=str(data.get("name", "")),
        creation_date=str(data.get("creationDate", "")),
        version=_as_int(data.get("version")),
        type=_as_int(data.get("type")),
        hash=str(data.get("hash", udb.get("hash", "") or "")),
        device_name=str(udb.get("deviceName", "")),
        schema_version=_as_int(udb.get("schemaVersion")),
        last_modified_date=str(udb.get("lastModifiedDate", "")),
        database_name=str(udb.get("databaseName", "userData.db")),
        extra=extra,
    )


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@contextmanager
def _extract_to_tempfile(zf: zipfile.ZipFile, member: str) -> Iterator[Path]:
    """Write `member` to a temp file because sqlite3 needs a real path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(zf.read(member))
        tmp.flush()
        tmp_path = Path(tmp.name)
    try:
        yield tmp_path
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _read_user_data(
    db_path: Path,
    manifest: BackupManifest,
    source: str,
) -> BackupContents:
    # Open URI mode=ro so any accidental write raises immediately.
    uri = f"file:{db_path}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        tables = _list_tables(conn)
        locations_by_id = _select_locations(conn, tables)
        tags = _select_tags(conn, tables)
        notes = _select_notes(conn, tables, locations_by_id, tags)
        highlights = _select_highlights(conn, tables, locations_by_id)
        bookmarks = _select_bookmarks(conn, tables, locations_by_id)
        input_fields = _select_input_fields(conn, tables, locations_by_id)

    return BackupContents(
        source_path=source,
        manifest=manifest,
        locations=list(locations_by_id.values()),
        notes=notes,
        highlights=highlights,
        bookmarks=bookmarks,
        tags=tags,
        input_fields=input_fields,
    )


def _list_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _select(
    conn: sqlite3.Connection,
    table: str,
    wanted: list[str],
) -> list[sqlite3.Row]:
    """SELECT only columns that actually exist on `table`."""
    cols = _columns(conn, table)
    present = [c for c in wanted if c in cols]
    if not present:
        return []
    sql = f"SELECT {', '.join(present)} FROM {table}"
    try:
        return conn.execute(sql).fetchall()
    except sqlite3.DatabaseError as e:
        logger.warning("Failed to read %s: %s", table, e)
        return []


def _select_locations(
    conn: sqlite3.Connection,
    tables: set[str],
) -> dict[int, Location]:
    if "Location" not in tables:
        return {}
    rows = _select(
        conn,
        "Location",
        [
            "LocationId",
            "BookNumber",
            "ChapterNumber",
            "DocumentId",
            "Track",
            "IssueTagNumber",
            "KeySymbol",
            "MepsLanguage",
            "Type",
            "Title",
        ],
    )
    out: dict[int, Location] = {}
    for r in rows:
        try:
            loc = Location(
                location_id=int(r["LocationId"]),
                book_number=_row_int(r, "BookNumber"),
                chapter_number=_row_int(r, "ChapterNumber"),
                document_id=_row_int(r, "DocumentId"),
                track=_row_int(r, "Track"),
                issue_tag_number=_row_int(r, "IssueTagNumber"),
                key_symbol=_row_str(r, "KeySymbol"),
                meps_language=_row_int(r, "MepsLanguage"),
                type=_row_int(r, "Type"),
                title=_row_str(r, "Title"),
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.warning("Skipping malformed Location row: %s", e)
            continue
        out[loc.location_id] = loc
    return out


def _select_tags(conn: sqlite3.Connection, tables: set[str]) -> list[Tag]:
    if "Tag" not in tables:
        return []
    rows = _select(conn, "Tag", ["TagId", "Name", "Type"])
    out: list[Tag] = []
    for r in rows:
        try:
            out.append(
                Tag(
                    tag_id=int(r["TagId"]),
                    name=_row_str(r, "Name"),
                    type=_row_int(r, "Type") or 1,
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def _select_notes(
    conn: sqlite3.Connection,
    tables: set[str],
    locations: dict[int, Location],
    tags: list[Tag],
) -> list[UserNote]:
    if "Note" not in tables:
        return []
    rows = _select(
        conn,
        "Note",
        [
            "NoteId",
            "Guid",
            "UserMarkId",
            "LocationId",
            "Title",
            "Content",
            "LastModified",
            "Created",
            "BlockType",
            "BlockIdentifier",
        ],
    )
    tag_lookup = _build_note_tag_lookup(conn, tables, {t.tag_id: t.name for t in tags})
    out: list[UserNote] = []
    for r in rows:
        try:
            note_id = int(r["NoteId"])
            location_id = _row_int(r, "LocationId")
            out.append(
                UserNote(
                    note_id=note_id,
                    guid=_row_str(r, "Guid"),
                    user_mark_id=_row_int(r, "UserMarkId"),
                    title=_row_str(r, "Title"),
                    content=_row_str(r, "Content"),
                    last_modified=_row_str(r, "LastModified"),
                    created=_row_str(r, "Created"),
                    block_type=_row_int(r, "BlockType"),
                    block_identifier=_row_int(r, "BlockIdentifier"),
                    location=locations.get(location_id) if location_id else None,
                    tags=tag_lookup.get(note_id, []),
                )
            )
        except (KeyError, ValueError) as e:
            logger.warning("Skipping malformed Note row: %s", e)
            continue
    return out


def _build_note_tag_lookup(
    conn: sqlite3.Connection,
    tables: set[str],
    tag_names_by_id: dict[int, str],
) -> dict[int, list[str]]:
    if "TagMap" not in tables or not tag_names_by_id:
        return {}
    rows = _select(conn, "TagMap", ["NoteId", "TagId"])
    out: dict[int, list[str]] = {}
    for r in rows:
        note_id = _row_int(r, "NoteId")
        tag_id = _row_int(r, "TagId")
        if note_id is None or tag_id is None:
            continue
        name = tag_names_by_id.get(tag_id)
        if name:
            out.setdefault(note_id, []).append(name)
    return out


def _select_highlights(
    conn: sqlite3.Connection,
    tables: set[str],
    locations: dict[int, Location],
) -> list[UserHighlight]:
    if "UserMark" not in tables:
        return []
    marks = _select(
        conn,
        "UserMark",
        [
            "UserMarkId",
            "ColorIndex",
            "LocationId",
            "StyleIndex",
            "UserMarkGuid",
        ],
    )
    block_ranges_by_mark = _block_ranges_by_mark(conn, tables)
    out: list[UserHighlight] = []
    for r in marks:
        try:
            mark_id = int(r["UserMarkId"])
            location_id = _row_int(r, "LocationId")
            loc = locations.get(location_id) if location_id else None
            if loc is None:
                continue
            out.append(
                UserHighlight(
                    user_mark_id=mark_id,
                    color_index=_row_int(r, "ColorIndex") or 0,
                    style_index=_row_int(r, "StyleIndex") or 0,
                    user_mark_guid=_row_str(r, "UserMarkGuid"),
                    location=loc,
                    block_ranges=block_ranges_by_mark.get(mark_id, []),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def _block_ranges_by_mark(
    conn: sqlite3.Connection,
    tables: set[str],
) -> dict[int, list[dict]]:
    if "BlockRange" not in tables:
        return {}
    rows = _select(
        conn,
        "BlockRange",
        [
            "BlockRangeId",
            "BlockType",
            "Identifier",
            "StartToken",
            "EndToken",
            "UserMarkId",
        ],
    )
    out: dict[int, list[dict]] = {}
    for r in rows:
        mark_id = _row_int(r, "UserMarkId")
        if mark_id is None:
            continue
        out.setdefault(mark_id, []).append(
            {
                "block_type": _row_int(r, "BlockType"),
                "identifier": _row_int(r, "Identifier"),
                "start_token": _row_int(r, "StartToken"),
                "end_token": _row_int(r, "EndToken"),
            }
        )
    return out


def _select_bookmarks(
    conn: sqlite3.Connection,
    tables: set[str],
    locations: dict[int, Location],
) -> list[Bookmark]:
    if "Bookmark" not in tables:
        return []
    rows = _select(
        conn,
        "Bookmark",
        [
            "BookmarkId",
            "LocationId",
            "Slot",
            "Title",
            "Snippet",
            "BlockType",
            "BlockIdentifier",
        ],
    )
    out: list[Bookmark] = []
    for r in rows:
        try:
            location_id = _row_int(r, "LocationId")
            loc = locations.get(location_id) if location_id else None
            if loc is None:
                continue
            out.append(
                Bookmark(
                    bookmark_id=int(r["BookmarkId"]),
                    slot=_row_int(r, "Slot") or 0,
                    title=_row_str(r, "Title"),
                    snippet=_row_str(r, "Snippet"),
                    block_type=_row_int(r, "BlockType"),
                    block_identifier=_row_int(r, "BlockIdentifier"),
                    location=loc,
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def _select_input_fields(
    conn: sqlite3.Connection,
    tables: set[str],
    locations: dict[int, Location],
) -> list[InputField]:
    if "InputField" not in tables:
        return []
    rows = _select(conn, "InputField", ["LocationId", "TextTag", "Value"])
    out: list[InputField] = []
    for r in rows:
        location_id = _row_int(r, "LocationId")
        if location_id is None:
            continue
        out.append(
            InputField(
                location_id=location_id,
                text_tag=_row_str(r, "TextTag"),
                value=_row_str(r, "Value"),
                location=locations.get(location_id),
            )
        )
    return out


# ── Row helpers ──────────────────────────────────────────────────────────


def _row_int(row: sqlite3.Row, key: str) -> int | None:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return None
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_str(row: sqlite3.Row, key: str) -> str:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return ""
    if value is None:
        return ""
    return str(value)
