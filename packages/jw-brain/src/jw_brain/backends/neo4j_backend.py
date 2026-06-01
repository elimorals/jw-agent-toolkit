"""Neo4j GraphBackend — opt-in external. Stub para tests --neo4j-tests."""

from __future__ import annotations

import json
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class Neo4jBackend:
    """Minimal Neo4j adapter. Lazy imports neo4j-driver."""

    name = "neo4j"

    def __init__(self, *, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "jw-brain Neo4j backend requires `neo4j`. "
                "Install with: uv add 'jw-brain[neo4j]'"
            ) from exc

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._db = database
        with self._driver.session(database=self._db) as session:
            session.run(
                "CREATE CONSTRAINT canonical_id IF NOT EXISTS "
                "FOR (n:Node) REQUIRE n.canonical_id IS UNIQUE"
            )

    def upsert_node(self, *, node_type, canonical_id, properties, provenance) -> str:
        with self._driver.session(database=self._db) as session:
            session.run(
                "MERGE (n:Node {canonical_id: $cid}) "
                "SET n.node_type = $nt, n.properties = $props, "
                "    n.provenance = $prov, n.updated_at = datetime()",
                cid=canonical_id, nt=node_type,
                props=json.dumps(properties or {}),
                prov=json.dumps(provenance or {}),
            )
        return canonical_id

    def upsert_edge(self, *, edge_type, from_node, to_node, properties, provenance) -> str:
        with self._driver.session(database=self._db) as session:
            session.run(
                "MATCH (a:Node {canonical_id: $from_id}) "
                "MATCH (b:Node {canonical_id: $to_id}) "
                "MERGE (a)-[r:EDGE {edge_type: $et}]->(b) "
                "SET r.properties = $props, r.provenance = $prov",
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
            arrow = "-[r:EDGE]-" if direction == "both" else (
                "-[r:EDGE]->" if direction == "out" else "<-[r:EDGE]-"
            )
            edge_filter = "{edge_type: $et}" if edge_type else ""
            pattern = (
                f"(a:Node {{canonical_id: $cid}})-[*1..{hops}]-(b:Node)"
                if direction == "both"
                else f"(a:Node {{canonical_id: $cid}}){arrow}{edge_filter}(b:Node)"
            )
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
            nodes = [dict(r) for r in session.run("MATCH (n:Node) RETURN n")]
            edges = [
                dict(r)
                for r in session.run(
                    "MATCH (a)-[r:EDGE]->(b) "
                    "RETURN a.canonical_id AS s, b.canonical_id AS t, r"
                )
            ]
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
            nodes_f = tar.extractfile("nodes.json")
            edges_f = tar.extractfile("edges.json")
            assert nodes_f and edges_f
            nodes = json.loads(nodes_f.read())
            edges = json.loads(edges_f.read())
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
                from_node=entry["s"],
                to_node=entry["t"],
                properties=json.loads(r.get("properties", "{}")),
                provenance=json.loads(r.get("provenance", "{}")),
            )

    def stats(self) -> dict[str, Any]:
        with self._driver.session(database=self._db) as session:
            n_nodes = session.run("MATCH (n:Node) RETURN count(n) AS c").single()["c"]
            n_edges = session.run("MATCH ()-[r:EDGE]->() RETURN count(r) AS c").single()["c"]
            by_type = {
                r["node_type"]: r["c"]
                for r in session.run(
                    "MATCH (n:Node) RETURN n.node_type AS node_type, count(*) AS c"
                )
            }
        return {"n_nodes": n_nodes, "n_edges": n_edges, "by_type": by_type}
