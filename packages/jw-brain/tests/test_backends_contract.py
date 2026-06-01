"""Contract tests for GraphBackend implementations.

Both DuckDB (default) and Neo4j (opt-in) MUST pass every test here.
Run Neo4j-backed tests with: pytest --neo4j-tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_brain.backends import GraphBackend, get_backend


@pytest.fixture
def backend(backend_name: str, tmp_path: Path) -> GraphBackend:
    if backend_name == "duckdb":
        return get_backend("duckdb", path=tmp_path / "test.duckdb")
    if backend_name == "neo4j":
        return get_backend("neo4j", uri="bolt://localhost:7687", user="neo4j", password="test")
    raise ValueError(backend_name)


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
    snap_path = tmp_path / "snap.tar"
    backend.snapshot(snap_path)
    assert snap_path.exists()

    backend.upsert_node(node_type="Verse", canonical_id="v2", properties={"y": 2}, provenance={})
    backend.restore(snap_path)
    assert backend.get_node("v1") is not None
    assert backend.get_node("v2") is None


def test_stats_reports_counts_by_type(backend: GraphBackend) -> None:
    backend.upsert_node(node_type="Verse", canonical_id="v1", properties={}, provenance={})
    backend.upsert_node(node_type="Topic", canonical_id="t1", properties={}, provenance={})
    stats = backend.stats()
    assert stats["n_nodes"] == 2
    assert stats["by_type"]["Verse"] == 1
    assert stats["by_type"]["Topic"] == 1
