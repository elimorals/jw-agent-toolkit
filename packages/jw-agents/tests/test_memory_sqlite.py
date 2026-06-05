"""F61 — SqliteMemoryStore con Fernet opt-in."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from jw_agents.memory import MemoryRecord, SqliteMemoryStore


def test_sqlite_persists_across_instances(tmp_path):
    db = tmp_path / "memory.db"
    store1 = SqliteMemoryStore(db_path=db)
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(UTC),
        kind="question",
        content="¿Por qué los TJ no celebran cumpleaños?",
        metadata={"lang": "es"},
    )
    store1.record(record)

    # Nueva instancia: debe leer del mismo db
    store2 = SqliteMemoryStore(db_path=db)
    hits = store2.recall(session_id="s1")
    assert len(hits) == 1
    assert hits[0].content == record.content


def test_sqlite_recall_with_substring_query(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(UTC)
    store.record(MemoryRecord("s1", base, "answer", "La Trinidad no es bíblica", {}))
    store.record(MemoryRecord("s1", base, "answer", "El alma no es inmortal", {}))
    hits = store.recall(session_id="s1", query="Trinidad")
    assert len(hits) == 1
    assert "Trinidad" in hits[0].content


def test_sqlite_recall_kind_filter(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(UTC)
    store.record(MemoryRecord("s1", base, "question", "q1", {}))
    store.record(MemoryRecord("s1", base, "preference", "español", {}))
    prefs = store.recall(session_id="s1", kind="preference")
    assert len(prefs) == 1 and prefs[0].kind == "preference"


def test_sqlite_forget_returns_count(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(UTC)
    for i in range(3):
        store.record(MemoryRecord("s1", base, "question", f"q{i}", {}))
    n = store.forget("s1")
    assert n == 3


def test_sqlite_encrypted_with_fernet_key(tmp_path, monkeypatch):
    """Con JW_MEMORY_KEY presente, content se almacena cifrado."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JW_MEMORY_KEY", key)
    db = tmp_path / "memory.db"
    store = SqliteMemoryStore(db_path=db)
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(UTC),
        kind="answer",
        content="Información sensible del usuario",
        metadata={},
    )
    store.record(record)

    # Leer raw del sqlite: NO debe contener el plaintext
    import sqlite3
    conn = sqlite3.connect(db)
    raw = conn.execute("SELECT content FROM records").fetchone()[0]
    assert "Información sensible" not in raw.decode("utf-8", errors="ignore") \
        if isinstance(raw, bytes) else "Información sensible" not in raw

    # Pero recall normal lo descifra
    hits = store.recall(session_id="s1")
    assert hits[0].content == record.content


def test_sqlite_missing_key_when_db_encrypted_raises(tmp_path, monkeypatch):
    """Si el db tiene records cifrados y la key se pierde, error claro."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JW_MEMORY_KEY", key)
    db = tmp_path / "memory.db"
    store = SqliteMemoryStore(db_path=db)
    store.record(MemoryRecord("s1", datetime.now(UTC), "answer", "secreto", {}))

    monkeypatch.delenv("JW_MEMORY_KEY")
    with pytest.raises(RuntimeError, match="encrypted but JW_MEMORY_KEY"):
        SqliteMemoryStore(db_path=db).recall(session_id="s1")
