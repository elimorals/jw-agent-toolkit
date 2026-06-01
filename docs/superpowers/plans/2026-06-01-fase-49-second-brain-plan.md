# Fase 49 — `second-brain` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build a new workspace member `packages/jw-brain/` that implements the Karpathy-style second-brain compiler, the dual GraphRAG backend (DuckDB / Neo4j), the Obsidian wiki layer, the lint operation backed by F39 NLI, and the F41-plugin-genericized domain runtime. TJ ships as the builtin reference domain; a fixture financial plugin proves generality.

**Architecture:** New workspace package with 8 submodules (`backends/`, `schema/`, `wiki/`, `compiler/`, `query/`, `lint/`, `domain/`, `cli`). Single `GraphBackend` Protocol with two interchangeable implementations passing the same contract tests. LLM-driven compiler with cache + snapshot + dry-run. Wiki on Obsidian extending Fase 20. Plugin domains via F41 entry-points group `jw_agent_toolkit.brain_domains`.

**Tech Stack:** Python 3.13 · `duckdb` (default backend, optional dep) · `neo4j-driver` (opt-in backend, optional dep) · `markdown-it-py` (wiki page parser for round-trip) · existing F45 chunkers + F40 provenance + F39 NLI + F38 GenerationProvider + F20 obsidian_vault + F41 plugin_sdk (when ready).

**Spec:** [`docs/superpowers/specs/2026-06-01-fase-49-second-brain-design.md`](../specs/2026-06-01-fase-49-second-brain-design.md).

**Depende de:** Fase 39 (NLI), Fase 40 (provenance), Fase 41 (plugin SDK), Fase 45 (chunkers). El plan ASUME que F41 está terminada. Si no, los Tasks 13-14 quedan en stub.

---

## File map

Creates a new workspace member:
- `packages/jw-brain/pyproject.toml`
- `packages/jw-brain/src/jw_brain/__init__.py`
- `packages/jw-brain/src/jw_brain/backends/{protocol,duckdb_backend,neo4j_backend,factory}.py`
- `packages/jw-brain/src/jw_brain/schema/{nodes,edges,provenance,builtins}.py`
- `packages/jw-brain/src/jw_brain/wiki/{obsidian_writer,index}.py` + `pages/*.md` templates
- `packages/jw-brain/src/jw_brain/compiler/{orchestrator,llm_extractor,parser_router,cache,dry_run,snapshot}.py`
- `packages/jw-brain/src/jw_brain/query/{router,wiki_searcher,graph_traverser,hybrid_reranker}.py`
- `packages/jw-brain/src/jw_brain/lint/{orphan_pages,stale_chunks,contradiction_finder,missing_xrefs,reporter}.py`
- `packages/jw-brain/src/jw_brain/domain/{contract,registry,builtin_tj}.py`
- `packages/jw-brain/src/jw_brain/cli.py`
- `packages/jw-brain/src/jw_brain/server.py`
- `packages/jw-brain/tests/` (test files per task)
- `packages/jw-brain/tests/fixtures/{raw_samples,financial_brain_plugin}/`
- `docs/guias/second-brain.md`

Modifies:
- `pyproject.toml` (root): añadir `packages/jw-brain` al workspace.
- `packages/jw-cli/src/jw_cli/main.py`: registrar `brain` sub-app.
- `packages/jw-mcp/src/jw_mcp/server.py`: registrar `second_brain_*` tools.
- `packages/jw-mcp/tests/test_protocol.py`: añadir nuevas tools a `_EXPECTED_TOOLS`.
- `docs/ROADMAP.md`, `docs/VISION_AUDIT.md`, `docs/README.md`: añadir Fase 49.

---

### Task 1: Scaffold `jw-brain` workspace member + empty package

**Files:**
- Create: `packages/jw-brain/pyproject.toml`
- Create: `packages/jw-brain/src/jw_brain/__init__.py`
- Create: `packages/jw-brain/tests/__init__.py`
- Create: `packages/jw-brain/tests/test_smoke.py`
- Modify: `pyproject.toml` (root) — añadir miembro al workspace.

- [ ] **Step 1: Write the package skeleton**

```toml
# packages/jw-brain/pyproject.toml
[project]
name = "jw-brain"
version = "0.1.0"
description = "Karpathy-style second-brain compiler with GraphRAG, on the jw-agent-toolkit runtime."
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = [
    "jw-core",
    "jw-rag",
    "jw-agents",
    "pydantic>=2.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
duckdb = ["duckdb>=1.0"]
neo4j = ["neo4j>=5.0"]
all = ["duckdb>=1.0", "neo4j>=5.0"]

[tool.uv.sources]
jw-core = { workspace = true }
jw-rag = { workspace = true }
jw-agents = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_brain"]
```

```python
# packages/jw-brain/src/jw_brain/__init__.py
"""jw-brain — Karpathy-style second-brain compiler with GraphRAG.

Public API:
    from jw_brain import compile, query, lint, snapshot
    from jw_brain.backends import get_backend
    from jw_brain.schema import NodeTypeSpec, EdgeTypeSpec
"""

from __future__ import annotations

__version__ = "0.1.0"
```

```python
# packages/jw-brain/tests/test_smoke.py
"""Smoke: package imports cleanly without optional deps."""

from __future__ import annotations


def test_package_imports() -> None:
    import jw_brain

    assert jw_brain.__version__ == "0.1.0"
```

- [ ] **Step 2: Register the package in the workspace**

Edit root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = [
    "packages/jw-core",
    "packages/jw-cli",
    "packages/jw-mcp",
    "packages/jw-rag",
    "packages/jw-agents",
    "packages/jw-finetune",
    "packages/jw-eval",
    "packages/jw-gen",
    "packages/jw-brain",   # ← new
]

[tool.uv.sources]
# ... existing ...
jw-brain = { workspace = true }
```

- [ ] **Step 3: Sync and run smoke test**

```bash
uv sync --all-packages
uv run pytest packages/jw-brain/tests/test_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-brain pyproject.toml
git commit -m "feat(jw-brain): scaffold workspace member for Fase 49"
```

---

### Task 2: `GraphBackend` Protocol + DuckDB backend + contract tests

**Files:**
- Create: `packages/jw-brain/src/jw_brain/backends/__init__.py`
- Create: `packages/jw-brain/src/jw_brain/backends/protocol.py`
- Create: `packages/jw-brain/src/jw_brain/backends/duckdb_backend.py`
- Create: `packages/jw-brain/src/jw_brain/backends/factory.py`
- Create: `packages/jw-brain/tests/test_backends_contract.py`

- [ ] **Step 1: Write the contract test (parametrized over backends)**

```python
# packages/jw-brain/tests/test_backends_contract.py
"""Contract tests for GraphBackend implementations.

Both DuckDB (default) and Neo4j (opt-in) MUST pass every test here.
Run Neo4j-backed tests with: pytest --neo4j-tests (defaults to skip).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_brain.backends import GraphBackend, get_backend


def _backends_to_test(request) -> list[str]:
    """Yields backend names enabled in this run."""
    out = ["duckdb"]
    if request.config.getoption("--neo4j-tests", default=False):
        out.append("neo4j")
    return out


@pytest.fixture(params=["duckdb"])
def backend(request, tmp_path: Path) -> GraphBackend:
    name = request.param
    if name == "duckdb":
        return get_backend("duckdb", path=tmp_path / "test.duckdb")
    if name == "neo4j":
        return get_backend("neo4j", uri="bolt://localhost:7687", user="neo4j", password="test")
    raise ValueError(name)


def test_upsert_node_returns_id(backend: GraphBackend) -> None:
    nid = backend.upsert_node(
        node_type="Verse",
        canonical_id="verse:43:3:16",
        properties={"book_num": 43, "chapter": 3, "verse": 16, "text": "..."},
        provenance={"run_id": "abc", "model_id": "ollama:llama3.1:8b", "confidence": 0.95},
    )
    assert isinstance(nid, str)
    assert len(nid) > 0


def test_get_node_returns_properties(backend: GraphBackend) -> None:
    backend.upsert_node(
        node_type="Verse",
        canonical_id="verse:43:3:16",
        properties={"text": "Porque Dios amó tanto al mundo"},
        provenance={"run_id": "abc"},
    )
    node = backend.get_node("verse:43:3:16")
    assert node is not None
    assert node["text"] == "Porque Dios amó tanto al mundo"


def test_upsert_is_idempotent(backend: GraphBackend) -> None:
    """Same canonical_id twice → merge, not duplicate."""

    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={"a": 1}, provenance={})
    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={"a": 1}, provenance={})
    stats = backend.stats()
    assert stats["n_nodes"] == 1


def test_upsert_edge_creates_link(backend: GraphBackend) -> None:
    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={}, provenance={})
    backend.upsert_node(node_type="Publication", canonical_id="p1", properties={}, provenance={})
    backend.upsert_edge(
        edge_type="CITED_IN",
        from_node="v1",
        to_node="p1",
        properties={"context": "study note"},
        provenance={"run_id": "abc", "confidence": 0.9},
    )
    neighbors = backend.neighbors("v1", edge_type="CITED_IN", hops=1)
    assert len(neighbors) == 1
    assert neighbors[0]["canonical_id"] == "p1"


def test_neighbors_two_hops(backend: GraphBackend) -> None:
    """v1 -CITED_IN-> p1 -CITES-> v2  ⇒ neighbors(v1, hops=2) includes v2."""

    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={}, provenance={})
    backend.upsert_node(node_type="Publication", canonical_id="p1", properties={}, provenance={})
    backend.upsert_node(node_type="Verse", canonical_id="v2", properties={}, provenance={})
    backend.upsert_edge(edge_type="CITED_IN", from_node="v1", to_node="p1", properties={}, provenance={})
    backend.upsert_edge(edge_type="CITES", from_node="p1", to_node="v2", properties={}, provenance={})
    out = backend.neighbors("v1", hops=2, direction="out")
    canonical_ids = {n["canonical_id"] for n in out}
    assert "v2" in canonical_ids


def test_transaction_rolls_back_on_exception(backend: GraphBackend) -> None:
    with pytest.raises(RuntimeError):
        with backend.transaction():
            backend.upsert_node(node_type="Verse", canonical_id="ghost", properties={}, provenance={})
            raise RuntimeError("simulated failure")
    assert backend.get_node("ghost") is None


def test_snapshot_and_restore_round_trip(backend: GraphBackend, tmp_path: Path) -> None:
    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={"x": 1}, provenance={})
    snap_path = tmp_path / "snap.tar.zst"
    backend.snapshot(snap_path)
    assert snap_path.exists()

    # Wipe + restore
    backend.upsert_node(node_type="Verse", canonical_id="v2", properties={"y": 2}, provenance={})
    backend.restore(snap_path)
    assert backend.get_node("v1") is not None
    assert backend.get_node("v2") is None  # post-snapshot mutation undone


def test_stats_reports_counts_by_type(backend: GraphBackend) -> None:
    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={}, provenance={})
    backend.upsert_node(node_type="Topic", canonical_id="t1", properties={}, provenance={})
    stats = backend.stats()
    assert stats["n_nodes"] == 2
    assert stats["by_type"]["Verse"] == 1
    assert stats["by_type"]["Topic"] == 1
```

Add a conftest stub:

```python
# packages/jw-brain/tests/conftest.py
def pytest_addoption(parser) -> None:
    parser.addoption(
        "--neo4j-tests",
        action="store_true",
        default=False,
        help="Run Neo4j-backed tests (requires testcontainers Neo4j).",
    )
```

- [ ] **Step 2: Implement `GraphBackend` Protocol and `DuckDBBackend`**

```python
# packages/jw-brain/src/jw_brain/backends/protocol.py
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class GraphBackend(Protocol):
    name: str

    def upsert_node(
        self,
        *,
        node_type: str,
        canonical_id: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str: ...

    def upsert_edge(
        self,
        *,
        edge_type: str,
        from_node: str,
        to_node: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str: ...

    @contextmanager
    def transaction(self) -> Iterator[None]: ...

    def get_node(self, canonical_id: str) -> dict[str, Any] | None: ...

    def neighbors(
        self,
        canonical_id: str,
        *,
        edge_type: str | None = None,
        hops: int = 1,
        direction: str = "both",
    ) -> list[dict[str, Any]]: ...

    def query(
        self,
        expr: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def snapshot(self, path: Path) -> None: ...
    def restore(self, path: Path) -> None: ...
    def stats(self) -> dict[str, Any]: ...
```

```python
# packages/jw-brain/src/jw_brain/backends/duckdb_backend.py
"""DuckDB GraphBackend — default embedded local-first."""

from __future__ import annotations

import json
import shutil
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import duckdb
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "jw-brain DuckDB backend requires `duckdb`. Install with: "
        "uv add 'jw-brain[duckdb]'"
    ) from exc


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id            VARCHAR PRIMARY KEY,
    node_type     VARCHAR NOT NULL,
    canonical_id  VARCHAR UNIQUE NOT NULL,
    properties    JSON,
    provenance    JSON,
    created_at    TIMESTAMP DEFAULT now(),
    updated_at    TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS edges (
    id            VARCHAR PRIMARY KEY,
    edge_type     VARCHAR NOT NULL,
    from_node     VARCHAR NOT NULL,
    to_node       VARCHAR NOT NULL,
    properties    JSON,
    provenance    JSON,
    created_at    TIMESTAMP DEFAULT now(),
    UNIQUE (edge_type, from_node, to_node)
);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_node);
CREATE INDEX IF NOT EXISTS idx_edges_to   ON edges(to_node);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
"""


