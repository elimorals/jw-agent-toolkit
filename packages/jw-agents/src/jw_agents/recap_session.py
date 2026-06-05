"""F61.8 — agente procedural que recapitula sesiones previas.

NO usa LLM. Agrupa records de memory por session_id, ordena por timestamp
(descending), devuelve findings con summary corto + excerpts por kind.

Compatible con la decisión arquitectónica "LLM no en camino crítico".
Si el caller (CLI/MCP/Claude Desktop) quiere narrativa rica, puede tomar
el AgentResult y pasarlo a un LLM downstream.
"""
from __future__ import annotations

from collections import defaultdict

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.memory import MemoryRecord, MemoryStore


async def recap_previous_session(
    *,
    memory: MemoryStore,
    current_session_id: str,
    limit: int = 5,
    max_excerpts_per_kind: int = 3,
) -> AgentResult:
    """Genera un recap procedural de las sesiones previas del usuario.

    Args:
        memory: MemoryStore donde están los records persistidos.
        current_session_id: sesión actual (se excluye del recap).
        limit: número máximo de sesiones previas a recapitular.
        max_excerpts_per_kind: cuántos contenidos por kind se incluyen en metadata.

    Returns:
        AgentResult con un Finding por sesión previa (ordenadas por
        timestamp desc). Cada Finding tiene:
          - summary: "Sesión <id>: <N> records (X preguntas, Y objeciones, ...)"
          - metadata.excerpts_by_kind: {kind: [content, content, ...]}
          - metadata.session_id
          - metadata.last_timestamp_iso
    """
    all_sessions = memory.list_sessions()
    other_sessions = [s for s in all_sessions if s != current_session_id]
    if not other_sessions:
        return AgentResult(
            query="recap",
            agent_name="recap_session",
            findings=[],
            warnings=[],
            metadata={"sessions_scanned": 0},
        )

    # Collect records per session
    session_records: dict[str, list[MemoryRecord]] = {}
    for sid in other_sessions:
        records = memory.recall(session_id=sid, limit=200)
        if records:
            session_records[sid] = records

    # Sort sessions by most recent record timestamp (desc)
    sorted_sessions = sorted(
        session_records.items(),
        key=lambda kv: max(r.timestamp for r in kv[1]),
        reverse=True,
    )[:limit]

    findings: list[Finding] = []
    for sid, records in sorted_sessions:
        by_kind: dict[str, list[str]] = defaultdict(list)
        for r in sorted(records, key=lambda r: r.timestamp, reverse=True):
            if len(by_kind[r.kind]) < max_excerpts_per_kind:
                by_kind[r.kind].append(r.content)
        last_ts = max(r.timestamp for r in records)
        counts_phrase = ", ".join(
            f"{len([r for r in records if r.kind == k])} {k}{'s' if len([r for r in records if r.kind == k]) != 1 else ''}"
            for k in sorted({r.kind for r in records})
        )
        summary = (
            f"Sesión {sid}: {len(records)} records ({counts_phrase}). "
            f"Último: {last_ts.isoformat()}"
        )
        findings.append(
            Finding(
                summary=summary,
                citation=Citation(
                    url="",
                    title=f"memory:session:{sid}",
                    kind="memory_recap",
                    metadata={"session_id": sid},
                ),
                excerpt=(by_kind.get("question") or by_kind.get("answer") or [""])[0][:200],
                metadata={
                    "session_id": sid,
                    "last_timestamp_iso": last_ts.isoformat(),
                    "record_count": len(records),
                    "excerpts_by_kind": dict(by_kind),
                },
            )
        )

    return AgentResult(
        query="recap",
        agent_name="recap_session",
        findings=findings,
        warnings=[],
        metadata={
            "sessions_scanned": len(other_sessions),
            "sessions_recapped": len(findings),
        },
    )
