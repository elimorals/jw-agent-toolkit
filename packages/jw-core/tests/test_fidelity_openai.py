"""Tests for OpenAINLI provider.

Uses a FakeOpenAIClient that emulates ``client.chat.completions.create`` with
``response_format={"type": "json_schema", ...}`` and returns canned JSON.
"""

from __future__ import annotations

import json
from typing import Any

from jw_core.fidelity.nli_providers.openai_nli import OpenAINLI


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def test_openai_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAINLI()
    assert p.is_available() is False


def test_openai_parses_entails(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "entails", "score": 0.88, "reason": "ok"}))
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "entails"
    assert v.score == 0.88
    assert v.provider == "openai-nli"


def test_openai_uses_structured_output(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "neutral", "score": 0.5}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="A", premise="B")
    sent = client.chat.completions.calls[0]
    rf = sent["response_format"]
    assert rf["type"] == "json_schema"
    assert "json_schema" in rf
    schema = rf["json_schema"]["schema"]
    assert "verdict" in schema["properties"]
    assert "score" in schema["properties"]


def test_openai_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("JW_NLI_OPENAI_MODEL", "gpt-4o")
    client = _FakeOpenAIClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="A", premise="B")
    assert client.chat.completions.calls[0]["model"] == "gpt-4o"


def test_openai_fallback_on_garbage(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient("not json")
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
    assert v.score == 0.5


def test_openai_truncates_long_premise(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "entails", "score": 0.8}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="short", premise="y" * 20000)
    sent = client.chat.completions.calls[0]
    user_msg = sent["messages"][-1]["content"]
    assert "y" * 6000 in user_msg
    assert "y" * 7000 not in user_msg


def test_openai_fallback_on_invalid_verdict(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "??", "score": 1.0}))
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
