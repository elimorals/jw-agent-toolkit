"""In-memory MemoryStore para tests y default."""
from __future__ import annotations

from jw_agents.memory.protocol import MemoryKind, MemoryRecord


class FakeMemoryStore:
    """In-memory store. No persistencia entre instancias."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def record(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        results = self._records
        if session_id is not None:
            results = [r for r in results if r.session_id == session_id]
        if kind is not None:
            results = [r for r in results if r.kind == kind]
        if query is not None:
            q = query.lower()
            results = [r for r in results if q in r.content.lower()]
            results.sort(
                key=lambda r: r.content.lower().count(q),
                reverse=True,
            )
        else:
            results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def list_sessions(self) -> list[str]:
        return list({r.session_id for r in self._records})

    def forget(self, session_id: str) -> int:
        before = len(self._records)
        self._records = [r for r in self._records if r.session_id != session_id]
        return before - len(self._records)