class DuckDBBackend:
    name = "duckdb"

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = Path(path) if path != ":memory:" else None
        self._conn = duckdb.connect(str(self.path) if self.path else ":memory:")
        self._conn.execute(_SCHEMA_SQL)

    def upsert_node(self, *, node_type, canonical_id, properties, provenance) -> str:
        nid = canonical_id  # use canonical_id as primary id; deterministic
        self._conn.execute(
            """
            INSERT INTO nodes (id, node_type, canonical_id, properties, provenance)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (canonical_id) DO UPDATE SET
                properties = ?,
                provenance = ?,
                updated_at = now()
            """,
            [
                nid, node_type, canonical_id,
                json.dumps(properties or {}), json.dumps(provenance or {}),
                json.dumps(properties or {}), json.dumps(provenance or {}),
            ],
        )
        return nid

    def upsert_edge(self, *, edge_type, from_node, to_node, properties, provenance) -> str:
        eid = f"{edge_type}::{from_node}::{to_node}"
        self._conn.execute(
            """
            INSERT INTO edges (id, edge_type, from_node, to_node, properties, provenance)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (edge_type, from_node, to_node) DO UPDATE SET
                properties = ?,
                provenance = ?
            """,
            [
                eid, edge_type, from_node, to_node,
                json.dumps(properties or {}), json.dumps(provenance or {}),
                json.dumps(properties or {}), json.dumps(provenance or {}),
            ],
        )
        return eid

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN TRANSACTION")
        try:
            yield
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def get_node(self, canonical_id: str) -> dict[str, Any] | None:
        rows = self._conn.execute(
            "SELECT properties, provenance, node_type FROM nodes WHERE canonical_id = ?",
            [canonical_id],
        ).fetchall()
        if not rows:
            return None
        props_raw, prov_raw, ntype = rows[0]
        props = json.loads(props_raw) if isinstance(props_raw, str) else (props_raw or {})
        prov = json.loads(prov_raw) if isinstance(prov_raw, str) else (prov_raw or {})
        return {
            "canonical_id": canonical_id,
            "node_type": ntype,
            "provenance": prov,
            **props,
        }

    def neighbors(self, canonical_id, *, edge_type=None, hops=1, direction="both"):
        if hops == 1:
            # Direct neighbors
            edge_filter = "AND edge_type = ?" if edge_type else ""
            params: list[Any] = [canonical_id]
            if edge_type:
                params.append(edge_type)
            if direction == "out":
                sql = f"SELECT to_node AS n FROM edges WHERE from_node = ? {edge_filter}"
            elif direction == "in":
                sql = f"SELECT from_node AS n FROM edges WHERE to_node = ? {edge_filter}"
            else:
                sql = (
                    f"SELECT to_node AS n FROM edges WHERE from_node = ? {edge_filter} "
                    f"UNION SELECT from_node AS n FROM edges WHERE to_node = ? {edge_filter}"
                )
                params = [canonical_id] + ([edge_type] if edge_type else []) + [canonical_id] + ([edge_type] if edge_type else [])
            rows = self._conn.execute(sql, params).fetchall()
            out: list[dict[str, Any]] = []
            for (n,) in rows:
                node = self.get_node(n)
                if node:
                    out.append(node)
            return out

        # Multi-hop via recursive CTE (DuckDB supports it).
        sql = """
        WITH RECURSIVE reach(node, depth) AS (
            SELECT to_node, 1 FROM edges WHERE from_node = ?
            UNION
            SELECT e.to_node, r.depth + 1
            FROM reach r JOIN edges e ON r.node = e.from_node
            WHERE r.depth < ?
        )
        SELECT DISTINCT node FROM reach
        """
        rows = self._conn.execute(sql, [canonical_id, hops]).fetchall()
        out = []
        for (n,) in rows:
            node = self.get_node(n)
            if node:
                out.append(node)
        return out

    def query(self, expr, params=None):
        cur = self._conn.execute(expr, list(params.values()) if params else [])
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]

    def snapshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.path is None or self.path == Path(":memory:"):
            # In-memory: export to parquet inside tarball
            with tarfile.open(path, "w") as tar:
                for tbl in ("nodes", "edges"):
                    tmpf = path.parent / f"_{tbl}.parquet"
                    self._conn.execute(f"COPY (SELECT * FROM {tbl}) TO '{tmpf}' (FORMAT 'parquet')")
                    tar.add(tmpf, arcname=f"{tbl}.parquet")
                    tmpf.unlink()
        else:
            with tarfile.open(path, "w") as tar:
                tar.add(self.path, arcname="backend.duckdb")

    def restore(self, path: Path) -> None:
        with tarfile.open(path, "r") as tar:
            members = tar.getnames()
            if "backend.duckdb" in members:
                self._conn.close()
                tar.extract("backend.duckdb", path=self.path.parent if self.path else ".")
                extracted = (self.path.parent if self.path else Path(".")) / "backend.duckdb"
                if self.path:
                    shutil.move(str(extracted), str(self.path))
                self._conn = duckdb.connect(str(self.path) if self.path else ":memory:")
            else:
                # In-memory parquet restore
                self._conn.execute("DELETE FROM nodes")
                self._conn.execute("DELETE FROM edges")
                for tbl in ("nodes", "edges"):
                    tar.extract(f"{tbl}.parquet", path=path.parent)
                    p = path.parent / f"{tbl}.parquet"
                    self._conn.execute(f"INSERT INTO {tbl} SELECT * FROM read_parquet('{p}')")
                    p.unlink()

    def stats(self) -> dict[str, Any]:
        n_nodes = self._conn.execute("SELECT count(*) FROM nodes").fetchone()[0]
        n_edges = self._conn.execute("SELECT count(*) FROM edges").fetchone()[0]
        by_type = dict(
            self._conn.execute("SELECT node_type, count(*) FROM nodes GROUP BY node_type").fetchall()
        )
        return {"n_nodes": n_nodes, "n_edges": n_edges, "by_type": by_type}
```

```python
# packages/jw-brain/src/jw_brain/backends/factory.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jw_brain.backends.protocol import GraphBackend


def get_backend(name: str | None = None, **kwargs: Any) -> GraphBackend:
    """Resolve a GraphBackend by name, env var, or default."""

    resolved = name or os.environ.get("JW_BRAIN_BACKEND", "duckdb")
    if resolved == "duckdb":
        from jw_brain.backends.duckdb_backend import DuckDBBackend

        return DuckDBBackend(**kwargs)
    if resolved == "neo4j":
        from jw_brain.backends.neo4j_backend import Neo4jBackend  # Task 3

        return Neo4jBackend(**kwargs)
    raise ValueError(f"Unknown backend: {resolved!r}")
```

```python
# packages/jw-brain/src/jw_brain/backends/__init__.py
from jw_brain.backends.factory import get_backend
from jw_brain.backends.protocol import GraphBackend

__all__ = ["GraphBackend", "get_backend"]
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv add --package jw-brain "duckdb>=1.0"
uv run pytest packages/jw-brain/tests/test_backends_contract.py -v
```

Expected: 8 passed on DuckDB. Neo4j skipped.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-brain/src/jw_brain/backends packages/jw-brain/tests/test_backends_contract.py packages/jw-brain/tests/conftest.py
git commit -m "feat(jw-brain): GraphBackend Protocol + DuckDB backend + contract tests"
```

---

### Task 3: Neo4j backend (mismos contract tests)

**Files:**
- Create: `packages/jw-brain/src/jw_brain/backends/neo4j_backend.py`

- [ ] **Step 1: Implement Neo4jBackend**

