from __future__ import annotations

import httpx
import numpy as np
import pytest

from jw_rag.embed_providers.ollama import OllamaEmbedProvider


def test_is_available_false_when_server_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    assert p.is_available() is False


def test_is_available_true_when_tags_returns_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    assert p.is_available() is True


def test_embed_returns_normalized_768_dim_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        assert request.url.path == "/api/embeddings"
        return httpx.Response(200, json={"embedding": [3.0, 4.0] + [0.0] * 766})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    out = p.embed(["hello"])
    assert out.shape == (1, 768)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)


def test_embed_loops_per_text() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        import json as _json

        body = _json.loads(request.content)
        calls.append(body["prompt"])
        return httpx.Response(200, json={"embedding": [1.0] + [0.0] * 767})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    p.embed(["a", "b", "c"])
    assert calls == ["a", "b", "c"]
