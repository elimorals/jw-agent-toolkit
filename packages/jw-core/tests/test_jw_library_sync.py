"""Tests for jw_core.integrations.jw_library_sync (incremental sync)."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jw_core.integrations.jw_library_sync import (
    SyncEntry,
    SyncStateStore,
    compute_sync_plan,
    sync_backup_to_rag,
)
from jw_core.parsers.jw_library_backup import parse_jw_library_backup

# ── Fixture builder ─────────────────────────────────────────────────────


def _build_backup(
    tmp_path: Path,
    *,
    archive_name: str = "demo.jwlibrary",
    hash_: str = "deadbeef",
    locations: list[dict] | None = None,
    notes: list[dict] | None = None,
    bookmarks: list[dict] | None = None,
    input_fields: list[dict] | None = None,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "userData.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Location (LocationId INTEGER PRIMARY KEY, BookNumber INTEGER, ChapterNumber INTEGER, DocumentId INTEGER, Track INTEGER, IssueTagNumber INTEGER, KeySymbol TEXT, MepsLanguage INTEGER, Type INTEGER, Title TEXT);
        CREATE TABLE Note (NoteId INTEGER PRIMARY KEY, Guid TEXT, UserMarkId INTEGER, LocationId INTEGER, Title TEXT, Content TEXT, LastModified TEXT, Created TEXT, BlockType INTEGER, BlockIdentifier INTEGER);
        CREATE TABLE Bookmark (BookmarkId INTEGER PRIMARY KEY, LocationId INTEGER, PublicationLocationId INTEGER, Slot INTEGER, Title TEXT, Snippet TEXT, BlockType INTEGER, BlockIdentifier INTEGER);
        CREATE TABLE InputField (LocationId INTEGER, TextTag TEXT, Value TEXT);
        """
    )
    for loc in locations or []:
        conn.execute(
            "INSERT INTO Location VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                loc.get(k)
                for k in (
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
                )
            ],
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
    for f in input_fields or []:
        conn.execute(
            "INSERT INTO InputField VALUES (?,?,?)",
            [f.get("LocationId"), f.get("TextTag", ""), f.get("Value", "")],
        )
    conn.commit()
    conn.close()

    manifest = {
        "name": archive_name,
        "creationDate": "2024-11-15",
        "version": 1,
        "type": 0,
        "hash": hash_,
        "userDataBackup": {"databaseName": "userData.db", "schemaVersion": 14},
    }
    archive = tmp_path / archive_name
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.write(db_path, "userData.db")
    db_path.unlink()
    return archive


# ── Tiny fake VectorStore ──────────────────────────────────────────────


@dataclass
class _StoredChunk:
    id: str
    text: str
    source_id: str
    metadata: dict[str, Any]


