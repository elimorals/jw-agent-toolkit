"""F61 — Protocol y FakeMemoryStore."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jw_agents.memory import FakeMemoryStore, MemoryRecord, MemoryStore


def test_fake_implements_protocol():
    assert isinstance(FakeMemoryStore(), MemoryStore)


def test_fake_record_then_recall():
    store = FakeMemoryStore()
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(timezone.utc),
        kind="question",
        content="¿Es la Trinidad doctrina bíblica?",
        metadata={"language": "es"},
    )
    store.record(record)
    hits = store.recall(session_id="s1", query="Trinidad")
    assert len(hits) == 1
    assert hits[0].content == record.content


def test_fake_recall_filters_by_kind():
    store = FakeMemoryStore()
    base_ts = datetime.now(timezone.utc)
    store.record(MemoryRecord("s1", base_ts, "question", "q1", {}))
    store.record(MemoryRecord("s1", base_ts, "objection", "o1", {}))
    questions = store.recall(session_id="s1", kind="question")
    objections = store.recall(session_id="s1", kind="objection")
    assert len(questions) == 1 and questions[0].kind == "question"
    assert len(objections) == 1 and objections[0].kind == "objection"


def test_fake_list_sessions():
    store = FakeMemoryStore()
    base_ts = datetime.now(timezone.utc)
    store.record(MemoryRecord("s1", base_ts, "question", "q1", {}))
    store.record(MemoryRecord("s2", base_ts, "question", "q2", {}))
    sessions = store.list_sessions()
    assert set(sessions) == {"s1", "s2"}


def test_fake_forget_session():
    store = FakeMemoryStore()
    base_ts = datetime.now(timezone.utc)
    store.record(MemoryRecord("s1", base_ts, "question", "q1", {}))
    store.record(MemoryRecord("s2", base_ts, "question", "q2", {}))
    n = store.forget(session_id="s1")
    assert n == 1
    assert store.list_sessions() == ["s2"]


def test_fake_recall_unknown_session_returns_empty():
    store = FakeMemoryStore()
    assert store.recall(session_id="never_existed") == []


def test_memory_record_immutable():
    record = MemoryRecord("s1", datetime.now(timezone.utc), "question", "q", {})
    with pytest.raises(AttributeError):
        record.content = "modified"  # frozen dataclass
