"""LettaMemoryStore: usa letta-ai/letta como backend de memoria.

Letta corre como server local o remoto. F61 lo trata como API client puro:
- record() emite mensajes al agente Letta vía messages.create
- recall() obtiene historial vía messages.list y filtra cliente-side

Setup mínimo (local):
    docker run -p 8283:8283 letta/letta:latest
    export LETTA_BASE_URL=http://localhost:8283
    export LETTA_AGENT_ID=<agent-id-creado-via-letta-ui>
    export LETTA_TOKEN=<opcional si configuraste auth>
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from jw_agents.memory.protocol import MemoryKind, MemoryRecord


class LettaMemoryStore:
    """Backend memory respaldado por un Letta agent."""

    def __init__(self, *, client: Any, agent_id: str):
        self._client = client
        self._agent_id = agent_id

    @classmethod
    def from_env(cls) -> LettaMemoryStore:
        agent_id = os.environ.get("LETTA_AGENT_ID")
        if not agent_id:
            raise RuntimeError(
                "LETTA_AGENT_ID env var required. Create an agent in Letta UI first."
            )
        try:
            from letta_client import Letta
        except ImportError as exc:
            raise ModuleNotFoundError(
                "letta-client not installed. Run: uv add 'jw-agents[memory-letta]'"
            ) from exc

        base_url = os.environ.get("LETTA_BASE_URL")
        token = os.environ.get("LETTA_TOKEN")
        client = Letta(base_url=base_url, token=token) if base_url else Letta(token=token)
        return cls(client=client, agent_id=agent_id)

    def record(self, record: MemoryRecord) -> None:
        payload = f"[{record.kind}] (session={record.session_id}) {record.content}"
        if record.metadata:
            payload += f"\nmetadata: {record.metadata}"
        self._client.agents.messages.create(
            agent_id=self._agent_id,
            messages=[{"role": "user", "content": payload}],
        )

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        # Letta messages.list devuelve historial; filtramos client-side
        response = self._client.agents.messages.list(
            agent_id=self._agent_id, limit=max(limit * 4, 50)
        )
        records: list[MemoryRecord] = []
        for msg in getattr(response, "data", []):
            content = getattr(msg, "content", "") or ""
            if not content.startswith("["):  # ignora system/assistant
                continue
            # Parse "[kind] (session=X) content"
            try:
                kind_end = content.index("]")
                detected_kind = content[1:kind_end]
                rest = content[kind_end + 1 :].lstrip()
                session_start = rest.index("(session=") + len("(session=")
                session_end = rest.index(")", session_start)
                detected_session = rest[session_start:session_end]
                text = rest[session_end + 1 :].lstrip()
            except (ValueError, IndexError):
                continue
            if session_id and detected_session != session_id:
                continue
            if kind and detected_kind != kind:
                continue
            if query and query.lower() not in text.lower():
                continue
            ts = getattr(msg, "created_at", None) or datetime.now()
            records.append(
                MemoryRecord(
                    session_id=detected_session,
                    timestamp=ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts)),
                    kind=detected_kind,  # type: ignore[arg-type]
                    content=text,
                    metadata={},
                )
            )
            if len(records) >= limit:
                break
        return records

    def list_sessions(self) -> list[str]:
        # Letta no indexa por session_id, scan all
        response = self._client.agents.messages.list(agent_id=self._agent_id, limit=200)
        sessions: set[str] = set()
        for msg in getattr(response, "data", []):
            content = getattr(msg, "content", "") or ""
            try:
                session_start = content.index("(session=") + len("(session=")
                session_end = content.index(")", session_start)
                sessions.add(content[session_start:session_end])
            except (ValueError, IndexError):
                continue
        return sorted(sessions)

    def forget(self, session_id: str) -> int:
        # Letta no expone DELETE selectivo por contenido — limitación documentada
        raise NotImplementedError(
            "LettaMemoryStore does not support selective forget. "
            "Use Letta UI to reset agent memory, or switch to SqliteMemoryStore."
        )
