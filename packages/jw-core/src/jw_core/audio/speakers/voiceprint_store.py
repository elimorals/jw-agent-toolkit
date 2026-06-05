"""Local sqlite store for voice embeddings.

Patrón privacy-first: opt-in Fernet via `JW_VOICEPRINT_KEY` (precedente F61
memory en `jw_core.privacy.encryption`).

- Sin la env var: el store funciona en texto plano (modo default).
- Con la env var: nombre + embedding se cifran con Fernet por fila.

Schema dual-mode: una bandera `encrypted` por fila permite mezclar registros
heredados en plaintext con nuevos cifrados sin migración destructiva.
"""

from __future__ import annotations

import io
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _default_db_path() -> Path:
    base = Path(os.environ.get("JW_VOICEPRINT_DB", "~/.jw-agent-toolkit/voiceprints.db"))
    return base.expanduser()


def _load_fernet():  # type: ignore[no-untyped-def]
    """Return a Fernet instance if `JW_VOICEPRINT_KEY` is set, else None."""
    key = os.environ.get("JW_VOICEPRINT_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet

    return Fernet(key.encode() if isinstance(key, str) else key)


@dataclass(frozen=True)
class Voiceprint:
    """Embedding de voz enrolado + nombre real de la persona."""

    name: str
    embedding: np.ndarray
    enrolled_at_iso: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS voiceprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_blob BLOB NOT NULL,
    embedding_blob BLOB NOT NULL,
    enrolled_at TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0
);
PRAGMA user_version = 1;
"""


class VoiceprintStore:
    """Sqlite-backed catalog of (name → embedding) entries.

    Multiple voiceprints per name are allowed (different recording
    sessions add fidelity). The mapper picks the highest-similarity
    match across all enrolled prints.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def save(self, vp: Voiceprint) -> None:
        """Persist a voiceprint. Encrypts iff `JW_VOICEPRINT_KEY` is set."""
        fernet = _load_fernet()
        name_bytes = vp.name.encode("utf-8")
        buf = io.BytesIO()
        np.save(buf, vp.embedding, allow_pickle=False)
        emb_bytes = buf.getvalue()
        encrypted = 0
        if fernet is not None:
            name_bytes = fernet.encrypt(name_bytes)
            emb_bytes = fernet.encrypt(emb_bytes)
            encrypted = 1
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO voiceprints (name_blob, embedding_blob, enrolled_at, encrypted) "
                "VALUES (?, ?, ?, ?)",
                (name_bytes, emb_bytes, vp.enrolled_at_iso, encrypted),
            )
            conn.commit()

    def list_all(self) -> list[Voiceprint]:
        """Return every enrolled voiceprint (decrypts on the fly)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT name_blob, embedding_blob, enrolled_at, encrypted FROM voiceprints"
            ).fetchall()
        result: list[Voiceprint] = []
        for name_blob, emb_blob, ts, encrypted in rows:
            if encrypted:
                fernet = _load_fernet()
                if fernet is None:
                    raise RuntimeError(
                        "Database has encrypted rows but JW_VOICEPRINT_KEY is not set"
                    )
                name_blob = fernet.decrypt(name_blob)
                emb_blob = fernet.decrypt(emb_blob)
            name = name_blob.decode("utf-8")
            embedding = np.load(io.BytesIO(emb_blob), allow_pickle=False)
            result.append(
                Voiceprint(name=name, embedding=embedding, enrolled_at_iso=ts)
            )
        return result

    def delete(self, name: str) -> int:
        """Delete all voiceprints for `name`. Returns count deleted.

        Walks rows in Python because encrypted name blobs can't be matched
        via SQL `WHERE`. Cost is O(rows) — acceptable for a personal store
        with O(dozens) of enrolled voices.
        """
        fernet = _load_fernet()
        ids_to_delete: list[int] = []
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, name_blob, encrypted FROM voiceprints"
            ).fetchall()
            for vp_id, name_blob, encrypted in rows:
                if encrypted:
                    if fernet is None:
                        raise RuntimeError(
                            "Database has encrypted rows but JW_VOICEPRINT_KEY is not set"
                        )
                    name_blob = fernet.decrypt(name_blob)
                vp_name = name_blob.decode("utf-8")
                if vp_name == name:
                    ids_to_delete.append(vp_id)
            for vp_id in ids_to_delete:
                conn.execute("DELETE FROM voiceprints WHERE id = ?", (vp_id,))
            conn.commit()
        return len(ids_to_delete)
