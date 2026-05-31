"""Tests for the new grammar/json_schema kwargs on OllamaAdapter.

We mock httpx.AsyncClient with a respx route so no real network is hit.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from jw_core.grammar.schemas import AgentResultModel
from jw_core.privacy.ollama_adapter import OllamaAdapter, OllamaError


class _FakeResponse:
    def __init__(self, payload: dict[str, str], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("POST", "x"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, str]:
        return self._payload


class _FakeClient:
    def __init__(self, expected_grammar: str | None) -> None:
        self.expected_grammar = expected_grammar
        self.last_payload: dict[str, object] | None = None

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def get(self, _url: str) -> _FakeResponse:
        return _FakeResponse({"models": []})

    async def post(self, _url: str, json: dict[str, object]) -> _FakeResponse:  # noqa: A002
        self.last_payload = json
        return _FakeResponse({"response": '{"query":"q","agent_name":"a","findings":[]}'})


def test_ollama_adapter_passes_grammar_in_options(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(expected_grammar="grammar-string-here")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: fake)

    adapter = OllamaAdapter()
    asyncio.run(adapter.generate("p", grammar="grammar-string-here"))

    assert fake.last_payload is not None
    opts = fake.last_payload.get("options", {})
    assert isinstance(opts, dict)
    assert opts.get("grammar") == "grammar-string-here"


def test_ollama_adapter_converts_json_schema_to_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(expected_grammar=None)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: fake)

    adapter = OllamaAdapter()
    asyncio.run(adapter.generate("p", json_schema=AgentResultModel))

    assert fake.last_payload is not None
    opts = fake.last_payload.get("options", {})
    assert isinstance(opts, dict)
    assert "citation-url" in str(opts.get("grammar", ""))


def test_ollama_adapter_temperature_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeClient(expected_grammar=None)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: fake)

    adapter = OllamaAdapter()
    asyncio.run(adapter.generate("p", temperature=0.7))

    assert fake.last_payload is not None
    opts = fake.last_payload.get("options", {})
    assert isinstance(opts, dict)
    assert opts.get("temperature") == pytest.approx(0.7)


def test_ollama_adapter_raises_when_grammar_and_schema_both_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeClient(expected_grammar=None)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: fake)

    adapter = OllamaAdapter()
    with pytest.raises(OllamaError):
        asyncio.run(adapter.generate("p", grammar="x", json_schema=AgentResultModel))
