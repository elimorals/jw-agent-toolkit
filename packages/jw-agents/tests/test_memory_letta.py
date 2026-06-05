"""F61 — LettaMemoryStore. Tests con mock del cliente Letta."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

pytest.importorskip("letta_client", reason="letta-client not installed")


def test_letta_record_calls_client():
    from jw_agents.memory import LettaMemoryStore, MemoryRecord

    mock_client = MagicMock()
    store = LettaMemoryStore(client=mock_client, agent_id="agent-123")
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(timezone.utc),
        kind="answer",
        content="La Trinidad no es bíblica",
        metadata={},
    )
    store.record(record)
    mock_client.agents.messages.create.assert_called_once()


def test_letta_recall_queries_client():
    from jw_agents.memory import LettaMemoryStore

    mock_client = MagicMock()
    mock_messages = MagicMock()
    mock_messages.data = []
    mock_client.agents.messages.list.return_value = mock_messages

    store = LettaMemoryStore(client=mock_client, agent_id="agent-123")
    hits = store.recall(session_id="s1", query="Trinidad")
    assert hits == []
    mock_client.agents.messages.list.assert_called_once()


def test_letta_factory_requires_agent_id(monkeypatch):
    """Sin LETTA_AGENT_ID env, factory falla con mensaje claro."""
    from jw_agents.memory.letta import LettaMemoryStore

    monkeypatch.delenv("LETTA_AGENT_ID", raising=False)
    monkeypatch.delenv("LETTA_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="LETTA_AGENT_ID"):
        LettaMemoryStore.from_env()
