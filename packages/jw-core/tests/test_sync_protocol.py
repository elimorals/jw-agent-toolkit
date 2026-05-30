"""Tests for the E2E sync protocol (Gap 14)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

cryptography = pytest.importorskip("cryptography")

from jw_core.privacy.encryption import FieldEncryptor, generate_key
from jw_core.privacy.sync import (
    SCHEMA_VERSION,
    SyncEnvelope,
    decrypt_envelope,
    encrypt_envelope,
    export_envelope,
    merge_into_databases,
    read_bundle,
    write_bundle,
)


def _make_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE notes (note_id TEXT PRIMARY KEY, body TEXT, updated_at_unix REAL)"
        )
        conn.executescript(
            """
            INSERT INTO notes VALUES ('a', 'first body', 100.0);
            INSERT INTO notes VALUES ('b', 'second body', 200.0);
            """
        )


def test_envelope_export_includes_rows() -> None:
    tmp = Path(tempfile.mkdtemp())
    _make_db(tmp / "n.db")
    env = export_envelope({"notes": tmp / "n.db"})
    assert env.schema_version == SCHEMA_VERSION
    rows = env.stores["notes:notes"]
    assert len(rows) == 2
    assert any(r["note_id"] == "a" for r in rows)


def test_envelope_roundtrip_through_encryption() -> None:
    tmp = Path(tempfile.mkdtemp())
    _make_db(tmp / "n.db")
    env = export_envelope({"notes": tmp / "n.db"})
    key = generate_key()
    enc = FieldEncryptor(key=key)
    blob = encrypt_envelope(env, enc)
    assert isinstance(blob, bytes)
    decoded = decrypt_envelope(blob, FieldEncryptor(key=key))
    assert decoded.stores["notes:notes"][0]["body"] in ("first body", "second body")


def test_merge_prefers_newer_timestamps() -> None:
    src_tmp = Path(tempfile.mkdtemp())
    dst_tmp = Path(tempfile.mkdtemp())
    _make_db(src_tmp / "n.db")
    _make_db(dst_tmp / "n.db")
    # Update destination to be newer for note 'a'.
    with sqlite3.connect(dst_tmp / "n.db") as conn:
        conn.execute("UPDATE notes SET body=?, updated_at_unix=? WHERE note_id=?", ("dst version", 500.0, "a"))

    # Modify source to be older for 'a' but newer for 'b'.
    with sqlite3.connect(src_tmp / "n.db") as conn:
        conn.execute("UPDATE notes SET body=?, updated_at_unix=? WHERE note_id=?", ("src OLD a", 50.0, "a"))
        conn.execute("UPDATE notes SET body=?, updated_at_unix=? WHERE note_id=?", ("src NEW b", 999.0, "b"))

    env = export_envelope({"notes": src_tmp / "n.db"})
    applied = merge_into_databases(env, {"notes": dst_tmp / "n.db"})
    assert applied["notes:notes"] == 1  # only b applied

    with sqlite3.connect(dst_tmp / "n.db") as conn:
        a_body = conn.execute("SELECT body FROM notes WHERE note_id='a'").fetchone()[0]
        b_body = conn.execute("SELECT body FROM notes WHERE note_id='b'").fetchone()[0]
    assert a_body == "dst version"  # destination wins
    assert b_body == "src NEW b"  # source wins


def test_write_and_read_bundle_roundtrip() -> None:
    tmp = Path(tempfile.mkdtemp())
    _make_db(tmp / "n.db")
    env = export_envelope({"notes": tmp / "n.db"}, metadata={"source": "phone"})
    key = generate_key()
    enc = FieldEncryptor(key=key)
    bundle = tmp / "out.jws"
    write_bundle(env, bundle, enc)
    again = read_bundle(bundle, FieldEncryptor(key=key))
    assert again.metadata == {"source": "phone"}
    assert again.stores