class _FakeStore:
    """Stub that records add()/delete_by_source_ids() calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.chunks: list[_StoredChunk] = []
        self.add_log: list[list[_StoredChunk]] = []
        self.delete_log: list[list[str]] = []

    @property
    def count(self) -> int:
        return len(self.chunks)

    def add(self, chunks: list[Any]) -> None:
        recorded = [
            _StoredChunk(id=c.id, text=c.text, source_id=c.source_id, metadata=dict(c.metadata)) for c in chunks
        ]
        self.chunks.extend(recorded)
        self.add_log.append(recorded)

    def delete_by_source_ids(self, ids: list[str]) -> int:
        targets = set(ids)
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.source_id not in targets]
        removed = before - len(self.chunks)
        self.delete_log.append(list(ids))
        return removed

    def save(self) -> None:
        return None


# ── State store ────────────────────────────────────────────────────────


def test_state_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = SyncStateStore(path)
    loaded = store.load("bkA")
    assert loaded.backup_id == "bkA"
    assert loaded.notes == {}
    loaded.notes["g1"] = SyncEntry(
        item_id="g1", source_id="jwlib:note:1", last_modified="2024-11-15", content_hash="h1"
    )
    store.save(loaded)

    again = SyncStateStore(path).load("bkA")
    assert "g1" in again.notes
    assert again.notes["g1"].source_id == "jwlib:note:1"


def test_state_store_keeps_multiple_backups(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = SyncStateStore(path)
    a = store.load("bkA")
    a.notes["g1"] = SyncEntry(item_id="g1", source_id="x", content_hash="ha")
    store.save(a)
    b = store.load("bkB")
    b.notes["g2"] = SyncEntry(item_id="g2", source_id="y", content_hash="hb")
    store.save(b)
    a_again = SyncStateStore(path).load("bkA")
    b_again = SyncStateStore(path).load("bkB")
    assert "g1" in a_again.notes
    assert "g2" in b_again.notes


def test_state_store_handles_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not json")
    state = SyncStateStore(path).load("any")
    assert state.notes == {}


# ── Diff engine ────────────────────────────────────────────────────────


def test_first_sync_marks_everything_new(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {"NoteId": 1, "Guid": "g1", "LocationId": 1, "Title": "t1", "Content": "c1", "LastModified": "2024-11-15"}
        ],
        bookmarks=[{"BookmarkId": 1, "LocationId": 1, "Title": "Juan 3:16", "Snippet": "snippet"}],
        input_fields=[{"LocationId": 1, "TextTag": "q1", "Value": "respuesta"}],
    )
    backup = parse_jw_library_backup(archive)
    state = SyncStateStore(tmp_path / "s.json").load("ignored")
    plan = compute_sync_plan(backup, state)
    assert len(plan.new_notes) == 1
    assert len(plan.new_bookmarks) == 1
    assert len(plan.new_input_fields) == 1
    assert plan.deleted_note_source_ids == []
    assert plan.is_noop is False


def test_unchanged_second_sync_is_noop(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {"NoteId": 1, "Guid": "g1", "LocationId": 1, "Title": "t1", "Content": "c1", "LastModified": "2024-11-15"}
        ],
    )
    store_path = tmp_path / "store"
    store_path.mkdir()
    store = _FakeStore(store_path)
    sync_backup_to_rag(archive, store, state_path=tmp_path / "state.json")
    # Second sync with the same archive.
    report = sync_backup_to_rag(archive, store, state_path=tmp_path / "state.json")
    assert report.plan.is_noop is True
    assert report.chunks_added == 0
    assert report.chunks_removed == 0


def test_modified_note_is_updated_in_place(tmp_path: Path) -> None:
    archive_v1 = _build_backup(
        tmp_path / "v1",
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 1,
                "Guid": "g1",
                "LocationId": 1,
                "Title": "v1",
                "Content": "first body",
                "LastModified": "2024-11-15",
            }
        ],
    )
    archive_v2 = _build_backup(
        tmp_path / "v2",
        archive_name="demo-v2.jwlibrary",
        hash_="deadbeef",  # same hash → same backup_id, so state carries over
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 1,
                "Guid": "g1",
                "LocationId": 1,
                "Title": "v2",
                "Content": "REVISED body",
                "LastModified": "2024-11-20",
            }
        ],
    )
    store = _FakeStore(tmp_path / "store")
    state_path = tmp_path / "state.json"
    sync_backup_to_rag(archive_v1, store, state_path=state_path)
    assert store.count == 1
    report = sync_backup_to_rag(archive_v2, store, state_path=state_path)
    assert len(report.plan.updated_notes) == 1
    assert report.chunks_removed >= 1
    assert report.chunks_added >= 1
    # Final store should hold exactly 1 chunk — the new version.
    assert store.count == 1
    assert "REVISED" in store.chunks[0].text


def test_deleted_note_is_removed_from_store(tmp_path: Path) -> None:
    archive_v1 = _build_backup(
        tmp_path / "v1",
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 1,
                "Guid": "g1",
                "LocationId": 1,
                "Title": "keep",
                "Content": "kept note body",
                "LastModified": "2024-11-15",
            },
            {
                "NoteId": 2,
                "Guid": "g2",
                "LocationId": 1,
                "Title": "drop",
                "Content": "dropped note body",
                "LastModified": "2024-11-15",
            },
        ],
    )
    archive_v2 = _build_backup(
        tmp_path / "v2",
        archive_name="demo-v2.jwlibrary",
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 1,
                "Guid": "g1",
                "LocationId": 1,
                "Title": "keep",
                "Content": "kept note body",
                "LastModified": "2024-11-15",
            },
        ],
    )
    store = _FakeStore(tmp_path / "store")
    state_path = tmp_path / "state.json"
    sync_backup_to_rag(archive_v1, store, state_path=state_path)
    assert store.count == 2
    report = sync_backup_to_rag(archive_v2, store, state_path=state_path)
    assert "jwlib:note:2" in report.plan.deleted_note_source_ids
    assert store.count == 1


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[{"NoteId": 1, "Guid": "g1", "LocationId": 1, "Title": "t", "Content": "c", "LastModified": "x"}],
    )
    state_path = tmp_path / "state.json"
    store = _FakeStore(tmp_path / "store")
    report = sync_backup_to_rag(archive, store, state_path=state_path, dry_run=True)
    assert report.dry_run is True
    assert store.count == 0
    assert not state_path.exists()  # state untouched in dry run
    assert len(report.plan.new_notes) == 1


def test_short_notes_below_min_chars_skipped(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {"NoteId": 1, "Guid": "g1", "LocationId": 1, "Title": "", "Content": "x", "LastModified": "x"},
            {
                "NoteId": 2,
                "Guid": "g2",
                "LocationId": 1,
                "Title": "ok",
                "Content": "this is long enough",
                "LastModified": "x",
            },
        ],
    )
    store = _FakeStore(tmp_path / "store")
    report = sync_backup_to_rag(archive, store, state_path=tmp_path / "s.json", min_chars=8)
    # Only the second one was ingested.
    assert report.chunks_added == 1
    assert store.count == 1


def test_include_bookmarks_false_skips_them(tmp_path: Path) -> None:
    archive = _build_backup(
        tmp_path,
        locations=[{"LocationId": 1, "BookNumber": 43, "ChapterNumber": 3, "Type": 2}],
        notes=[
            {
                "NoteId": 1,
                "Guid": "g1",
                "LocationId": 1,
                "Title": "n",
                "Content": "content body here",
                "LastModified": "",
            }
        ],
        bookmarks=[{"BookmarkId": 1, "LocationId": 1, "Title": "skip me", "Snippet": "definitely long enough text"}],
    )
    store = _FakeStore(tmp_path / "store")
    report = sync_backup_to_rag(archive, store, state_path=tmp_path / "s.json", include_bookmarks=False)
    assert report.chunks_added == 1  # only the note
    assert all("bookmark" not in c.source_id for c in store.chunks)
