"""VoiceprintStore: sqlite con embeddings de voz."""

from __future__ import annotations

import sqlite3

import numpy as np

from jw_core.audio.speakers.voiceprint_store import Voiceprint, VoiceprintStore


def test_save_and_load_voiceprint(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    embedding = np.random.randn(192).astype(np.float32)
    store.save(
        Voiceprint(
            name="Hno Pablo",
            embedding=embedding,
            enrolled_at_iso="2026-06-05T10:00:00Z",
        )
    )
    voiceprints = store.list_all()
    assert len(voiceprints) == 1
    assert voiceprints[0].name == "Hno Pablo"
    np.testing.assert_allclose(voiceprints[0].embedding, embedding, rtol=1e-5)


def test_delete_by_name(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    emb1 = np.random.randn(192).astype(np.float32)
    emb2 = np.random.randn(192).astype(np.float32)
    store.save(Voiceprint(name="A", embedding=emb1, enrolled_at_iso="2026-06-05T10:00:00Z"))
    store.save(Voiceprint(name="B", embedding=emb2, enrolled_at_iso="2026-06-05T10:01:00Z"))
    n = store.delete("A")
    assert n == 1
    assert {vp.name for vp in store.list_all()} == {"B"}


def test_encrypted_with_fernet_key(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JW_VOICEPRINT_KEY", key)
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    emb = np.random.randn(192).astype(np.float32)
    store.save(
        Voiceprint(
            name="SENSITIVE",
            embedding=emb,
            enrolled_at_iso="2026-06-05T10:00:00Z",
        )
    )
    # Raw bytes should not contain "SENSITIVE" plaintext
    conn = sqlite3.connect(tmp_path / "vp.db")
    row = conn.execute("SELECT name_blob FROM voiceprints").fetchone()
    raw = row[0]
    assert b"SENSITIVE" not in raw
    # Roundtrip via load
    loaded = store.list_all()
    assert loaded[0].name == "SENSITIVE"
    np.testing.assert_allclose(loaded[0].embedding, emb, rtol=1e-5)


def test_unencrypted_default(tmp_path, monkeypatch):
    """Without JW_VOICEPRINT_KEY env, store works in plaintext mode."""
    monkeypatch.delenv("JW_VOICEPRINT_KEY", raising=False)
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    emb = np.random.randn(192).astype(np.float32)
    store.save(Voiceprint(name="Plain", embedding=emb, enrolled_at_iso="2026-06-05T10:00:00Z"))
    loaded = store.list_all()
    assert loaded[0].name == "Plain"


def test_delete_missing_returns_zero(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    assert store.delete("nobody") == 0


def test_default_db_path_uses_env(tmp_path, monkeypatch):
    """JW_VOICEPRINT_DB env var redirects the default db path."""
    target = tmp_path / "custom" / "vp.db"
    monkeypatch.setenv("JW_VOICEPRINT_DB", str(target))
    store = VoiceprintStore()
    emb = np.random.randn(8).astype(np.float32)
    store.save(Voiceprint(name="X", embedding=emb, enrolled_at_iso="2026-06-05T10:00:00Z"))
    assert target.exists()
