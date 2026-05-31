"""Tests for jw_core.integrations.obsidian_vault (Phase 20)."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from jw_core.integrations.obsidian_vault import (
    VaultSyncStateStore,
    export_backup_to_vault,
    index_vault_to_rag,
    iter_vault_notes,
    parse_markdown_note,
)

# ── Fixture: minimal vault ─────────────────────────────────────────────


def _seed_vault(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        full = root / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")


def _seed_backup(tmp_path: Path) -> Path:
    db_path = tmp_path / "userData.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Location (LocationId INTEGER PRIMARY KEY, BookNumber INTEGER, ChapterNumber INTEGER, DocumentId INTEGER, Track INTEGER, IssueTagNumber INTEGER, KeySymbol TEXT, MepsLanguage INTEGER, Type INTEGER, Title TEXT);
        CREATE TABLE Note (NoteId INTEGER PRIMARY KEY, Guid TEXT, UserMarkId INTEGER, LocationId INTEGER, Title TEXT, Content TEXT, LastModified TEXT, Created TEXT, BlockType INTEGER, BlockIdentifier INTEGER);
        INSERT INTO Location VALUES (1, 43, 3, NULL, NULL, NULL, 'nwtsty', 0, 2, 'Juan 3');
        INSERT INTO Location VALUES (2, NULL, NULL, 1102021201, NULL, 20240401, 'w24', 0, 0, 'WT 2024-04');
        INSERT INTO Note VALUES (10, 'g-1', NULL, 1, 'El amor de Dios', 'Juan 3:16 muestra...', '2024-11-15', '2024-11-10', NULL, NULL);
        INSERT INTO Note VALUES (20, 'g-2', NULL, 2, 'Estudio del Watchtower', 'Comentario sobre el artículo', '2024-11-16', '2024-11-12', NULL, NULL);
        """
    )
    conn.commit()
    conn.close()
    manifest = {
        "name": "demo.jwlibrary",
        "creationDate": "2024-11-15",
        "version": 1,
        "type": 0,
        "hash": "deadbeef",
        "userDataBackup": {"databaseName": "userData.db", "schemaVersion": 14, "deviceName": "test"},
    }
    archive = tmp_path / "demo.jwlibrary"
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
    def __init__(self, path: Path) -> None:
        self.path = path
        self.chunks: list[_StoredChunk] = []

    @property
    def count(self) -> int:
        return len(self.chunks)

    def add(self, chunks: list[Any]) -> None:
        for c in chunks:
            self.chunks.append(_StoredChunk(id=c.id, text=c.text, source_id=c.source_id, metadata=dict(c.metadata)))

    def delete_by_source_ids(self, ids: list[str]) -> int:
        before = len(self.chunks)
        targets = set(ids)
        self.chunks = [c for c in self.chunks if c.source_id not in targets]
        return before - len(self.chunks)

    def save(self) -> None:
        return None


# ── parse_markdown_note ─────────────────────────────────────────────────


def test_parse_md_with_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "note.md"
    p.write_text(
        "---\n"
        'title: "My note"\n'
        "tags:\n"
        "  - ministry\n"
        "  - personal\n"
        "pinned: true\n"
        "---\n"
        "# Real Title\n\nBody text here.\n",
        encoding="utf-8",
    )
    note = parse_markdown_note(p)
    assert note.title == "Real Title"
    assert note.frontmatter["title"] == "My note"
    assert note.frontmatter["pinned"] is True
    assert note.tags == ["ministry", "personal"]
    assert "Body text here" in note.body
    assert note.content_hash  # populated


def test_parse_md_inline_list(tmp_path: Path) -> None:
    p = tmp_path / "n.md"
    p.write_text(
        "---\ntags: [a, b, c]\n---\n# T\nbody",
        encoding="utf-8",
    )
    note = parse_markdown_note(p)
    assert note.tags == ["a", "b", "c"]


def test_parse_md_without_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "plain.md"
    p.write_text("# Heading\n\nSome body.", encoding="utf-8")
    note = parse_markdown_note(p)
    assert note.title == "Heading"
    assert note.tags == []
    assert note.frontmatter == {}


def test_parse_md_title_fallback_to_filename(tmp_path: Path) -> None:
    p = tmp_path / "fallback.md"
    p.write_text("body without heading", encoding="utf-8")
    note = parse_markdown_note(p)
    assert note.title == "fallback"


# ── iter_vault_notes ────────────────────────────────────────────────────


def test_iter_vault_skips_obsidian_metadata(tmp_path: Path) -> None:
    _seed_vault(
        tmp_path,
        {
            "Note 1.md": "# a\nbody",
            "folder/Note 2.md": "# b\nbody",
            ".obsidian/workspace.json": "{}",
            ".trash/old.md": "# old\nbody",
            "node_modules/x.md": "# nope",
        },
    )
    paths = sorted(p.name for p in iter_vault_notes(tmp_path))
    assert paths == ["Note 1.md", "Note 2.md"]


