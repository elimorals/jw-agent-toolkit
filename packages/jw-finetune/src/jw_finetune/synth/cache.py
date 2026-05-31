"""SQLite-backed cache for synthesized Q&A pairs.

Cache key = SHA256(chunk_id + chunk_text + qa_style + language + n_pairs +
                   provider_name + model).

The cache lives in `~/.cache/jw-finetune/synth.db` by default. Rerunning
`jw-finetune prepare` with the same chunks + recipe is a no-op (hot cache),
which lets users tweak training hyperparams without re-paying for Q&A
synthesis. The cache stores the JSON-serialized list of QAPairs.

Why SQLite and not JSON-on-disk? Two reasons:
  1. Concurrent prepare runs (async with semaphore) need atomic writes.
  2. We want to query by hash without loading the whole file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from jw_finetune.data.formats import QAPair

logger = logging.getLogger(__name__)


def _default_cache_path() -> Path:
    base = Path.home() / ".cache" / "jw-finetune"
    base.mkdir(parents=True, exist_ok=True)
    return base / "synth.db"


def _hash_key(
    *,
    chunk_id: str,
    chunk_text: str,
    qa_style: str,
    language: str,
    n_pairs: int,
    provider_name: str,
    provider_model: str,
) -> str:
    h = hashlib.sha256()
    for part in (
        chunk_id,
        chunk_text,
        qa_style,
        language,
        str(n_pairs),
        provider_name,
        provider_model,
    ):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class SynthCache:
    """Persistent cache of synthesized Q&A results keyed by (chunk, params)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else _default_cache_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS synth_results (
                    key TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    qa_style TEXT NOT NULL,
                    language TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    pairs_json TEXT NOT NULL,
                    n_pairs INTEGER NOT NULL,
                    n_rejected INTEGER NOT NULL DEFAULT 0,
                    created_ts REAL NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_synth_chunk ON synth_results(chunk_id)")
            db.commit()

    def get(self, key: str) -> list[QAPair] | None:
        with closing(sqlite3.connect(str(self.path))) as db:
            row = db.execute("SELECT pairs_json FROM synth_results WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return [
            QAPair(
                question=d["question"],
                answer=d["answer"],
                source_chunk_id=d["source_chunk_id"],
                language=d["language"],
                metadata={k: str(v) for k, v in (d.get("metadata") or {}).items()},
            )
            for d in data
        ]

    def put(
        self,
        key: str,
        pairs: Iterable[QAPair],
        *,
        chunk_id: str,
        qa_style: str,
        language: str,
        provider: str,
        n_rejected: int = 0,
    ) -> None:
        pairs_list = list(pairs)
        payload = json.dumps(
            [
                {
                    "question": p.question,
                    "answer": p.answer,
                    "source_chunk_id": p.source_chunk_id,
                    "language": p.language,
                    "metadata": dict(p.metadata),
                }
                for p in pairs_list
            ],
            ensure_ascii=False,
        )
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute(
                "INSERT OR REPLACE INTO synth_results "
                "(key, chunk_id, qa_style, language, provider, "
                "pairs_json, n_pairs, n_rejected, created_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    chunk_id,
                    qa_style,
                    language,
                    provider,
                    payload,
                    len(pairs_list),
                    n_rejected,
                    time.time(),
                ),
            )
            db.commit()

    def stats(self) -> dict[str, int]:
        with closing(sqlite3.connect(str(self.path))) as db:
            row = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(n_pairs), 0), COALESCE(SUM(n_rejected), 0) FROM synth_results"
            ).fetchone()
        return {
            "entries": row[0],
            "total_pairs": row[1],
            "total_rejected": row[2],
        }

    def clear(self) -> int:
        with closing(sqlite3.connect(str(self.path))) as db:
            cur = db.execute("SELECT COUNT(*) FROM synth_results")
            n = cur.fetchone()[0]
            db.execute("DELETE FROM synth_results")
            db.commit()
        return n


def cache_key_for(
    chunk_id: str,
    chunk_text: str,
    qa_style: str,
    language: str,
    n_pairs: int,
    provider_name: str,
    provider_model: str,
) -> str:
    """Public helper to compute the cache key for a given synth call."""
    return _hash_key(
        chunk_id=chunk_id,
        chunk_text=chunk_text,
        qa_style=qa_style,
        language=language,
        n_pairs=n_pairs,
        provider_name=provider_name,
        provider_model=provider_model,
    )
