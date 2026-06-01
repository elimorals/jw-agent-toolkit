"""BrainDomain Protocol — what a domain plugin must provide."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrainDomain(Protocol):
    """Structural contract for a domain plugin.

    Required attributes:
      name: str
      nodes: list[NodeTypeSpec-like]  (each has .name, .canonical_id_pattern, .properties, .obsidian_subdir, .confidence_threshold)
      edges: list[EdgeTypeSpec-like]  (each has .name, .sources, .targets)

    The plugin SDK (Fase 41) discovers BrainDomain implementations via
    entry-point group `jw_agent_toolkit.brain_domains`.
    """

    name: str
    nodes: list[Any]
    edges: list[Any]
