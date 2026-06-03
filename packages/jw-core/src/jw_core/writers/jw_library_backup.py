"""Writer for `.jwlibrary` backup archives — inverse of `parsers.jw_library_backup`.

Lets a caller (re)produce a `.jwlibrary` archive from a `userData.db` SQLite
file. The two main use cases are:

  1. **Round-trip edit**: extract → modify → repack. Use `update_backup()` —
     opens an existing archive, lets you run callbacks against the SQLite
     connection, then writes a new archive with refreshed manifest + hash.

  2. **Build from scratch**: caller already has a complete `userData.db`
     (e.g. constructed by an agent that wrote notes/highlights). Use
     `write_backup()` directly.

Algorithm ported from `erykjj/jwlmanager` (MIT, Python). The merge logic
of jwlmanager lives in a closed-source binary (`libjwlCore.*`) — not
ported here. This module covers only the export/packaging side.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "BackupWriteError",
    "update_backup",
    "write_backup",
]


class BackupWriteError(RuntimeError):
    """Raised when a `.jwlibrary` can't be written."""


_APP_NAME = "jw-core"


def write_backup(
    out_path: Path | str,
    *,
    user_data_db_path: Path | str,
    device_name: str | None = None,
    creation_date: str | None = None,
    schema_version_fallback: int = 16,
) -> Path:
    """Package an existing `userData.db` as a `.jwlibrary` archive.

    The manifest's `schemaVersion` is taken from `PRAGMA user_version` on
    the DB; `schema_version_fallback` is used only if that pragma returns 0.
    The manifest's `hash` is SHA-256 of the SQLite file bytes (as JW Library
    produces).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    db_path = Path(user_data_db_path)
    if not db_path.is_file():
        raise BackupWriteError(f"userData db not found: {db_path}")

    now_iso = creation_date or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Stamp the LastModified table (best-effort: the table is optional in
    # very old schemas; we silently skip it if absent so the writer still
    # works against synthesized fixtures).
    with closing(sqlite3.connect(db_path)) as conn:
        with suppress(sqlite3.OperationalError):
            conn.execute("UPDATE LastModified SET LastModified = ?", (now_iso,))
            conn.commit()
        row = conn.execute("PRAGMA user_version;").fetchone()
        schema_version = (row[0] if row else 0) or schema_version_fallback

    db_bytes = db_path.read_bytes()
    db_hash = hashlib.sha256(db_bytes).hexdigest()

    manifest = {
        "name": _APP_NAME,
        "creationDate": now_iso,
        "version": 1,
        "type": 0,
        "userDataBackup": {
            "lastModifiedDate": now_iso,
            "deviceName": device_name or _APP_NAME,
            "databaseName": "userData.db",
            "hash": db_hash,
            "schemaVersion": schema_version,
        },
    }
    manifest_bytes = json.dumps(manifest, indent=None, separators=(",", ":")).encode("utf-8")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("userData.db", db_bytes)
    return out_path


def update_backup(
    in_path: Path | str,
    out_path: Path | str,
    modify_fn: Callable[[sqlite3.Connection], None] | None = None,
    *,
    device_name: str | None = None,
) -> Path:
    """Extract `in_path`, optionally run `modify_fn(conn)` on the SQLite, repack to `out_path`.

    `modify_fn` is called inside a `sqlite3.Connection` to the extracted DB.
    Commits are handled by the caller (we commit defensively at the end too).
    If `modify_fn is None`, this is effectively a re-stamp of the manifest.
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if not in_path.is_file():
        raise BackupWriteError(f"input archive not found: {in_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(in_path) as zin:
                zin.extractall(tmp_path)
        except zipfile.BadZipFile as e:
            raise BackupWriteError(f"input archive is not a valid ZIP: {in_path}") from e
        db_path = tmp_path / "userData.db"
        if not db_path.is_file():
            # Some manifests rename the DB; honor that.
            manifest_path = tmp_path / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                db_name = manifest.get("userDataBackup", {}).get("databaseName", "userData.db")
                db_path = tmp_path / db_name
        if not db_path.is_file():
            raise BackupWriteError(f"userData db missing from archive: {in_path}")

        if modify_fn is not None:
            with closing(sqlite3.connect(db_path)) as conn:
                modify_fn(conn)
                conn.commit()

        # Stage the resulting DB to its final write location.
        staged_db = tmp_path / "userData.db"
        if db_path != staged_db:
            shutil.copyfile(db_path, staged_db)

        return write_backup(out_path, user_data_db_path=staged_db, device_name=device_name)
