"""Session history (opt-in longitudinal tracking)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel


class HistoryRow(BaseModel):
    report_id: str
    recording_hash: str
    part_kind: str
    language: str
    scores: dict[str, int]
    timestamp: str


class SessionHistory:
    """SQLite-backed tracker for talk_lab reports (local-only)."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                recording_hash TEXT NOT NULL,
                part_kind TEXT NOT NULL,
                language TEXT NOT NULL,
                scores_json TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def track(
        self,
        *,
        recording_hash: str,
        report_id: str,
        scores: dict[str, int],
        part_kind: str,
        language: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO reports "
            "(report_id, recording_hash, part_kind, language, scores_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                report_id,
                recording_hash,
                part_kind,
                language,
                json.dumps(scores),
            ),
        )
        self._conn.commit()

    def list(self) -> list[HistoryRow]:
        cur = self._conn.execute(
            "SELECT report_id, recording_hash, part_kind, language, "
            "scores_json, timestamp FROM reports ORDER BY timestamp DESC"
        )
        rows = []
        for r in cur:
            rows.append(
                HistoryRow(
                    report_id=r[0],
                    recording_hash=r[1],
                    part_kind=r[2],
                    language=r[3],
                    scores=json.loads(r[4]),
                    timestamp=r[5],
                )
            )
        return rows

    def compare(
        self, report_id_a: str, report_id_b: str
    ) -> dict[str, int]:
        cur = self._conn.execute(
            "SELECT report_id, scores_json FROM reports WHERE report_id IN (?, ?)",
            (report_id_a, report_id_b),
        )
        a: dict[str, int] = {}
        b: dict[str, int] = {}
        for rid, sj in cur:
            d = json.loads(sj)
            if rid == report_id_a:
                a = d
            else:
                b = d
        return {
            pid: b.get(pid, 0) - a.get(pid, 0) for pid in {*a.keys(), *b.keys()}
        }
