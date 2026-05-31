"""Tests for AnthropicAdapter — uses a stub SDK to avoid network/anthropic dep."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest
from jw_core.grammar.schemas import AgentResultModel


def _install_fake_anthropic(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    class _ContentBlock:
        type = "tool_use"
        input = {
            "query": "stub",
            "agent_name": "stub",
            "findings": [
                {
                    "summary": "ok",
                    "citation": {
                        "url": "https://wol.jw.org/en/wol/d/r1/lp-e/2024",
                        "title": "",
                        "kind": "article",
                    },
                    "excerpt": "",
                }
            ],
            "warnings": [],
        }

    class _Message:
        content = [_ContentBlock()]
        stop_reason = "tool_use"

    class _Messages:
        def create(self, **kwargs: object) -> _Message:
            captured.append(kwargs)
            return _Message()

    class _Anthropic:
        def __init__(self, *_: object, **__: object) -> None:
            self.messages = _Messages()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = _Anthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    return captured


def test_anthropic_adapter_uses_tool_use(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_fake_anthropic(monkeypatch)
    from jw_core.privacy.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(model="claude-haiku-test")
    raw = asyncio.run(adapter.generate("question", json_schema=AgentResultModel))

    assert captured, "anthropic client was not called"
    call = captured[-1]
    tools = call["tools"]
    assert tools[0]["name"] == "emit_agent_result"
    assert "input_schema" in tools[0]
    assert "findings" in tools[0]["input_schema"]["properties"]

    parsed = AgentResultModel.model_validate_json(raw)
    assert parsed.findings[0].citation.url.startswith("https://wol.jw.org/")


def test_anthropic_adapter_raises_on_raw_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_anthropic(monkeypatch)
    from jw_core.privacy.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.generate("p", grammar="root ::= 'x'"))


def test_anthropic_adapter_is_available_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_anthropic(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from jw_core.privacy.anthropic_adapter import AnthropicAdapter

    assert asyncio.run(AnthropicAdapter().is_available()) is False

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert asyncio.run(AnthropicAdapter().is_available()) is True
