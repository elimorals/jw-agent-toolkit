"""Memoria persistente opt-in para agentes JW.

Public API:
    MemoryStore         — Protocol
    MemoryRecord        — dataclass
    MemoryKind          — Literal type alias
    FakeMemoryStore     — in-memory backend (default para tests)
    SqliteMemoryStore   — local file backend (default para producción)
    LettaMemoryStore    — opt-in Letta backend
    build_memory_store  — factory resolver env-driven
"""
from jw_agents.memory.fake import FakeMemoryStore
from jw_agents.memory.protocol import MemoryKind, MemoryRecord, MemoryStore

# Lazy imports: Sqlite/Letta se exponen solo si la dep está disponible
try:
    from jw_agents.memory.sqlite import SqliteMemoryStore
except ImportError:
    pass

try:
    from jw_agents.memory.letta import LettaMemoryStore
except ImportError:
    pass

try:
    from jw_agents.memory.factory import build_memory_store
except ImportError:
    pass

__all__ = [
    "MemoryStore",
    "MemoryRecord",
    "MemoryKind",
    "FakeMemoryStore",
    "SqliteMemoryStore",
    "LettaMemoryStore",
    "build_memory_store",
]