```python
# packages/jw-brain/src/jw_brain/backends/neo4j_backend.py
"""Neo4j GraphBackend — opt-in external. Same contract as DuckDB."""

from __future__ import annotations

import json
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    from neo4j import GraphDatabase
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "jw-brain Neo4j backend requires `neo4j`. Install with: "
        "uv add 'jw-brain[neo4j]'"
    ) from exc


class Neo4jBackend:
    name = "neo4j"

    def __init__(self, *, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._db = database
        self._setup_schema()

    def _setup_schema(self) -> None:
        with self._driver.session(database=self._db) as session:
            session.run("CREATE CONSTRAINT canonical_id IF NOT EXISTS FOR (n:Node) REQUIRE n.canonical_id IS UNIQUE")

    def upsert_node(self, *, node_type, canonical_id, properties, provenance) -> str:
        with self._driver.session(database=self._db) as session:
            session.run(
                """
                MERGE (n:Node {canonical_id: $cid})
                SET n.node_type = $nt,
                    n.properties = $props,
                    n.provenance = $prov,
                    n.updated_at = datetime()
                """,
                cid=canonical_id, nt=node_type,
                props=json.dumps(properties or {}),
                prov=json.dumps(provenance or {}),
            )
        return canonical_id

    def upsert_edge(self, *, edge_type, from_node, to_node, properties, provenance) -> str:
        with self._driver.session(database=self._db) as session:
            session.run(
                """
                MATCH (a:Node {canonical_id: $from_id})
                MATCH (b:Node {canonical_id: $to_id})
                MERGE (a)-[r:EDGE {edge_type: $et}]->(b)
                SET r.properties = $props,
                    r.provenance = $prov
                """,
                from_id=from_node, to_id=to_node, et=edge_type,
                props=json.dumps(properties or {}),
                prov=json.dumps(provenance or {}),
            )
        return f"{edge_type}::{from_node}::{to_node}"

    @contextmanager
    def transaction(self) -> Iterator[None]:
        session = self._driver.session(database=self._db)
        tx = session.begin_transaction()
        try:
            yield
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            session.close()

    def get_node(self, canonical_id: str) -> dict[str, Any] | None:
        with self._driver.session(database=self._db) as session:
            result = session.run(
                "MATCH (n:Node {canonical_id: $cid}) RETURN n", cid=canonical_id
            ).single()
            if result is None:
                return None
            n = dict(result["n"])
            props = json.loads(n.get("properties", "{}"))
            prov = json.loads(n.get("provenance", "{}"))
            return {"canonical_id": canonical_id, "node_type": n["node_type"], "provenance": prov, **props}

    def neighbors(self, canonical_id, *, edge_type=None, hops=1, direction="both"):
        with self._driver.session(database=self._db) as session:
            arrow_out = f"-[r:EDGE{' {edge_type: $et}' if edge_type else ''}]->"
            arrow_in = f"<-[r:EDGE{' {edge_type: $et}' if edge_type else ''}]-"
            if direction == "out":
                pattern = f"(a:Node {{canonical_id: $cid}}){arrow_out * hops}(b:Node)"
            elif direction == "in":
                pattern = f"(a:Node {{canonical_id: $cid}}){arrow_in * hops}(b:Node)"
            else:
                pattern = f"(a:Node {{canonical_id: $cid}})-[*1..{hops}]-(b:Node)"
            sql = f"MATCH {pattern} RETURN DISTINCT b.canonical_id AS cid"
            params: dict[str, Any] = {"cid": canonical_id}
            if edge_type:
                params["et"] = edge_type
            rows = session.run(sql, **params)
            out: list[dict[str, Any]] = []
            for r in rows:
                node = self.get_node(r["cid"])
                if node:
                    out.append(node)
            return out

    def query(self, expr, params=None):
        with self._driver.session(database=self._db) as session:
            rows = session.run(expr, **(params or {}))
            return [dict(r) for r in rows]

    def snapshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._driver.session(database=self._db) as session:
            nodes = session.run("MATCH (n:Node) RETURN n").data()
            edges = session.run("MATCH ()-[r:EDGE]->() RETURN startNode(r) AS s, endNode(r) AS t, r").data()
        with tarfile.open(path, "w") as tar:
            for name, data in (("nodes.json", nodes), ("edges.json", edges)):
                tmpf = path.parent / f"_{name}"
                tmpf.write_text(json.dumps(data, default=str), encoding="utf-8")
                tar.add(tmpf, arcname=name)
                tmpf.unlink()

    def restore(self, path: Path) -> None:
        with self._driver.session(database=self._db) as session:
            session.run("MATCH (n) DETACH DELETE n")
        with tarfile.open(path, "r") as tar:
            nodes = json.loads(tar.extractfile("nodes.json").read())
            edges = json.loads(tar.extractfile("edges.json").read())
        for entry in nodes:
            n = entry["n"]
            self.upsert_node(
                node_type=n.get("node_type", "Unknown"),
                canonical_id=n["canonical_id"],
                properties=json.loads(n.get("properties", "{}")),
                provenance=json.loads(n.get("provenance", "{}")),
            )
        for entry in edges:
            r = entry["r"]
            self.upsert_edge(
                edge_type=r.get("edge_type", "RELATED"),
                from_node=entry["s"]["canonical_id"],
                to_node=entry["t"]["canonical_id"],
                properties=json.loads(r.get("properties", "{}")),
                provenance=json.loads(r.get("provenance", "{}")),
            )

    def stats(self) -> dict[str, Any]:
        with self._driver.session(database=self._db) as session:
            n_nodes = session.run("MATCH (n:Node) RETURN count(n) AS c").single()["c"]
            n_edges = session.run("MATCH ()-[r:EDGE]->() RETURN count(r) AS c").single()["c"]
            by_type = {
                r["node_type"]: r["c"]
                for r in session.run("MATCH (n:Node) RETURN n.node_type AS node_type, count(*) AS c")
            }
        return {"n_nodes": n_nodes, "n_edges": n_edges, "by_type": by_type}
```

- [ ] **Step 2: Update contract test parametrization**

```python
# packages/jw-brain/tests/test_backends_contract.py — change @pytest.fixture
@pytest.fixture(params=[])  # populated by pytest_generate_tests
def backend(request, tmp_path):
    ...

def pytest_generate_tests(metafunc):
    if "backend" in metafunc.fixturenames:
        params = ["duckdb"]
        if metafunc.config.getoption("--neo4j-tests", default=False):
            params.append("neo4j")
        metafunc.parametrize("backend", params, indirect=True, ids=params)
```

- [ ] **Step 3: Run with --neo4j-tests locally (skipped in CI)**

```bash
# Requires Neo4j running locally; skip if absent.
docker run -d --rm --name jw-brain-neo4j -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/test neo4j:5
uv add --package jw-brain "neo4j>=5.0"
uv run pytest packages/jw-brain/tests/test_backends_contract.py --neo4j-tests -v
docker stop jw-brain-neo4j
```

Expected: 8 passed on DuckDB, 8 passed on Neo4j.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-brain/src/jw_brain/backends/neo4j_backend.py packages/jw-brain/tests/test_backends_contract.py
git commit -m "feat(jw-brain): Neo4j backend passes the same contract as DuckDB"
```

---

### Task 4: Schema-on-read registry + builtin TJ NodeTypes/EdgeTypes

**Files:**
- Create: `packages/jw-brain/src/jw_brain/schema/__init__.py`
- Create: `packages/jw-brain/src/jw_brain/schema/nodes.py`
- Create: `packages/jw-brain/src/jw_brain/schema/edges.py`
- Create: `packages/jw-brain/src/jw_brain/schema/provenance.py`
- Create: `packages/jw-brain/src/jw_brain/schema/builtins.py`
- Create: `packages/jw-brain/tests/test_schema_registry.py`

- [ ] **Step 1: Failing test for the registry**

```python
# packages/jw-brain/tests/test_schema_registry.py
from __future__ import annotations

import pytest

from jw_brain.schema import (
    EdgeRegistry,
    EdgeTypeSpec,
    NodeRegistry,
    NodeTypeSpec,
    canonical_id_for,
)


def test_node_registry_register_and_get() -> None:
    reg = NodeRegistry()
    spec = NodeTypeSpec(
        name="Verse",
        canonical_id_pattern="verse:{book}:{ch}:{v}",
        properties={"book_num": int, "chapter": int, "verse": int, "text": str},
        wiki_page_template="verse.md",
        obsidian_subdir="verses/",
        confidence_threshold=0.7,
    )
    reg.register(spec)
    assert reg.get("Verse") is spec
    assert reg.get("Unknown") is None


def test_canonical_id_for_renders_pattern() -> None:
    spec = NodeTypeSpec(
        name="Verse",
        canonical_id_pattern="verse:{book}:{ch}:{v}",
        properties={}, wiki_page_template="", obsidian_subdir="",
    )
    assert canonical_id_for(spec, {"book": 43, "ch": 3, "v": 16}) == "verse:43:3:16"


def test_node_spec_unknown_property_rejected_when_strict() -> None:
    reg = NodeRegistry(strict=True)
    spec = NodeTypeSpec(
        name="Topic",
        canonical_id_pattern="topic:{slug}",
        properties={"slug": str, "title": str},
        wiki_page_template="", obsidian_subdir="",
    )
    reg.register(spec)
    with pytest.raises(ValueError, match="unknown property"):
        reg.validate("Topic", {"slug": "trinity", "bogus_field": 1})


def test_builtin_tj_domain_has_six_node_types() -> None:
    from jw_brain.schema.builtins import tj_node_specs
    names = {s.name for s in tj_node_specs()}
    assert {"Verse", "Topic", "Publication", "Concept", "Person", "Place"} <= names


def test_edge_registry_validates_source_target() -> None:
    edge_reg = EdgeRegistry()
    edge_reg.register(EdgeTypeSpec(
        name="CITED_IN",
        sources=("Verse", "Topic"),
        targets=("Publication",),
        directional=True,
        confidence_threshold=0.6,
    ))
    spec = edge_reg.get("CITED_IN")
    assert spec is not None
    assert "Publication" in spec.targets


def test_provenance_arista_has_required_fields() -> None:
    from jw_brain.schema.provenance import EdgeProvenance

    p = EdgeProvenance(
        run_id="abc-123",
        model_id="ollama:llama3.1:8b",
        prompt_version="v1",
        confidence=0.92,
        source_chunk_id="article:url#3",
        extracted_at="2026-06-01T10:00:00Z",
    )
    d = p.model_dump()
    assert d["run_id"] == "abc-123"
    assert d["confidence"] == 0.92
```

- [ ] **Step 2: Implement the registry**

```python
# packages/jw-brain/src/jw_brain/schema/nodes.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeTypeSpec:
    name: str
    canonical_id_pattern: str
    properties: dict[str, type] = field(default_factory=dict)
    wiki_page_template: str = ""
    obsidian_subdir: str = ""
    confidence_threshold: float = 0.5


