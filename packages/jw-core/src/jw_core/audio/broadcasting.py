"""JW Broadcasting (tv.jw.org) — search over subtitle/transcription text.

`PubMediaClient.get_publication(..., file_format="MP4")` already returns
files with `subtitle_url` for VTT subtitles. We don't re-implement that
fetch — we provide:

  1. A subtitle parser (WebVTT → segments with start/end/text).
  2. A tiny SQLite index that stores segments and supports full-text
     search across many videos.

VISION.md item #3: "Búsqueda en transcripciones de JW Broadcasting".
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VTTSegment:
    start: float
    end: float
    text: str


@dataclass
class IndexedVideo:
    video_id: str
    title: str = ""
    language: str = "en"
    duration_seconds: float = 0.0
    source_url: str = ""
    subtitle_url: str = ""
    segments: list[VTTSegment] = field(default_factory=list)


# ── WebVTT parser ────────────────────────────────────────────────────────


_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)


def parse_vtt(vtt_text: str) -> list[VTTSegment]:
    """Parse WebVTT/SRT text into a list of segments. Forgiving of variants."""
    segments: list[VTTSegment] = []
    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _TIMESTAMP_RE.search(line)
        if not m:
            i += 1
            continue
        start = _to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        i += 1
        text_parts: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_parts.append(_strip_tags(lines[i].strip()))
            i += 1
        text = " ".join(text_parts).strip()
        if text:
            segments.append(VTTSegment(start=start, end=end, text=text))
    return segments


def _to_seconds(hh: str, mm: str, ss: str, ms: str) -> float:
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text)


# ── SQLite FTS5 index ────────────────────────────────────────────────────


def _default_index_path() -> Path:
    return Path(os.getenv("JW_BROADCASTING_INDEX", "~/.jw-agent-toolkit/broadcasting.db")).expanduser()


class BroadcastingIndex:
    """Tiny FTS5-backed index over JW Broadcasting subtitle segments."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        duration_seconds REAL NOT NULL DEFAULT 0,
        source_url TEXT NOT NULL DEFAULT '',
        subtitle_url TEXT NOT NULL DEFAULT ''
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS segments USING fts5(
        video_id UNINDEXED,
        start UNINDEXED,
        end UNINDEXED,
        text,
        language UNINDEXED
    );
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path).expanduser() if path else _default_index_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def index_video(self, video: IndexedVideo) -> int:
        self._conn.execute(
            "INSERT OR REPLACE INTO videos "
            "(video_id, title, language, duration_seconds, source_url, subtitle_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                video.video_id,
                video.title,
                video.language,
                video.duration_seconds,
                video.source_url,
                video.subtitle_url,
            ),
        )
        self._conn.execute("DELETE FROM segments WHERE video_id = ?", (video.video_id,))
        for seg in video.segments:
            self._conn.execute(
                "INSERT INTO segments (video_id, start, end, text, language) VALUES (?, ?, ?, ?, ?)",
                (video.video_id, seg.start, seg.end, seg.text, video.language),
            )
        self._conn.commit()
        return len(video.segments)

    def search(self, query: str, *, language: str | None = None, top_k: int = 10) -> list[dict[str, object]]:
        sql = (
            "SELECT s.video_id, s.start, s.end, s.text, v.title, v.source_url, v.language "
            "FROM segments s LEFT JOIN videos v ON v.video_id = s.video_id "
            "WHERE segments MATCH ? "
        )
        params: list[object] = [query]
        if language:
            sql += "AND s.language = ? "
            params.append(language)
        sql += "ORDER BY rank LIMIT ?"
        params.append(top_k)
        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        return [
            {
                "video_id": r["video_id"],
                "start": r["start"],
                "end": r["end"],
                "text": r["text"],
                "title": r["title"],
                "source_url": r["source_url"],
                "language": r["language"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, int]:
        videos = self._conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        segments = self._conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        return {"videos": videos, "segments": segments}

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> BroadcastingIndex:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def index_vtt_file(
    index: BroadcastingIndex,
    vtt_path: Path | str,
    *,
    video_id: str,
    title: str = "",
    language: str = "en",
    source_url: str = "",
) -> int:
    """Convenience: parse a VTT file and add it to the index."""
    text = Path(vtt_path).read_text(encoding="utf-8")
    segments = parse_vtt(text)
    duration = segments[-1].end if segments else 0.0
    return index.index_video(
        IndexedVideo(
            video_id=video_id,
            title=title,
            language=language,
            duration_seconds=duration,
            source_url=source_url,
            subtitle_url=str(vtt_path),
            segments=segments,
        )
    )


def deeplink_for_segment(source_url: str, start: float) -> str:
    """Append `?t=Ns` to a JW Broadcasting URL."""
    seconds = int(start)
    if "?" in source_url:
        return f"{source_url}&t={seconds}s"
    return f"{source_url}?t={seconds}s"
