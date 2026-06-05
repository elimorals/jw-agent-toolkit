# Fase 61 — Memoria persistente opt-in (Letta adapter) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un módulo `jw_agents.memory` con un `MemoryStore` Protocol y dos backends — `SqliteMemoryStore` (default, local-first, opcional Fernet) y `LettaMemoryStore` (opt-in via `letta-ai/letta`) — que permite a `conversation_assistant` y a futuros agentes de estudio personal recordar discusiones doctrinales pasadas, preferencias del usuario y contexto de sesión sin perderlo entre conversaciones.

**Architecture:** Patrón ya validado por F25 (`RevisitStore`) y F14 (`StudentProgress`): sqlite en `~/.jw-agent-toolkit/` + opt-in Fernet via env var. Se introduce un Protocol `MemoryStore` con 4 métodos (`record`, `recall`, `list_sessions`, `forget`) y 3 backends concretos: `FakeMemoryStore` (default, in-memory, para tests), `SqliteMemoryStore` (persistencia local), `LettaMemoryStore` (proxy a Letta agent runtime). `conversation_assistant` y futuros agentes reciben `memory: MemoryStore | None` como kwarg — sin memory, comportamiento inalterado (compatibilidad estricta).

**Tech Stack:** Python 3.13 · `cryptography` (Fernet, ya en stack via F25) · `letta-client >= 0.3` (opt-in extra `[memory-letta]`) · sqlite3 stdlib.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) §"Re-evaluación honesta" punto 6 ("SÍ con reserva" — solo si construyes asistente que recuerde discusiones doctrinales pasadas).

**Depende de:** F25 (precedente sqlite+Fernet), F32 (life_topics agent que probablemente quiera memoria), F14 (StudentProgress passphrase pattern). NO depende de F58.

---

## File map

Crea (jw-agents):
- `packages/jw-agents/src/jw_agents/memory/__init__.py` — re-exports Public API
- `packages/jw-agents/src/jw_agents/memory/protocol.py` — `MemoryStore` Protocol + dataclasses
- `packages/jw-agents/src/jw_agents/memory/fake.py` — `FakeMemoryStore` (in-memory)
- `packages/jw-agents/src/jw_agents/memory/sqlite.py` — `SqliteMemoryStore` (default backend)
- `packages/jw-agents/src/jw_agents/memory/letta.py` — `LettaMemoryStore` (opt-in)
- `packages/jw-agents/src/jw_agents/memory/factory.py` — `build_memory_store()` resolver env-driven
- `packages/jw-agents/tests/test_memory_protocol.py`
- `packages/jw-agents/tests/test_memory_sqlite.py`
- `packages/jw-agents/tests/test_memory_letta.py`
- `packages/jw-agents/tests/test_memory_factory.py`
- `packages/jw-agents/tests/test_conversation_assistant_with_memory.py` — integración con agente existente

Modifica (jw-agents):
- `packages/jw-agents/pyproject.toml` — añadir extra `memory-letta = ["letta-client>=0.3"]`
- `packages/jw-agents/src/jw_agents/__init__.py` — re-export `MemoryStore`, `build_memory_store`
- `packages/jw-agents/src/jw_agents/conversation_assistant.py` — añadir param `memory: MemoryStore | None = None`

Modifica (MCP):
- `packages/jw-mcp/src/jw_mcp/server.py` — añadir tools `memory_recall`, `memory_record`, `memory_forget_session`
- `packages/jw-mcp/tests/test_protocol.py` — registrar 3 tools

Doc:
- `docs/guias/memoria-asistente.md` — guía operativa (setup, seguridad, ejemplos)
- `docs/ROADMAP.md`, `docs/README.md`, master plan — updates

---

## Decisiones clave de diseño (anti-placeholder)

### Por qué Letta como backend opt-in en vez de "el backend"
Letta es excelente pero pesa (~500 MB con deps) y agrega un runtime separado (server Letta). Para 80% de los usuarios JW que solo quieren "recuerda que la semana pasada hablamos sobre Daniel 9", **sqlite + Fernet basta**. Letta tiene sentido cuando necesitas:
- Agente con memoria jerárquica (core/archival/recall) y multi-paso
- Theory of mind por usuario
- Replicación cross-device

Mantener ambos backends bajo un Protocol común permite arrancar simple y escalar sin reescribir agentes.

