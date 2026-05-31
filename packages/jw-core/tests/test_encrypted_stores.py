"""Gap 2: confirm FieldEncryptor is wired to the three local stores.

We verify that when JW_PRIVACY_KEY is set, the on-disk SQLite cells are
ciphertext (NOT readable plain), but the API roundtrips return the
original values.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

cryptography = pytest.importorskip("cryptography")

from jw_agents.revisit_tracker import Revisit, RevisitStore
from jw_core.personalization.memory import MemoryEntry, SessionMemory
from jw_core.privacy.encryption import FieldEncryptor, generate_key
from jw_core.study.personal_notes import PersonalNote, PersonalNoteStore


def _tmp() -> Path:
    return Path(tempfile.mkdtemp()) / "x.db"


def _raw_cells(path: Path, table: str, col: str) -> list[str]:
    with sqlite3.connect(path) as conn:
        return [r[0] for r in conn.execute(f"SELECT {col} FROM {table}")]


# ── Personal notes ──────────────────────────────────────────────────────


def test_personal_notes_encrypted_when_key_provided() -> None:
    path = _tmp()
    enc = FieldEncryptor(key=generate_key())
    with PersonalNoteStore(path, encryptor=enc) as store:
        note = store.add(
            PersonalNote(
                book_num=43,
                chapter=3,
                verse=16,
                title="On love",
                body="Plaintext we never want to leak.",
            )
        )
        # Decrypted roundtrip works.
        got = store.get(note.note_id)
        assert got.body == "Plaintext we never want to leak."
    # Raw disk does NOT contain the plaintext.
    raw_bodies = _raw_cells(path, "notes", "body")
    assert all("Plaintext" not in cell for cell in raw_bodies)


def test_personal_notes_passthrough_without_key() -> None:
    path = _tmp()
    with PersonalNoteStore(path) as store:
        store.add(PersonalNote(book_num=1, chapter=1, verse=1, body="readable"))
    raw_bodies = _raw_cells(path, "notes", "body")
    assert "readable" in raw_bodies


# ── Revisit tracker ─────────────────────────────────────────────────────


def test_revisit_store_encrypted_columns() -> None:
    path = _tmp()
    enc = FieldEncryptor(key=generate_key())
    with RevisitStore(path, encryptor=enc) as store:
        store.upsert(
            Revisit(
                interest_id="alex",
                name_alias="Alex Doe",
                notes="Discussed John 3:16 yesterday",
                language="en",
            )
        )
        rev = store.get("alex")
        assert rev.notes.startswith("Discussed")
        assert rev.name_alias == "Alex Doe"
        # Search via API still works because we fall back to in-memory decryption.
        hits = store.search("yesterday")
        assert len(hits) == 1
    raw_notes = _raw_cells(path, "revisits", "notes")
    assert all("Discussed" not in cell for cell in raw_notes)
    raw_aliases = _raw_cells(path, "revisits", "name_alias")
    assert all("Alex Doe" not in cell for cell in raw_aliases)


# ── Session memory ─────────────────────────────────────────────────────


def test_session_memory_encrypted_text() -> None:
    path = _tmp()
    enc = FieldEncryptor(key=generate_key())
    with SessionMemory(path, encryptor=enc) as mem:
        mem.add(MemoryEntry(user_id="me", kind="topic", text="Trinity", metadata={"hint": "doctrinal"}))
        items = mem.recent("me")
        assert items[0].text == "Trinity"
        assert items[0].metadata == {"hint": "doctrinal"}
    raw_text = _raw_cells(path, "memory", "text")
    assert all("Trinity" not in cell for cell in raw_text)
