"""VisualIndexer: builds a SQLite + numpy index over sampled frames (Fase 69).

Storage layout under `<root>`:

    index.sqlite         frames table + FTS5 over caption||ocr||transcript
    vectors.npy          (N, dim) float32 normalized CLIP embeddings
    meta.json            provider versions, dim, count

Frames themselves are NEVER stored; thumbs are optional and JPEG-encoded
at 256x144 to keep disk usage bounded.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from jw_core.broadcasting.visual.models import IndexStats, VisualFrame

logger = logging.getLogger(__name__)


class VisualIndexer:
    """SQLite + numpy-backed visual index over (video_id, frames)."""

    def __init__(
        self,
        root: Path | str,
        *,
        embedding_dim: int = 64,
        vlm_name: str = "fake-vlm",
        clip_name: str = "fake-clip",
    ) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._embedding_dim = embedding_dim
        self._sqlite_path = self._root / "index.sqlite"
        self._vectors_path = self._root / "vectors.npy"
        self._meta_path = self._root / "meta.json"
        self._thumbs_dir = self._root / "thumbs"
        self._conn = sqlite3.connect(self._sqlite_path)
        self._init_schema()
        self._write_meta(vlm_name=vlm_name, clip_name=clip_name)

    # ---- schema / meta -------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS frames (
                embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                timestamp_s REAL NOT NULL,
                caption TEXT NOT NULL,
                ocr_text TEXT DEFAULT '',
                thumb_path TEXT DEFAULT NULL,
                transcript_concurrent TEXT DEFAULT ''
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS frames_video ON frames(video_id)"
        )
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                caption,
                ocr_text,
                transcript_concurrent,
                content='frames',
                content_rowid='embedding_id'
            )
            """
        )
        self._conn.commit()

    def _write_meta(self, *, vlm_name: str, clip_name: str) -> None:
        meta = {
            "embedding_dim": self._embedding_dim,
            "vlm_name": vlm_name,
            "clip_name": clip_name,
        }
        self._meta_path.write_text(json.dumps(meta, indent=2))

    # ---- ingest --------------------------------------------------------

    def add_frame(
        self,
        *,
        video_id: str,
        timestamp_s: float,
        caption: str,
        embedding: list[float],
        ocr_text: str = "",
        thumb_path: str | None = None,
        transcript_concurrent: str = "",
    ) -> int:
        """Add one frame and its embedding. Returns the assigned embedding_id."""

        if len(embedding) != self._embedding_dim:
            raise ValueError(
                f"embedding dim mismatch: got {len(embedding)}, "
                f"expected {self._embedding_dim}"
            )

        cur = self._conn.execute(
            "INSERT INTO frames "
            "(video_id, timestamp_s, caption, ocr_text, thumb_path, "
            "transcript_concurrent) VALUES (?, ?, ?, ?, ?, ?)",
            (
                video_id,
                float(timestamp_s),
                caption,
                ocr_text,
                thumb_path,
                transcript_concurrent,
            ),
        )
        embedding_id = int(cur.lastrowid)
        self._conn.execute(
            "INSERT INTO frames_fts (rowid, caption, ocr_text, transcript_concurrent) "
            "VALUES (?, ?, ?, ?)",
            (embedding_id, caption, ocr_text, transcript_concurrent),
        )
        self._conn.commit()

        self._append_embedding(np.asarray(embedding, dtype=np.float32))
        return embedding_id

    def _append_embedding(self, vec: np.ndarray) -> None:
        if self._vectors_path.exists():
            existing = np.load(self._vectors_path)
            new = np.vstack([existing, vec.reshape(1, -1)])
        else:
            new = vec.reshape(1, -1)
        np.save(self._vectors_path, new.astype(np.float32))

    def add_frames(self, frames: Iterable[tuple[VisualFrame, list[float]]]) -> int:
        """Bulk add. Returns count added."""
        n = 0
        for frame, emb in frames:
            self.add_frame(
                video_id=frame.video_id,
                timestamp_s=frame.timestamp_s,
                caption=frame.caption,
                embedding=emb,
                ocr_text=frame.ocr_text,
                thumb_path=frame.thumb_path,
                transcript_concurrent=frame.transcript_concurrent,
            )
            n += 1
        return n

    # ---- stats / inspection -------------------------------------------

    def stats(self) -> IndexStats:
        cur = self._conn.execute(
            "SELECT COUNT(DISTINCT video_id), COUNT(*) FROM frames"
        )
        videos, frames = cur.fetchone()
        videos = int(videos or 0)
        frames = int(frames or 0)
        storage_bytes = 0
        for p in (self._sqlite_path, self._vectors_path, self._meta_path):
            if p.exists():
                storage_bytes += p.stat().st_size
        if self._thumbs_dir.exists():
            for p in self._thumbs_dir.rglob("*"):
                if p.is_file():
                    storage_bytes += p.stat().st_size
        avg = (frames / videos) if videos else 0.0
        return IndexStats(
            videos_indexed=videos,
            frames_total=frames,
            embeddings_dim=self._embedding_dim,
            storage_mb=storage_bytes / (1024 * 1024),
            avg_frame_per_video=avg,
        )

    def load_vectors(self) -> np.ndarray:
        if not self._vectors_path.exists():
            return np.zeros((0, self._embedding_dim), dtype=np.float32)
        return np.load(self._vectors_path).astype(np.float32)

    def list_frames(
        self, *, video_id: str | None = None
    ) -> list[VisualFrame]:
        if video_id:
            cur = self._conn.execute(
                "SELECT embedding_id, video_id, timestamp_s, caption, "
                "ocr_text, thumb_path, transcript_concurrent "
                "FROM frames WHERE video_id = ? ORDER BY timestamp_s",
                (video_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT embedding_id, video_id, timestamp_s, caption, "
                "ocr_text, thumb_path, transcript_concurrent "
                "FROM frames ORDER BY video_id, timestamp_s"
            )
        out: list[VisualFrame] = []
        for row in cur:
            out.append(
                VisualFrame(
                    embedding_id=int(row[0]),
                    video_id=row[1],
                    timestamp_s=float(row[2]),
                    caption=row[3],
                    ocr_text=row[4] or "",
                    thumb_path=row[5],
                    transcript_concurrent=row[6] or "",
                )
            )
        return out

    def close(self) -> None:
        self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        """Expose connection for the hybrid_search module."""
        return self._conn

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim
