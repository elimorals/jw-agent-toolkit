"""Tests for OllamaNLI — local LLM judge via Ollama HTTP API.

We bypass the network by injecting an ``httpx.Client`` built on
``httpx.MockTransport`` (stdlib-only of httpx; no respx dependency needed).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from jw_core.fidelity.nli_providers.ollama_nli import OllamaNLI


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ollama_unavailable_when_server_down() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ECONNREFUSED")

    p = OllamaNLI(http_client=_mock_client(handler))
    assert p.is_available() is False


def test_ollama_unavailable_when_model_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    p = OllamaNLI(http_client=_mock_client(handler))
    assert p.is_available() is False


def test_ollama_available_when_model_present() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3.1:8b-instruct"}]})

    p = OllamaNLI(http_client=_mock_client(handler))
    assert p.is_available() is True


def test_ollama_evaluate_parses_entails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.1:8b-instruct"}]})
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps({"verdict": "entails", "score": 0.87, "reason": "ok"})}},
            )
        return httpx.Response(404)

    p = OllamaNLI(http_client=_mock_client(handler))
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "entails"
    assert v.score == 0.87
    assert v.provider == "ollama-nli"


def test_ollama_fallback_on_garbage_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.1:8b-instruct"}]})
        return httpx.Response(200, json={"message": {"content": "not even json"}})

    p = OllamaNLI(http_client=_mock_client(handler))
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
    assert v.score == 0.5


def test_ollama_uses_env_host(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://example.local:9999")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "example.local"
        assert request.url.port == 9999
        return httpx.Response(200, json={"models": [{"name": "llama3.1:8b-instruct"}]})

    p = OllamaNLI(http_client=_mock_client(handler))
    assert p.is_available() is True


def test_ollama_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_OLLAMA_MODEL", "qwen2.5:7b")
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"verdict": "entails", "score": 0.9})}},
        )

    p = OllamaNLI(http_client=_mock_client(handler))
    p.evaluate(claim="A", premise="B")
    assert captured
    assert captured[0]["model"] == "qwen2.5:7b"
    assert captured[0]["format"] == "json"
