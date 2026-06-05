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
    properties    VARCHAR,
    provenance    VARCHAR,
    created_at    TIMESTAMP DEFAULT now(),
    updated_at    TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS edges (
    id            VARCHAR PRIMARY KEY,
    edge_type     VARCHAR NOT NULL,
    from_node     VARCHAR NOT NULL,
    to_node       VARCHAR NOT NULL,
    properties    VARCHAR,
    provenance    VARCHAR,
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
        self.path: Path | None = (
            Path(path) if str(path) != ":memory:" else None
        )
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.path) if self.path else ":memory:")
        self._conn.execute(_SCHEMA_SQL)

    def upsert_node(self, *, node_type, canonical_id, properties, provenance) -> str:
        nid = canonical_id
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
        props = json.loads(props_raw) if props_raw else {}
        prov = json.loads(prov_raw) if prov_raw else {}
        return {
            "canonical_id": canonical_id,
            "node_type": ntype,
            "provenance": prov,
            **props,
        }

    def neighbors(self, canonical_id, *, edge_type=None, hops=1, direction="both"):
        if hops == 1:
            params: list[Any] = []
            if direction == "out":
                sql = "SELECT to_node FROM edges WHERE from_node = ?"
                params.append(canonical_id)
                if edge_type:
                    sql += " AND edge_type = ?"
                    params.append(edge_type)
            elif direction == "in":
                sql = "SELECT from_node FROM edges WHERE to_node = ?"
                params.append(canonical_id)
                if edge_type:
                    sql += " AND edge_type = ?"
                    params.append(edge_type)
            else:
                if edge_type:
                    sql = (
                        "SELECT to_node FROM edges WHERE from_node = ? AND edge_type = ? "
                        "UNION SELECT from_node FROM edges WHERE to_node = ? AND edge_type = ?"
                    )
                    params = [canonical_id, edge_type, canonical_id, edge_type]
                else:
                    sql = (
                        "SELECT to_node FROM edges WHERE from_node = ? "
                        "UNION SELECT from_node FROM edges WHERE to_node = ?"
                    )
                    params = [canonical_id, canonical_id]
            rows = self._conn.execute(sql, params).fetchall()
            out: list[dict[str, Any]] = []
            for (n,) in rows:
                node = self.get_node(n)
                if node:
                    out.append(node)
            return out

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
        if self.path is None:
            with tarfile.open(path, "w") as tar:
                for tbl in ("nodes", "edges"):
                    tmpf = path.parent / f"_{tbl}.parquet"
                    self._conn.execute(
                        f"COPY (SELECT * FROM {tbl}) TO '{tmpf}' (FORMAT 'parquet')"
                    )
                    tar.add(tmpf, arcname=f"{tbl}.parquet")
                    tmpf.unlink()
        else:
            # Force flush to disk before tarring the file.
            self._conn.execute("CHECKPOINT")
            with tarfile.open(path, "w") as tar:
                tar.add(self.path, arcname="backend.duckdb")

    def restore(self, path: Path) -> None:
        with tarfile.open(path, "r") as tar:
            members = tar.getnames()
            if "backend.duckdb" in members and self.path is not None:
                self._conn.close()
                extract_to = path.parent / "_restore_tmp"
                extract_to.mkdir(parents=True, exist_ok=True)
                tar.extract("backend.duckdb", path=extract_to)
                extracted = extract_to / "backend.duckdb"
                shutil.move(str(extracted), str(self.path))
                extract_to.rmdir()
                self._conn = duckdb.connect(str(self.path))
                self._conn.execute(_SCHEMA_SQL)
            else:
                self._conn.execute("DELETE FROM nodes")
                self._conn.execute("DELETE FROM edges")
                extract_to = path.parent / "_restore_tmp"
                extract_to.mkdir(parents=True, exist_ok=True)
                for tbl in ("nodes", "edges"):
                    tar.extract(f"{tbl}.parquet", path=extract_to)
                    p = extract_to / f"{tbl}.parquet"
                    self._conn.execute(
                        f"INSERT INTO {tbl} SELECT * FROM read_parquet('{p}')"
                    )
                    p.unlink()
                extract_to.rmdir()

    def stats(self) -> dict[str, Any]:
        n_nodes = self._conn.execute("SELECT count(*) FROM nodes").fetchone()[0]
        n_edges = self._conn.execute("SELECT count(*) FROM edges").fetchone()[0]
        by_type = dict(
            self._conn.execute(
                "SELECT node_type, count(*) FROM nodes GROUP BY node_type"
            ).fetchall()
        )
        return {"n_nodes": n_nodes, "n_edges": n_edges, "by_type": by_type}

    # ── F58.8 helpers — listing nodes/edges by type for loader/test
    # introspection. Intentionally NOT in the Protocol: these are
    # backend-concrete helpers, not contract.
    def list_nodes(self, *, node_type: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT canonical_id, properties, provenance FROM nodes WHERE node_type = ?",
            [node_type],
        ).fetchall()
        out: list[dict[str, Any]] = []
        for canonical_id, props_raw, prov_raw in rows:
            props = json.loads(props_raw) if props_raw else {}
            prov = json.loads(prov_raw) if prov_raw else {}
            out.append(
                {
                    "canonical_id": canonical_id,
                    "node_type": node_type,
                    "properties": props,
                    "provenance": prov,
                }
            )
        return out

    def list_edges(self, *, edge_type: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT from_node, to_node, properties, provenance FROM edges WHERE edge_type = ?",
            [edge_type],
        ).fetchall()
        out: list[dict[str, Any]] = []
        for from_node, to_node, props_raw, prov_raw in rows:
            props = json.loads(props_raw) if props_raw else {}
            prov = json.loads(prov_raw) if prov_raw else {}
            out.append(
                {
                    "edge_type": edge_type,
                    "source_canonical_id": from_node,
                    "target_canonical_id": to_node,
                    "properties": props,
                    "provenance": prov,
                }
            )
        return out
