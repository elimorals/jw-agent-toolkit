"""Factory env-driven para MemoryStore."""
from __future__ import annotations

import os

from jw_agents.memory.fake import FakeMemoryStore
from jw_agents.memory.protocol import MemoryStore


def build_memory_store() -> MemoryStore:
    """Resuelve un MemoryStore según env vars.

    Precedencia:
        JW_MEMORY_BACKEND=fake|sqlite|letta (default: fake)
        JW_MEMORY_DB=<path>             (solo para sqlite)
        JW_MEMORY_KEY=<fernet_key>       (solo para sqlite, opt-in encryption)
        LETTA_BASE_URL, LETTA_AGENT_ID, LETTA_TOKEN (solo para letta)

    Returns:
        Una instancia que cumple MemoryStore Protocol.

    Raises:
        ValueError: si JW_MEMORY_BACKEND tiene valor no reconocido.
        RuntimeError: si el backend pedido falta configuración mínima.
        ModuleNotFoundError: si el backend pedido no está instalado (Letta).
    """
    backend = os.environ.get("JW_MEMORY_BACKEND", "fake").lower()
    if backend == "fake":
        return FakeMemoryStore()
    if backend == "sqlite":
        from jw_agents.memory.sqlite import SqliteMemoryStore
        return SqliteMemoryStore()
    if backend == "letta":
        from jw_agents.memory.letta import LettaMemoryStore
        return LettaMemoryStore.from_env()
    raise ValueError(
        f"unknown memory backend: {backend!r}. "
        "Set JW_MEMORY_BACKEND to one of: fake, sqlite, letta."
    )
