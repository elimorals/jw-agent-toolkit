"""F61 — factory resuelve backend según env."""
from __future__ import annotations

import pytest

from jw_agents.memory import FakeMemoryStore, build_memory_store


def test_factory_default_returns_fake(monkeypatch):
    """Sin JW_MEMORY_BACKEND, devuelve Fake (zero-config)."""
    monkeypatch.delenv("JW_MEMORY_BACKEND", raising=False)
    store = build_memory_store()
    assert isinstance(store, FakeMemoryStore)


def test_factory_sqlite_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("JW_MEMORY_BACKEND", "sqlite")
    monkeypatch.setenv("JW_MEMORY_DB", str(tmp_path / "memory.db"))
    store = build_memory_store()
    assert type(store).__name__ == "SqliteMemoryStore"


def test_factory_letta_requires_setup(monkeypatch):
    """letta sin LETTA_AGENT_ID falla con mensaje claro."""
    monkeypatch.setenv("JW_MEMORY_BACKEND", "letta")
    monkeypatch.delenv("LETTA_AGENT_ID", raising=False)
    with pytest.raises(RuntimeError, match="LETTA_AGENT_ID"):
        build_memory_store()


def test_factory_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("JW_MEMORY_BACKEND", "redis")  # no soportado
    with pytest.raises(ValueError, match="unknown memory backend"):
        build_memory_store()
