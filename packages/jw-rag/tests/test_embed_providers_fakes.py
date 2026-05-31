"""Tests for deterministic Fake embed providers."""

from __future__ import annotations

import numpy as np
import pytest
from jw_rag.embed_providers import EmbedProvider
from jw_rag.embed_providers.fakes import (
    FakeBGEM3,
    FakeCohereEmbed,
    FakeJinaEmbed,
    FakeMultilingualE5,
    FakeOllamaEmbed,
    FakeVoyageEmbed,
)


@pytest.mark.parametrize(
    "cls,expected_dim,expected_name,expected_target",
    [
        (FakeBGEM3, 1024, "bge-m3", "cpu"),
        (FakeMultilingualE5, 1024, "multilingual-e5", "cpu"),
        (FakeJinaEmbed, 1024, "jina", "api"),
        (FakeCohereEmbed, 1024, "cohere", "api"),
        (FakeVoyageEmbed, 1024, "voyage", "api"),
        (FakeOllamaEmbed, 768, "ollama", "cpu"),
    ],
)
def test_fakes_satisfy_protocol(cls: type, expected_dim: int, expected_name: str, expected_target: str) -> None:
    p = cls()
    assert isinstance(p, EmbedProvider)
    assert p.name == expected_name
    assert p.target == expected_target
    assert p.dim == expected_dim
    assert p.is_available() is True


@pytest.mark.parametrize(
    "cls", [FakeBGEM3, FakeMultilingualE5, FakeJinaEmbed, FakeCohereEmbed, FakeVoyageEmbed, FakeOllamaEmbed]
)
def test_fake_embed_shape_and_normalization(cls: type) -> None:
    p = cls()
    out = p.embed(["hello", "world", "tres"])
    assert out.shape == (3, p.dim)
    assert out.dtype == np.float32
    # L2-normalized
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_fake_embed_is_deterministic() -> None:
    p1 = FakeBGEM3()
    p2 = FakeBGEM3()
    a = p1.embed(["doctrine", "trinidad"])
    b = p2.embed(["doctrine", "trinidad"])
    np.testing.assert_array_equal(a, b)


def test_fake_embed_empty_input() -> None:
    p = FakeJinaEmbed()
    out = p.embed([])
    assert out.shape == (0, p.dim)