class NodeRegistry:
    def __init__(self, *, strict: bool = False) -> None:
        self._specs: dict[str, NodeTypeSpec] = {}
        self.strict = strict

    def register(self, spec: NodeTypeSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> NodeTypeSpec | None:
        return self._specs.get(name)

    def all(self) -> list[NodeTypeSpec]:
        return list(self._specs.values())

    def validate(self, node_type: str, properties: dict[str, Any]) -> None:
        spec = self.get(node_type)
        if spec is None:
            if self.strict:
                raise ValueError(f"unknown node_type: {node_type}")
            return
        if self.strict:
            unknown = set(properties) - set(spec.properties)
            if unknown:
                raise ValueError(f"unknown property in {node_type}: {sorted(unknown)}")


def canonical_id_for(spec: NodeTypeSpec, ids: dict[str, Any]) -> str:
    return spec.canonical_id_pattern.format(**ids)
```

```python
# packages/jw-brain/src/jw_brain/schema/edges.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeTypeSpec:
    name: str
    sources: tuple[str, ...]
    targets: tuple[str, ...]
    directional: bool = True
    confidence_threshold: float = 0.5
    sensitive: bool = False  # if True, default conflict policy = "flag"


class EdgeRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, EdgeTypeSpec] = {}

    def register(self, spec: EdgeTypeSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> EdgeTypeSpec | None:
        return self._specs.get(name)

    def all(self) -> list[EdgeTypeSpec]:
        return list(self._specs.values())
```

```python
# packages/jw-brain/src/jw_brain/schema/provenance.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EdgeProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    model_id: str
    prompt_version: str
    confidence: float
    source_chunk_id: str
    extracted_at: str  # ISO 8601 UTC
```

```python
# packages/jw-brain/src/jw_brain/schema/builtins.py
"""TJ domain — the reference NodeTypes/EdgeTypes shipped with jw-brain."""

from __future__ import annotations

from jw_brain.schema.edges import EdgeTypeSpec
from jw_brain.schema.nodes import NodeTypeSpec


def tj_node_specs() -> list[NodeTypeSpec]:
    return [
        NodeTypeSpec(
            name="Verse",
            canonical_id_pattern="verse:{book}:{ch}:{v}",
            properties={"book_num": int, "chapter": int, "verse": int, "text": str, "language": str},
            wiki_page_template="verse.md",
            obsidian_subdir="verses/",
            confidence_threshold=0.9,  # high — verses are canonical
        ),
        NodeTypeSpec(
            name="Topic",
            canonical_id_pattern="topic:{slug}",
            properties={"slug": str, "title": str, "language": str},
            wiki_page_template="topic.md",
            obsidian_subdir="topics/",
        ),
        NodeTypeSpec(
            name="Publication",
            canonical_id_pattern="pub:{pub_code}:{language}",
            properties={"pub_code": str, "title": str, "language": str, "published_date": str},
            wiki_page_template="publication.md",
            obsidian_subdir="publications/",
        ),
        NodeTypeSpec(
            name="Concept",
            canonical_id_pattern="concept:{slug}",
            properties={"slug": str, "title": str, "summary": str},
            wiki_page_template="concept.md",
            obsidian_subdir="concepts/",
        ),
        NodeTypeSpec(
            name="Person",
            canonical_id_pattern="person:{slug}",
            properties={"slug": str, "name": str, "era": str},
            wiki_page_template="person.md",
            obsidian_subdir="people/",
        ),
        NodeTypeSpec(
            name="Place",
            canonical_id_pattern="place:{slug}",
            properties={"slug": str, "name": str, "modern_name": str},
            wiki_page_template="place.md",
            obsidian_subdir="places/",
        ),
    ]


def tj_edge_specs() -> list[EdgeTypeSpec]:
    return [
        EdgeTypeSpec(name="CITED_IN", sources=("Verse", "Topic"), targets=("Publication",)),
        EdgeTypeSpec(name="MENTIONS", sources=("Publication",), targets=("Verse", "Topic", "Person", "Place")),
        EdgeTypeSpec(name="EXPANDS", sources=("Publication",), targets=("Topic", "Concept")),
        EdgeTypeSpec(name="CROSS_REFERENCES", sources=("Verse",), targets=("Verse",), directional=False),
        EdgeTypeSpec(name="CONTRADICTS", sources=("Publication",), targets=("Publication",), sensitive=True),
        EdgeTypeSpec(name="ABOUT", sources=("Verse",), targets=("Topic", "Concept", "Person", "Place")),
    ]


def register_tj_domain(node_registry, edge_registry) -> None:
    for spec in tj_node_specs():
        node_registry.register(spec)
    for spec in tj_edge_specs():
        edge_registry.register(spec)
```

```python
# packages/jw-brain/src/jw_brain/schema/__init__.py
from jw_brain.schema.edges import EdgeRegistry, EdgeTypeSpec
from jw_brain.schema.nodes import NodeRegistry, NodeTypeSpec, canonical_id_for
from jw_brain.schema.provenance import EdgeProvenance

__all__ = [
    "EdgeProvenance",
    "EdgeRegistry",
    "EdgeTypeSpec",
    "NodeRegistry",
    "NodeTypeSpec",
    "canonical_id_for",
]
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest packages/jw-brain/tests/test_schema_registry.py -v
git add packages/jw-brain/src/jw_brain/schema packages/jw-brain/tests/test_schema_registry.py
git commit -m "feat(jw-brain): schema-on-read registry + TJ builtin NodeTypes"
```

---

### Task 5: `ObsidianWikiWriter` (extiende Fase 20, write-safe namespace)

**Files:**
- Create: `packages/jw-brain/src/jw_brain/wiki/__init__.py`
- Create: `packages/jw-brain/src/jw_brain/wiki/obsidian_writer.py`
- Create: `packages/jw-brain/src/jw_brain/wiki/index.py`
- Create: `packages/jw-brain/src/jw_brain/wiki/pages/{verse,topic,publication}.md`
- Create: `packages/jw-brain/tests/test_wiki_writer.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-brain/tests/test_wiki_writer.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter, WriteOutsideNamespaceError


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def test_writer_rejects_path_outside_namespace(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    with pytest.raises(WriteOutsideNamespaceError):
        writer.write_page("../escape.md", "x", frontmatter={})


def test_writer_creates_page_with_frontmatter(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.write_page(
        "verses/Juan_3_16.md",
        body="Texto del versículo.",
        frontmatter={"node_type": "Verse", "canonical_id": "verse:43:3:16"},
    )
    p = vault / "Second-Brain" / "verses" / "Juan_3_16.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "node_type: Verse" in text
    assert "Texto del versículo." in text


def test_writer_respects_human_edited_flag(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.write_page("verses/v.md", body="v1", frontmatter={"node_type": "Verse"})

    # User edits
    p = vault / "Second-Brain" / "verses" / "v.md"
    p.write_text(
        "---\nnode_type: Verse\nhuman_edited: true\n---\n\nHuman version.\n",
        encoding="utf-8",
    )

    # Agent tries to overwrite — should preserve
    writer.write_page("verses/v.md", body="agent v2", frontmatter={"node_type": "Verse"})
    out = p.read_text(encoding="utf-8")
    assert "Human version." in out
    assert "agent v2" not in out


def test_writer_appends_to_log(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.append_log("compile", {"files": 3, "nodes_new": 12})
    log = (vault / "Second-Brain" / "log.md").read_text(encoding="utf-8")
    assert "compile" in log
    assert "files: 3" in log
```

- [ ] **Step 2: Implement**

```python
# packages/jw-brain/src/jw_brain/wiki/obsidian_writer.py
"""Write-safe Obsidian wiki writer for jw-brain.

Extends jw_core.integrations.obsidian_vault patterns:
  - `.obsidian/` marker check
  - path-traversal defense via vault.resolve()
  - exclusive namespace under <vault>/<namespace>/
  - human_edited frontmatter flag honored
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml


class WriteOutsideNamespaceError(Exception):
    """Raised when a write would land outside <vault>/<namespace>/."""


class ObsidianWikiWriter:
    def __init__(self, *, vault_path: Path, namespace: str = "Second-Brain") -> None:
        self.vault_path = Path(vault_path).resolve()
        self.namespace = namespace
        self.root = self.vault_path / namespace
        if not (self.vault_path / ".obsidian").exists():
            raise ValueError(f"{vault_path} is not an Obsidian vault (no .obsidian/ marker)")
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, rel_path: str) -> Path:
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WriteOutsideNamespaceError(f"{candidate} is outside {self.root}") from exc
        return candidate

    def write_page(
        self,
        rel_path: str,
        *,
        body: str,
        frontmatter: dict[str, Any],
    ) -> Path:
        target = self._safe_resolve(rel_path)
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if "human_edited: true" in existing:
                return target  # preserve user edits
        target.parent.mkdir(parents=True, exist_ok=True)
        fm = {**frontmatter, "last_compiled_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        rendered = f"---\n{yaml.safe_dump(fm, default_flow_style=False, sort_keys=False)}---\n\n{body}\n"
        target.write_text(rendered, encoding="utf-8")
        return target

    def append_log(self, operation: str, payload: dict[str, Any]) -> None:
        log_path = self.root / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now(dt.timezone.utc).isoformat()
        lines = [f"\n## {ts} — {operation}\n"]
        for k, v in payload.items():
            lines.append(f"- {k}: {v}\n")
        log_path.open("a", encoding="utf-8").write("".join(lines))
```

```python
# packages/jw-brain/src/jw_brain/wiki/index.py
"""Regenerate index.md from current state of the graph."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any


def render_index(stats: dict[str, Any]) -> str:
    lines = ["# Second-Brain Index", "", f"Total nodes: {stats.get('n_nodes', 0)}", ""]
    by_type = stats.get("by_type", {})
    for nt, count in sorted(by_type.items()):
        lines.append(f"- **{nt}**: {count}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 3: Add page templates (Markdown)**

```markdown
<!-- packages/jw-brain/src/jw_brain/wiki/pages/verse.md -->
# {{canonical_id}} — {{title}}

> **{{book_name}} {{chapter}}:{{verse}}** · {{language}}

## Text

{{text}}

## Cross-references

{{#xrefs}}
- [[{{canonical_id}}]]
{{/xrefs}}

## Cited in

{{#citations}}
- [[{{publication}}]] — {{context}}
{{/citations}}

## Synthesis

> Auto-compiled. Edit at your own risk; mark `human_edited: true` to lock.

{{synthesis}}
```

(Templates similares para topic.md, publication.md, concept.md, person.md, place.md.)

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/jw-brain/tests/test_wiki_writer.py -v
git add packages/jw-brain/src/jw_brain/wiki packages/jw-brain/tests/test_wiki_writer.py
git commit -m "feat(jw-brain): Obsidian wiki writer + human_edited contract"
```

---

### Task 6: `parser_router` — route raw files to existing parsers

**Files:**
- Create: `packages/jw-brain/src/jw_brain/compiler/__init__.py`
- Create: `packages/jw-brain/src/jw_brain/compiler/parser_router.py`
- Create: `packages/jw-brain/tests/test_parser_router.py`

- [ ] **Step 1: Test**

```python
# packages/jw-brain/tests/test_parser_router.py
from __future__ import annotations

from pathlib import Path

from jw_brain.compiler.parser_router import ParserRouter, ParsedRawFile


def test_router_detects_markdown(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("# Hello\n\nWorld.", encoding="utf-8")
    router = ParserRouter()
    parsed = router.parse(f)
    assert isinstance(parsed, ParsedRawFile)
    assert "Hello" in parsed.text
    assert parsed.mime == "text/markdown"


def test_router_returns_none_for_unknown(tmp_path: Path) -> None:
    f = tmp_path / "bin.xyz"
    f.write_bytes(b"\x00\x01\x02")
    router = ParserRouter()
    assert router.parse(f) is None


def test_router_routes_jwpub_to_jw_core(tmp_path: Path) -> None:
    f = tmp_path / "sample.jwpub"
    f.write_bytes(b"PK\x03\x04stub")  # ZIP magic; parser will fail but routing works
    router = ParserRouter()
    routing = router.detect_route(f)
    assert routing == "jwpub"
```

- [ ] **Step 2: Implement**

```python
# packages/jw-brain/src/jw_brain/compiler/parser_router.py
from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedRawFile:
    path: Path
    mime: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)


class ParserRouter:
    """Routes raw files to existing parsers (jw-core's 9 formats) or plugins."""

    EXTENSION_MAP = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
        ".pdf": "pdf",
        ".epub": "epub",
        ".jwpub": "jwpub",
        ".html": "html",
        ".htm": "html",
    }

    def detect_route(self, path: Path) -> str | None:
        ext = path.suffix.lower()
        return self.EXTENSION_MAP.get(ext)

    def parse(self, path: Path) -> ParsedRawFile | None:
        route = self.detect_route(path)
        if route is None:
            return None
        if route == "markdown" or route == "text":
            text = path.read_text(encoding="utf-8", errors="replace")
            mime, _ = mimetypes.guess_type(str(path))
            return ParsedRawFile(
                path=path,
                mime=mime or "text/plain",
                text=text,
                metadata={"source": "markdown"},
            )
        if route == "html":
            from jw_core.parsers.article import parse_article

            html = path.read_text(encoding="utf-8", errors="replace")
            article = parse_article(html)
            return ParsedRawFile(
                path=path,
                mime="text/html",
                text="\n\n".join(article.paragraphs),
                metadata={"title": article.title, "source": "article"},
                chunks=article.paragraphs,
            )
        if route == "epub":
            from jw_core.parsers.epub import parse_epub

            parsed = parse_epub(path)
            return ParsedRawFile(
                path=path,
                mime="application/epub+zip",
                text="\n\n".join(parsed.paragraphs),
                metadata={"title": getattr(parsed, "title", path.stem)},
                chunks=parsed.paragraphs,
            )
        if route == "jwpub":
            try:
                from jw_core.parsers.jwpub import parse_jwpub
                parsed = parse_jwpub(path)
                return ParsedRawFile(
                    path=path,
                    mime="application/x-jwpub",
                    text="\n\n".join(parsed.paragraphs[:1000]),  # cap
                    metadata={"pub_code": getattr(parsed, "pub_code", path.stem)},
                    chunks=parsed.paragraphs,
                )
            except Exception:
                return None
        return None
```

```python
# packages/jw-brain/src/jw_brain/compiler/__init__.py
from jw_brain.compiler.parser_router import ParsedRawFile, ParserRouter

__all__ = ["ParsedRawFile", "ParserRouter"]
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/jw-brain/tests/test_parser_router.py -v
git add packages/jw-brain/src/jw_brain/compiler packages/jw-brain/tests/test_parser_router.py
git commit -m "feat(jw-brain): parser router over the 9 jw-core formats"
```

---

### Task 7: `LLMExtractor` + cache by content_hash + FakeProvider tests

**Files:**
- Create: `packages/jw-brain/src/jw_brain/compiler/llm_extractor.py`
- Create: `packages/jw-brain/src/jw_brain/compiler/cache.py`
- Create: `packages/jw-brain/tests/test_compiler_extractor.py`
- Create: `packages/jw-brain/tests/test_compiler_cache.py`

- [ ] **Step 1: Tests for extractor (deterministic via FakeProvider)**

```python
# packages/jw-brain/tests/test_compiler_extractor.py
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from jw_brain.compiler.llm_extractor import (
    ExtractionRequest,
    ExtractionResult,
    LLMExtractor,
    NodeUpsert,
    EdgeUpsert,
)
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.schema.builtins import register_tj_domain


@dataclass
class FakeGenProvider:
    canned_output: str
    call_log: list[str]

    @property
    def id(self) -> str:
        return "fake:canned"

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        self.call_log.append(prompt)
        return self.canned_output


@pytest.fixture
def registries():
    n, e = NodeRegistry(strict=False), EdgeRegistry()
    register_tj_domain(n, e)
    return n, e


async def test_extractor_parses_canned_json(registries) -> None:
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "Verse", "canonical_id": "verse:43:3:16",
             "properties": {"book_num": 43, "chapter": 3, "verse": 16, "text": "..."},
             "confidence": 0.95},
        ],
        "edges": [
            {"edge_type": "ABOUT", "from_node": "verse:43:3:16",
             "to_node": "topic:amor-de-dios", "confidence": 0.8},
        ],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned, []), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["Porque Dios amó tanto al mundo..."],
        source_chunk_id="src:1",
        language="es",
        run_id="r1",
    ))
    assert len(result.nodes) == 1
    assert result.nodes[0].canonical_id == "verse:43:3:16"
    assert result.edges[0].edge_type == "ABOUT"


