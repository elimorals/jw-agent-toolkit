"""Tests for Jina v3 embed provider — uses respx to stub HTTPX."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from jw_rag.embed_providers.jina import JinaEmbeddingsV3Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert JinaEmbeddingsV3Provider().is_available() is False


def test_is_available_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")
    assert JinaEmbeddingsV3Provider().is_available() is True


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "abcdefgh1234")
    p = JinaEmbeddingsV3Provider()
    rep = repr(p)
    assert "abcdefgh1234" not in rep
    assert "***" in rep


def test_embed_returns_normalized_vectors_with_stub_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        # Return two unnormalized vectors; provider must normalize.
        data = {
            "data": [
                {"embedding": [3.0, 4.0] + [0.0] * 1022},
                {"embedding": [0.0, 0.0, 5.0] + [0.0] * 1021},
            ]
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    p = JinaEmbeddingsV3Provider(transport=transport)
    out = p.embed(["hola", "mundo"])

    assert out.shape == (2, 1024)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
    assert "api.jina.ai" in captured["url"]
    assert captured["json"]["input"] == ["hola", "mundo"]


def test_embed_empty_input_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")
    out = JinaEmbeddingsV3Provider().embed([])
    assert out.shape == (0, 1024)
