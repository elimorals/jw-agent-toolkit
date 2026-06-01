"""NodeType registry — schema-on-read."""

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
