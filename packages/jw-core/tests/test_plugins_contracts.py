"""Tests for jw_core.plugins.contracts — the 5 Protocols + EntryPointSpec."""

from __future__ import annotations

from typing import Any

import pytest
from jw_core.plugins.contracts import (
    AgentPlugin,
    EmbedderPlugin,
    EntryPointSpec,
    GenProviderPlugin,
    ParserPlugin,
    VLMProviderPlugin,
)


def test_entry_point_spec_namespaced_name() -> None:
    spec = EntryPointSpec(
        name="my_agent",
        group="jw_agent_toolkit.agents",
        module="my_pkg.mod",
        attr="my_agent",
        dist_name="my-pkg",
        dist_version="1.0.0",
    )
    assert spec.namespaced_name == "my-pkg:my_agent"


def test_entry_point_spec_is_hashable() -> None:
    spec = EntryPointSpec(
        name="x",
        group="g",
        module="m",
        attr="a",
        dist_name="d",
        dist_version="1",
    )
    {spec}  # smoke: frozen+hashable


def test_agent_plugin_protocol_accepts_async_callable() -> None:
    async def my_agent(**kwargs: Any) -> Any:
        return {"ok": True, "kwargs": kwargs}

    my_agent.__name__ = "my_agent"
    assert isinstance(my_agent, AgentPlugin)


def test_agent_plugin_protocol_rejects_sync_only_object() -> None:
    class NotAnAgent:
        pass

    assert not isinstance(NotAnAgent(), AgentPlugin)


def test_parser_plugin_protocol() -> None:
    def parse(raw: bytes | str, *, source_url: str | None = None) -> Any:
        return {"raw": raw, "source_url": source_url}

    assert isinstance(parse, ParserPlugin)


def test_embedder_plugin_protocol_shape() -> None:
    class FakeEmb:
        name = "fake"
        target = "cpu"
        dim = 8

        def is_available(self) -> bool:
            return True

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * self.dim for _ in texts]

    assert isinstance(FakeEmb(), EmbedderPlugin)


def test_vlm_provider_protocol_shape() -> None:
    class FakeVLM:
        name = "fake-vlm"

        def is_available(self) -> bool:
            return True

        def describe(self, image_bytes: bytes, *, language: str = "en") -> str:
            return f"fake[{language}] len={len(image_bytes)}"

    assert isinstance(FakeVLM(), VLMProviderPlugin)


def test_gen_provider_protocol_shape() -> None:
    class FakeGen:
        name = "fake-gen"

        def is_available(self) -> bool:
            return True

        def generate(self, prompt: str, *, max_tokens: int = 128) -> str:
            return f"fake[{max_tokens}]: {prompt}"

    assert isinstance(FakeGen(), GenProviderPlugin)


def test_entry_point_spec_resolve_calls_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    calls: list[tuple[str, str]] = []

    def fake_import(module: str) -> Any:
        calls.append(("import", module))

        class _M:
            def __getattr__(self, name: str) -> Any:
                calls.append(("get", name))
                return sentinel

        return _M()

    monkeypatch.setattr("jw_core.plugins.contracts.import_module", fake_import)

    spec = EntryPointSpec(
        name="x",
        group="g",
        module="my.pkg",
        attr="x",
        dist_name="d",
        dist_version="1",
    )
    got = spec.resolve()
    assert got is sentinel
    assert ("import", "my.pkg") in calls
    assert ("get", "x") in calls
