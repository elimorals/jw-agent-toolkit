"""Builtin TJ BrainDomain."""

from __future__ import annotations

from jw_brain.schema.builtins import tj_edge_specs, tj_node_specs


class TJBrainDomain:
    name = "tj"
    nodes = tj_node_specs()
    edges = tj_edge_specs()