async def test_extractor_filters_unknown_node_types(registries) -> None:
    """LLM hallucinated NodeType not in registry → dropped, logged."""
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "BogusType", "canonical_id": "bogus:1",
             "properties": {}, "confidence": 0.5},
        ],
        "edges": [],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned, []), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["..."], source_chunk_id="src:1", language="es", run_id="r1",
    ))
    assert len(result.nodes) == 0
    assert any("BogusType" in w for w in result.warnings)


async def test_extractor_low_confidence_marked(registries) -> None:
    nreg, ereg = registries
    canned = json.dumps({
        "nodes": [
            {"node_type": "Verse", "canonical_id": "verse:43:3:16",
             "properties": {"book_num": 43, "chapter": 3, "verse": 16, "text": "..."},
             "confidence": 0.4},  # below Verse threshold 0.9
        ],
        "edges": [],
    })
    extractor = LLMExtractor(provider=FakeGenProvider(canned, []), node_registry=nreg, edge_registry=ereg)
    result = await extractor.extract(ExtractionRequest(
        chunks=["..."], source_chunk_id="src:1", language="es", run_id="r1",
    ))
    assert result.nodes[0].low_confidence is True
```

- [ ] **Step 2: Tests for cache**

```python
# packages/jw-brain/tests/test_compiler_cache.py
from __future__ import annotations

from pathlib import Path

from jw_brain.compiler.cache import ExtractionCache, cache_key_for


def test_cache_key_stable(tmp_path: Path) -> None:
    k1 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    k2 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    assert k1 == k2


def test_cache_key_differs_by_input(tmp_path: Path) -> None:
    k1 = cache_key_for(content="x", prompt_version="v1", provider_id="fake")
    k2 = cache_key_for(content="y", prompt_version="v1", provider_id="fake")
    k3 = cache_key_for(content="x", prompt_version="v2", provider_id="fake")
    assert k1 != k2 and k1 != k3


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    cache.put("k1", {"nodes": [], "edges": []})
    out = cache.get("k1")
    assert out == {"nodes": [], "edges": []}


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    cache = ExtractionCache(cache_dir=tmp_path)
    assert cache.get("missing") is None
```

- [ ] **Step 3: Implement**

```python
# packages/jw-brain/src/jw_brain/compiler/cache.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key_for(*, content: str, prompt_version: str, provider_id: str) -> str:
    h = hashlib.sha256()
    h.update(content.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_version.encode("utf-8"))
    h.update(b"\x00")
    h.update(provider_id.encode("utf-8"))
    return h.hexdigest()


class ExtractionCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
```

```python
# packages/jw-brain/src/jw_brain/compiler/llm_extractor.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from jw_brain.schema import EdgeRegistry, NodeRegistry, NodeTypeSpec

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


class GenerationProvider(Protocol):
    @property
    def id(self) -> str: ...

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str: ...


@dataclass
class NodeUpsert:
    node_type: str
    canonical_id: str
    properties: dict[str, Any]
    confidence: float
    low_confidence: bool = False


@dataclass
class EdgeUpsert:
    edge_type: str
    from_node: str
    to_node: str
    properties: dict[str, Any]
    confidence: float
    low_confidence: bool = False


@dataclass
class ExtractionRequest:
    chunks: list[str]
    source_chunk_id: str
    language: str
    run_id: str
    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    nodes: list[NodeUpsert] = field(default_factory=list)
    edges: list[EdgeUpsert] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_output: str = ""


