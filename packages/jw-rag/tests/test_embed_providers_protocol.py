"""Tests for EmbedProvider Protocol + Target literal."""

from __future__ import annotations

import typing

import numpy as np
import pytest

from jw_rag.embed_providers import EmbedProvider, Target


def test_target_literal_values() -> None:
    values = typing.get_args(Target)
    assert set(values) == {"api", "mlx", "nvidia", "cpu"}


def test_embed_provider_is_runtime_checkable() -> None:
    class Dummy:
        name = "dummy"
        target: Target = "cpu"
        dim = 8

        def is_available(self) -> bool:
            return True

        def embed(self, texts: list[str]) -> np.ndarray:
            return np.zeros((len(texts), self.dim), dtype=np.float32)

    assert isinstance(Dummy(), EmbedProvider)


def test_embed_provider_rejects_non_conforming() -> None:
    class Missing:
        name = "missing"
        target: Target = "cpu"
        dim = 8

        # no embed() and no is_available()

    assert not isinstance(Missing(), EmbedProvider)
