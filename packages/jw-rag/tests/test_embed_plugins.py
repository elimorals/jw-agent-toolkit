"""Tests for jw-rag ↔ jw_core.plugins embedder integration."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec
from jw_rag.embed_providers.factory import _instantiate_registry


class _PluginEmbedder:
    name = "plugin_test_emb"
    target = "cpu"
    dim = 4

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), self.dim), dtype=np.float32)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_instantiate_registry_includes_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EntryPointSpec(
        name="plugin_test_emb",
        group="jw_agent_toolkit.embedders",
        module="dummy",
        attr="PluginEmb",
        dist_name="plugin-pkg",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _PluginEmbedder

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_rag.embed_providers.factory.get_plugins",
        lambda group: {"plugin_test_emb": spec} if group == "jw_agent_toolkit.embedders" else {},
    )

    registry = _instantiate_registry()
    names = [p.name for p in registry]
    assert "plugin_test_emb" in names


def test_instantiate_registry_skips_broken_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EntryPointSpec(
        name="broken_emb",
        group="jw_agent_toolkit.embedders",
        module="dummy",
        attr="X",
        dist_name="broken",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        raise RuntimeError("import failed")

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_rag.embed_providers.factory.get_plugins",
        lambda group: {"broken_emb": spec} if group == "jw_agent_toolkit.embedders" else {},
    )

    registry = _instantiate_registry()
    names = [p.name for p in registry]
    assert "broken_emb" not in names
