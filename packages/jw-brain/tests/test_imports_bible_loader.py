"""F58.8 — BibleLoader orquesta el pipeline procedural.

E2E: parsea el fixture sintético `it_mini.jwpub` y verifica que el
backend recibe upserts coherentes para Person/Place/Passage/Period y los
edges MENTIONED_IN_PASSAGE / LOCATED_IN_PASSAGE.

No usa LLM — todos los datos vienen del catálogo curado + parser
procedural sobre JWPUB descifrado.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_brain.backends.duckdb_backend import DuckDBBackend
from jw_brain.imports.bible.loader import BibleLoader

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


@pytest.fixture()
def backend(tmp_path: Path) -> DuckDBBackend:
    # `DuckDBBackend.__init__` aplica el schema. No hay `initialize_schema`
    # separado en este backend; el ctor es suficiente.
    return DuckDBBackend(tmp_path / "test.duckdb")


def test_loader_imports_periods_first(backend: DuckDBBackend) -> None:
    loader = BibleLoader(backend=backend)
    stats = loader.import_periods()
    assert stats.periods_upserted == 10
    nodes = backend.list_nodes(node_type="Period")
    assert len(nodes) == 10
    # Los slugs del catálogo se materializan al canonical_id `period:<slug>`.
    canonical_ids = {n["canonical_id"] for n in nodes}
    assert "period:patriarchal" in canonical_ids
    assert "period:roman_era" in canonical_ids


def test_loader_imports_insight_jwpub(backend: DuckDBBackend) -> None:
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    stats = loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    # Fixture: Abraham + Moses (persons), Jerusalem (place).
    assert stats.persons_upserted == 2
    assert stats.places_upserted == 1

    persons = backend.list_nodes(node_type="Person")
    person_ids = {p["canonical_id"] for p in persons}
    assert "person:abraham" in person_ids
    assert "person:moses" in person_ids

    places = backend.list_nodes(node_type="Place")
    place_ids = {p["canonical_id"] for p in places}
    assert "place:jerusalem" in place_ids


def test_loader_creates_first_mention_passage_nodes(backend: DuckDBBackend) -> None:
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)

    passages = {p["canonical_id"] for p in backend.list_nodes(node_type="Passage")}
    # Abraham → Gen 11:26 ⇒ book 1, ch 11, verse 26.
    assert "passage:1:11:26" in passages
    # Moses → Ex 2:10 ⇒ book 2, ch 2, verse 10.
    assert "passage:2:2:10" in passages
    # Jerusalem → 2 Sam 5:6 ⇒ book 10, ch 5, verse 6.
    assert "passage:10:5:6" in passages


def test_loader_creates_mentioned_in_passage_edges(backend: DuckDBBackend) -> None:
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)

    edges = backend.list_edges(edge_type="MENTIONED_IN_PASSAGE")
    pairs = {(e["source_canonical_id"], e["target_canonical_id"]) for e in edges}
    assert ("person:abraham", "passage:1:11:26") in pairs
    assert ("person:moses", "passage:2:2:10") in pairs

    located = backend.list_edges(edge_type="LOCATED_IN_PASSAGE")
    located_pairs = {(e["source_canonical_id"], e["target_canonical_id"]) for e in located}
    assert ("place:jerusalem", "passage:10:5:6") in located_pairs


def test_loader_enriches_place_with_geocoords(backend: DuckDBBackend) -> None:
    """F58.13 — al upsertar un Place cuyo slug está en `place_catalog`,
    el loader hidrata latitude/longitude/region/modern_name/eras_active."""
    import json

    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)

    places = backend.list_nodes(node_type="Place")
    jerusalem = next((p for p in places if p["canonical_id"] == "place:jerusalem"), None)
    assert jerusalem is not None

    props = jerusalem.get("properties", {})
    if isinstance(props, str):
        props = json.loads(props)

    assert props.get("latitude") is not None
    assert 31.0 < props["latitude"] < 32.0
    assert props.get("longitude") is not None
    assert 35.0 < props["longitude"] < 36.0
    assert props.get("region") == "Judea"
    assert "Jerusalem" in props.get("modern_name", "")


def test_loader_is_idempotent(backend: DuckDBBackend) -> None:
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    s1 = loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    s2 = loader.import_insight(FIXTURE, symbol="it", meps_language=0)

    nodes = backend.list_nodes(node_type="Person")
    # Re-correr no crea filas extras: el canonical_id colisiona y el upsert
    # actualiza en sitio.
    assert len(nodes) == s1.persons_upserted
    assert s2.persons_upserted == s1.persons_upserted

    # Lo mismo para edges: la PK (edge_type, from_node, to_node) absorbe
    # repeticiones.
    edges = backend.list_edges(edge_type="MENTIONED_IN_PASSAGE")
    assert len(edges) == s1.edges_upserted - 1  # 1 LOCATED_IN_PASSAGE entre los edges totales
