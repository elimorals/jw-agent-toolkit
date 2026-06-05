"""Tests for jw_core.plugins.verify."""

from __future__ import annotations

from typing import Any

import pytest
from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import (
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)
from jw_core.plugins.verify import (
    OPTIONAL_BY_GROUP,
    REQUIRED_BY_GROUP,
    _verify_spec,
    verify_plugin,
)


class _GoodAgent:
    __name__ = "good_agent"

    async def __call__(self, **kwargs: Any) -> Any:
        return kwargs


class _BadAgent:
    """Lacks __call__ entirely."""

    __name__ = "bad_agent"


class _GoodEmbedder:
    name = "good_emb"
    target = "cpu"
    dim = 8

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


def _spec(group: str, name: str = "x", dist_name: str = "demo", version: str = "1.0.0") -> EntryPointSpec:
    return EntryPointSpec(
        name=name,
        group=group,
        module="some.mod",
        attr=name,
        dist_name=dist_name,
        dist_version=version,
    )


def test_required_by_group_keys_match_known_groups() -> None:
    assert set(REQUIRED_BY_GROUP) == {
        "jw_agent_toolkit.agents",
        "jw_agent_toolkit.parsers",
        "jw_agent_toolkit.embedders",
        "jw_agent_toolkit.vlm_providers",
        "jw_agent_toolkit.gen_providers",
    }


def test_optional_by_group_subset_of_required_keys() -> None:
    assert set(OPTIONAL_BY_GROUP) == set(REQUIRED_BY_GROUP)


def test_verify_spec_happy_agent() -> None:
    report = _verify_spec(_spec("jw_agent_toolkit.agents"), target=_GoodAgent())
    assert report.ok
    assert "__call__" in report.required_present
    assert report.required_missing == ()


def test_verify_spec_missing_call() -> None:
    report = _verify_spec(_spec("jw_agent_toolkit.agents"), target=_BadAgent())
    assert not report.ok
    assert "__call__" in report.required_missing


def test_verify_spec_optional_present() -> None:
    class Agent:
        __name__ = "withlang"
        languages = ["en", "es"]

        async def __call__(self, **kwargs: Any) -> Any:
            return kwargs

    report = _verify_spec(_spec("jw_agent_toolkit.agents"), target=Agent())
    assert "languages" in report.optional_present
    assert "version" in report.optional_missing


def test_verify_spec_embedder_happy() -> None:
    report = _verify_spec(_spec("jw_agent_toolkit.embedders"), target=_GoodEmbedder())
    assert report.ok
    assert set(report.required_present) == {"name", "target", "dim", "is_available", "embed"}


def test_verify_spec_version_constraint_satisfied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jw_core.__version__", "1.5.0", raising=False)
    spec = _spec("jw_agent_toolkit.agents")
    report = _verify_spec(
        spec,
        target=_GoodAgent(),
        plugin_dependencies=("jw-agent-toolkit>=1.0,<2.0",),
    )
    assert report.version_satisfied
    assert report.version_constraint == "jw-agent-toolkit>=1.0,<2.0"


def test_verify_spec_version_constraint_violated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jw_core.__version__", "0.1.0", raising=False)
    spec = _spec("jw_agent_toolkit.agents")
    report = _verify_spec(
        spec,
        target=_GoodAgent(),
        plugin_dependencies=("jw-agent-toolkit>=99.0",),
    )
    assert not report.version_satisfied
    assert not report.ok


def test_verify_plugin_strict_raises_on_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_STRICT", "1")
    spec = _spec("jw_agent_toolkit.agents", name="bad")

    def fake_resolve_spec(name: str, group: str) -> tuple[EntryPointSpec, Any]:  # noqa: ARG001
        return spec, _BadAgent()

    monkeypatch.setattr("jw_core.plugins.verify._resolve_spec", fake_resolve_spec)
    with pytest.raises(PluginContractError):
        verify_plugin("bad", "jw_agent_toolkit.agents")


def test_verify_plugin_strict_raises_on_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_STRICT", "1")
    monkeypatch.setattr("jw_core.__version__", "0.1.0", raising=False)
    spec = _spec("jw_agent_toolkit.agents", name="vmiss")

    def fake_resolve_spec(name: str, group: str) -> tuple[EntryPointSpec, Any]:  # noqa: ARG001
        return spec, _GoodAgent()

    def fake_deps(_: EntryPointSpec) -> tuple[str, ...]:
        return ("jw-agent-toolkit>=99.0",)

    monkeypatch.setattr("jw_core.plugins.verify._resolve_spec", fake_resolve_spec)
    monkeypatch.setattr("jw_core.plugins.verify._plugin_dependencies", fake_deps)
    with pytest.raises(PluginVersionMismatch):
        verify_plugin("vmiss", "jw_agent_toolkit.agents")


def test_verify_plugin_soft_returns_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PLUGINS_STRICT", raising=False)
    spec = _spec("jw_agent_toolkit.agents", name="bad")

    def fake_resolve_spec(name: str, group: str) -> tuple[EntryPointSpec, Any]:  # noqa: ARG001
        return spec, _BadAgent()

    monkeypatch.setattr("jw_core.plugins.verify._resolve_spec", fake_resolve_spec)
    report = verify_plugin("bad", "jw_agent_toolkit.agents")
    assert not report.ok
    assert "__call__" in report.required_missing


def test_verify_plugin_unknown_raises_plugin_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_core.plugins.verify.get_plugins",
        lambda group: {},  # noqa: ARG005
    )
    with pytest.raises(PluginError):
        verify_plugin("ghost", "jw_agent_toolkit.agents")
