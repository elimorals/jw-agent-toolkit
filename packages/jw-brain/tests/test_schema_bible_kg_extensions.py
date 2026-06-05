"""F58 amplía el schema TJ con Period y edges temporales/cross-cutting."""
from jw_brain.schema.builtins import tj_edge_specs, tj_node_specs


def test_tj_includes_period_node_spec():
    nodes = {n.name: n for n in tj_node_specs()}
    assert "Period" in nodes
    period = nodes["Period"]
    assert "start_year_bce" in period.properties
    assert "end_year_bce" in period.properties or "end_year_ce" in period.properties


def test_tj_includes_passage_node_spec():
    nodes = {n.name: n for n in tj_node_specs()}
    assert "Passage" in nodes


def test_tj_includes_lived_in_period_edge():
    edges = {e.name for e in tj_edge_specs()}
    assert "LIVED_IN_PERIOD" in edges


def test_tj_includes_mentioned_in_passage_edge():
    edges = {e.name for e in tj_edge_specs()}
    assert "MENTIONED_IN_PASSAGE" in edges
