"""Protocol y dataclasses del módulo memory.

Un MemoryStore es una bóveda de records por sesión que permite a un
agente recuperar contexto pasado para informar respuestas futuras.

NO es un LLM con memoria semántica — es un store con métodos simples
de recall (substring/BM25/kind-filter). Si el agente quiere un summary
narrativo de los records, lo genera el agente (no el store).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

MemoryKind = Literal[
    "question",         # pregunta del usuario al agente
    "answer",           # respuesta del agente
    "fact_recalled",    # un hecho que el agente quiere preservar (ej. "el usuario es precursor regular")
    "preference",       # preferencia explícita del usuario (idioma, tono)
    "objection",        # objeción común que el usuario ha escuchado / planteado
]


@dataclass(frozen=True)
class MemoryRecord:
    """Unidad atómica de memoria. Immutable post-creación."""
    session_id: str
    timestamp: datetime
    kind: MemoryKind
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MemoryStore(Protocol):
    """Interfaz que cumplen Fake/Sqlite/Letta backends."""

    def record(self, record: MemoryRecord) -> None:
        """Persiste un record. Idempotencia es responsabilidad del backend
        (Sqlite usa UNIQUE; Fake permite duplicados; Letta gestiona internamente)."""

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Devuelve hasta `limit` records ordenados por relevancia (si hay query)
        o por timestamp desc (si no). Filtros AND."""

    def list_sessions(self) -> list[str]:
        """Devuelve session_ids únicos almacenados (orden no garantizado)."""

    def forget(self, session_id: str) -> int:
        """Elimina todos los records de la sesión dada. Devuelve cuántos borró."""
