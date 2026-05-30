"""SQLite-backed disk cache with TTL.

Used by HTTP clients to avoid re-fetching responses within their freshness
window. Thread-safe: connection is shared across threads with
`check_same_thread=False` and access is serialized via a `threading.Lock`.
SQLite's own WAL locking handles cross-process safety.

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
import threading
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
        # check_same_thread=False allows the connection object to be used
        # from multiple threads; we serialize access ourselves with a Lock
        # so SQLite's own per-statement locking doesn't surprise us.
        self._conn = sqlite3.connect(
            self.path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._lock = threading.Lock()
        with self._lock:
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
        with self._lock:
            row = self._conn.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,)).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if time.time() > expires_at:
                # Lazy eviction.
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            return value

    def set(self, key: str, value: bytes, *, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.time() + ttl
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache(key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at),
            )

    def delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache")

    def cleanup_expired(self) -> int:
        """Remove rows past their TTL. Returns the number deleted."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
            return cur.rowcount or 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            live = self._conn.execute("SELECT COUNT(*) FROM cache WHERE expires_at >= ?", (time.time(),)).fetchone()[0]
        return {"total": total, "live": live, "expired": total - live}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # Allow use as a context manager for tests / short-lived scripts.
    def __enter__(self) -> DiskCache:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
