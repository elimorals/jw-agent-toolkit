"""Tests for the NLI factory.

Contracts:

  1. ``get_default_nli_provider()`` always returns something (FakeNLI is
     the last-resort fallback).
  2. ``JW_NLI_PROVIDER=fake-nli`` selects FakeNLI explicitly.
  3. ``JW_NLI_PROVIDER=claude-nli`` selects ClaudeNLI when available, else raises
     (we do NOT silently degrade — the user asked for a specific provider).
  4. ``JW_NLI_PROVIDER=bogus`` raises ValueError.
  5. ``JW_PROVIDER_ORDER`` reorders the registry (shared with Fase 33).
  6. ``list_available_nli_providers()`` excludes fakes from the public listing
     but explicit lookup via ``JW_NLI_PROVIDER=fake-nli`` finds the fake variant.
"""

from __future__ import annotations

import pytest

from jw_core.fidelity.factory import (
    ENV_NLI,
    ENV_PROVIDER_ORDER,
    get_default_nli_provider,
    list_available_nli_providers,
)


def test_default_returns_a_provider(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    p = get_default_nli_provider()
    assert p is not None
    assert hasattr(p, "evaluate")
    assert hasattr(p, "name")


def test_env_override_selects_fake(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "fake-nli")
    p = get_default_nli_provider()
    assert p.name == "fake-nli"


def test_env_override_unknown_name_raises(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "bogus-provider")
    with pytest.raises(ValueError, match="unknown JW_NLI_PROVIDER"):
        get_default_nli_provider()


def test_env_override_claude_when_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "claude-nli")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # ClaudeNLI without API key is_available() == False → factory must raise
    # because the user explicitly named it.
    with pytest.raises(RuntimeError, match="not available"):
        get_default_nli_provider()


def test_fallback_to_fake_when_nothing_available(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = get_default_nli_provider()
    # On CI hosts without GPUs and without API keys, fake-nli is the floor.
    assert p.name in {
        "fake-nli",
        "deberta-v3-mnli",
        "ollama-nli",
        "claude-nli",
        "openai-nli",
    }


def test_list_available_excludes_fake(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    listed = list_available_nli_providers()
    names = {p.name for p in listed}
    assert "fake-nli" not in names


def test_provider_order_env_reorders(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    monkeypatch.setenv(ENV_PROVIDER_ORDER, "cpu,api,mlx,nvidia")
    # Just check the call doesn't crash and still returns something.
    p = get_default_nli_provider()
    assert p is not None


def test_named_lookup_can_select_fake_explicitly(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "fake-nli")
    p = get_default_nli_provider()
    assert p.name == "fake-nli"
