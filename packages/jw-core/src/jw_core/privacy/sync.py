"""End-to-end encrypted sync between devices (Gap 14).

Protocol summary:

  1. **Pairing** — device A generates a passphrase and shows a QR code
     containing the URL-safe Fernet key derived from it (or the raw key).
     Device B scans the QR (or reads the passphrase in) and derives the
     same key.

  2. **Export** — every store on the device is dumped to a self-contained
     JSON envelope, encrypted with the shared key, and written to a single
     file (`bundle.jws`).

  3. **Import** — receiving device decrypts the envelope and applies it
     row-by-row (last-write-wins by `updated_at_unix`).

  4. **Transport** — entirely up to the user. We provide the cipher; the
     bytes can travel via AirDrop, USB, email attachment, Telegram secret
     chat, etc.

The envelope is forward-compatible (`schema_version` + `stores` dict).
"""

from __future__ import annotations

import io
import json
import logging
import sqlite3
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jw_core.privacy.encryption import FieldEncryptor, EncryptionError, generate_key

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ENVELOPE_MAGIC = "jws/v1"


@dataclass
class SyncEnvelope:
    schema_version: int
    created_at_unix: float
    stores: dict[str, list[dict[str, Any]]]
    metadata: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "magic": ENVELOPE_MAGIC,
                "schema_version": self.schema_version,
                "created_at_unix": self.created_at_unix,
                "stores": self.stores,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> SyncEnvelope:
        data = json.loads(raw)
        if data.get("magic") != ENVELOPE_MAGIC:
            raise ValueError("not a jw-sync envelope")
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            created_at_unix=float(data.get("created_at_unix", 0.0)),
            stores=data.get("stores", {}),
            metadata=data.get("metadata", {}),
        )


# ── Export ──────────────────────────────────────────────────────────────


def export_envelope(
    db_paths: dict[str, Path | str],
    *,
    metadata: dict[str, Any] | None = None,
) -> SyncEnvelope:
    """Dump rows from each SQLite file in `db_paths` into an envelope.

    `db_paths` maps a friendly store name (e.g. "notes") to its DB file.
    Every primary table in the DB is exported (we discover via
    sqlite_master).
    """
    stores: dict[str, list[dict[str, Any]]] = {}
    for name, raw_path in db_paths.items():
        path = Path(raw_path).expanduser()
        if not path.exists():
            continue
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'"
                )
            ]
            for table in tables:
                rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
                stores[f"{name}:{table}"] = rows
    return SyncEnvelope(
        schema_version=SCHEMA_VERSION,
        created_at_unix=time.time(),
        stores=stores,
        metadata=metadata or {},
    )


def encrypt_envelope(env: SyncEnvelope, encryptor: FieldEncryptor) -> bytes:
    if not encryptor.enabled:
        raise EncryptionError("Sync requires an active key. Set JW_PRIVACY_KEY or pass a key.")
    return encryptor.encrypt(env.to_json()).encode("ascii")


def decrypt_envelope(payload: bytes, encryptor: FieldEncryptor) -> SyncEnvelope:
    if not encryptor.enabled:
        raise EncryptionError("Sync requires an active key.")
    plain = encryptor.decrypt(payload.decode("ascii"))
    return SyncEnvelope.from_json(plain)


def write_bundle(env: SyncEnvelope, dest: Path | str, encryptor: FieldEncryptor) -> Path:
    dest_p = Path(dest).expanduser()
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    dest_p.write_bytes(encrypt_envelope(env, encryptor))
    return dest_p


def read_bundle(path: Path | str, encryptor: FieldEncryptor) -> SyncEnvelope:
    return decrypt_envelope(Path(path).expanduser().read_bytes(), encryptor)


# ── Import (last-write-wins) ────────────────────────────────────────────


def merge_into_databases(
    env: SyncEnvelope,
    db_paths: dict[str, Path | str],
    *,
    timestamp_column: str = "updated_at_unix",
) -> dict[str, int]:
    """Apply rows from `env` to each named DB. Returns rows-applied count per store."""
    applied: dict[str, int] = {}
    for full_name, rows in env.stores.items():
        store_name, _, table_name = full_name.partition(":")
        if not table_name:
            continue
        path = db_paths.get(store_name)
        if path is None:
            continue
        path_p = Path(path).expanduser()
        if not path_p.exists():
            logger.warning("Skipping %s: target DB %s missing", store_name, path_p)
            continue
        count = 0
        with sqlite3.connect(path_p) as conn:
            for row in rows:
                # Detect primary key column
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})")]
                pks = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})") if r[5]]
                pk = pks[0] if pks else cols[0]
                # Compare timestamps when both have the column.
                if timestamp_column in row and timestamp_column in cols:
                    cur = conn.execute(
                        f"SELECT {timestamp_column} FROM {table_name} WHERE {pk} = ?",
                        (row.get(pk),),
                    ).fetchone()
                    if cur and cur[0] and float(cur[0]) >= float(row.get(timestamp_column, 0)):
                        continue
                placeholders = ", ".join("?" for _ in cols)
                cleaned = {c: row.get(c) for c in cols}
                conn.execute(
                    f"INSERT OR REPLACE INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})",
                    [cleaned[c] for c in cols],
                )
                count += 1
            conn.commit()
        applied[full_name] = count
    return applied
