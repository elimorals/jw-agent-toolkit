"""Tests for ClaudeNLI provider.

We never hit the real API: the test injects a FakeAnthropicClient that
returns canned JSON. This keeps CI offline + deterministic.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from jw_core.fidelity.nli_providers.claude_nli import ClaudeNLI


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(self.response_text)


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeMessages(response_text)


def test_claude_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeNLI()
    assert p.is_available() is False


def test_claude_available_with_api_key(monkeypatch) -> None:
    # Skip if anthropic SDK isn't installed in the dev env
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    p = ClaudeNLI()
    assert p.is_available() is True


def test_claude_parses_entails(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.91, "reason": "supported"}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B", language="es")
    assert v.verdict == "entails"
    assert v.score == 0.91
    assert v.provider == "claude-nli"
    assert v.raw["reason"] == "supported"


def test_claude_parses_contradicts(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "contradicts", "score": 0.83, "reason": "negation"}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "contradicts"
    assert v.score == 0.83


def test_claude_parses_neutral_default(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "neutral", "score": 0.5}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"


def test_claude_fallback_on_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient("not even json at all")
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
    assert v.score == 0.5
    assert "parse_error" in v.raw


def test_claude_fallback_on_invalid_verdict(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "maybe", "score": 0.9}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"


def test_claude_truncates_long_premise(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.8}))
    p = ClaudeNLI(client=client)
    very_long_premise = "x" * 20000
    p.evaluate(claim="short", premise=very_long_premise)
    sent = client.messages.calls[0]
    user_msg = sent["messages"][0]["content"]
    assert "x" * 6000 in user_msg
    assert "x" * 7000 not in user_msg


def test_claude_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv("JW_NLI_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = ClaudeNLI(client=client)
    p.evaluate(claim="A", premise="B")
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5-20251001"


def test_claude_sets_prompt_caching(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = ClaudeNLI(client=client)
    p.evaluate(claim="A", premise="B")
    sent = client.messages.calls[0]
    system = sent["system"]
    assert isinstance(system, list)
    assert any(block.get("cache_control", {}).get("type") == "ephemeral" for block in system if isinstance(block, dict))
