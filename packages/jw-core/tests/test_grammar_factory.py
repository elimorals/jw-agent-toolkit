"""Tests for jw_core.grammar.factory — provider selection."""

from __future__ import annotations

import asyncio

import pytest
from jw_core.grammar.factory import (
    ConstrainedCaller,
    get_default_constrained_caller,
)
from jw_core.grammar.fake import FakeConstrainedCaller


def test_protocol_satisfied_by_fake() -> None:
    caller: ConstrainedCaller = FakeConstrainedCaller(seed=0)
    assert asyncio.run(caller.is_available()) is True


def test_factory_returns_fake_when_provider_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    caller = get_default_constrained_caller(provider="fake")
    assert isinstance(caller, FakeConstrainedCaller)


def test_factory_respects_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "fake")
    caller = get_default_constrained_caller()
    assert isinstance(caller, FakeConstrainedCaller)


def test_factory_falls_back_to_fake_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("JW_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("JW_OLLAMA_HOST", "http://127.0.0.1:1")  # guaranteed-dead port
    caller = get_default_constrained_caller()
    assert isinstance(caller, FakeConstrainedCaller)
    captured = capsys.readouterr()
    assert "fake" in (captured.err + captured.out).lower()


def test_factory_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_LLM_PROVIDER", "azure")
    with pytest.raises(ValueError):
        get_default_constrained_caller()
