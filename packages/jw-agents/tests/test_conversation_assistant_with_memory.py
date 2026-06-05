"""F61 — conversation_assistant respeta memory: MemoryStore | None."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jw_agents.conversation_assistant import conversation_assistant
from jw_agents.memory import FakeMemoryStore, MemoryRecord


@pytest.mark.asyncio
async def test_conversation_assistant_no_memory_works_as_before():
    """Sin memory: comportamiento legacy preservado (compatibilidad)."""
    result = await conversation_assistant(
        "¿Es Jesús Dios?",
        language="S",
        # SIN memory kwarg
    )
    assert result is not None
    assert result.agent_name == "conversation_assistant"


@pytest.mark.asyncio
async def test_conversation_assistant_records_to_memory():
    """Con memory provisto, agente registra question + answer."""
    memory = FakeMemoryStore()
    result = await conversation_assistant(
        "¿Es Jesús Dios?",
        language="S",
        session_id="test_session",
        memory=memory,
    )
    records = memory.recall(session_id="test_session")
    kinds = {r.kind for r in records}
    assert "question" in kinds
    # answer puede o no estar (depende de si findings != [])


@pytest.mark.asyncio
async def test_conversation_assistant_recalls_past_objection():
    """Si memoria tiene una objeción previa, el agente la añade como hint."""
    memory = FakeMemoryStore()
    memory.record(MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(timezone.utc),
        kind="objection",
        content="El usuario antes dijo: 'la Biblia se contradice sobre Jesús'",
        metadata={},
    ))
    result = await conversation_assistant(
        "Cuéntame sobre Jesús",
        language="S",
        session_id="s1",
        memory=memory,
    )
    # El agente debe haber consultado memory; verifica que warnings o
    # metadata refleja al menos un recall
    assert (
        "recalled_objections" in result.metadata
        or any("memory" in w.lower() for w in result.warnings)
        or any("objection" in (f.metadata.get("source") or "") for f in result.findings)
    )
