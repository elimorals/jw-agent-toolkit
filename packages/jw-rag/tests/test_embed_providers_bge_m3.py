"""Tests for BGEM3Provider — gated by sentence-transformers availability."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from jw_rag.embed_providers.bge_m3 import BGEM3Provider, _detect_target


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert BGEM3Provider().is_available() is False


def test_detect_target_prefers_mlx_on_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.processor", lambda: "arm")
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object() if name == "mlx" else None)
    assert _detect_target() == "mlx"


def test_detect_target_falls_back_to_cpu_on_x86_no_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.processor", lambda: "x86_64")
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert _detect_target() == "cpu"


@pytest.mark.embeddings_local
def test_real_embed_returns_normalized_1024_vectors() -> None:
    p = BGEM3Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed; run with [embeddings-local] extra")
    out = p.embed(["hello world", "hola mundo"])
    assert out.shape == (2, 1024)
    assert out.dtype == np.float32
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
