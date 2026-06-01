"""EdgeType registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeTypeSpec:
    name: str
    sources: tuple[str, ...]
    targets: tuple[str, ...]
    directional: bool = True
    confidence_threshold: float = 0.5
    sensitive: bool = False  # default conflict policy = "flag" when True


class EdgeRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, EdgeTypeSpec] = {}

    def register(self, spec: EdgeTypeSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> EdgeTypeSpec | None:
        return self._specs.get(name)

    def all(self) -> list[EdgeTypeSpec]:
        return list(self._specs.values())
