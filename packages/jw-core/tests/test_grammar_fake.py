"""Tests for FakeConstrainedCaller — the deterministic GBNF sampler."""

from __future__ import annotations

import asyncio

import pytest

from jw_core.grammar.fake import FakeConstrainedCaller
from jw_core.grammar.schemas import AgentResultModel


def test_fake_caller_is_available() -> None:
    caller = FakeConstrainedCaller(seed=0)
    assert asyncio.run(caller.is_available()) is True


def test_fake_caller_emits_valid_agent_result() -> None:
    caller = FakeConstrainedCaller(seed=42)
    raw = asyncio.run(caller.generate("any prompt", json_schema=AgentResultModel))
    parsed = AgentResultModel.model_validate_json(raw)
    assert parsed.query == "any prompt"
    assert len(parsed.findings) >= 1
    for f in parsed.findings:
        assert f.citation.url.startswith("https://wol.jw.org/")


def test_fake_caller_is_deterministic_for_seed() -> None:
    a = asyncio.run(FakeConstrainedCaller(seed=7).generate("x", json_schema=AgentResultModel))
    b = asyncio.run(FakeConstrainedCaller(seed=7).generate("x", json_schema=AgentResultModel))
    assert a == b


def test_fake_caller_uses_allowed_urls_when_provided() -> None:
    allowed = ["https://wol.jw.org/es/wol/d/r4/lp-s/abcd"]
    caller = FakeConstrainedCaller(seed=1, allowed_urls=allowed)
    raw = asyncio.run(caller.generate("x", json_schema=AgentResultModel))
    parsed = AgentResultModel.model_validate_json(raw)
    assert all(f.citation.url in allowed for f in parsed.findings)


def test_fake_caller_requires_schema_or_grammar() -> None:
    with pytest.raises(ValueError):
        asyncio.run(FakeConstrainedCaller(seed=0).generate("x"))