### Patrón privacy-first replicado de F25
`RevisitStore` (`packages/jw-agents/src/jw_agents/revisit_tracker.py:75`) ya validó:
1. Sqlite en `~/.jw-agent-toolkit/<feature>.db`
2. Opt-in Fernet via env var (`JW_MEMORY_KEY` para F61)
3. Consent `y/N` cuando se crea por primera vez
4. NO cloud por default

F61 hereda exactamente este patrón. No re-inventamos.

### Sesión = conversación coherente, no día
Una "sesión" es un identificador que el caller decide (puede ser UUID generado al iniciar conversation_assistant, o `daily-2026-06-04` para "todo lo que se discutió hoy"). El store no impone semántica temporal — es un namespace de records.

### Schema de records: pequeño y semántico
```python
@dataclass(frozen=True)
class MemoryRecord:
    session_id: str
    timestamp: datetime  # UTC
    kind: Literal["question", "answer", "fact_recalled", "preference", "objection"]
    content: str
    metadata: dict[str, Any]  # incluye BibleRef opcionales, source urls, etc.
```

`kind` es discreto para permitir `recall(kind="objection")` rápido. `metadata` es libre para extender sin migración de schema.

### `recall()` con scoring por relevancia, no solo recientes
El backend Sqlite implementa scoring básico: `BM25` opcional (si rank-bm25 está disponible — ya está en `jw-rag`) o substring matching fallback. Letta usa su propio recall vector. No LLM en este Path — es retrieval determinístico para el caller (un agente) que opcionalmente luego invoca LLM con los records como contexto.

### Sin migración de schema: SqliteMemoryStore arranca con su esquema actual
Si el schema necesita cambiar en el futuro, se versiona via `PRAGMA user_version` (precedente F25). F61 arranca con version=1.

---

### Task 1: Protocol + dataclasses + FakeMemoryStore

**Files:**
- Create: `packages/jw-agents/src/jw_agents/memory/__init__.py`
- Create: `packages/jw-agents/src/jw_agents/memory/protocol.py`
- Create: `packages/jw-agents/src/jw_agents/memory/fake.py`
- Create: `packages/jw-agents/tests/test_memory_protocol.py`

- [ ] **Step 1: Failing tests del Protocol y Fake**

```python
# packages/jw-agents/tests/test_memory_protocol.py
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
```

- [ ] **Step 2: Run, expect FAIL**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run pytest packages/jw-agents/tests/test_memory_protocol.py -v`
Expected: ImportError.

- [ ] **Step 3: Implementar Protocol + dataclasses**

```python
# packages/jw-agents/src/jw_agents/memory/protocol.py
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
```

```python
# packages/jw-agents/src/jw_agents/memory/fake.py
"""In-memory MemoryStore para tests y default."""
from __future__ import annotations

from jw_agents.memory.protocol import MemoryKind, MemoryRecord


class FakeMemoryStore:
    """In-memory store. No persistencia entre instancias."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def record(self, record: MemoryRecord) -> None:
        self._records.append(record)

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        results = self._records
        if session_id is not None:
            results = [r for r in results if r.session_id == session_id]
        if kind is not None:
            results = [r for r in results if r.kind == kind]
        if query is not None:
            q = query.lower()
            results = [r for r in results if q in r.content.lower()]
            results.sort(
                key=lambda r: r.content.lower().count(q),
                reverse=True,
            )
        else:
            results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def list_sessions(self) -> list[str]:
        return list({r.session_id for r in self._records})

    def forget(self, session_id: str) -> int:
        before = len(self._records)
        self._records = [r for r in self._records if r.session_id != session_id]
        return before - len(self._records)
```

```python
# packages/jw-agents/src/jw_agents/memory/__init__.py
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
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest packages/jw-agents/tests/test_memory_protocol.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/memory/ packages/jw-agents/tests/test_memory_protocol.py
git commit -m "feat(jw-agents): F61.1 memory protocol plus FakeMemoryStore"
```

---

### Task 2: `SqliteMemoryStore` con Fernet opt-in

**Files:**
- Create: `packages/jw-agents/src/jw_agents/memory/sqlite.py`
- Create: `packages/jw-agents/tests/test_memory_sqlite.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-agents/tests/test_memory_sqlite.py
"""F61 — SqliteMemoryStore con Fernet opt-in."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jw_agents.memory import MemoryRecord, SqliteMemoryStore


