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


PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]

ENV_EMBED = "JW_EMBED_PROVIDER"
ENV_PROVIDER_ORDER = "JW_PROVIDER_ORDER"


def _provider_order() -> list[Target]:
    raw = os.getenv(ENV_PROVIDER_ORDER, "")
    if not raw.strip():
        return PROVIDER_ORDER_DEFAULT
    parts: list[Target] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece in {"api", "mlx", "nvidia", "cpu"}:
            parts.append(piece)  # type: ignore[arg-type]
    return parts or PROVIDER_ORDER_DEFAULT


def _instantiate_registry() -> list[EmbedProvider]:
    """Build the full provider registry (real + fakes), without calling is_available()."""
    from jw_rag.embed_providers.bge_m3 import BGEM3Provider
    from jw_rag.embed_providers.cohere import CohereEmbedV3Provider
    from jw_rag.embed_providers.fakes import (
        FakeBGEM3,
        FakeCohereEmbed,
        FakeJinaEmbed,
        FakeMultilingualE5,
        FakeOllamaEmbed,
        FakeVoyageEmbed,
    )
    from jw_rag.embed_providers.jina import JinaEmbeddingsV3Provider
    from jw_rag.embed_providers.multilingual_e5 import MultilingualE5Provider
    from jw_rag.embed_providers.ollama import OllamaEmbedProvider
    from jw_rag.embed_providers.voyage import VoyageMultilingualProvider

    return [
        # Real providers
        CohereEmbedV3Provider(),
        JinaEmbeddingsV3Provider(),
        VoyageMultilingualProvider(),
        BGEM3Provider(),
        MultilingualE5Provider(),
        OllamaEmbedProvider(),
        # Fakes — always considered available, used by tests via JW_EMBED_PROVIDER=fake-*
        FakeBGEM3(),
        FakeMultilingualE5(),
        FakeJinaEmbed(),
        FakeCohereEmbed(),
        FakeVoyageEmbed(),
        FakeOllamaEmbed(),
    ]


def _named_lookup(name: str) -> EmbedProvider | None:
    """Resolve JW_EMBED_PROVIDER name. Accepts both 'jina' and 'fake-jina'."""
    is_fake = name.startswith("fake-")
    bare = name.removeprefix("fake-")
    for p in _instantiate_registry():
        if p.name != bare:
            continue
        # Fake-prefixed name must hit a Fake instance
        if is_fake and type(p).__module__.endswith(".fakes"):
            return p
        if not is_fake and not type(p).__module__.endswith(".fakes"):
            return p
    return None


def list_available_embedders() -> list[EmbedProvider]:
    """Return registry filtered by `is_available()` and sorted per PROVIDER_ORDER.

    Fake providers are excluded — they exist to be selected explicitly via
    `JW_EMBED_PROVIDER=fake-*` (handled by `_named_lookup`).
    """
    order = _provider_order()
    registry = [p for p in _instantiate_registry() if p.is_available() and not type(p).__module__.endswith(".fakes")]
    return sorted(registry, key=lambda p: order.index(p.target) if p.target in order else len(order))


def get_default_embedder() -> EmbedProvider:
    """Resolve default embed provider.

    Order:
      1. JW_EMBED_PROVIDER env (exact name match, raises if unknown)
      2. First provider in PROVIDER_ORDER whose is_available() == True
      3. FakeEmbedder (legacy fallback, with WARNING log)
    """
    env_name = os.getenv(ENV_EMBED, "").strip()
    if env_name:
        provider = _named_lookup(env_name)
        if provider is None:
            raise ValueError(f"unknown JW_EMBED_PROVIDER={env_name!r}")
        return provider

    available = list_available_embedders()
    if available:
        return available[0]

    from jw_rag.embed import FakeEmbedder

    logger.warning(
        "No real embed provider available — falling back to FakeEmbedder (semantically empty). "
        "Install an extra (e.g. `pip install jw-rag[embeddings-local]`) or set an API key."
    )
    return FakeEmbedder()
