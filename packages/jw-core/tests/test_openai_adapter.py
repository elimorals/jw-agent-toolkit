"""Tests for OpenAIAdapter — uses a stub SDK."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from jw_core.grammar.schemas import AgentResultModel


def _install_fake_openai(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    class _Message:
        content = (
            '{"query":"q","agent_name":"a","findings":'
            '[{"summary":"ok",'
            '"citation":{"url":"https://wol.jw.org/en/wol/d/r1/lp-e/2024",'
            '"title":"","kind":"article"},'
            '"excerpt":""}],"warnings":[]}'
        )

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs: object) -> _Response:
            captured.append(kwargs)
            return _Response()

    class _Chat:
        completions = _Completions()

    class _OpenAI:
        def __init__(self, *_: object, **__: object) -> None:
            self.chat = _Chat()

    fake = types.ModuleType("openai")
    fake.OpenAI = _OpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", fake)
    return captured


def test_openai_adapter_uses_structured_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_fake_openai(monkeypatch)
    from jw_core.privacy.openai_adapter import OpenAIAdapter

    raw = asyncio.run(
        OpenAIAdapter(model="gpt-4o-mini").generate("q", json_schema=AgentResultModel)
    )

    rf = captured[-1]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert "findings" in rf["json_schema"]["schema"]["properties"]

    parsed = AgentResultModel.model_validate_json(raw)
    assert parsed.findings[0].citation.url.startswith("https://wol.jw.org/")


def test_openai_adapter_raises_on_raw_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch)
    from jw_core.privacy.openai_adapter import OpenAIAdapter

    with pytest.raises(NotImplementedError):
        asyncio.run(OpenAIAdapter().generate("p", grammar="x"))


def test_openai_adapter_is_available_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch)
    from jw_core.privacy.openai_adapter import OpenAIAdapter

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert asyncio.run(OpenAIAdapter().is_available()) is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert asyncio.run(OpenAIAdapter().is_available()) is True