def test_sqlite_persists_across_instances(tmp_path):
    db = tmp_path / "memory.db"
    store1 = SqliteMemoryStore(db_path=db)
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(timezone.utc),
        kind="question",
        content="¿Por qué los TJ no celebran cumpleaños?",
        metadata={"lang": "es"},
    )
    store1.record(record)

    # Nueva instancia: debe leer del mismo db
    store2 = SqliteMemoryStore(db_path=db)
    hits = store2.recall(session_id="s1")
    assert len(hits) == 1
    assert hits[0].content == record.content


def test_sqlite_recall_with_substring_query(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(timezone.utc)
    store.record(MemoryRecord("s1", base, "answer", "La Trinidad no es bíblica", {}))
    store.record(MemoryRecord("s1", base, "answer", "El alma no es inmortal", {}))
    hits = store.recall(session_id="s1", query="Trinidad")
    assert len(hits) == 1
    assert "Trinidad" in hits[0].content


def test_sqlite_recall_kind_filter(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(timezone.utc)
    store.record(MemoryRecord("s1", base, "question", "q1", {}))
    store.record(MemoryRecord("s1", base, "preference", "español", {}))
    prefs = store.recall(session_id="s1", kind="preference")
    assert len(prefs) == 1 and prefs[0].kind == "preference"


def test_sqlite_forget_returns_count(tmp_path):
    store = SqliteMemoryStore(db_path=tmp_path / "memory.db")
    base = datetime.now(timezone.utc)
    for i in range(3):
        store.record(MemoryRecord("s1", base, "question", f"q{i}", {}))
    n = store.forget("s1")
    assert n == 3


def test_sqlite_encrypted_with_fernet_key(tmp_path, monkeypatch):
    """Con JW_MEMORY_KEY presente, content se almacena cifrado."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JW_MEMORY_KEY", key)
    db = tmp_path / "memory.db"
    store = SqliteMemoryStore(db_path=db)
    record = MemoryRecord(
        session_id="s1",
        timestamp=datetime.now(timezone.utc),
        kind="answer",
        content="Información sensible del usuario",
        metadata={},
    )
    store.record(record)

    # Leer raw del sqlite: NO debe contener el plaintext
    import sqlite3
    conn = sqlite3.connect(db)
    raw = conn.execute("SELECT content FROM records").fetchone()[0]
    assert "Información sensible" not in raw.decode("utf-8", errors="ignore") \
        if isinstance(raw, bytes) else "Información sensible" not in raw

    # Pero recall normal lo descifra
    hits = store.recall(session_id="s1")
    assert hits[0].content == record.content


def test_sqlite_missing_key_when_db_encrypted_raises(tmp_path, monkeypatch):
    """Si el db tiene records cifrados y la key se pierde, error claro."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("JW_MEMORY_KEY", key)
    db = tmp_path / "memory.db"
    store = SqliteMemoryStore(db_path=db)
    store.record(MemoryRecord("s1", datetime.now(timezone.utc), "answer", "secreto", {}))

    monkeypatch.delenv("JW_MEMORY_KEY")
    with pytest.raises(RuntimeError, match="encrypted but JW_MEMORY_KEY"):
        SqliteMemoryStore(db_path=db).recall(session_id="s1")
```

- [ ] **Step 2: Implementar SqliteMemoryStore**

```python
# packages/jw-agents/src/jw_agents/memory/sqlite.py
"""SqliteMemoryStore: persistencia local con cifrado Fernet opt-in.

Patrón heredado de F25 RevisitStore.

Esquema:
    CREATE TABLE records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        kind TEXT NOT NULL,
        content BLOB NOT NULL,           -- bytes; plaintext UTF-8 o ciphertext Fernet
        metadata TEXT NOT NULL,          -- JSON
        encrypted INTEGER NOT NULL       -- 0 plain, 1 fernet
    )

Cifrado:
- Si env `JW_MEMORY_KEY` presente al record(), content se cifra antes de INSERT.
- recall() detecta el flag `encrypted` por fila y descifra si aplica.
- Si JW_MEMORY_KEY falta y hay rows con encrypted=1, recall raises.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from jw_agents.memory.protocol import MemoryKind, MemoryRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    content BLOB NOT NULL,
    metadata TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_records_session_id ON records(session_id);
CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind);
PRAGMA user_version = 1;
"""


def _default_db_path() -> Path:
    base = Path(os.environ.get("JW_MEMORY_DB", "~/.jw-agent-toolkit/memory.db"))
    return base.expanduser()


def _load_fernet():
    key = os.environ.get("JW_MEMORY_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography package required for JW_MEMORY_KEY") from exc
    return Fernet(key.encode() if isinstance(key, str) else key)


class SqliteMemoryStore:
    """Persistencia local sqlite con cifrado opt-in."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def record(self, record: MemoryRecord) -> None:
        fernet = _load_fernet()
        content_bytes = record.content.encode("utf-8")
        encrypted = 0
        if fernet is not None:
            content_bytes = fernet.encrypt(content_bytes)
            encrypted = 1
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO records (session_id, timestamp, kind, content, metadata, encrypted) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.session_id,
                    record.timestamp.isoformat(),
                    record.kind,
                    content_bytes,
                    json.dumps(record.metadata, ensure_ascii=False),
                    encrypted,
                ),
            )
            conn.commit()

    def recall(
        self,
        *,
        session_id: str | None = None,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = (
                f"SELECT session_id, timestamp, kind, content, metadata, encrypted "
                f"FROM records{where} ORDER BY timestamp DESC LIMIT ?"
            )
            rows = conn.execute(sql, [*params, limit * 4]).fetchall()

        fernet = _load_fernet()
        records: list[MemoryRecord] = []
        for row in rows:
            content_blob = row["content"]
            if row["encrypted"]:
                if fernet is None:
                    raise RuntimeError(
                        "Database is encrypted but JW_MEMORY_KEY env var is not set"
                    )
                content_text = fernet.decrypt(content_blob).decode("utf-8")
            else:
                content_text = (
                    content_blob.decode("utf-8")
                    if isinstance(content_blob, bytes)
                    else content_blob
                )
            records.append(
                MemoryRecord(
                    session_id=row["session_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    kind=row["kind"],  # type: ignore[arg-type]
                    content=content_text,
                    metadata=json.loads(row["metadata"]),
                )
            )

        if query is not None:
            q = query.lower()
            records = [r for r in records if q in r.content.lower()]
            records.sort(
                key=lambda r: r.content.lower().count(q),
                reverse=True,
            )
        return records[:limit]

    def list_sessions(self) -> list[str]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT DISTINCT session_id FROM records").fetchall()
        return [r[0] for r in rows]

    def forget(self, session_id: str) -> int:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute("DELETE FROM records WHERE session_id = ?", (session_id,))
            conn.commit()
            return cur.rowcount
```

- [ ] **Step 3: Run, expect PASS**

Run: `uv run pytest packages/jw-agents/tests/test_memory_sqlite.py -v`
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-agents/src/jw_agents/memory/sqlite.py packages/jw-agents/tests/test_memory_sqlite.py
git commit -m "feat(jw-agents): F61.2 SqliteMemoryStore with Fernet opt-in encryption"
```

---

### Task 3: `LettaMemoryStore` opt-in backend

**Files:**
- Create: `packages/jw-agents/src/jw_agents/memory/letta.py`
- Create: `packages/jw-agents/tests/test_memory_letta.py`
- Modify: `packages/jw-agents/pyproject.toml` — extra `memory-letta`

- [ ] **Step 1: Añadir extra**

```toml
# packages/jw-agents/pyproject.toml
[project.optional-dependencies]
memory-letta = ["letta-client>=0.3"]
```

- [ ] **Step 2: Failing tests (con mock para Letta)**

```python
# packages/jw-agents/tests/test_memory_letta.py
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
```

- [ ] **Step 3: Implementar**

```python
# packages/jw-agents/src/jw_agents/memory/letta.py
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
    def from_env(cls) -> "LettaMemoryStore":
        try:
            from letta_client import Letta
        except ImportError as exc:
            raise ModuleNotFoundError(
                "letta-client not installed. Run: uv add 'jw-agents[memory-letta]'"
            ) from exc

        base_url = os.environ.get("LETTA_BASE_URL")
        token = os.environ.get("LETTA_TOKEN")
        agent_id = os.environ.get("LETTA_AGENT_ID")
        if not agent_id:
            raise RuntimeError(
                "LETTA_AGENT_ID env var required. Create an agent in Letta UI first."
            )
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
```

- [ ] **Step 4: Run, expect PASS o skipped**

Run: `uv run pytest packages/jw-agents/tests/test_memory_letta.py -v`
Expected: 3 passed si letta-client instalado, sino 3 skipped.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/memory/letta.py packages/jw-agents/tests/test_memory_letta.py packages/jw-agents/pyproject.toml
git commit -m "feat(jw-agents): F61.3 LettaMemoryStore backend with from_env factory"
```

---

### Task 4: Factory `build_memory_store()` env-driven

**Files:**
- Create: `packages/jw-agents/src/jw_agents/memory/factory.py`
- Create: `packages/jw-agents/tests/test_memory_factory.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-agents/tests/test_memory_factory.py
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
```

- [ ] **Step 2: Implementar factory**

```python
# packages/jw-agents/src/jw_agents/memory/factory.py
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
```

- [ ] **Step 3: Run, expect PASS**

Run: `uv run pytest packages/jw-agents/tests/test_memory_factory.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-agents/src/jw_agents/memory/factory.py packages/jw-agents/tests/test_memory_factory.py
git commit -m "feat(jw-agents): F61.4 build_memory_store factory env-driven"
```

---

### Task 5: Integrar `memory` en `conversation_assistant`

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/conversation_assistant.py`
- Create: `packages/jw-agents/tests/test_conversation_assistant_with_memory.py`

- [ ] **Step 1: Failing test del wire-up**

```python
# packages/jw-agents/tests/test_conversation_assistant_with_memory.py
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
        "recalled" in result.metadata
        or any("memory" in w.lower() for w in result.warnings)
        or any("objection" in (f.metadata.get("source") or "") for f in result.findings)
    )
```

- [ ] **Step 2: Modificar `conversation_assistant.py`**

Localizar la firma actual:
```python
async def conversation_assistant(
    text: str,
    *,
    language: str = "E",
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    max_subheadings: int = 6,
) -> AgentResult:
```

Modificar a:
```python
async def conversation_assistant(
    text: str,
    *,
    language: str = "E",
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    max_subheadings: int = 6,
    memory: "MemoryStore | None" = None,
    session_id: str | None = None,
) -> AgentResult:
```

E inyectar lógica de record/recall en los puntos clave:

```python
# Al inicio (después de inicializar clients):
recalled_objections: list[MemoryRecord] = []
if memory is not None and session_id is not None:
    recalled_objections = memory.recall(
        session_id=session_id, kind="objection", limit=5
    )

# Tras procesar la query y antes de devolver result:
if memory is not None and session_id is not None:
    from datetime import datetime, timezone
    memory.record(MemoryRecord(
        session_id=session_id,
        timestamp=datetime.now(timezone.utc),
        kind="question",
        content=text,
        metadata={"language": language},
    ))
    # Si findings tiene algo, registrar como answer
    if result.findings:
        memory.record(MemoryRecord(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            kind="answer",
            content="; ".join(f.summary for f in result.findings[:3]),
            metadata={"finding_count": len(result.findings)},
        ))
    # Anotar en metadata del result
    result.metadata["recalled_objections"] = len(recalled_objections)
```

(Adapta exactamente al flow del archivo — el agente ya tiene su pipeline; este sprint solo añade los record/recall en los puntos adecuados.)

- [ ] **Step 3: Importar `MemoryStore` y `MemoryRecord` (lazy)**

Top del archivo:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jw_agents.memory import MemoryRecord, MemoryStore
```

Y dentro de la función, cuando se usa:
```python
from jw_agents.memory import MemoryRecord
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/jw-agents/tests/test_conversation_assistant_with_memory.py -v`
Expected: 3 passed.

- [ ] **Step 5: Smoke con tests existentes**

Run: `uv run pytest packages/jw-agents/tests/ -k conversation -v`
Expected: tests previos de conversation_assistant siguen verdes (compatibility).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-agents/src/jw_agents/conversation_assistant.py packages/jw-agents/tests/test_conversation_assistant_with_memory.py
git commit -m "feat(jw-agents): F61.5 wire memory MemoryStore into conversation_assistant opt-in"
```

---

### Task 6: MCP tools `memory_recall`, `memory_record`, `memory_forget_session`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_protocol.py`

- [ ] **Step 1: Añadir tools**

```python
# En jw_mcp/server.py

_memory_store: Any | None = None


def _get_memory_store():
    global _memory_store
    if _memory_store is None:
        from jw_agents.memory import build_memory_store
        _memory_store = build_memory_store()
    return _memory_store


@mcp.tool
async def memory_record(
    session_id: str,
    kind: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persiste un record en el MemoryStore (backend determinado por
    JW_MEMORY_BACKEND env).

    Args:
        session_id: identificador de sesión libre.
        kind: 'question' | 'answer' | 'fact_recalled' | 'preference' | 'objection'.
        content: texto del record.
        metadata: dict libre (BibleRefs, source_urls, etc.).
    """
    from datetime import datetime, timezone
    from jw_agents.memory import MemoryRecord

    valid_kinds = {"question", "answer", "fact_recalled", "preference", "objection"}
    if kind not in valid_kinds:
        return {"error": f"invalid kind: {kind}. Use one of {sorted(valid_kinds)}"}
    try:
        store = _get_memory_store()
        store.record(MemoryRecord(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            kind=kind,  # type: ignore[arg-type]
            content=content,
            metadata=metadata or {},
        ))
        return {"recorded": True, "session_id": session_id, "kind": kind}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def memory_recall(
    session_id: str | None = None,
    query: str | None = None,
    kind: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Recupera records del MemoryStore filtrando por sesión, kind y/o query.

    Returns dict con `records: [{session_id, timestamp, kind, content, metadata}]`.
    """
    try:
        store = _get_memory_store()
        records = store.recall(
            session_id=session_id, query=query, kind=kind, limit=limit
        )
        return {
            "records": [
                {
                    "session_id": r.session_id,
                    "timestamp": r.timestamp.isoformat(),
                    "kind": r.kind,
                    "content": r.content,
                    "metadata": r.metadata,
                }
                for r in records
            ],
            "count": len(records),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def memory_forget_session(session_id: str) -> dict[str, Any]:
    """Elimina todos los records de una sesión. Útil para 'olvida la
    conversación de hoy' o reset privado."""
    try:
        store = _get_memory_store()
        n = store.forget(session_id=session_id)
        return {"forgotten": n, "session_id": session_id}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 2: Añadir las 3 tools a `_EXPECTED_TOOLS`**

- [ ] **Step 3: Run protocol test**

```bash
uv run pytest packages/jw-mcp/tests/test_protocol.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/
git commit -m "feat(jw-mcp): F61.6 expose memory_record memory_recall memory_forget_session tools"
```

---

### Task 7: Guía + ROADMAP + master plan

**Files:**
- Create: `docs/guias/memoria-asistente.md`
- Modify: `docs/README.md`, `docs/ROADMAP.md`, master plan

- [ ] **Step 1: Guía operativa**

```markdown
# Memoria persistente del asistente (Fase 61)

> Permite al `conversation_assistant` (y futuros agentes) recordar
> discusiones doctrinales pasadas, preferencias del usuario y objeciones
> ya tratadas — sin perder contexto entre sesiones.

## Backends disponibles

| Backend | Local-first | Setup | Caso de uso |
|---|---|---|---|
| `fake` (default) | ✓ in-memory | nada | tests, ejecuciones one-shot |
| `sqlite` (recomendado) | ✓ archivo local | nada (auto-create) | uso personal continuo |
| `letta` (opt-in) | ✗ requiere server | docker + agent UI | multi-device sync, memoria jerárquica |

Elige con env var: `export JW_MEMORY_BACKEND=sqlite`.

## SqliteMemoryStore + cifrado opcional

Default: archivo `~/.jw-agent-toolkit/memory.db` (plaintext).

Para cifrar TODO content con Fernet:

```bash
# Generar key una sola vez:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → guardarla EN tu password manager (vault, 1Password)

export JW_MEMORY_KEY="<la-key-generada>"
```

**ATENCIÓN**: si pierdes la key, los records cifrados son irrecuperables.
El toolkit NO escribe la key a disco ni la sincroniza.

## Letta backend

Para memoria jerárquica + multi-device sync:

```bash
# 1. Levantar Letta server (Docker)
docker run -p 8283:8283 letta/letta:latest

# 2. Crear agente en Letta UI (http://localhost:8283)
#    Copiar el agent_id

# 3. Setup env vars
export JW_MEMORY_BACKEND=letta
export LETTA_BASE_URL=http://localhost:8283
export LETTA_AGENT_ID=<agent-id-de-letta-ui>
export LETTA_TOKEN=<opcional si auth activo>

# 4. Instalar dep
uv add 'jw-agents[memory-letta]'
```

## Uso desde Python

```python
from jw_agents.memory import build_memory_store
from jw_agents.conversation_assistant import conversation_assistant

memory = build_memory_store()  # respeta JW_MEMORY_BACKEND
result = await conversation_assistant(
    "¿Por qué los TJ no aceptan transfusiones?",
    language="S",
    session_id="conversation-2026-06-04",
    memory=memory,
)
```

## Uso desde MCP / Claude

```
@jw-agent-toolkit memory_record
  session_id: conversation-2026-06-04
  kind: preference
  content: El usuario prefiere explicaciones cortas con 2-3 citas máximo

@jw-agent-toolkit memory_recall
  session_id: conversation-2026-06-04
  query: transfusiones
```

## Privacy first

- TODO el storage es local (sqlite) por default.
- El cifrado Fernet es **opt-in** (env var) — no en path crítico.
- `forget(session_id)` borra **inmediatamente**, sin papelera ni sync.
- El toolkit NO sube records a la nube en ningún backend (Letta opcionalmente
  los expone vía API, pero esa decisión queda en el usuario).
- `JW_MEMORY_DB` apunta a archivo local; el usuario puede backupearlo
  manualmente (recomendado: junto con sus notas Obsidian del F20).
```

- [ ] **Step 2: docs/README.md y ROADMAP.md**

```markdown
# docs/README.md
- [Memoria persistente del asistente](guias/memoria-asistente.md) — Fase 61: SqliteMemoryStore + LettaMemoryStore opt-in para que conversation_assistant recuerde objeciones, preferencias y context entre sesiones.
```

```markdown
# docs/ROADMAP.md
## Fase 61 — Memoria persistente opt-in ✅

- ✅ `MemoryStore` Protocol + `MemoryRecord` dataclass.
- ✅ `FakeMemoryStore` (default in-memory), `SqliteMemoryStore` (default disk), `LettaMemoryStore` (opt-in).
- ✅ Fernet opt-in via `JW_MEMORY_KEY` (precedente F25).
- ✅ Factory `build_memory_store()` env-driven.
- ✅ Wire-up en `conversation_assistant` con compatibility preservada (memory=None).
- ✅ MCP tools `memory_record/recall/forget_session`.
- ⬜ Auto-recap entre sesiones (futuro): agente que resuma sesión previa al iniciar nueva.
- ⬜ Voz reconocida → speaker_id de F64 alimenta automáticamente `preference` records.
```

- [ ] **Step 3: Marcar F61 ✅ en master plan**

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs(F61): memory persistence guide plus ROADMAP entry"
```

---

## Tests resumen

```bash
uv run pytest packages/jw-agents/tests/test_memory_protocol.py \
              packages/jw-agents/tests/test_memory_sqlite.py \
              packages/jw-agents/tests/test_memory_letta.py \
              packages/jw-agents/tests/test_memory_factory.py \
              packages/jw-agents/tests/test_conversation_assistant_with_memory.py \
              packages/jw-mcp/tests/test_protocol.py \
              -v --tb=short
```

Sin letta-client: ~20 passed + 3 skipped. Con letta: ~23 passed.

---

## Self-review checklist

- ✅ **Cobertura de spec**: Protocol + 3 backends + factory + agent integration + MCP + cifrado opt-in + docs.
- ✅ **No placeholders**: cada Step tiene código real. Sección de wire-up en `conversation_assistant` describe puntos de inyección (depende de leer el archivo real para integración fina — marcado como "adapta al flow actual").
- ✅ **Consistencia de tipos**: `MemoryStore` Protocol estable en 3 implementaciones. `MemoryRecord` frozen dataclass usado consistentemente. `MemoryKind` Literal en Protocol, factory y MCP tools.
- ⚠️ **Letta API instability**: letta-client está pre-1.0 — sus signatures pueden cambiar. La Task 3 implementa contra v0.3 actual. Si rompe en futuro, el test mock lo detecta antes del code path real.
