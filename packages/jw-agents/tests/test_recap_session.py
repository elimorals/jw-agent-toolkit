"""F61.8 — recap_previous_session agent."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from jw_agents.memory import FakeMemoryStore, MemoryRecord
from jw_agents.recap_session import recap_previous_session


@pytest.mark.asyncio
async def test_recap_no_history_returns_empty_findings():
    memory = FakeMemoryStore()
    result = await recap_previous_session(memory=memory, current_session_id="new")
    assert result.agent_name == "recap_session"
    assert result.findings == []


@pytest.mark.asyncio
async def test_recap_groups_records_by_session():
    memory = FakeMemoryStore()
    base = datetime.now(timezone.utc)
    # Sesión previa "yesterday"
    memory.record(MemoryRecord("yesterday", base - timedelta(days=1), "question", "¿Trinidad?", {}))
    memory.record(MemoryRecord("yesterday", base - timedelta(days=1), "answer", "No bíblica", {}))
    memory.record(MemoryRecord("yesterday", base - timedelta(days=1), "objection", "Mt 28:19", {}))
    # Sesión "current" no debe aparecer en recap
    memory.record(MemoryRecord("current", base, "question", "actual", {}))

    result = await recap_previous_session(memory=memory, current_session_id="current")
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert "yesterday" in finding.summary
    # Each summary should mention counts or excerpts
    assert "3" in finding.summary or "Trinidad" in finding.summary


@pytest.mark.asyncio
async def test_recap_multiple_previous_sessions_ordered_by_recency():
    memory = FakeMemoryStore()
    base = datetime.now(timezone.utc)
    memory.record(MemoryRecord("old", base - timedelta(days=10), "question", "viejo", {}))
    memory.record(MemoryRecord("recent", base - timedelta(days=1), "question", "reciente", {}))
    memory.record(MemoryRecord("now", base, "question", "actual", {}))

    result = await recap_previous_session(memory=memory, current_session_id="now")
    # Both old and recent should be listed
    assert len(result.findings) == 2
    # Recent first (descending by timestamp)
    assert "recent" in result.findings[0].summary
    assert "old" in result.findings[1].summary


@pytest.mark.asyncio
async def test_recap_limit_param():
    memory = FakeMemoryStore()
    base = datetime.now(timezone.utc)
    for i in range(5):
        memory.record(MemoryRecord(f"sess_{i}", base - timedelta(days=i), "question", f"q{i}", {}))

    result = await recap_previous_session(memory=memory, current_session_id="now", limit=2)
    assert len(result.findings) == 2


@pytest.mark.asyncio
async def test_recap_max_excerpts_per_kind():
    """Cada finding debe traer hasta N excerpts por kind."""
    memory = FakeMemoryStore()
    base = datetime.now(timezone.utc)
    for i in range(10):
        memory.record(MemoryRecord("prev", base - timedelta(hours=i), "question", f"q{i}", {}))

    result = await recap_previous_session(
        memory=memory, current_session_id="now", max_excerpts_per_kind=3,
    )
    # The single finding should report 3 question excerpts in metadata
    finding = result.findings[0]
    excerpts = finding.metadata.get("excerpts_by_kind", {}).get("question", [])
    assert len(excerpts) <= 3
