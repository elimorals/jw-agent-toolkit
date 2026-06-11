"""jw_core.broadcasting.visual - frame-level visual index (Fase 69)."""

from __future__ import annotations

from jw_core.broadcasting.visual.models import (
    IndexStats,
    VisualFrame,
    VisualSearchHit,
)
from jw_core.broadcasting.visual.providers import (
    CLIPEncoder,
    FakeCLIPEncoder,
    FakeVLMProvider,
    VLMProvider,
)

__all__ = [
    "CLIPEncoder",
    "FakeCLIPEncoder",
    "FakeVLMProvider",
    "IndexStats",
    "VLMProvider",
    "VisualFrame",
    "VisualSearchHit",
]
