"""E2E: import periods + insight, ejecutar query 'qué personas se mencionan
en el libro Gen' contra DuckDB. Verifica que el grafo está correctamente
poblado para responder queries reales."""
from pathlib import Path

import pytest

from jw_brain.backends.duckdb_backend import DuckDBBackend
from jw_brain.imports.bible.loader import BibleLoader

FIXTURE = (
    Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"
)


@pytest.fixture()
def hydrated_brain(tmp_path):
    backend = DuckDBBackend(tmp_path / "test.duckdb")
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    return backend


def test_query_persons_in_genesis(hydrated_brain):
    """Equivalente a Cypher:
        MATCH (p:Node {node_type:'Person'})-[:MENTIONED_IN_PASSAGE]->(pa:Node {node_type:'Passage'})
        WHERE pa.book_num = 1 RETURN p.name
    """
    persons_in_genesis = hydrated_brain.query_persons_in_book(book_num=1)
    names = {p["name"] for p in persons_in_genesis}
    assert "Abraham" in names


def test_period_node_count(hydrated_brain):
    periods = hydrated_brain.list_nodes(node_type="Period")
    assert len(periods) == 10