def test_iter_vault_raises_for_missing_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        next(iter_vault_notes(tmp_path / "nope"))


# ── index_vault_to_rag ──────────────────────────────────────────────────


def test_index_vault_first_run_indexes_everything(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(
        vault,
        {
            "a.md": "# A\n" + "alpha body. " * 5,
            "folder/b.md": "# B\n" + "beta body. " * 5,
        },
    )
    store = _FakeStore(tmp_path / "store")
    report = index_vault_to_rag(vault, store, state_path=tmp_path / "state.json")
    assert report.indexed == 2
    assert report.chunks_added >= 2
    assert store.count >= 2


def test_index_vault_second_run_unchanged_is_noop(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, {"a.md": "# A\n" + "body. " * 5})
    store = _FakeStore(tmp_path / "store")
    state_path = tmp_path / "state.json"
    index_vault_to_rag(vault, store, state_path=state_path)
    r2 = index_vault_to_rag(vault, store, state_path=state_path)
    assert r2.indexed == 0
    assert r2.updated == 0
    assert r2.unchanged == 1


def test_index_vault_detects_modifications(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, {"a.md": "# A\n" + "original body. " * 4})
    store = _FakeStore(tmp_path / "store")
    state_path = tmp_path / "state.json"
    index_vault_to_rag(vault, store, state_path=state_path)
    # Mutate the file.
    (vault / "a.md").write_text("# A\n" + "REVISED body. " * 4, encoding="utf-8")
    r2 = index_vault_to_rag(vault, store, state_path=state_path)
    assert r2.updated == 1
    assert r2.chunks_removed >= 1
    assert any("REVISED" in c.text for c in store.chunks)


def test_index_vault_evicts_deleted_files(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(
        vault,
        {
            "keep.md": "# Keep\n" + "kept body. " * 4,
            "drop.md": "# Drop\n" + "dropped body. " * 4,
        },
    )
    store = _FakeStore(tmp_path / "store")
    state_path = tmp_path / "state.json"
    index_vault_to_rag(vault, store, state_path=state_path)
    assert store.count >= 2
    (vault / "drop.md").unlink()
    r2 = index_vault_to_rag(vault, store, state_path=state_path)
    assert r2.deleted == 1
    assert all("dropped" not in c.text for c in store.chunks)


def test_index_vault_tag_filter(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(
        vault,
        {
            "with-tag.md": "---\ntags:\n  - ministry\n---\n# A\nbody is long enough here.",
            "no-tag.md": "# B\nbody is long enough here too.",
        },
    )
    store = _FakeStore(tmp_path / "store")
    report = index_vault_to_rag(vault, store, state_path=tmp_path / "state.json", require_tag="ministry")
    assert report.indexed == 1
    assert report.skipped == 1


def test_index_vault_skips_short_notes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, {"tiny.md": "# A\nx"})
    store = _FakeStore(tmp_path / "store")
    report = index_vault_to_rag(vault, store, state_path=tmp_path / "state.json", min_chars=50)
    assert report.skipped == 1
    assert store.count == 0


# ── export_backup_to_vault ──────────────────────────────────────────────


def test_export_creates_files_per_note(tmp_path: Path) -> None:
    archive = _seed_backup(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    report = export_backup_to_vault(archive, vault, language="es")
    assert report.files_written == 2
    # Bible-anchored note lands under JW Library/bible/.../
    files = list(vault.rglob("*.md"))
    assert any("bible/43" in str(p).replace("\\", "/") for p in files)
    # Publication-anchored note lands under publications/.
    assert any("publications/w24" in str(p).replace("\\", "/") for p in files)


def test_export_idempotent_default(tmp_path: Path) -> None:
    archive = _seed_backup(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    r1 = export_backup_to_vault(archive, vault)
    r2 = export_backup_to_vault(archive, vault)
    assert r2.files_written == 0
    assert r2.files_skipped == r1.files_written


def test_export_overwrite_flag(tmp_path: Path) -> None:
    archive = _seed_backup(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    export_backup_to_vault(archive, vault)
    r2 = export_backup_to_vault(archive, vault, overwrite=True)
    assert r2.files_written == 2
    assert r2.files_skipped == 0


def test_export_note_has_frontmatter(tmp_path: Path) -> None:
    archive = _seed_backup(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    export_backup_to_vault(archive, vault, language="es")
    for f in vault.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "note_id:" in text


# ── State store ────────────────────────────────────────────────────────


def test_vault_state_store_roundtrip(tmp_path: Path) -> None:
    store = VaultSyncStateStore(tmp_path / "state.json")
    s = store.load("/some/root")
    assert s.notes == {}
    store.save(s)
    again = VaultSyncStateStore(tmp_path / "state.json").load("/some/root")
    assert again.vault_root == "/some/root"
