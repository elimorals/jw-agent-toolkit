"""Incremental sync of `.jwlibrary` backups into an external store.

A user typically exports a new backup every few weeks. Re-ingesting the
entire archive each time would (a) duplicate notes the agent already saw,
(b) silently keep deleted notes in the index. This module diffs the new
backup against a sidecar **state file** and reports — and optionally
applies — exactly which notes/bookmarks/input-fields need to be added,
re-indexed, or removed.

State file shape (JSON, on disk next to the RAG store):

    {
        "backup_id": "<manifest.hash or name fallback>",
        "last_synced_at": "2024-11-15T20:00:00",
        "notes": {
            "<guid-or-note_id>": {
                "note_id": 10,
                "guid": "abc-…",
                "last_modified": "2024-11-15",
                "source_id": "jwlib:note:10",
                "title_hash": "…",
            }
        },
        "bookmarks": { "<bookmark_id>": {"last_modified": "", "source_id": "jwlib:bookmark:1"} },
        "input_fields": { "<location_id>:<text_tag>": {"value_hash": "…", "source_id": "jwlib:input:5:q1"} }
    }

The state is keyed by `manifest.hash` (or `manifest.name` when hash is
absent) so the user can sync several backups (multiple devices) into the
same store without collisions.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from jw_core.parsers.jw_library_backup import (
    BackupContents,
    Bookmark,
    InputField,
    UserNote,
    parse_jw_library_backup,
)

if TYPE_CHECKING:
    from jw_rag.store import VectorStore

logger = logging.getLogger(__name__)

__all__ = [
    "SyncEntry",
    "SyncPlan",
    "SyncReport",
    "SyncState",
    "SyncStateStore",
    "compute_sync_plan",
    "sync_backup_to_rag",
]


# ── State models ───────────────────────────────────────────────────────


@dataclass
class SyncEntry:
    """One tracked item in the state file."""

    item_id: str  # guid or numeric id, as string
    source_id: str  # chunk source_id used in VectorStore
    last_modified: str = ""
    content_hash: str = ""


@dataclass
class SyncState:
    """Sidecar state for one tracked backup_id."""

    backup_id: str
    last_synced_at: str = ""
    notes: dict[str, SyncEntry] = field(default_factory=dict)
    bookmarks: dict[str, SyncEntry] = field(default_factory=dict)
    input_fields: dict[str, SyncEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "last_synced_at": self.last_synced_at,
            "notes": {k: v.__dict__ for k, v in self.notes.items()},
            "bookmarks": {k: v.__dict__ for k, v in self.bookmarks.items()},
            "input_fields": {k: v.__dict__ for k, v in self.input_fields.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> SyncState:
        def parse(section: dict) -> dict[str, SyncEntry]:
            return {k: SyncEntry(**v) for k, v in (section or {}).items()}

        return cls(
            backup_id=str(data.get("backup_id", "")),
            last_synced_at=str(data.get("last_synced_at", "")),
            notes=parse(data.get("notes", {})),
            bookmarks=parse(data.get("bookmarks", {})),
            input_fields=parse(data.get("input_fields", {})),
        )


class SyncStateStore:
    """Load/save `SyncState` objects from a JSON file on disk.

    The file holds a top-level dict keyed by `backup_id` so the same path
    can track multiple backups (e.g. iPhone vs iPad of the same user).
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()

    def load(self, backup_id: str) -> SyncState:
        if not self.path.exists():
            return SyncState(backup_id=backup_id)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Sync state %s unreadable (%s); starting fresh", self.path, e)
            return SyncState(backup_id=backup_id)
        entry = data.get(backup_id)
        if not isinstance(entry, dict):
            return SyncState(backup_id=backup_id)
        return SyncState.from_dict(entry)

    def save(self, state: SyncState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (json.JSONDecodeError, OSError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[state.backup_id] = state.to_dict()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# ── Plan / report ──────────────────────────────────────────────────────


@dataclass
class SyncPlan:
    """What the sync would do; computed before any mutation."""

    new_notes: list[UserNote] = field(default_factory=list)
    updated_notes: list[UserNote] = field(default_factory=list)
    deleted_note_source_ids: list[str] = field(default_factory=list)
    new_bookmarks: list[Bookmark] = field(default_factory=list)
    updated_bookmarks: list[Bookmark] = field(default_factory=list)
    deleted_bookmark_source_ids: list[str] = field(default_factory=list)
    new_input_fields: list[InputField] = field(default_factory=list)
    updated_input_fields: list[InputField] = field(default_factory=list)
    deleted_input_field_source_ids: list[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not any(
            (
                self.new_notes,
                self.updated_notes,
                self.deleted_note_source_ids,
                self.new_bookmarks,
                self.updated_bookmarks,
                self.deleted_bookmark_source_ids,
                self.new_input_fields,
                self.updated_input_fields,
                self.deleted_input_field_source_ids,
            )
        )

    def summary(self) -> dict[str, int]:
        return {
            "new_notes": len(self.new_notes),
            "updated_notes": len(self.updated_notes),
            "deleted_notes": len(self.deleted_note_source_ids),
            "new_bookmarks": len(self.new_bookmarks),
            "updated_bookmarks": len(self.updated_bookmarks),
            "deleted_bookmarks": len(self.deleted_bookmark_source_ids),
            "new_input_fields": len(self.new_input_fields),
            "updated_input_fields": len(self.updated_input_fields),
            "deleted_input_fields": len(self.deleted_input_field_source_ids),
        }


@dataclass
class SyncReport:
    """What the sync actually did."""

    backup_id: str
    plan: SyncPlan
    chunks_added: int = 0
    chunks_removed: int = 0
    dry_run: bool = False
    state_path: str = ""
    backup_path: str = ""

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "backup_path": self.backup_path,
            "state_path": self.state_path,
            "dry_run": self.dry_run,
            "chunks_added": self.chunks_added,
            "chunks_removed": self.chunks_removed,
            "is_noop": self.plan.is_noop,
            "summary": self.plan.summary(),
        }


# ── Diff engine ────────────────────────────────────────────────────────


def _backup_id(backup: BackupContents) -> str:
    """Stable identifier for a backup (hash if present, else name fallback)."""
    if backup.manifest.hash:
        return backup.manifest.hash
    name = backup.manifest.name or backup.source_path
    return "sha256:" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def _note_key(note: UserNote) -> str:
    """Prefer the GUID — stable across schema migrations. Fall back to id."""
    return note.guid or f"id:{note.note_id}"


def _note_content_hash(note: UserNote) -> str:
    return _hash(f"{note.title}\n{note.content}\n{','.join(sorted(note.tags))}")


def _bookmark_key(bm: Bookmark) -> str:
    return f"id:{bm.bookmark_id}"


def _bookmark_content_hash(bm: Bookmark) -> str:
    return _hash(f"{bm.title}\n{bm.snippet}\n{bm.slot}")


def _input_field_key(f: InputField) -> str:
    return f"{f.location_id}:{f.text_tag}"


def _input_field_content_hash(f: InputField) -> str:
    return _hash(f.value)


def _note_source_id(note: UserNote) -> str:
    return f"jwlib:note:{note.note_id}"


def _bookmark_source_id(bm: Bookmark) -> str:
    return f"jwlib:bookmark:{bm.bookmark_id}"


def _input_field_source_id(f: InputField) -> str:
    return f"jwlib:input:{f.location_id}:{f.text_tag}"


def compute_sync_plan(backup: BackupContents, state: SyncState) -> SyncPlan:
    """Diff `backup` against the recorded `state` without touching anything.

    A row is considered **updated** when its content hash changes — this
    covers both `last_modified` bumps and silent edits where the timestamp
    in the SQLite row is identical but the body differs (rare but
    observed when the user reverts then re-edits).
    """
    plan = SyncPlan()

    seen_notes: set[str] = set()
    for note in backup.notes:
        key = _note_key(note)
        seen_notes.add(key)
        prev = state.notes.get(key)
        new_hash = _note_content_hash(note)
        if prev is None:
            plan.new_notes.append(note)
        elif prev.content_hash != new_hash or prev.last_modified != note.last_modified:
            plan.updated_notes.append(note)
    for key, entry in state.notes.items():
        if key not in seen_notes:
            plan.deleted_note_source_ids.append(entry.source_id)

    seen_bm: set[str] = set()
    for bm in backup.bookmarks:
        key = _bookmark_key(bm)
        seen_bm.add(key)
        prev = state.bookmarks.get(key)
        new_hash = _bookmark_content_hash(bm)
        if prev is None:
            plan.new_bookmarks.append(bm)
        elif prev.content_hash != new_hash:
            plan.updated_bookmarks.append(bm)
    for key, entry in state.bookmarks.items():
        if key not in seen_bm:
            plan.deleted_bookmark_source_ids.append(entry.source_id)

    seen_inp: set[str] = set()
    for f in backup.input_fields:
        key = _input_field_key(f)
        seen_inp.add(key)
        prev = state.input_fields.get(key)
        new_hash = _input_field_content_hash(f)
        if prev is None:
            plan.new_input_fields.append(f)
        elif prev.content_hash != new_hash:
            plan.updated_input_fields.append(f)
    for key, entry in state.input_fields.items():
        if key not in seen_inp:
            plan.deleted_input_field_source_ids.append(entry.source_id)

    return plan


# ── Apply plan ─────────────────────────────────────────────────────────


def sync_backup_to_rag(
    backup_path: Path | str,
    store: VectorStore,
    *,
    state_path: Path | str | None = None,
    include_bookmarks: bool = True,
    include_input_fields: bool = True,
    dry_run: bool = False,
    min_chars: int = 8,
) -> SyncReport:
    """Diff the backup against the sidecar state and apply the delta to `store`.

    Args:
        backup_path: Path to a `.jwlibrary` archive.
        store: Open `VectorStore` to mutate. Must support
            `delete_by_source_ids` (added in this phase).
        state_path: Where to keep the sidecar JSON. Defaults to
            `<store.path>/jw_library_sync.json`.
        include_bookmarks: Track + (re-)ingest bookmark snippets.
        include_input_fields: Track + (re-)ingest input-field answers.
        dry_run: Compute and return the plan without mutating store or state.
        min_chars: Minimum content length to ingest (drops empty notes).

    Returns:
        `SyncReport` with the plan + applied counts.
    """
    from jw_rag.chunker import chunk_paragraphs  # Local import — avoids hard dep at import time.

    backup = parse_jw_library_backup(backup_path)
    backup_id = _backup_id(backup)

    state_file = Path(state_path) if state_path else Path(store.path) / "jw_library_sync.json"
    state_store = SyncStateStore(state_file)
    state = state_store.load(backup_id)

    plan = compute_sync_plan(backup, state)

    if dry_run:
        return SyncReport(
            backup_id=backup_id,
            plan=plan,
            dry_run=True,
            state_path=str(state_file),
            backup_path=str(backup_path),
        )

    # 1. Remove chunks for deleted/updated items.
    to_remove = list(plan.deleted_note_source_ids) + [
        _note_source_id(n) for n in plan.updated_notes
    ]
    if include_bookmarks:
        to_remove += plan.deleted_bookmark_source_ids
        to_remove += [_bookmark_source_id(b) for b in plan.updated_bookmarks]
    if include_input_fields:
        to_remove += plan.deleted_input_field_source_ids
        to_remove += [_input_field_source_id(f) for f in plan.updated_input_fields]
    chunks_removed = store.delete_by_source_ids(to_remove)

    # 2. Add chunks for new + updated items. Update state for every seen
    #    item (even when skipped for being too short) so subsequent syncs
    #    don't re-report it as "new".
    chunks_added = 0
    for note in [*plan.new_notes, *plan.updated_notes]:
        body = _note_body(note)
        if len(body) >= min_chars:
            chunks = chunk_paragraphs(
                [body],
                source_id=_note_source_id(note),
                metadata=_note_metadata(backup, note),
            )
            store.add(chunks)
            chunks_added += len(chunks)
        state.notes[_note_key(note)] = SyncEntry(
            item_id=_note_key(note),
            source_id=_note_source_id(note),
            last_modified=note.last_modified,
            content_hash=_note_content_hash(note),
        )

    if include_bookmarks:
        for bm in [*plan.new_bookmarks, *plan.updated_bookmarks]:
            body = "\n".join(p for p in (bm.title, bm.snippet) if p).strip()
            if len(body) >= min_chars:
                chunks = chunk_paragraphs(
                    [body],
                    source_id=_bookmark_source_id(bm),
                    metadata=_bookmark_metadata(backup, bm),
                )
                store.add(chunks)
                chunks_added += len(chunks)
            state.bookmarks[_bookmark_key(bm)] = SyncEntry(
                item_id=_bookmark_key(bm),
                source_id=_bookmark_source_id(bm),
                content_hash=_bookmark_content_hash(bm),
            )

    if include_input_fields:
        for f in [*plan.new_input_fields, *plan.updated_input_fields]:
            if len(f.value or "") >= min_chars:
                chunks = chunk_paragraphs(
                    [f.value],
                    source_id=_input_field_source_id(f),
                    metadata=_input_field_metadata(backup, f),
                )
                store.add(chunks)
                chunks_added += len(chunks)
            state.input_fields[_input_field_key(f)] = SyncEntry(
                item_id=_input_field_key(f),
                source_id=_input_field_source_id(f),
                content_hash=_input_field_content_hash(f),
            )

    # 3. Evict tracked-but-deleted items from state.
    for key in list(state.notes.keys()):
        if state.notes[key].source_id in plan.deleted_note_source_ids:
            del state.notes[key]
    for key in list(state.bookmarks.keys()):
        if state.bookmarks[key].source_id in plan.deleted_bookmark_source_ids:
            del state.bookmarks[key]
    for key in list(state.input_fields.keys()):
        if state.input_fields[key].source_id in plan.deleted_input_field_source_ids:
            del state.input_fields[key]

    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    state_store.save(state)

    return SyncReport(
        backup_id=backup_id,
        plan=plan,
        chunks_added=chunks_added,
        chunks_removed=chunks_removed,
        dry_run=False,
        state_path=str(state_file),
        backup_path=str(backup_path),
    )


# ── Metadata helpers (same shape as ingest.py — kept here to avoid cycle) ──


def _note_body(note: UserNote) -> str:
    parts: list[str] = []
    if note.title:
        parts.append(note.title)
    if note.content:
        parts.append(note.content)
    return "\n".join(parts).strip()


def _note_metadata(backup: BackupContents, note: UserNote) -> dict:
    md = {
        "kind": "user_note",
        "note_id": note.note_id,
        "guid": note.guid,
        "created": note.created,
        "last_modified": note.last_modified,
        "tags": list(note.tags),
        "source_backup": backup.manifest.name or backup.source_path,
    }
    if note.location is not None:
        md.update(
            {
                "book_num": note.location.book_number,
                "chapter": note.location.chapter_number,
                "key_symbol": note.location.key_symbol,
                "document_id": note.location.document_id,
                "meps_language": note.location.meps_language,
            }
        )
    return md


def _bookmark_metadata(backup: BackupContents, bm: Bookmark) -> dict:
    return {
        "kind": "user_bookmark",
        "bookmark_id": bm.bookmark_id,
        "slot": bm.slot,
        "book_num": bm.location.book_number,
        "chapter": bm.location.chapter_number,
        "key_symbol": bm.location.key_symbol,
        "document_id": bm.location.document_id,
        "source_backup": backup.manifest.name or backup.source_path,
    }


def _input_field_metadata(backup: BackupContents, f: InputField) -> dict:
    loc = f.location
    return {
        "kind": "user_input",
        "location_id": f.location_id,
        "text_tag": f.text_tag,
        "key_symbol": loc.key_symbol if loc else "",
        "document_id": loc.document_id if loc else None,
        "source_backup": backup.manifest.name or backup.source_path,
    }
