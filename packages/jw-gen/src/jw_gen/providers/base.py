"""Common Protocol for all generation providers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from jw_gen.models import CostHint, GenerationRequest, Kind, Target


@runtime_checkable
class GenerationProvider(Protocol):
    name: str
    kind: Kind
    target: Target

    def is_available(self) -> bool: ...
    def cost_estimate(self, request: GenerationRequest) -> CostHint: ...
    def generate(self, request: GenerationRequest) -> Path: ...