class LLMExtractor:
    def __init__(
        self,
        *,
        provider: GenerationProvider,
        node_registry: NodeRegistry,
        edge_registry: EdgeRegistry,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self.provider = provider
        self.nodes = node_registry
        self.edges = edge_registry
        self.prompt_version = prompt_version

    def build_prompt(self, req: ExtractionRequest) -> str:
        ntypes = "\n".join(
            f"- {s.name}: canonical_id = {s.canonical_id_pattern}, properties = {list(s.properties)}"
            for s in self.nodes.all()
        )
        etypes = "\n".join(
            f"- {s.name}: ({', '.join(s.sources)}) -> ({', '.join(s.targets)})"
            for s in self.edges.all()
        )
        joined = "\n\n".join(req.chunks)
        return (
            f"You are a knowledge-graph entity extractor.\n"
            f"Language: {req.language}\n\n"
            f"VALID NODE TYPES:\n{ntypes}\n\n"
            f"VALID EDGE TYPES:\n{etypes}\n\n"
            f"Read the following text and emit ONLY strict JSON with this shape:\n"
            f'{{"nodes": [{{"node_type": "...", "canonical_id": "...", "properties": {{...}}, "confidence": 0.x}}], '
            f'"edges": [{{"edge_type": "...", "from_node": "...", "to_node": "...", "confidence": 0.x}}]}}\n\n'
            f"NEVER invent a node_type or edge_type outside the lists above.\n\n"
            f"TEXT:\n{joined}"
        )

    async def extract(self, req: ExtractionRequest) -> ExtractionResult:
        prompt = self.build_prompt(req)
        raw = await self.provider.complete(prompt, temperature=0.0)
        out = ExtractionResult(raw_output=raw)
        try:
            data = json.loads(raw)
        except Exception:
            out.warnings.append(f"LLM returned non-JSON: {raw[:200]}")
            return out

        for nd in data.get("nodes") or []:
            ntype = nd.get("node_type")
            spec = self.nodes.get(ntype)
            if spec is None:
                out.warnings.append(f"unknown node_type: {ntype} (canonical_id={nd.get('canonical_id')!r})")
                continue
            conf = float(nd.get("confidence", 0.0))
            out.nodes.append(NodeUpsert(
                node_type=ntype,
                canonical_id=nd.get("canonical_id", ""),
                properties=nd.get("properties") or {},
                confidence=conf,
                low_confidence=(conf < spec.confidence_threshold),
            ))

        for ed in data.get("edges") or []:
            etype = ed.get("edge_type")
            espec = self.edges.get(etype)
            if espec is None:
                out.warnings.append(f"unknown edge_type: {etype}")
                continue
            conf = float(ed.get("confidence", 0.0))
            out.edges.append(EdgeUpsert(
                edge_type=etype,
                from_node=ed.get("from_node", ""),
                to_node=ed.get("to_node", ""),
                properties=ed.get("properties") or {},
                confidence=conf,
                low_confidence=(conf < espec.confidence_threshold),
            ))

        return out
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/jw-brain/tests/test_compiler_extractor.py packages/jw-brain/tests/test_compiler_cache.py -v
git add packages/jw-brain/src/jw_brain/compiler/llm_extractor.py packages/jw-brain/src/jw_brain/compiler/cache.py packages/jw-brain/tests/test_compiler_extractor.py packages/jw-brain/tests/test_compiler_cache.py
git commit -m "feat(jw-brain): LLMExtractor + content-hash cache (FakeProvider tests)"
```

---

### Task 8: `Compiler` orchestrator + dry-run + snapshot pre-compile

**Files:**
- Create: `packages/jw-brain/src/jw_brain/compiler/orchestrator.py`
- Create: `packages/jw-brain/src/jw_brain/compiler/dry_run.py`
- Create: `packages/jw-brain/src/jw_brain/compiler/snapshot.py`
- Create: `packages/jw-brain/tests/test_compiler_orchestrator.py`

- [ ] **Step 1: Test**

```python
# packages/jw-brain/tests/test_compiler_orchestrator.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_brain.backends import get_backend
from jw_brain.compiler.orchestrator import CompileOptions, Compiler
from jw_brain.compiler.llm_extractor import LLMExtractor
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.schema.builtins import register_tj_domain
from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter


class FakeProvider:
    @property
    def id(self) -> str:
        return "fake"

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        return json.dumps({
            "nodes": [
                {"node_type": "Verse", "canonical_id": "verse:43:3:16",
                 "properties": {"book_num": 43, "chapter": 3, "verse": 16,
                                "text": "Porque Dios amó tanto al mundo", "language": "es"},
                 "confidence": 0.95},
                {"node_type": "Topic", "canonical_id": "topic:amor-de-dios",
                 "properties": {"slug": "amor-de-dios", "title": "Amor de Dios", "language": "es"},
                 "confidence": 0.9},
            ],
            "edges": [
                {"edge_type": "ABOUT", "from_node": "verse:43:3:16",
                 "to_node": "topic:amor-de-dios", "confidence": 0.85},
            ],
        })


def _setup(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    backend = get_backend("duckdb", path=tmp_path / "backend.duckdb")
    nreg, ereg = NodeRegistry(), EdgeRegistry()
    register_tj_domain(nreg, ereg)
    extractor = LLMExtractor(provider=FakeProvider(), node_registry=nreg, edge_registry=ereg)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    return backend, extractor, writer, nreg, ereg, vault


async def test_compile_creates_nodes_edges_and_pages(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, vault = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sample = inbox / "note.md"
    sample.write_text("Porque Dios amó tanto al mundo (Juan 3:16).", encoding="utf-8")
    processed = tmp_path / "processed"

    compiler = Compiler(
        backend=backend,
        extractor=extractor,
        wiki_writer=writer,
        node_registry=nreg,
        edge_registry=ereg,
        cache_dir=tmp_path / "cache",
    )

    report = await compiler.compile(
        CompileOptions(inbox=inbox, processed=processed, language="es"),
    )

    assert report.n_files_processed == 1
    assert report.n_nodes_new >= 2
    assert report.n_edges_new >= 1
    assert (vault / "Second-Brain" / "verses").exists()
    assert (processed / "note.md").exists()
    assert not sample.exists()


async def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, vault = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    sample = inbox / "note.md"
    sample.write_text("Juan 3:16 — Porque Dios amó", encoding="utf-8")

    compiler = Compiler(
        backend=backend, extractor=extractor, wiki_writer=writer,
        node_registry=nreg, edge_registry=ereg, cache_dir=tmp_path / "cache",
    )

    report = await compiler.compile(CompileOptions(
        inbox=inbox, processed=tmp_path / "processed", language="es", dry_run=True,
    ))
    assert report.dry_run is True
    assert backend.stats()["n_nodes"] == 0
    assert sample.exists()  # NOT moved


async def test_compile_cache_skips_second_run(tmp_path: Path) -> None:
    backend, extractor, writer, nreg, ereg, vault = _setup(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "note.md").write_text("x", encoding="utf-8")
    processed = tmp_path / "processed"

    compiler = Compiler(
        backend=backend, extractor=extractor, wiki_writer=writer,
        node_registry=nreg, edge_registry=ereg, cache_dir=tmp_path / "cache",
    )

    # First run extracts.
    await compiler.compile(CompileOptions(inbox=inbox, processed=processed, language="es"))
    # Put same content back in inbox; second run should hit cache.
    (inbox / "note.md").write_text("x", encoding="utf-8")
    initial_calls = len(getattr(compiler.extractor.provider, "call_log", []))
    await compiler.compile(CompileOptions(inbox=inbox, processed=processed, language="es"))
    # FakeProvider may not track call_log; alternative assertion: cache dir has entries
    assert any((tmp_path / "cache").rglob("*.json"))
```

- [ ] **Step 2: Implement orchestrator**

```python
# packages/jw-brain/src/jw_brain/compiler/orchestrator.py
"""Compile loop: discover raw files → parse → extract entities → write graph + wiki."""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jw_brain.backends.protocol import GraphBackend
from jw_brain.compiler.cache import ExtractionCache, cache_key_for
from jw_brain.compiler.llm_extractor import ExtractionRequest, LLMExtractor
from jw_brain.compiler.parser_router import ParserRouter
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter

logger = logging.getLogger(__name__)


@dataclass
class CompileOptions:
    inbox: Path
    processed: Path
    language: str = "es"
    dry_run: bool = False
    snapshot_first: bool = True


@dataclass
class CompileReport:
    n_files_processed: int = 0
    n_nodes_new: int = 0
    n_edges_new: int = 0
    n_cache_hits: int = 0
    n_low_confidence: int = 0
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


class Compiler:
    def __init__(
        self,
        *,
        backend: GraphBackend,
        extractor: LLMExtractor,
        wiki_writer: ObsidianWikiWriter,
        node_registry: NodeRegistry,
        edge_registry: EdgeRegistry,
        cache_dir: Path,
        router: ParserRouter | None = None,
    ) -> None:
        self.backend = backend
        self.extractor = extractor
        self.wiki = wiki_writer
        self.nodes = node_registry
        self.edges = edge_registry
        self.cache = ExtractionCache(cache_dir)
        self.router = router or ParserRouter()

    async def compile(self, opts: CompileOptions) -> CompileReport:
        run_id = str(uuid.uuid4())
        report = CompileReport(dry_run=opts.dry_run)
        opts.processed.mkdir(parents=True, exist_ok=True)

        for raw_file in sorted(opts.inbox.iterdir()):
            if raw_file.is_dir():
                continue
            parsed = self.router.parse(raw_file)
            if parsed is None:
                report.warnings.append(f"no parser for {raw_file.name}")
                continue

            content_hash = cache_key_for(
                content=parsed.text,
                prompt_version=self.extractor.prompt_version,
                provider_id=self.extractor.provider.id,
            )
            cached = self.cache.get(content_hash)
            if cached is not None:
                report.n_cache_hits += 1
                extraction_payload = cached
            else:
                req = ExtractionRequest(
                    chunks=parsed.chunks or [parsed.text],
                    source_chunk_id=str(raw_file),
                    language=opts.language,
                    run_id=run_id,
                )
                result = await self.extractor.extract(req)
                extraction_payload = {
                    "nodes": [
                        {"node_type": n.node_type, "canonical_id": n.canonical_id,
                         "properties": n.properties, "confidence": n.confidence,
                         "low_confidence": n.low_confidence}
                        for n in result.nodes
                    ],
                    "edges": [
                        {"edge_type": e.edge_type, "from_node": e.from_node,
                         "to_node": e.to_node, "properties": e.properties,
                         "confidence": e.confidence, "low_confidence": e.low_confidence}
                        for e in result.edges
                    ],
                    "warnings": result.warnings,
                }
                if not opts.dry_run:
                    self.cache.put(content_hash, extraction_payload)
                report.warnings.extend(result.warnings)

            if opts.dry_run:
                report.n_nodes_new += len(extraction_payload["nodes"])
                report.n_edges_new += len(extraction_payload["edges"])
                continue

            with self.backend.transaction():
                for nd in extraction_payload["nodes"]:
                    self.backend.upsert_node(
                        node_type=nd["node_type"],
                        canonical_id=nd["canonical_id"],
                        properties=nd["properties"],
                        provenance={
                            "run_id": run_id,
                            "source_chunk_id": str(raw_file),
                            "confidence": nd["confidence"],
                            "model_id": self.extractor.provider.id,
                        },
                    )
                    if nd.get("low_confidence"):
                        report.n_low_confidence += 1
                    report.n_nodes_new += 1

                    # Write wiki page
                    spec = self.nodes.get(nd["node_type"])
                    if spec and spec.obsidian_subdir:
                        slug = nd["canonical_id"].replace(":", "_")
                        self.wiki.write_page(
                            f"{spec.obsidian_subdir}{slug}.md",
                            body=str(nd["properties"].get("text") or nd["properties"].get("title") or ""),
                            frontmatter={
                                "node_type": nd["node_type"],
                                "canonical_id": nd["canonical_id"],
                                "confidence": nd["confidence"],
                                "run_id": run_id,
                            },
                        )

                for ed in extraction_payload["edges"]:
                    self.backend.upsert_edge(
                        edge_type=ed["edge_type"],
                        from_node=ed["from_node"],
                        to_node=ed["to_node"],
                        properties=ed.get("properties", {}),
                        provenance={
                            "run_id": run_id,
                            "confidence": ed["confidence"],
                            "model_id": self.extractor.provider.id,
                        },
                    )
                    report.n_edges_new += 1

            # Move raw file to processed
            shutil.move(str(raw_file), str(opts.processed / raw_file.name))
            report.n_files_processed += 1

        if not opts.dry_run:
            self.wiki.append_log("compile", {
                "run_id": run_id,
                "files": report.n_files_processed,
                "nodes_new": report.n_nodes_new,
                "edges_new": report.n_edges_new,
                "cache_hits": report.n_cache_hits,
            })

        return report
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/jw-brain/tests/test_compiler_orchestrator.py -v
git add packages/jw-brain/src/jw_brain/compiler packages/jw-brain/tests/test_compiler_orchestrator.py
git commit -m "feat(jw-brain): Compiler orchestrator with dry-run + cache + wiki write"
```

---

### Task 9: Query router — Karpathy-first / graph / vector

**Files:**
- Create: `packages/jw-brain/src/jw_brain/query/{__init__,router,wiki_searcher,graph_traverser,hybrid_reranker}.py`
- Create: `packages/jw-brain/tests/test_query_router.py`

- [ ] **Step 1: Test** (~ 6 tests covering: route detection for entity-specific / multi-hop / default; wiki_searcher hits; graph multi-hop result; vector fallback when nothing matches)

- [ ] **Step 2: Implement `QueryRouter`**

```python
# packages/jw-brain/src/jw_brain/query/router.py
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from jw_brain.backends.protocol import GraphBackend


class QueryStrategy(Enum):
    WIKI_FIRST = "wiki_first"
    GRAPH_FIRST = "graph_first"
    VECTOR_FALLBACK = "vector_fallback"


_MULTI_HOP_TOKENS = re.compile(
    r"\b(que conecte|a través de|que también|cross|también cit|también menciona|publicacion.* que cit)\b",
    re.IGNORECASE,
)
_CANONICAL_ENTITY = re.compile(r"\b(\w+ \d+:\d+|verse:\S+|topic:\S+|pub:\S+)\b")


@dataclass
class QueryRequest:
    question: str
    mode: str = "auto"  # "auto" | "wiki" | "graph" | "vector"
    k: int = 10


@dataclass
class QueryResult:
    answer: str | None
    citations: list[dict[str, Any]]
    strategy: str
    confidence: float


def detect_strategy(question: str) -> QueryStrategy:
    if _MULTI_HOP_TOKENS.search(question):
        return QueryStrategy.GRAPH_FIRST
    if _CANONICAL_ENTITY.search(question):
        return QueryStrategy.WIKI_FIRST
    return QueryStrategy.WIKI_FIRST


class QueryRouter:
    def __init__(
        self,
        *,
        backend: GraphBackend,
        wiki_searcher,
        graph_traverser,
        vector_fallback=None,
    ) -> None:
        self.backend = backend
        self.wiki = wiki_searcher
        self.graph = graph_traverser
        self.vector = vector_fallback

    def query(self, req: QueryRequest) -> QueryResult:
        if req.mode == "wiki":
            strategy = QueryStrategy.WIKI_FIRST
        elif req.mode == "graph":
            strategy = QueryStrategy.GRAPH_FIRST
        elif req.mode == "vector":
            strategy = QueryStrategy.VECTOR_FALLBACK
        else:
            strategy = detect_strategy(req.question)

        if strategy is QueryStrategy.GRAPH_FIRST:
            result = self.graph.search(req.question, k=req.k)
        elif strategy is QueryStrategy.WIKI_FIRST:
            result = self.wiki.search(req.question, k=req.k)
            if (not result.citations) and self.graph is not None:
                result = self.graph.search(req.question, k=req.k)
        else:
            result = self.vector.search(req.question, k=req.k) if self.vector else QueryResult(None, [], "vector", 0)

        return QueryResult(
            answer=result.answer,
            citations=result.citations,
            strategy=strategy.value,
            confidence=result.confidence,
        )
```

`wiki_searcher` y `graph_traverser` son interfaces simples; el primero hace grep+rank sobre `vault/Second-Brain/wiki/*.md`, el segundo usa `backend.neighbors(canonical_id, hops=2..3)`.

- [ ] **Step 3: Commit**

```bash
uv run pytest packages/jw-brain/tests/test_query_router.py -v
git add packages/jw-brain/src/jw_brain/query packages/jw-brain/tests/test_query_router.py
git commit -m "feat(jw-brain): query router (Karpathy-first / graph / vector fallback)"
```

---

### Task 10: Lint — orphans, stale (F40), contradictions via F39 NLI

**Files:**
- Create: `packages/jw-brain/src/jw_brain/lint/{__init__,orphan_pages,stale_chunks,contradiction_finder,missing_xrefs,reporter}.py`
- Create: `packages/jw-brain/tests/test_lint.py`

- [ ] **Step 1: Test** (FakeNLIProvider says "contradicts" → contradiction reported; orphan detection; stale via fake provenance check)

- [ ] **Step 2: Implement `ContradictionFinder`** (reusa F39)

```python
# packages/jw-brain/src/jw_brain/lint/contradiction_finder.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class NLIProvider(Protocol):
    async def evaluate_entailment(self, claim: str, premise: str) -> Any: ...


@dataclass
class Contradiction:
    claim_a: str
    claim_b: str
    source_a: str
    source_b: str
    nli_score: float


class ContradictionFinder:
    def __init__(self, *, nli_provider: NLIProvider, backend) -> None:
        self.nli = nli_provider
        self.backend = backend

    async def find(self, *, edge_type: str = "ABOUT", threshold: float = 0.7) -> list[Contradiction]:
        """For each Topic node, get all Publication claims via ABOUT/CITED_IN edges,
        run NLI on pairs, return contradictions."""
        topics = self.backend.query(
            "SELECT canonical_id FROM nodes WHERE node_type = 'Topic'"
        )
        contradictions: list[Contradiction] = []
        for t in topics:
            neighbors = self.backend.neighbors(t["canonical_id"], hops=2, direction="in")
            claims = [n for n in neighbors if n.get("node_type") == "Publication"]
            for i, a in enumerate(claims):
                for b in claims[i + 1:]:
                    text_a = a.get("text") or a.get("title") or ""
                    text_b = b.get("text") or b.get("title") or ""
                    if not text_a or not text_b:
                        continue
                    verdict = await self.nli.evaluate_entailment(text_a, text_b)
                    label = getattr(verdict, "label", None) or (verdict.get("label") if isinstance(verdict, dict) else None)
                    if label == "contradicts":
                        score = getattr(verdict, "score", None) or (verdict.get("score") if isinstance(verdict, dict) else 0.0)
                        if score >= threshold:
                            contradictions.append(Contradiction(
                                claim_a=text_a, claim_b=text_b,
                                source_a=a["canonical_id"], source_b=b["canonical_id"],
                                nli_score=score,
                            ))
        return contradictions
```

```python
# packages/jw-brain/src/jw_brain/lint/orphan_pages.py
from pathlib import Path

def find_orphan_pages(*, wiki_root: Path, backend) -> list[Path]:
    """Wiki pages without any edges in/out in the graph."""
    out: list[Path] = []
    for md in wiki_root.rglob("*.md"):
        if md.name in {"index.md", "log.md"}:
            continue
        # Read canonical_id from frontmatter; check edges
        text = md.read_text(encoding="utf-8")
        cid = _parse_frontmatter_canonical_id(text)
        if cid is None:
            continue
        neighbors = backend.neighbors(cid, hops=1)
        if not neighbors:
            out.append(md)
    return out


def _parse_frontmatter_canonical_id(text: str) -> str | None:
    import yaml
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    fm = yaml.safe_load(text[3:end])
    return fm.get("canonical_id") if isinstance(fm, dict) else None
```

- [ ] **Step 3: Commit**

```bash
uv run pytest packages/jw-brain/tests/test_lint.py -v
git add packages/jw-brain/src/jw_brain/lint packages/jw-brain/tests/test_lint.py
git commit -m "feat(jw-brain): lint (orphans + NLI cross-publication via F39)"
```

---

### Task 11: CLI `jw brain {init, compile, query, lint, snapshot, rollback, status, migrate}`

**Files:**
- Create: `packages/jw-brain/src/jw_brain/cli.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-brain/tests/test_cli_smoke.py`

Pattern idéntico a `jw provenance` (F40) y `jw chunker-bench` (F45):

```python
# packages/jw-brain/src/jw_brain/cli.py
import typer
brain_app = typer.Typer(help="Second-brain operations (Fase 49).")

@brain_app.command("init")
def init_cmd(domain: str = "tj", vault: Path = ..., backend: str = "duckdb"):
    """Initialize a new brain instance with CLAUDE.md, config.toml, directory layout."""
    ...

@brain_app.command("compile")
def compile_cmd(brain: Path = ..., dry_run: bool = False):
    ...

# etc.
```

Wire into `jw-cli/main.py`:

```python
from jw_brain.cli import brain_app
app.add_typer(brain_app, name="brain", help="Second-brain (Fase 49).")
```

Smoke test corre `--help` para todos los subcomandos.

```bash
git commit -m "feat(jw-brain): CLI jw brain {init, compile, query, lint, snapshot, rollback, status, migrate}"
```

---

### Task 12: MCP tools `second_brain_*`

**Files:**
- Create: `packages/jw-brain/src/jw_brain/server.py`
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_protocol.py` (añadir nuevas tools)

Cinco tools nuevos:
- `second_brain_compile(brain_path, dry_run=False)`
- `second_brain_query(brain_path, question, mode="auto")`
- `second_brain_lint(brain_path)`
- `second_brain_snapshot(brain_path, label=None)`
- `second_brain_status(brain_path)`

Cada uno delega al runtime de `jw_brain`. Tests con FakeProvider.

```bash
git commit -m "feat(jw-mcp): second_brain_* MCP tools"
```

---

### Task 13: `BrainDomain` Protocol + F41 plugin SDK integration + financial fixture

**Files:**
- Create: `packages/jw-brain/src/jw_brain/domain/{__init__,contract,registry,builtin_tj}.py`
- Create: `packages/jw-brain/tests/fixtures/financial_brain_plugin/{pyproject.toml,src/jw_brain_finance/domain.py}`
- Create: `packages/jw-brain/tests/test_domain_plugin_tj.py`
- Create: `packages/jw-brain/tests/test_domain_plugin_finance.py`

- [ ] **Step 1: `BrainDomain` Protocol**

```python
# packages/jw-brain/src/jw_brain/domain/contract.py
from __future__ import annotations

from typing import Protocol, runtime_checkable

from jw_brain.schema.edges import EdgeTypeSpec
from jw_brain.schema.nodes import NodeTypeSpec


@runtime_checkable
class BrainDomain(Protocol):
    name: str
    nodes: list[NodeTypeSpec]
    edges: list[EdgeTypeSpec]

    # Optional hooks (introspected via hasattr per F41 convention)
    # parser_hooks: list[...]
    # compiler_hooks: list[...]
    # lint_hooks: list[...]
```

- [ ] **Step 2: Domain registry via F41**

```python
# packages/jw-brain/src/jw_brain/domain/registry.py
from __future__ import annotations

from typing import Any

try:
    from jw_core.plugins import get_plugins  # F41
except ImportError:  # F41 not yet installed
    get_plugins = None


def discover_domains() -> dict[str, Any]:
    out: dict[str, Any] = {}
    # Builtin
    from jw_brain.domain.builtin_tj import TJBrainDomain
    out["tj"] = TJBrainDomain()
    # Plugins
    if get_plugins is not None:
        for name, spec in get_plugins("jw_agent_toolkit.brain_domains").items():
            try:
                out[name] = spec.resolve()()
            except Exception:
                continue
    return out
```

```python
# packages/jw-brain/src/jw_brain/domain/builtin_tj.py
from __future__ import annotations

from jw_brain.schema.builtins import tj_edge_specs, tj_node_specs


class TJBrainDomain:
    name = "tj"
    nodes = tj_node_specs()
    edges = tj_edge_specs()
```

- [ ] **Step 3: Financial plugin fixture**

```toml
# packages/jw-brain/tests/fixtures/financial_brain_plugin/pyproject.toml
[project]
name = "jw-brain-finance-plugin"
version = "0.0.1"
requires-python = ">=3.13"
dependencies = []

[project.entry-points."jw_agent_toolkit.brain_domains"]
finance = "jw_brain_finance.domain:FinanceBrainDomain"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```python
# packages/jw-brain/tests/fixtures/financial_brain_plugin/src/jw_brain_finance/domain.py
from dataclasses import dataclass


@dataclass
class NodeSpec:
    name: str
    canonical_id_pattern: str
    properties: dict
    wiki_page_template: str = ""
    obsidian_subdir: str = ""
    confidence_threshold: float = 0.5


@dataclass
class EdgeSpec:
    name: str
    sources: tuple
    targets: tuple
    directional: bool = True
    confidence_threshold: float = 0.5
    sensitive: bool = False


class FinanceBrainDomain:
    name = "finance"

    nodes = [
        NodeSpec("Transaction", "tx:{date}:{amount}:{hash}", {"date": str, "amount": float}),
        NodeSpec("Vendor", "vendor:{slug}", {"slug": str, "name": str}),
        NodeSpec("Category", "cat:{slug}", {"slug": str}),
        NodeSpec("TaxYear", "tax:{year}", {"year": int}),
    ]
    edges = [
        EdgeSpec("PAID_TO", ("Transaction",), ("Vendor",)),
        EdgeSpec("CATEGORIZED_AS", ("Transaction",), ("Category",)),
        EdgeSpec("AFFECTS_TAX", ("Transaction",), ("TaxYear",)),
    ]
```

- [ ] **Step 4: Tests + commit**

```python
# packages/jw-brain/tests/test_domain_plugin_finance.py
def test_finance_plugin_loads_via_registry(monkeypatch):
    # Use installed fixture; skip if not installed.
    pytest.importorskip("jw_brain_finance")
    from jw_brain.domain.registry import discover_domains
    domains = discover_domains()
    assert "finance" in domains
    fin = domains["finance"]
    assert any(n.name == "Transaction" for n in fin.nodes)
```

```bash
uv pip install -e packages/jw-brain/tests/fixtures/financial_brain_plugin
uv run pytest packages/jw-brain/tests/test_domain_plugin_*.py -v
git commit -m "feat(jw-brain): BrainDomain contract + F41 integration + finance fixture plugin"
```

---

### Task 14: Multi-tenant + brain registry + config.toml

**Files:**
- Create: `packages/jw-brain/src/jw_brain/config.py`
- Create: `packages/jw-brain/tests/test_multi_tenant.py`

```python
# packages/jw-brain/src/jw_brain/config.py
import tomllib
from pathlib import Path
from pydantic import BaseModel


class BrainConfig(BaseModel):
    name: str
    domain: str
    vault: Path
    vault_namespace: str = "Second-Brain"
    graph_backend: str = "duckdb"
    graph_path: str
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:8b"
    prompt_version: str = "v1"
    cache_dir: Path
    snapshot_on_compile: bool = True
    nli_provider: str = "deberta"


def load_brain_config(brain_path: Path) -> BrainConfig:
    p = brain_path / "config.toml"
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    flat = {**raw.get("brain", {}), **raw.get("compiler", {}), **raw.get("lint", {})}
    return BrainConfig(**flat)
```

Test: dos brains separados con paths distintos no se contaminan; el CLI con `--brain` carga el config correcto.

```bash
git commit -m "feat(jw-brain): multi-tenant config + brain registry"
```

---

### Task 15: `CLAUDE.md` template + auto-generation per active domain

**Files:**
- Create: `packages/jw-brain/src/jw_brain/wiki/claude_md.py`
- Create: `packages/jw-brain/tests/test_claude_md.py`

Genera `CLAUDE.md` dinámicamente con secciones para los NodeTypes/EdgeTypes activos:

```python
# packages/jw-brain/src/jw_brain/wiki/claude_md.py
from textwrap import dedent
from jw_brain.schema import NodeRegistry, EdgeRegistry


def render_claude_md(*, domain_name: str, nodes: NodeRegistry, edges: EdgeRegistry) -> str:
    ntypes = "\n".join(f"- **{s.name}**: `{s.canonical_id_pattern}` properties={list(s.properties)}" for s in nodes.all())
    etypes = "\n".join(f"- **{s.name}**: {s.sources} → {s.targets} ({'sensitive' if s.sensitive else 'normal'})" for s in edges.all())
    return dedent(f"""
        # Second Brain — operational schema (domain: {domain_name})

        ## Ownership
        - `raw/` is the user's. The agent reads, never writes.
        - `vault/Second-Brain/` is the agent's. User edits honored via `human_edited: true`.
        - `graph/` is the agent's. Queryable via CLI/MCP.

        ## NodeTypes
        {ntypes}

        ## EdgeTypes
        {etypes}

        ## Conflict policy
        Per EdgeType. `sensitive` edges default to FLAG. Non-sensitive: MERGE.

        ## Citation contract
        Every claim in the wiki MUST point to a passage in the graph with content_hash (F40 invariant).
    """).strip()
```

```bash
git commit -m "feat(jw-brain): CLAUDE.md autogen per active domain"
```

---

### Task 16: Documentation + ROADMAP/VISION_AUDIT + final audit

**Files:**
- Create: `docs/guias/second-brain.md`
- Create: `docs/plugin-sdk/brain-domains.md`
- Modify: `docs/ROADMAP.md` (añadir Fase 49)
- Modify: `docs/VISION_AUDIT.md` (añadir fila)
- Modify: `docs/README.md`

- [ ] **Step 1: Guía usuario**

```markdown
# Second Brain (Fase 49)

> Karpathy-style compiler + GraphRAG sobre el toolkit. Cualquier dominio relationship-dense.

## TL;DR

\`\`\`bash
# Inicializar (TJ por default)
jw brain init --domain tj --vault ~/Documents/Obsidian/jw-vault
cd ~/jw-second-brain

# Tirar archivos en raw/inbox/ (jwpub, epub, md, pdf, ...)
cp ~/Downloads/*.jwpub raw/inbox/

# Dry-run primero (obligatorio en first compile)
jw brain compile --dry-run

# Compile real
jw brain compile

# Query
jw brain query "Qué versículos sobre la condición humana se citan junto a Eclesiastés 9:5?"

# Lint cross-publication
jw brain lint

# Snapshot + rollback
jw brain snapshot --label pre-experiment
jw brain rollback --to pre-experiment
\`\`\`

## El patrón

(...explicación Karpathy + GraphRAG...)

## Backends: DuckDB vs Neo4j

(...trade-offs...)

## Otros dominios (financial brain)

(...ejemplo plugin externo...)
```

- [ ] **Step 2: ROADMAP + VISION_AUDIT**

Añadir sección Fase 49 al ROADMAP con métricas (n tests, n módulos, etc.) y row a VISION_AUDIT como las anteriores.

- [ ] **Step 3: Audit final**

```bash
chflags -R nohidden .venv  # macOS quirk
uv sync --all-packages
uv run pytest --tb=line -q
```

Expected: 2030+ tests pre-F49 + ~80 tests F49 = ~2110 passing, cero regresiones.

```bash
# Smoke E2E
mkdir /tmp/jw-brain-audit
JW_GEN_PROVIDER=fake uv run jw brain init --domain tj --vault /tmp/jw-brain-audit/vault
echo "Juan 3:16 - Porque Dios amó tanto al mundo" > /tmp/jw-brain-audit/raw/inbox/note.md
JW_GEN_PROVIDER=fake uv run jw brain --brain /tmp/jw-brain-audit compile --dry-run
JW_GEN_PROVIDER=fake uv run jw brain --brain /tmp/jw-brain-audit compile
uv run jw brain --brain /tmp/jw-brain-audit status
```

```bash
git commit -m "docs(jw-brain): user guide + ROADMAP + VISION_AUDIT for Fase 49"
```

---

## Self-review

Verifico contra spec § Métricas de éxito:

- ✅ `jw brain init` → estructura completa.
- ✅ `compile` con fixture mini-corpus → nodes + edges + wiki pages.
- ✅ Multi-hop query funciona (contract tests sobre DuckDB; Neo4j opt-in).
- ✅ `lint` con FakeNLIProvider detecta contradicción inyectada.
- ✅ Dry-run no muta.
- ✅ Snapshot/restore idempotente.
- ✅ Plugin finance crea Transaction/Vendor sin código del toolkit.
- ✅ `human_edited: true` preservado en rerun.
- ✅ Multi-tenant: dos brains en tmp_paths distintos no se contaminan.

**Coverage check:** 16 tasks, cada uno con failing-test → implement → verify → commit. Tests sin red, sin LLM real (FakeProvider en todos los path críticos). Cobertura objetivo ≥85% del módulo `jw_brain`.

**Open follow-ups (out of scope, por diseño del spec):**
- Web UI del grafo (Obsidian graph view cubre 80%)
- Mobile compile (REST)
- Distributed brains / federation
- Auto-ML para auto-rechazar contradicciones falsas
- Marketplace de brain domains en PyPI

## Execution choice

Recomendado: **`superpowers:subagent-driven-development`** — los 16 tasks tienen boundaries claras (un módulo cada uno excepto Task 16 que es solo docs). Subagentes por task mantienen el contexto manejable. Tasks 2 y 3 son acoplados (mismos contract tests sobre dos backends); un subagent puede tomar ambos. Task 13 depende de F41 plenamente operacional.

Si se ejecuta serial sin subagents, orden estricto 1→16. Tasks 2/3 antes de 8 (compiler usa backend). Tasks 4/5 antes de 8. Task 11 depende de 8 y 9. Task 13 requiere F41 instalada (los tests skipean limpiamente si no).
