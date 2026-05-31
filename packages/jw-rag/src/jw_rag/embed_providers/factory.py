"""Embed provider Protocol, Target literal, and default-resolution factory.

Resolution order: env JW_EMBED_PROVIDER overrides everything; otherwise we
scan PROVIDER_ORDER (api, mlx, nvidia, cpu) and pick the first provider
that reports `is_available()` True. Fallback: FakeEmbedder with a warning.
"""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class EmbedProvider(Protocol):
    """Canonical embed provider contract.

    Implementations MUST:
      - expose `.name`, `.target`, `.dim` as instance/class attributes
      - return L2-normalized float32 vectors from `.embed()`
      - never touch the network or load heavy SDKs at __init__ time
      - return True from `.is_available()` only when calling `.embed()` would
        succeed in the current environment
    """

    name: str
    target: Target
    dim: int

    def is_available(self) -> bool: ...

    def embed(self, texts: list[str]) -> np.ndarray: ...


# Stubs replaced by real implementations in Task 4.
def get_default_embedder() -> EmbedProvider:  # pragma: no cover - replaced in Task 4
    raise NotImplementedError("Implemented in Task 4")


def list_available_embedders() -> list[EmbedProvider]:  # pragma: no cover - replaced in Task 4
    raise NotImplementedError("Implemented in Task 4")
