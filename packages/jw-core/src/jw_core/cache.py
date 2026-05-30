"""SQLite-backed disk cache with TTL.

Used by HTTP clients to avoid re-fetching responses within their freshness
window. The store is process-safe (SQLite's own locking) so multiple
clients in the same process share state.

Schema:
    cache(key TEXT PRIMARY KEY, value BLOB, expires_at REAL)

Where `expires_at` is a Unix timestamp (`time.time()`); a row is stale
once `time.time() > expires_at`. Stale rows survive until the next
opportunistic `cleanup_expired()` (or manual `clear()`).

The cache stores bytes; callers serialize their own values (JSON, pickle,
HTML text). Encoding/decoding is intentionally out of scope.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class DiskCache:
    """A simple TTL cache backed by SQLite.

    Args:
        path: file path for the SQLite DB. Created if missing.
        default_ttl_seconds: TTL used when `set()` is called without
            explicit TTL. Default 1 hour.
    """

    def __init__(
        self,
        path: Path | str = "~/.jw-agent-toolkit/cache.db",
        *,
        default_ttl_seconds: float = 3600.0,
    ) -> None:
        self.path = Path(path).expanduser()
        self.default_ttl_seconds = default_ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        # WAL keeps reads fast under concurrent writes.
        self._conn.execute("PRAGMA journal_mode=WAL")

    def get(self, key: str) -> bytes | None:
        """Return the bytes value, or None if missing/expired."""
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, expires_at = row
        if time.time() > expires_at:
            # Lazy eviction.
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            return None
        return value

    def set(
        self, key: str, value: bytes, *, ttl_seconds: float | None = None
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.time() + ttl
        self._conn.execute(
            "INSERT OR REPLACE INTO cache(key, value, expires_at) VALUES (?, ?, ?)",
            (key, value, expires_at),
        )

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache")

    def cleanup_expired(self) -> int:
        """Remove rows past their TTL. Returns the number deleted."""
        cur = self._conn.execute(
            "DELETE FROM cache WHERE expires_at < ?", (time.time(),)
        )
        return cur.rowcount or 0

    def stats(self) -> dict[str, int]:
        total = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        live = self._conn.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at >= ?", (time.time(),)
        ).fetchone()[0]
        return {"total": total, "live": live, "expired": total - live}

    def close(self) -> None:
        self._conn.close()

    # Allow use as a context manager for tests / short-lived scripts.
    def __enter__(self) -> "DiskCache":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
