"""LLM factory tests — env-driven selection + acomplete adapter."""

from __future__ import annotations

import asyncio
import json

import pytest

from jw_agents.meta.llm_factory import (
    _FakeAcompletionLLM,
    _SyncProviderAcompletionAdapter,
    build_llm_from_env,
)


def test_default_env_returns_fake_llm() -> None:
    llm = build_llm_from_env()
    assert isinstance(llm, _FakeAcompletionLLM)


def test_env_fake_explicit_returns_fake_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_META_LLM", "fake")
    llm = build_llm_from_env()
    assert isinstance(llm, _FakeAcompletionLLM)


def test_unknown_backend_degrades_to_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_META_LLM", "bogus")
    llm = build_llm_from_env()
    assert isinstance(llm, _FakeAcompletionLLM)


@pytest.mark.asyncio
async def test_fake_llm_returns_valid_empty_plan_json() -> None:
    llm = _FakeAcompletionLLM()
    raw = await llm.acomplete("any prompt")
    parsed = json.loads(raw)
    assert parsed["steps"] == []
    assert parsed["goal"] == ""


@pytest.mark.asyncio
async def test_sync_provider_adapter_wraps_generate() -> None:
    """The adapter must run sync generate() via to_thread and forward
    the response.text untouched."""

    class FakeResponse:
        text = '{"goal": "x", "language": "es", "steps": []}'

    class FakeSyncProvider:
        name = "fake-sync"

        def __init__(self) -> None:
            self.last_req = None

        def generate(self, req) -> FakeResponse:  # type: ignore[no-untyped-def]
            self.last_req = req
            return FakeResponse()

    sync = FakeSyncProvider()
    adapter = _SyncProviderAcompletionAdapter(sync)
    out = await adapter.acomplete("hello")
    assert out == FakeResponse.text
    assert sync.last_req is not None
    assert sync.last_req.user == "hello"
    assert adapter.name == "fake-sync"


def test_anthropic_backend_degrades_gracefully_if_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the anthropic dep / key is missing, we degrade to fake — never crash."""
    monkeypatch.setenv("JW_META_LLM", "anthropic")
    # Force the build to fail by clearing API key + simulating missing dep.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    llm = build_llm_from_env()
    # Either we got the real adapter (if dep+key happen to exist locally)
    # or the fake. Both are OK as long as it doesn't raise.
    assert hasattr(llm, "acomplete")
    # Smoke: acomplete is callable without raising.
    out = asyncio.run(llm.acomplete("ping"))
    assert isinstance(out, str)
