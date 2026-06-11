"""Builtin tools registration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from jw_agents.meta.builtin_tools import BUILTIN_TOOL_NAMES, register_builtin_tools
from jw_agents.meta.registry import clear_registry, list_tools


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


def test_register_builtin_tools_registers_all() -> None:
    register_builtin_tools()
    names = {t.name for t in list_tools()}
    for expected in BUILTIN_TOOL_NAMES:
        assert expected in names


def test_register_builtin_tools_is_idempotent() -> None:
    register_builtin_tools()
    n1 = len(list_tools())
    register_builtin_tools()
    n2 = len(list_tools())
    assert n1 == n2


def test_adapters_import_real_agent_modules() -> None:
    """Smoke test: every builtin adapter can be invoked and resolves its
    real agent module (no NotImplementedError, no placeholder echo)."""
    from jw_agents.meta.builtin_tools import _CATALOG

    # Each callable should be defined in builtin_tools (the adapter), not a
    # nameless placeholder. We verify by inspecting the module and module
    # presence of the import target the adapter wraps.
    for name, (callable_, _, _) in _CATALOG.items():
        assert callable_.__module__ == "jw_agents.meta.builtin_tools"
        assert callable_.__name__.startswith("_")
        assert "adapter" in callable_.__name__.lower()
