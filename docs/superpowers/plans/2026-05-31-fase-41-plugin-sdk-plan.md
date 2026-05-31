# Fase 41 — `plugin-sdk` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.plugins` — a five-group entry-point discovery layer that lets third parties extend agents, parsers, embedders, VLM providers and Gen providers without forking the monorepo.

**Architecture:** New subpackage `packages/jw-core/src/jw_core/plugins/` exposing `get_plugins(group)`, `verify_plugin(name, group)`, `clear_plugin_cache()`. Discovery via `importlib.metadata.entry_points`. Conflict policy defaults to `NAMESPACED`. Fail-soft by default, fail-hard via `JW_PLUGINS_STRICT=1`. Five surfaces integrate: `jw-eval` (`default_agent_registry`), `jw-rag` (`_instantiate_registry`), `jw-mcp` (`register_tools`), `jw-cli` (`jw plugins {list,verify,disable}`). Test fixture package installed at test time via subprocess `uv pip install -e`.

**Tech Stack:** Python 3.13 · `importlib.metadata` · `packaging.requirements` / `packaging.version` · `pydantic`/`dataclasses` · `pytest` + `monkeypatch` · `subprocess` + `uv pip install -e` for fixture install · `typer` (CLI).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-41-plugin-sdk-design.md`](../specs/2026-05-31-fase-41-plugin-sdk-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/plugins/__init__.py`
- `packages/jw-core/src/jw_core/plugins/errors.py`
- `packages/jw-core/src/jw_core/plugins/contracts.py`
- `packages/jw-core/src/jw_core/plugins/policy.py`
- `packages/jw-core/src/jw_core/plugins/registry.py`
- `packages/jw-core/src/jw_core/plugins/verify.py`
- `packages/jw-core/src/jw_core/plugins/factory.py`
- `packages/jw-core/tests/test_plugins_errors.py`
- `packages/jw-core/tests/test_plugins_contracts.py`
- `packages/jw-core/tests/test_plugins_policy.py`
- `packages/jw-core/tests/test_plugins_registry.py`
- `packages/jw-core/tests/test_plugins_verify.py`
- `packages/jw-core/tests/test_plugins_factory.py`
- `packages/jw-core/tests/test_plugins_e2e.py`
- `packages/jw-core/tests/conftest_plugins.py`
- `packages/jw-core/tests/fixtures/plugin_sample/pyproject.toml`
- `packages/jw-core/tests/fixtures/plugin_sample/README.md`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/__init__.py`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/agent.py`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/parser.py`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/embedder.py`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/vlm.py`
- `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/gen.py`
- `packages/jw-cli/src/jw_cli/commands/plugins.py`
- `docs/plugin-sdk/overview.md`
- `docs/plugin-sdk/security.md`
- `docs/plugin-sdk/capabilities.md`
- `docs/plugin-sdk/authoring.md`

Modifies:
- `packages/jw-core/src/jw_core/__init__.py` — re-export `__version__` (already exists), add `from jw_core.plugins import ...` (lazy).
- `packages/jw-eval/src/jw_eval/cli.py` — merge plugins into `default_agent_registry`.
- `packages/jw-rag/src/jw_rag/embed_providers/factory.py` — merge embedder plugins into `_instantiate_registry`.
- `packages/jw-mcp/src/jw_mcp/server.py` — register plugin tools.
- `packages/jw-cli/src/jw_cli/main.py` — register `plugins` subcommand.
- `packages/jw-cli/src/jw_cli/commands/__init__.py` — export `plugins` command.
- `.github/workflows/ci.yml` — add `plugin-sdk` offline job.
- `docs/VISION_AUDIT.md` — Fase 41 row.
- `docs/ROADMAP.md` — Fase 41 section.
- `docs/README.md` — link plugin-sdk guides.

---

### Task 1: Scaffold `jw_core.plugins` and `errors`

**Files:**
- Create: `packages/jw-core/src/jw_core/plugins/__init__.py`
- Create: `packages/jw-core/src/jw_core/plugins/errors.py`
- Create: `packages/jw-core/tests/test_plugins_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_errors.py
"""Tests for jw_core.plugins.errors."""

from __future__ import annotations

import pytest

from jw_core.plugins.errors import (
    PluginConflictError,
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)


def test_plugin_error_is_base() -> None:
    assert issubclass(PluginConflictError, PluginError)
    assert issubclass(PluginContractError, PluginError)
    assert issubclass(PluginVersionMismatch, PluginError)


def test_plugin_conflict_error_carries_names() -> None:
    err = PluginConflictError(
        name="dup",
        group="jw_agent_toolkit.agents",
        dist_names=("pkg-a", "pkg-b"),
        policy="reject",
    )
    assert err.name == "dup"
    assert err.dist_names == ("pkg-a", "pkg-b")
    assert "dup" in str(err)
    assert "pkg-a" in str(err)
    assert "pkg-b" in str(err)


def test_plugin_version_mismatch_carries_constraint() -> None:
    err = PluginVersionMismatch(
        plugin_name="foo",
        constraint="jw-agent-toolkit>=99.0",
        installed_version="0.1.0",
    )
    assert err.constraint == "jw-agent-toolkit>=99.0"
    assert "99.0" in str(err)
    assert "0.1.0" in str(err)


def test_plugin_contract_error_carries_missing() -> None:
    err = PluginContractError(
        plugin_name="foo",
        group="jw_agent_toolkit.agents",
        missing=["__call__"],
        extra={"reason": "not callable"},
    )
    assert err.missing == ["__call__"]
    assert "__call__" in str(err)


def test_can_raise_and_catch() -> None:
    with pytest.raises(PluginError):
        raise PluginConflictError("a", "g", ("x", "y"), "reject")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jw_core.plugins'`.

- [ ] **Step 3: Implement the package init and errors**

```python
# packages/jw-core/src/jw_core/plugins/__init__.py
"""jw_core.plugins — entry-point discovery for community extensions.

Public API:
    from jw_core.plugins import (
        get_plugins,
        clear_plugin_cache,
        verify_plugin,
        PluginError,
        PluginConflictError,
        PluginContractError,
        PluginVersionMismatch,
    )

Five extension-point groups (PEP 621 entry points):
    jw_agent_toolkit.agents
    jw_agent_toolkit.parsers
    jw_agent_toolkit.embedders
    jw_agent_toolkit.vlm_providers
    jw_agent_toolkit.gen_providers
"""

from __future__ import annotations

from jw_core.plugins.errors import (
    PluginConflictError,
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)
from jw_core.plugins.factory import clear_plugin_cache, get_plugins
from jw_core.plugins.verify import verify_plugin

__all__ = [
    "PluginConflictError",
    "PluginContractError",
    "PluginError",
    "PluginVersionMismatch",
    "clear_plugin_cache",
    "get_plugins",
    "verify_plugin",
]
```

```python
# packages/jw-core/src/jw_core/plugins/errors.py
"""Exception hierarchy for the plugin SDK."""

from __future__ import annotations


class PluginError(Exception):
    """Base for every plugin-SDK error."""


class PluginConflictError(PluginError):
    """Two plugins registered the same name and the conflict policy is REJECT."""

    def __init__(
        self,
        name: str,
        group: str,
        dist_names: tuple[str, ...],
        policy: str,
    ) -> None:
        self.name = name
        self.group = group
        self.dist_names = dist_names
        self.policy = policy
        super().__init__(
            f"plugin name conflict: {name!r} in group {group!r} "
            f"claimed by distributions {list(dist_names)} (policy={policy})"
        )


class PluginVersionMismatch(PluginError):
    """A plugin declares a jw-agent-toolkit constraint that the current install violates."""

    def __init__(
        self,
        plugin_name: str,
        constraint: str,
        installed_version: str,
    ) -> None:
        self.plugin_name = plugin_name
        self.constraint = constraint
        self.installed_version = installed_version
        super().__init__(
            f"plugin {plugin_name!r} requires {constraint!r} "
            f"but installed jw-agent-toolkit version is {installed_version!r}"
        )


class PluginContractError(PluginError):
    """A plugin fails the Protocol contract for its group."""

    def __init__(
        self,
        plugin_name: str,
        group: str,
        missing: list[str],
        extra: dict[str, str] | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.group = group
        self.missing = list(missing)
        self.extra = dict(extra or {})
        joined = ", ".join(missing) or "<none>"
        super().__init__(
            f"plugin {plugin_name!r} in group {group!r} missing required: [{joined}]"
        )
```

- [ ] **Step 4: Stub the downstream modules so `__init__` imports work**

We have to bootstrap `factory.py` and `verify.py` with empty stubs so the `__init__` import succeeds during this task. Real implementation lands in Tasks 5/6.

```python
# packages/jw-core/src/jw_core/plugins/factory.py
"""STUB — replaced in Task 6."""

from __future__ import annotations

from typing import Any


def get_plugins(group: str) -> dict[str, Any]:  # noqa: ARG001
    return {}


def clear_plugin_cache() -> None:
    return None
```

```python
# packages/jw-core/src/jw_core/plugins/verify.py
"""STUB — replaced in Task 5."""

from __future__ import annotations

from typing import Any


def verify_plugin(name: str, group: str) -> Any:  # noqa: ARG001
    raise NotImplementedError
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_errors.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins packages/jw-core/tests/test_plugins_errors.py
git commit -m "feat(plugin-sdk): scaffold jw_core.plugins package + error hierarchy"
```

---

### Task 2: Protocols (`contracts.py`)

**Files:**
- Create: `packages/jw-core/src/jw_core/plugins/contracts.py`
- Create: `packages/jw-core/tests/test_plugins_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_contracts.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_contracts.py -v`
Expected: FAIL — `cannot import name 'AgentPlugin'`.

- [ ] **Step 3: Implement contracts**

```python
# packages/jw-core/src/jw_core/plugins/contracts.py
"""Five Protocols + EntryPointSpec dataclass.

Protocols are `runtime_checkable` and intentionally structural — third-party
plugins don't need to import anything from jw-agent-toolkit, they just need to
match the shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Entry-point spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntryPointSpec:
    """Lazy descriptor for one entry point.

    The actual callable / object is resolved on demand via `.resolve()`.
    Stays frozen + hashable so we can de-dup by identity in the registry.
    """

    name: str
    group: str
    module: str
    attr: str
    dist_name: str
    dist_version: str

    @property
    def namespaced_name(self) -> str:
        """Stable disambiguation key under the NAMESPACED conflict policy."""
        return f"{self.dist_name}:{self.name}"

    def resolve(self) -> Any:
        """Load the entry-point target. Importing is deferred until this point."""
        mod = import_module(self.module)
        return getattr(mod, self.attr)


# ---------------------------------------------------------------------------
# Protocols — one per extension-point group
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentPlugin(Protocol):
    """A pluggable agent.

    Required:
      - `__name__: str` (attribute) — Python callables have this for free.
      - `__call__(**kwargs) -> Awaitable[Any]` — async callable.

    Optional (detected via hasattr at use-site, never required):
      - `languages: list[str]`
      - `version: str`
      - `cost_estimate(**kwargs) -> int`  (since v1.3, opt-in)
    """

    __name__: str

    def __call__(self, **kwargs: Any) -> Any: ...


@runtime_checkable
class ParserPlugin(Protocol):
    """A pluggable document parser.

    Required:
      - `__call__(raw, *, source_url=None) -> ParsedDocument-like`

    Optional:
      - `extensions: list[str]`
      - `mime_types: list[str]`
    """

    def __call__(
        self,
        raw: bytes | str,
        *,
        source_url: str | None = None,
    ) -> Any: ...


@runtime_checkable
class EmbedderPlugin(Protocol):
    """Mirrors jw_rag.embed_providers.factory.EmbedProvider for plugin registration."""

    name: str
    target: str
    dim: int

    def is_available(self) -> bool: ...

    def embed(self, texts: list[str]) -> Any: ...


@runtime_checkable
class VLMProviderPlugin(Protocol):
    """Mirrors jw_core.vision.VLMProvider."""

    name: str

    def is_available(self) -> bool: ...

    def describe(self, image_bytes: bytes, *, language: str = "en") -> str: ...


@runtime_checkable
class GenProviderPlugin(Protocol):
    """Mirrors jw_gen.GenerationProvider."""

    name: str

    def is_available(self) -> bool: ...

    def generate(self, prompt: str, *, max_tokens: int = 128) -> str: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_contracts.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins/contracts.py packages/jw-core/tests/test_plugins_contracts.py
git commit -m "feat(plugin-sdk): contracts — 5 Protocols + EntryPointSpec"
```

---

### Task 3: Conflict policy + env helpers (`policy.py`)

**Files:**
- Create: `packages/jw-core/src/jw_core/plugins/policy.py`
- Create: `packages/jw-core/tests/test_plugins_policy.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_policy.py
"""Tests for jw_core.plugins.policy."""

from __future__ import annotations

import pytest

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginConflictError
from jw_core.plugins.policy import (
    ConflictPolicy,
    apply_conflict_policy,
    read_env_set,
    read_policy_from_env,
)


def _spec(name: str, dist: str) -> EntryPointSpec:
    return EntryPointSpec(
        name=name,
        group="jw_agent_toolkit.agents",
        module=f"{dist}.mod",
        attr=name,
        dist_name=dist,
        dist_version="1.0.0",
    )


def test_conflict_policy_enum_values() -> None:
    assert ConflictPolicy.FIRST_WINS.value == "first_wins"
    assert ConflictPolicy.LAST_WINS.value == "last_wins"
    assert ConflictPolicy.NAMESPACED.value == "namespaced"
    assert ConflictPolicy.REJECT.value == "reject"


def test_read_env_set_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PLUGINS_ALLOW_LIST", raising=False)
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") is None


def test_read_env_set_empty_treated_as_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "")
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") is None


def test_read_env_set_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "a, b ,c")
    assert read_env_set("JW_PLUGINS_ALLOW_LIST") == {"a", "b", "c"}


def test_read_policy_from_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PLUGINS_CONFLICT_POLICY", raising=False)
    assert read_policy_from_env() == ConflictPolicy.NAMESPACED


def test_read_policy_from_env_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "first_wins")
    assert read_policy_from_env() == ConflictPolicy.FIRST_WINS


def test_read_policy_from_env_invalid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "weird")
    with caplog.at_level("WARNING"):
        assert read_policy_from_env() == ConflictPolicy.NAMESPACED
    assert any("weird" in r.message for r in caplog.records)


def test_apply_first_wins_keeps_existing() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.FIRST_WINS)
    assert out["x"].dist_name == "pkg-a"


def test_apply_last_wins_replaces() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.LAST_WINS)
    assert out["x"].dist_name == "pkg-b"


def test_apply_namespaced_emits_both_under_qualified_names() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    out = apply_conflict_policy(current, new, ConflictPolicy.NAMESPACED)
    # The bare "x" is removed; both live under their dist-qualified names.
    assert "x" not in out
    assert out["pkg-a:x"].dist_name == "pkg-a"
    assert out["pkg-b:x"].dist_name == "pkg-b"


def test_apply_namespaced_no_conflict_keeps_bare_name() -> None:
    current: dict = {}
    new = _spec("x", "pkg-a")
    out = apply_conflict_policy(current, new, ConflictPolicy.NAMESPACED)
    assert "x" in out
    assert "pkg-a:x" not in out


def test_apply_reject_raises() -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    with pytest.raises(PluginConflictError) as exc_info:
        apply_conflict_policy(current, new, ConflictPolicy.REJECT)
    assert "pkg-a" in str(exc_info.value)
    assert "pkg-b" in str(exc_info.value)


def test_apply_logs_warning_on_conflict(caplog: pytest.LogCaptureFixture) -> None:
    current = {"x": _spec("x", "pkg-a")}
    new = _spec("x", "pkg-b")
    with caplog.at_level("WARNING"):
        apply_conflict_policy(current, new, ConflictPolicy.FIRST_WINS)
    assert any("conflict" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_policy.py -v`
Expected: FAIL — `cannot import name 'ConflictPolicy'`.

- [ ] **Step 3: Implement policy**

```python
# packages/jw-core/src/jw_core/plugins/policy.py
"""Conflict policies + env-var helpers."""

from __future__ import annotations

import logging
import os
from enum import StrEnum

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginConflictError

logger = logging.getLogger(__name__)


class ConflictPolicy(StrEnum):
    """How to behave when two plugins register the same name in the same group."""

    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    NAMESPACED = "namespaced"
    REJECT = "reject"


ENV_POLICY = "JW_PLUGINS_CONFLICT_POLICY"
ENV_ALLOW = "JW_PLUGINS_ALLOW_LIST"
ENV_DENY = "JW_PLUGINS_DENY_LIST"
ENV_DISABLED = "JW_PLUGINS_DISABLED"
ENV_STRICT = "JW_PLUGINS_STRICT"


def read_env_set(var: str) -> set[str] | None:
    """Parse a CSV env var. Missing or empty → None (no filter)."""
    raw = os.getenv(var, "").strip()
    if not raw:
        return None
    return {piece.strip() for piece in raw.split(",") if piece.strip()}


def read_policy_from_env() -> ConflictPolicy:
    """Resolve the conflict policy from env; default NAMESPACED."""
    raw = os.getenv(ENV_POLICY, "").strip().lower()
    if not raw:
        return ConflictPolicy.NAMESPACED
    try:
        return ConflictPolicy(raw)
    except ValueError:
        logger.warning(
            "ignoring invalid %s=%r — falling back to NAMESPACED", ENV_POLICY, raw
        )
        return ConflictPolicy.NAMESPACED


def apply_conflict_policy(
    current: dict[str, EntryPointSpec],
    new: EntryPointSpec,
    policy: ConflictPolicy,
) -> dict[str, EntryPointSpec]:
    """Return an updated mapping after applying `policy` to (current, new).

    `current` is a fresh dict to mutate-and-return; callers should treat the
    return value as authoritative.
    """
    out = dict(current)
    existing = out.get(new.name)

    if existing is None:
        out[new.name] = new
        return out

    if existing.dist_name == new.dist_name and existing.module == new.module:
        # Same plugin coming back through different scans — no real conflict.
        return out

    logger.warning(
        "plugin name conflict in group %s: %r claimed by both %s and %s (policy=%s)",
        new.group,
        new.name,
        existing.dist_name,
        new.dist_name,
        policy.value,
    )

    if policy is ConflictPolicy.FIRST_WINS:
        return out
    if policy is ConflictPolicy.LAST_WINS:
        out[new.name] = new
        return out
    if policy is ConflictPolicy.NAMESPACED:
        out.pop(new.name, None)
        out[existing.namespaced_name] = existing
        out[new.namespaced_name] = new
        return out
    if policy is ConflictPolicy.REJECT:
        raise PluginConflictError(
            name=new.name,
            group=new.group,
            dist_names=(existing.dist_name, new.dist_name),
            policy=policy.value,
        )
    return out  # pragma: no cover  (exhaustive enum)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_policy.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins/policy.py packages/jw-core/tests/test_plugins_policy.py
git commit -m "feat(plugin-sdk): conflict policies + env helpers"
```

---

### Task 4: Registry — discovery with monkey-patched entry points

**Files:**
- Create: `packages/jw-core/src/jw_core/plugins/registry.py`
- Create: `packages/jw-core/tests/conftest_plugins.py`
- Create: `packages/jw-core/tests/test_plugins_registry.py`

- [ ] **Step 1: Write the autouse conftest for cache reset**

```python
# packages/jw-core/tests/conftest_plugins.py
"""Shared fixtures for plugin tests.

This file is auto-loaded via plain `conftest.py` re-export if the package
already has one; otherwise it's imported explicitly by individual modules.
The critical bit is the `_clear_plugin_cache` autouse fixture: without it,
`lru_cache` would leak across tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_plugin_cache() -> None:
    from jw_core.plugins import clear_plugin_cache

    clear_plugin_cache()
    yield
    clear_plugin_cache()
```

Hook it into `packages/jw-core/tests/conftest.py` (append, do not overwrite existing fixtures):

```python
# packages/jw-core/tests/conftest.py — APPEND
from tests.conftest_plugins import _clear_plugin_cache  # noqa: F401
```

If `tests/conftest.py` does not yet exist, create it with:

```python
# packages/jw-core/tests/conftest.py
"""Shared pytest fixtures for jw-core tests."""

from tests.conftest_plugins import _clear_plugin_cache  # noqa: F401
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_registry.py
"""Tests for jw_core.plugins.registry — discovery with monkey-patched entry points."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any

import pytest

from jw_core.plugins.registry import _discover, _entry_points_for_group


def _ep(name: str, group: str, dist_name: str = "pkg-a", value: str | None = None) -> EntryPoint:
    """Build an EntryPoint pointing to a real callable in this test module."""
    return EntryPoint(
        name=name,
        value=value or f"tests.fakes.agent_module:my_agent",
        group=group,
    )


def _patch_entry_points(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[tuple[EntryPoint, str, str]]],
) -> None:
    """Patch importlib.metadata.entry_points + distribution lookups.

    `mapping` is group → list of (ep, dist_name, dist_version).
    """

    def fake_eps(*, group: str | None = None, **_: Any):
        if group is None:
            flat: list[EntryPoint] = []
            for vals in mapping.values():
                flat.extend(ep for ep, _, _ in vals)
            return flat
        return [ep for ep, _, _ in mapping.get(group, [])]

    def fake_dist_for_ep(ep: EntryPoint) -> tuple[str, str]:
        for vals in mapping.values():
            for got_ep, name, ver in vals:
                if got_ep is ep:
                    return name, ver
        return "unknown", "0.0.0"

    monkeypatch.setattr("jw_core.plugins.registry.entry_points", fake_eps)
    monkeypatch.setattr(
        "jw_core.plugins.registry._distribution_for_entry_point", fake_dist_for_ep
    )


def test_entry_points_for_group_returns_list(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = _ep("foo", "jw_agent_toolkit.agents")
    _patch_entry_points(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg-a", "1.0")]})
    got = _entry_points_for_group("jw_agent_toolkit.agents")
    assert [e.name for e in got] == ["foo"]


def test_discover_returns_dict_keyed_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = _ep("translation_helper", "jw_agent_toolkit.agents")
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(ep, "trans-pkg", "1.2.3")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "translation_helper" in out
    spec = out["translation_helper"]
    assert spec.dist_name == "trans-pkg"
    assert spec.dist_version == "1.2.3"


def test_discover_filtered_by_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_ALLOW_LIST", "wanted")
    eps = [
        _ep("wanted", "jw_agent_toolkit.agents"),
        _ep("not_wanted", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert set(out.keys()) == {"wanted"}


def test_discover_filtered_by_deny_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_DENY_LIST", "banned")
    eps = [
        _ep("ok", "jw_agent_toolkit.agents"),
        _ep("banned", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert set(out.keys()) == {"ok"}


def test_discover_conflict_namespaced_default(monkeypatch: pytest.MonkeyPatch) -> None:
    eps = [
        _ep("dup", "jw_agent_toolkit.agents"),
        _ep("dup", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "dup" not in out
    assert "pkg-a:dup" in out
    assert "pkg-b:dup" in out


def test_discover_first_wins_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_CONFLICT_POLICY", "first_wins")
    eps = [
        _ep("dup", "jw_agent_toolkit.agents"),
        _ep("dup", "jw_agent_toolkit.agents"),
    ]
    _patch_entry_points(
        monkeypatch,
        {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1"), (eps[1], "pkg-b", "1")]},
    )
    out = _discover("jw_agent_toolkit.agents")
    assert "dup" in out
    assert out["dup"].dist_name == "pkg-a"


def test_discover_disabled_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PLUGINS_DISABLED", "1")
    eps = [_ep("foo", "jw_agent_toolkit.agents")]
    _patch_entry_points(monkeypatch, {"jw_agent_toolkit.agents": [(eps[0], "pkg-a", "1")]})
    assert _discover("jw_agent_toolkit.agents") == {}


def test_discover_unknown_group_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_entry_points(monkeypatch, {})
    assert _discover("jw_agent_toolkit.bogus") == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_registry.py -v`
Expected: FAIL — `cannot import name '_discover'`.

- [ ] **Step 4: Implement registry**

```python
# packages/jw-core/src/jw_core/plugins/registry.py
"""Discovery via `importlib.metadata.entry_points`.

Steps:
  1. Read group from importlib.metadata.entry_points(group=...).
  2. Resolve distribution name + version per EntryPoint.
  3. Build EntryPointSpec for each.
  4. Apply ALLOW_LIST/DENY_LIST filters.
  5. Fold via the active ConflictPolicy.

Cache lives in factory.py — registry is pure functions, no module-level state.
"""

from __future__ import annotations

import logging
import os
from importlib.metadata import EntryPoint, distributions, entry_points

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.policy import (
    ENV_DISABLED,
    apply_conflict_policy,
    read_env_set,
    read_policy_from_env,
)

logger = logging.getLogger(__name__)


GROUPS: tuple[str, ...] = (
    "jw_agent_toolkit.agents",
    "jw_agent_toolkit.parsers",
    "jw_agent_toolkit.embedders",
    "jw_agent_toolkit.vlm_providers",
    "jw_agent_toolkit.gen_providers",
)


def _entry_points_for_group(group: str) -> list[EntryPoint]:
    """Tiny wrapper for test seam — return list[EntryPoint] for the group."""
    return list(entry_points(group=group))


def _distribution_for_entry_point(ep: EntryPoint) -> tuple[str, str]:
    """Find which distribution declared `ep`.

    Returns (dist_name, dist_version). Falls back to ("unknown", "0.0.0") when
    the EntryPoint was constructed standalone (tests, dynamic registration).
    """
    target_module = ep.value.split(":", 1)[0]
    for dist in distributions():
        try:
            dist_eps = list(dist.entry_points)
        except Exception:  # pragma: no cover  (defensive)
            continue
        for d_ep in dist_eps:
            if (
                d_ep.name == ep.name
                and d_ep.group == ep.group
                and d_ep.value.split(":", 1)[0] == target_module
            ):
                return dist.metadata["Name"], dist.metadata["Version"]
    return "unknown", "0.0.0"


def _discover(group: str) -> dict[str, EntryPointSpec]:
    """Discover all plugins for `group` post-policy. Pure: no caching."""
    if os.getenv(ENV_DISABLED, "").strip() == "1":
        return {}

    allow = read_env_set("JW_PLUGINS_ALLOW_LIST")
    deny = read_env_set("JW_PLUGINS_DENY_LIST") or set()
    policy = read_policy_from_env()

    out: dict[str, EntryPointSpec] = {}
    for ep in _entry_points_for_group(group):
        if allow is not None and ep.name not in allow:
            continue
        if ep.name in deny:
            continue
        try:
            module, _, attr = ep.value.partition(":")
            if not module or not attr:
                logger.warning(
                    "skipping malformed entry point %r in group %r (value=%r)",
                    ep.name,
                    group,
                    ep.value,
                )
                continue
            dist_name, dist_version = _distribution_for_entry_point(ep)
            spec = EntryPointSpec(
                name=ep.name,
                group=group,
                module=module,
                attr=attr,
                dist_name=dist_name,
                dist_version=dist_version,
            )
            out = apply_conflict_policy(out, spec, policy)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to register plugin %r in group %r: %s", ep.name, group, exc
            )
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_registry.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins/registry.py packages/jw-core/tests/test_plugins_registry.py packages/jw-core/tests/conftest_plugins.py packages/jw-core/tests/conftest.py
git commit -m "feat(plugin-sdk): registry — entry-point discovery with policy"
```

---

### Task 5: Verify contracts + version + report (`verify.py`)

**Files:**
- Modify: `packages/jw-core/src/jw_core/plugins/verify.py`
- Modify: `packages/jw-core/src/jw_core/plugins/contracts.py` (add `VerifyReport`)
- Create: `packages/jw-core/tests/test_plugins_verify.py`

- [ ] **Step 1: Append `VerifyReport` to contracts.py**

Append to `packages/jw-core/src/jw_core/plugins/contracts.py`:

```python
# ---------------------------------------------------------------------------
# VerifyReport — structured outcome of verify_plugin()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyReport:
    """Structured report from `verify_plugin(name, group)`."""

    name: str
    group: str
    dist_name: str
    dist_version: str
    ok: bool
    required_present: tuple[str, ...]
    required_missing: tuple[str, ...]
    optional_present: tuple[str, ...]
    optional_missing: tuple[str, ...]
    version_constraint: str | None
    version_satisfied: bool
    errors: tuple[str, ...]
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_verify.py
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
    REQUIRED_BY_GROUP,
    OPTIONAL_BY_GROUP,
    _verify_spec,
    verify_plugin,
)


# ---- shape-only test seams ------------------------------------------------


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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_verify.py -v`
Expected: FAIL — `cannot import name 'REQUIRED_BY_GROUP'`.

- [ ] **Step 4: Implement verify**

Replace `packages/jw-core/src/jw_core/plugins/verify.py`:

```python
# packages/jw-core/src/jw_core/plugins/verify.py
"""Contract + version verification.

`verify_plugin(name, group)` returns a `VerifyReport` describing exactly which
required/optional attributes were found, and whether the plugin's
`jw-agent-toolkit` version constraint is satisfied.

Under `JW_PLUGINS_STRICT=1`, the function raises instead of returning a
report whose `ok` field is False.
"""

from __future__ import annotations

import logging
import os
from importlib.metadata import distribution
from typing import Any

from packaging.requirements import Requirement
from packaging.version import Version

import jw_core
from jw_core.plugins.contracts import EntryPointSpec, VerifyReport
from jw_core.plugins.errors import (
    PluginContractError,
    PluginError,
    PluginVersionMismatch,
)
from jw_core.plugins.factory import get_plugins
from jw_core.plugins.policy import ENV_STRICT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-group required + optional attribute lists.
# Required = MUST be present (verify fails otherwise).
# Optional = MAY be present (capability matrix; degrade gracefully).
# ---------------------------------------------------------------------------

REQUIRED_BY_GROUP: dict[str, tuple[str, ...]] = {
    "jw_agent_toolkit.agents": ("__call__",),
    "jw_agent_toolkit.parsers": ("__call__",),
    "jw_agent_toolkit.embedders": ("name", "target", "dim", "is_available", "embed"),
    "jw_agent_toolkit.vlm_providers": ("name", "is_available", "describe"),
    "jw_agent_toolkit.gen_providers": ("name", "is_available", "generate"),
}

OPTIONAL_BY_GROUP: dict[str, tuple[str, ...]] = {
    "jw_agent_toolkit.agents": ("languages", "version", "cost_estimate"),
    "jw_agent_toolkit.parsers": ("extensions", "mime_types"),
    "jw_agent_toolkit.embedders": ("max_tokens",),
    "jw_agent_toolkit.vlm_providers": ("languages",),
    "jw_agent_toolkit.gen_providers": ("max_tokens", "supports_streaming"),
}


def _plugin_dependencies(spec: EntryPointSpec) -> tuple[str, ...]:
    """Read declared `Requires-Dist` for the plugin's distribution.

    Returns the raw requirement strings; the caller parses with packaging.
    Empty tuple if distribution can't be resolved (test environments).
    """
    try:
        dist = distribution(spec.dist_name)
    except Exception:  # noqa: BLE001
        return ()
    return tuple(dist.requires or ())


def _check_version_constraint(
    requirements: tuple[str, ...],
    installed_version: str,
) -> tuple[str | None, bool]:
    """Find the jw-agent-toolkit constraint (if any) and check it."""
    for raw in requirements:
        try:
            req = Requirement(raw)
        except Exception:  # noqa: BLE001
            continue
        if req.name.lower().replace("_", "-") != "jw-agent-toolkit":
            continue
        if req.specifier and not req.specifier.contains(
            Version(installed_version), prereleases=True
        ):
            return raw, False
        return raw, True
    return None, True


def _verify_spec(
    spec: EntryPointSpec,
    *,
    target: Any,
    plugin_dependencies: tuple[str, ...] | None = None,
) -> VerifyReport:
    """Compute a VerifyReport for an already-resolved plugin target."""
    required = REQUIRED_BY_GROUP.get(spec.group, ())
    optional = OPTIONAL_BY_GROUP.get(spec.group, ())

    req_present = tuple(a for a in required if hasattr(target, a))
    req_missing = tuple(a for a in required if not hasattr(target, a))
    opt_present = tuple(a for a in optional if hasattr(target, a))
    opt_missing = tuple(a for a in optional if not hasattr(target, a))

    deps = plugin_dependencies if plugin_dependencies is not None else _plugin_dependencies(spec)
    installed = jw_core.__version__
    constraint, satisfied = _check_version_constraint(deps, installed)

    ok = not req_missing and satisfied

    return VerifyReport(
        name=spec.name,
        group=spec.group,
        dist_name=spec.dist_name,
        dist_version=spec.dist_version,
        ok=ok,
        required_present=req_present,
        required_missing=req_missing,
        optional_present=opt_present,
        optional_missing=opt_missing,
        version_constraint=constraint,
        version_satisfied=satisfied,
        errors=(),
    )


def _resolve_spec(name: str, group: str) -> tuple[EntryPointSpec, Any]:
    """Pull the spec from the registry and load its target."""
    plugins = get_plugins(group)
    spec = plugins.get(name)
    if spec is None:
        # Also accept namespaced lookups (dist:name).
        for v in plugins.values():
            if v.namespaced_name == name:
                spec = v
                break
    if spec is None:
        raise PluginError(f"plugin {name!r} not found in group {group!r}")
    return spec, spec.resolve()


def verify_plugin(name: str, group: str) -> VerifyReport:
    """Verify a discovered plugin. Strict mode raises; soft mode returns report."""
    spec, target = _resolve_spec(name, group)
    report = _verify_spec(spec, target=target)

    strict = os.getenv(ENV_STRICT, "").strip() == "1"

    if not report.version_satisfied:
        if strict:
            raise PluginVersionMismatch(
                plugin_name=name,
                constraint=report.version_constraint or "<unknown>",
                installed_version=jw_core.__version__,
            )
        logger.warning(
            "plugin %r requires %r but installed %r — skipping",
            name,
            report.version_constraint,
            jw_core.__version__,
        )

    if report.required_missing:
        if strict:
            raise PluginContractError(
                plugin_name=name,
                group=group,
                missing=list(report.required_missing),
            )
        logger.warning(
            "plugin %r in group %r missing required attrs: %s",
            name,
            group,
            list(report.required_missing),
        )

    return report
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_verify.py -v`
Expected: 11 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins/verify.py packages/jw-core/src/jw_core/plugins/contracts.py packages/jw-core/tests/test_plugins_verify.py
git commit -m "feat(plugin-sdk): verify_plugin + VerifyReport + version check"
```

---

### Task 6: Factory — cached `get_plugins` + `clear_plugin_cache`

**Files:**
- Modify: `packages/jw-core/src/jw_core/plugins/factory.py`
- Create: `packages/jw-core/tests/test_plugins_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_factory.py
"""Tests for jw_core.plugins.factory."""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from jw_core.plugins import clear_plugin_cache, get_plugins
from jw_core.plugins.errors import PluginError


def _patch_eps(
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[tuple[EntryPoint, str, str]]],
) -> list[int]:
    calls: list[int] = []

    def fake_eps(*, group: str | None = None, **_):
        calls.append(1)
        if group is None:
            return []
        return [ep for ep, _, _ in mapping.get(group, [])]

    def fake_dist(ep: EntryPoint) -> tuple[str, str]:
        for vals in mapping.values():
            for got, name, ver in vals:
                if got is ep:
                    return name, ver
        return "unknown", "0.0.0"

    monkeypatch.setattr("jw_core.plugins.registry.entry_points", fake_eps)
    monkeypatch.setattr("jw_core.plugins.registry._distribution_for_entry_point", fake_dist)
    return calls


def test_get_plugins_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    out = get_plugins("jw_agent_toolkit.agents")
    assert "foo" in out
    assert out["foo"].dist_name == "pkg"


def test_get_plugins_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    calls = _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    get_plugins("jw_agent_toolkit.agents")
    get_plugins("jw_agent_toolkit.agents")
    get_plugins("jw_agent_toolkit.agents")
    assert len(calls) == 1  # only first call hits entry_points


def test_clear_plugin_cache_forces_rediscovery(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    calls = _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    get_plugins("jw_agent_toolkit.agents")
    clear_plugin_cache()
    get_plugins("jw_agent_toolkit.agents")
    assert len(calls) == 2


def test_get_plugins_rejects_unknown_group(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_eps(monkeypatch, {})
    with pytest.raises(PluginError):
        get_plugins("jw_agent_toolkit.totally_made_up")


def test_get_plugins_empty_when_no_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_eps(monkeypatch, {})
    assert get_plugins("jw_agent_toolkit.agents") == {}


def test_get_plugins_returns_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = EntryPoint(name="foo", value="some.mod:foo", group="jw_agent_toolkit.agents")
    _patch_eps(monkeypatch, {"jw_agent_toolkit.agents": [(ep, "pkg", "1.0")]})
    out_a = get_plugins("jw_agent_toolkit.agents")
    out_a["INJECTED"] = out_a["foo"]
    out_b = get_plugins("jw_agent_toolkit.agents")
    assert "INJECTED" not in out_b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_plugins_factory.py -v`
Expected: FAIL — factory still stubbed, won't actually discover.

- [ ] **Step 3: Implement factory**

Replace `packages/jw-core/src/jw_core/plugins/factory.py`:

```python
# packages/jw-core/src/jw_core/plugins/factory.py
"""Public facade: cached `get_plugins(group)` + `clear_plugin_cache`."""

from __future__ import annotations

from functools import lru_cache

from jw_core.plugins.contracts import EntryPointSpec
from jw_core.plugins.errors import PluginError
from jw_core.plugins.registry import GROUPS, _discover


@lru_cache(maxsize=None)
def _cached_discover(group: str) -> tuple[tuple[str, EntryPointSpec], ...]:
    """Internal cached layer. Returns sorted-tuple form so `lru_cache` is happy.

    We can't cache a `dict` directly (mutable, unhashable). Tuple-of-pairs
    round-trips cheaply.
    """
    if group not in GROUPS:
        raise PluginError(
            f"unknown plugin group {group!r}; expected one of {list(GROUPS)}"
        )
    discovered = _discover(group)
    return tuple(sorted(discovered.items()))


def get_plugins(group: str) -> dict[str, EntryPointSpec]:
    """Return all plugins for `group`, post-policy + post-filter. Cached per process.

    The returned dict is a fresh copy each call — callers can mutate freely.
    """
    return dict(_cached_discover(group))


def clear_plugin_cache() -> None:
    """Reset the discovery cache. Useful in tests; idempotent."""
    _cached_discover.cache_clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_plugins_factory.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the full plugins test set to catch regressions**

Run: `uv run pytest packages/jw-core/tests/test_plugins_*.py -v`
Expected: all green so far (~47 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/plugins/factory.py packages/jw-core/tests/test_plugins_factory.py
git commit -m "feat(plugin-sdk): cached get_plugins + clear_plugin_cache"
```

---

### Task 7: Fixture plugin package (`plugin_sample`)

**Files:**
- Create: `packages/jw-core/tests/fixtures/plugin_sample/pyproject.toml`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/README.md`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/__init__.py`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/agent.py`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/parser.py`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/embedder.py`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/vlm.py`
- Create: `packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/gen.py`

- [ ] **Step 1: Create the fixture `pyproject.toml`**

```toml
# packages/jw-core/tests/fixtures/plugin_sample/pyproject.toml
[project]
name = "plugin-sample"
version = "0.1.0"
description = "Test fixture: a third-party plugin for jw-agent-toolkit"
requires-python = ">=3.13"
dependencies = []

[project.entry-points."jw_agent_toolkit.agents"]
plugin_sample_agent = "plugin_sample.agent:sample_agent"

[project.entry-points."jw_agent_toolkit.parsers"]
plugin_sample_parser = "plugin_sample.parser:sample_parser"

[project.entry-points."jw_agent_toolkit.embedders"]
plugin_sample_embedder = "plugin_sample.embedder:SampleEmbedder"

[project.entry-points."jw_agent_toolkit.vlm_providers"]
plugin_sample_vlm = "plugin_sample.vlm:SampleVLM"

[project.entry-points."jw_agent_toolkit.gen_providers"]
plugin_sample_gen = "plugin_sample.gen:SampleGen"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/plugin_sample"]
```

- [ ] **Step 2: Create the README**

```markdown
# plugin_sample

Test fixture package used by `jw-core`'s plugin-SDK e2e tests. NOT for
publication. Installed locally via `uv pip install -e` from the test runner.

Registers one entry point in each of the 5 jw_agent_toolkit.* groups.
```

- [ ] **Step 3: Create the package init**

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/__init__.py
"""plugin_sample — fixture used by jw-core's plugin SDK tests."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create the 5 plugin modules**

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/agent.py
"""Agent stub. Returns a deterministic payload."""

from __future__ import annotations

from typing import Any


async def sample_agent(**kwargs: Any) -> dict[str, Any]:
    """Plugin agent — echoes its kwargs in a shape compatible with AgentResult."""
    return {"findings": [], "echo": kwargs, "agent": "plugin_sample_agent"}


sample_agent.__name__ = "plugin_sample_agent"
sample_agent.languages = ["en", "es"]  # type: ignore[attr-defined]
sample_agent.version = "0.1.0"  # type: ignore[attr-defined]
```

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/parser.py
"""Parser stub. Returns a dict with the raw payload."""

from __future__ import annotations


def sample_parser(raw: bytes | str, *, source_url: str | None = None) -> dict:
    """Returns a ParsedDocument-like dict."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return {
        "text": text,
        "source_url": source_url,
        "parser": "plugin_sample_parser",
    }


sample_parser.extensions = [".sample"]  # type: ignore[attr-defined]
sample_parser.mime_types = ["application/x-plugin-sample"]  # type: ignore[attr-defined]
```

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/embedder.py
"""Embedder stub. Deterministic zero vectors."""

from __future__ import annotations


class SampleEmbedder:
    name = "plugin_sample_embedder"
    target = "cpu"
    dim = 8

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]
```

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/vlm.py
"""VLM stub."""

from __future__ import annotations


class SampleVLM:
    name = "plugin_sample_vlm"

    def is_available(self) -> bool:
        return True

    def describe(self, image_bytes: bytes, *, language: str = "en") -> str:
        return f"plugin_sample_vlm[{language}] len={len(image_bytes)}"
```

```python
# packages/jw-core/tests/fixtures/plugin_sample/src/plugin_sample/gen.py
"""Gen provider stub."""

from __future__ import annotations


class SampleGen:
    name = "plugin_sample_gen"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, *, max_tokens: int = 128) -> str:
        return f"plugin_sample_gen[{max_tokens}]: {prompt}"
```

- [ ] **Step 5: Verify the fixture package builds**

Run:
```bash
cd packages/jw-core/tests/fixtures/plugin_sample && uv build 2>&1 | tail -5
```
Expected: a wheel under `dist/`. Discard the wheel (we install editable, not the wheel).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/tests/fixtures/plugin_sample
git commit -m "test(plugin-sdk): fixture package 'plugin_sample' registering 5 entry points"
```

---

### Task 8: E2E test — install fixture in subprocess and verify discovery

**Files:**
- Create: `packages/jw-core/tests/test_plugins_e2e.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_plugins_e2e.py
"""End-to-end: install plugin_sample with `uv pip install -e` in a subprocess
that creates an ephemeral venv, then run discovery from inside that venv via
`-c` invocations.

Why subprocess: `importlib.metadata` is process-cached; we need a clean
interpreter to see the fixture's entry points without leaking into other tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "plugin_sample"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _have_uv() -> bool:
    return shutil.which("uv") is not None


pytestmark = pytest.mark.skipif(not _have_uv(), reason="uv not installed")


@pytest.fixture(scope="module")
def plugin_venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create an isolated venv with jw-core + plugin_sample installed editable."""
    venv = tmp_path_factory.mktemp("plugin_venv")
    subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)

    py = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"

    # Install jw-core editable + packaging
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(py),
            "-e",
            str(REPO_ROOT / "packages" / "jw-core"),
            "packaging",
        ],
        check=True,
        capture_output=True,
    )
    # Install the fixture editable
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), "-e", str(FIXTURE)],
        check=True,
        capture_output=True,
    )
    return py


def _run_in_venv(py: Path, code: str, env: dict[str, str] | None = None) -> str:
    """Run `code` in the venv and return stdout (stripped)."""
    full_env = {**os.environ, **(env or {})}
    out = subprocess.run(
        [str(py), "-c", code],
        check=True,
        capture_output=True,
        env=full_env,
        text=True,
    )
    return out.stdout.strip()


def test_e2e_agent_discovered(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "plugins = get_plugins('jw_agent_toolkit.agents')\n"
        "print(json.dumps(sorted(plugins.keys())))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    names = json.loads(out)
    assert "plugin_sample_agent" in names


def test_e2e_all_five_groups_discovered(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "groups = ["
        "  'jw_agent_toolkit.agents',"
        "  'jw_agent_toolkit.parsers',"
        "  'jw_agent_toolkit.embedders',"
        "  'jw_agent_toolkit.vlm_providers',"
        "  'jw_agent_toolkit.gen_providers',"
        "]\n"
        "out = {g: sorted(get_plugins(g).keys()) for g in groups}\n"
        "print(json.dumps(out))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    parsed = json.loads(out)
    assert "plugin_sample_agent" in parsed["jw_agent_toolkit.agents"]
    assert "plugin_sample_parser" in parsed["jw_agent_toolkit.parsers"]
    assert "plugin_sample_embedder" in parsed["jw_agent_toolkit.embedders"]
    assert "plugin_sample_vlm" in parsed["jw_agent_toolkit.vlm_providers"]
    assert "plugin_sample_gen" in parsed["jw_agent_toolkit.gen_providers"]


def test_e2e_verify_plugin_reports_ok(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import verify_plugin\n"
        "rep = verify_plugin('plugin_sample_agent', 'jw_agent_toolkit.agents')\n"
        "print(json.dumps({"
        "  'ok': rep.ok,"
        "  'required_present': list(rep.required_present),"
        "  'required_missing': list(rep.required_missing),"
        "  'optional_present': list(rep.optional_present),"
        "  'dist_name': rep.dist_name,"
        "  'version_satisfied': rep.version_satisfied,"
        "}))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    rep = json.loads(out)
    assert rep["ok"]
    assert "__call__" in rep["required_present"]
    assert "languages" in rep["optional_present"]
    assert rep["dist_name"] == "plugin-sample"


def test_e2e_disabled_env_short_circuits(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "print(json.dumps(list(get_plugins('jw_agent_toolkit.agents').keys())))\n"
    )
    out = _run_in_venv(plugin_venv, code, env={"JW_PLUGINS_DISABLED": "1"})
    assert json.loads(out) == []


def test_e2e_allow_list_filters(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "print(json.dumps(sorted(get_plugins('jw_agent_toolkit.agents').keys())))\n"
    )
    out = _run_in_venv(
        plugin_venv, code, env={"JW_PLUGINS_ALLOW_LIST": "nonexistent_only"}
    )
    assert json.loads(out) == []


def test_e2e_resolve_runs_callable(plugin_venv: Path) -> None:
    code = (
        "import asyncio, json\n"
        "from jw_core.plugins import get_plugins\n"
        "spec = get_plugins('jw_agent_toolkit.agents')['plugin_sample_agent']\n"
        "fn = spec.resolve()\n"
        "got = asyncio.run(fn(question='hi'))\n"
        "print(json.dumps({'agent': got['agent'], 'q': got['echo']['question']}))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    parsed = json.loads(out)
    assert parsed["agent"] == "plugin_sample_agent"
    assert parsed["q"] == "hi"
```

- [ ] **Step 2: Run test to verify it fails (then passes after fixture install)**

Run: `uv run pytest packages/jw-core/tests/test_plugins_e2e.py -v -s`
Expected: 6 passed. If `uv` is not on PATH it skips cleanly.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_plugins_e2e.py
git commit -m "test(plugin-sdk): e2e — fixture install + discovery in subprocess venv"
```

---

### Task 9: Wire `jw_core.plugins` API into `jw_core` top-level

**Files:**
- Modify: `packages/jw-core/src/jw_core/__init__.py`

- [ ] **Step 1: Read current init**

Run: `uv run python -c "import jw_core; print(jw_core.__file__)"` to confirm path.

- [ ] **Step 2: Append the re-export block**

Append to `packages/jw-core/src/jw_core/__init__.py`:

```python
# ---- Plugin SDK (Fase 41) -------------------------------------------------
# Exposed as `jw_core.plugins.*`. We import the submodule eagerly here so
# `from jw_core import plugins` works, but the heavy discovery is still lazy.
from jw_core import plugins as plugins  # noqa: E402, F401
```

- [ ] **Step 3: Smoke-test from a fresh interpreter**

Run:
```bash
uv run python -c "
from jw_core import plugins
from jw_core.plugins import get_plugins, verify_plugin, clear_plugin_cache
from jw_core.plugins import PluginError, PluginConflictError, PluginContractError, PluginVersionMismatch
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/src/jw_core/__init__.py
git commit -m "feat(plugin-sdk): re-export jw_core.plugins from jw_core package init"
```

---

### Task 10: Integrate plugins into `jw-eval.default_agent_registry`

**Files:**
- Modify: `packages/jw-eval/src/jw_eval/cli.py`
- Create: `packages/jw-eval/tests/test_plugin_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_plugin_integration.py
"""Tests for jw-eval ↔ jw_core.plugins integration."""

from __future__ import annotations

from typing import Any

import pytest

from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec
from jw_eval.cli import default_agent_registry


async def _fake_plugin_agent(**kwargs: Any) -> Any:
    return {"findings": [], "echo": kwargs, "agent": "fake_plugin"}


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_default_registry_includes_hardcoded_agents() -> None:
    reg = default_agent_registry()
    assert "apologetics" in reg
    assert "verse_explainer" in reg


def test_default_registry_merges_plugin_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EntryPointSpec(
        name="fake_plugin",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="fake_plugin",
        dist_name="fake-pkg",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_plugin_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_eval.cli.get_plugins",
        lambda group: {"fake_plugin": spec} if group == "jw_agent_toolkit.agents" else {},
    )
    reg = default_agent_registry()
    assert "fake_plugin" in reg


def test_plugin_does_not_override_core_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Plugin with same name as a hardcoded agent should NOT replace it.
    spec = EntryPointSpec(
        name="apologetics",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="apologetics",
        dist_name="bad-pkg",
        dist_version="0.1.0",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_plugin_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_eval.cli.get_plugins",
        lambda group: {"apologetics": spec} if group == "jw_agent_toolkit.agents" else {},
    )
    reg = default_agent_registry()
    # core wins
    assert reg["apologetics"] is not _fake_plugin_agent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_plugin_integration.py -v`
Expected: FAIL — `get_plugins` not imported in `jw_eval.cli`.

- [ ] **Step 3: Patch `default_agent_registry` in `cli.py`**

Edit `packages/jw-eval/src/jw_eval/cli.py`. Add to imports near the top, after the existing `from jw_eval.suite import Suite`:

```python
from jw_core.plugins import get_plugins
```

Replace the body of `default_agent_registry` (everything from `def default_agent_registry` to `return registry`) with:

```python
def default_agent_registry() -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Return the registry of real agents from jw-agents wrapped for sync invocation.

    Hardcoded core agents take precedence; community plugins are merged after.
    Plugins with the same name as a core agent are silently ignored — they
    remain accessible via their namespaced form (dist:name).
    """

    from jw_agents.apologetics import apologetics  # type: ignore[import-not-found]
    from jw_agents.conversation_assistant import conversation_assistant  # type: ignore[import-not-found]
    from jw_agents.letter_composer import letter_composer  # type: ignore[import-not-found]
    from jw_agents.life_topics import life_topics  # type: ignore[import-not-found]
    from jw_agents.meeting_helper import meeting_helper  # type: ignore[import-not-found]
    from jw_agents.news_monitor import news_monitor  # type: ignore[import-not-found]
    from jw_agents.research_topic import research_topic  # type: ignore[import-not-found]
    from jw_agents.student_part_helper import student_part_helper  # type: ignore[import-not-found]
    from jw_agents.study_conductor import prepare_lesson  # type: ignore[import-not-found]
    from jw_agents.verse_explainer import verse_explainer  # type: ignore[import-not-found]

    registry: dict[str, Callable[[dict[str, Any]], Any]] = {
        "apologetics": _make_sync_wrapper(apologetics),
        "conversation_assistant": _make_sync_wrapper(conversation_assistant),
        "letter_composer": _make_sync_wrapper(letter_composer),
        "life_topics": _make_sync_wrapper(life_topics),
        "meeting_helper": _make_sync_wrapper(meeting_helper),
        "news_monitor": _make_sync_wrapper(news_monitor),
        "research_topic": _make_sync_wrapper(research_topic),
        "study_conductor": _make_sync_wrapper(prepare_lesson),
        "student_part_helper": _make_sync_wrapper(student_part_helper),
        "verse_explainer": _make_sync_wrapper(verse_explainer),
    }

    # Fase 41 — merge community plugins. Core agents win; plugin sharing a
    # name is silently skipped (still available via namespaced lookup).
    for name, spec in get_plugins("jw_agent_toolkit.agents").items():
        if name in registry:
            continue
        try:
            registry[name] = _make_sync_wrapper(spec.resolve())
        except Exception:  # noqa: BLE001
            # Plugin failed to load — exclude from registry, do not crash eval.
            continue

    return registry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_plugin_integration.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run jw-eval regression**

Run: `uv run pytest packages/jw-eval/tests -v --tb=short`
Expected: prior tests stay green. No regression in Fase 22 cases.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/src/jw_eval/cli.py packages/jw-eval/tests/test_plugin_integration.py
git commit -m "feat(jw-eval): merge plugin-SDK agents into default_agent_registry"
```

---

### Task 11: Integrate plugins into `jw-rag.embed_providers.factory`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/factory.py`
- Create: `packages/jw-rag/tests/test_embed_plugins.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_plugins.py
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

    registry = _instantiate_registry()  # MUST NOT raise
    names = [p.name for p in registry]
    assert "broken_emb" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_plugins.py -v`
Expected: FAIL — `get_plugins` not imported in factory.

- [ ] **Step 3: Patch `_instantiate_registry`**

Edit `packages/jw-rag/src/jw_rag/embed_providers/factory.py`.

Add to imports (after `import numpy as np`):

```python
from jw_core.plugins import get_plugins
```

Replace `_instantiate_registry` (the existing function body) with:

```python
def _instantiate_registry() -> list[EmbedProvider]:
    """Build the full provider registry (real + fakes + plugins).

    Plugin embedders from `jw_agent_toolkit.embedders` are appended after the
    hardcoded ones. Plugins that raise during resolution are dropped silently
    (logged at WARN — see jw_core.plugins). Plugins that don't satisfy the
    structural EmbedProvider Protocol are also dropped.
    """
    from jw_rag.embed_providers.bge_m3 import BGEM3Provider
    from jw_rag.embed_providers.cohere import CohereEmbedV3Provider
    from jw_rag.embed_providers.fakes import (
        FakeBGEM3,
        FakeCohereEmbed,
        FakeJinaEmbed,
        FakeMultilingualE5,
        FakeOllamaEmbed,
        FakeVoyageEmbed,
    )
    from jw_rag.embed_providers.jina import JinaEmbeddingsV3Provider
    from jw_rag.embed_providers.multilingual_e5 import MultilingualE5Provider
    from jw_rag.embed_providers.ollama import OllamaEmbedProvider
    from jw_rag.embed_providers.voyage import VoyageMultilingualProvider

    registry: list[EmbedProvider] = [
        CohereEmbedV3Provider(),
        JinaEmbeddingsV3Provider(),
        VoyageMultilingualProvider(),
        BGEM3Provider(),
        MultilingualE5Provider(),
        OllamaEmbedProvider(),
        FakeBGEM3(),
        FakeMultilingualE5(),
        FakeJinaEmbed(),
        FakeCohereEmbed(),
        FakeVoyageEmbed(),
        FakeOllamaEmbed(),
    ]

    for _name, spec in get_plugins("jw_agent_toolkit.embedders").items():
        try:
            target = spec.resolve()
            instance = target() if isinstance(target, type) else target
        except Exception:  # noqa: BLE001
            logger.warning("plugin embedder %r failed to load — skipping", _name)
            continue
        if not isinstance(instance, EmbedProvider):
            logger.warning(
                "plugin embedder %r does not satisfy EmbedProvider Protocol — skipping",
                _name,
            )
            continue
        registry.append(instance)

    return registry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_plugins.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run jw-rag regression**

Run: `uv run pytest packages/jw-rag/tests -v --tb=short`
Expected: prior tests stay green.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/factory.py packages/jw-rag/tests/test_embed_plugins.py
git commit -m "feat(jw-rag): merge plugin-SDK embedders into provider registry"
```

---

### Task 12: Integrate plugins into `jw-mcp.server`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_plugin_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_plugin_tools.py
"""Tests for jw-mcp ↔ jw_core.plugins tool registration."""

from __future__ import annotations

from typing import Any

import pytest

from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec
from jw_mcp.server import register_plugin_tools


async def _fake_agent(**kwargs: Any) -> Any:
    return {"echo": kwargs}


class _FakeMCP:
    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    def tool(self, name: str | None = None):
        def deco(fn):
            self.registered.append((name or fn.__name__, fn.__doc__ or ""))
            return fn
        return deco


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def test_register_plugin_tools_emits_one_tool_per_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = EntryPointSpec(
        name="myagent",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="myagent",
        dist_name="x",
        dist_version="1",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        return _fake_agent

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_mcp.server.get_plugins",
        lambda group: {"myagent": spec} if group == "jw_agent_toolkit.agents" else {},
    )

    mcp = _FakeMCP()
    register_plugin_tools(mcp)
    names = [n for n, _ in mcp.registered]
    assert "agent.myagent" in names


def test_register_plugin_tools_handles_broken_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = EntryPointSpec(
        name="bad",
        group="jw_agent_toolkit.agents",
        module="dummy",
        attr="bad",
        dist_name="x",
        dist_version="1",
    )

    def fake_resolve(self: EntryPointSpec) -> Any:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(EntryPointSpec, "resolve", fake_resolve, raising=True)
    monkeypatch.setattr(
        "jw_mcp.server.get_plugins",
        lambda group: {"bad": spec} if group == "jw_agent_toolkit.agents" else {},
    )

    mcp = _FakeMCP()
    register_plugin_tools(mcp)  # MUST NOT raise
    assert mcp.registered == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_plugin_tools.py -v`
Expected: FAIL — `register_plugin_tools` does not exist.

- [ ] **Step 3: Add `register_plugin_tools` to `jw_mcp.server`**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
# ---------------------------------------------------------------------------
# Plugin-SDK integration (Fase 41) ------------------------------------------
# ---------------------------------------------------------------------------

import asyncio as _asyncio
import inspect as _inspect
import logging as _logging
from typing import Any as _Any

from jw_core.plugins import get_plugins

_logger = _logging.getLogger(__name__)


def _make_mcp_tool(name: str, fn: _Any):
    """Wrap a plugin agent into an MCP tool callable.

    MCP tools are async; the wrapper auto-handles sync agents by offloading to
    a thread, and async ones by awaiting directly.
    """
    is_coro = _inspect.iscoroutinefunction(fn)

    async def tool_fn(**kwargs: _Any) -> _Any:
        if is_coro:
            return await fn(**kwargs)
        return await _asyncio.to_thread(fn, **kwargs)

    tool_fn.__name__ = name
    tool_fn.__doc__ = (fn.__doc__ or f"Plugin agent: {name}").strip()
    return tool_fn


def register_plugin_tools(mcp: _Any) -> None:
    """Register every discovered agent plugin as an MCP tool named `agent.<name>`."""
    for plug_name, spec in get_plugins("jw_agent_toolkit.agents").items():
        try:
            target = spec.resolve()
        except Exception:  # noqa: BLE001
            _logger.warning(
                "skipping plugin agent %r — failed to resolve target", plug_name
            )
            continue
        tool_name = f"agent.{plug_name}"
        wrapped = _make_mcp_tool(tool_name, target)
        try:
            mcp.tool(name=tool_name)(wrapped)
        except Exception:  # noqa: BLE001
            _logger.warning(
                "skipping plugin agent %r — MCP refused tool registration", plug_name
            )
            continue
```

If the server has a single `register_tools()` entry point, also call `register_plugin_tools(mcp)` at the end of it. Locate the existing call site by:

```bash
grep -n "def register_tools" packages/jw-mcp/src/jw_mcp/server.py
```

Then inside that function, near the end, add:

```python
    register_plugin_tools(mcp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_plugin_tools.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run jw-mcp regression**

Run: `uv run pytest packages/jw-mcp/tests -v --tb=short`
Expected: prior tests stay green.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_plugin_tools.py
git commit -m "feat(jw-mcp): register plugin agents as agent.<name> MCP tools"
```

---

### Task 13: CLI — `jw plugins list / verify / disable`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/plugins.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-cli/tests/test_plugins_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_plugins_cli.py
"""Tests for `jw plugins {list,verify,disable}`."""

from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from jw_cli.main import app
from jw_core.plugins import clear_plugin_cache
from jw_core.plugins.contracts import EntryPointSpec, VerifyReport


runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_plugin_cache()
    yield
    clear_plugin_cache()


def _spec(name: str = "demo") -> EntryPointSpec:
    return EntryPointSpec(
        name=name,
        group="jw_agent_toolkit.agents",
        module="m",
        attr=name,
        dist_name="demo-pkg",
        dist_version="1.0.0",
    )


def test_plugins_list_default_human(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_cli.commands.plugins.get_plugins",
        lambda group: {"demo": _spec()} if group == "jw_agent_toolkit.agents" else {},
    )
    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "demo-pkg" in result.stdout


def test_plugins_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_cli.commands.plugins.get_plugins",
        lambda group: {"demo": _spec()} if group == "jw_agent_toolkit.agents" else {},
    )
    result = runner.invoke(app, ["plugins", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "jw_agent_toolkit.agents" in data
    assert data["jw_agent_toolkit.agents"][0]["name"] == "demo"


def test_plugins_verify_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    rep = VerifyReport(
        name="demo",
        group="jw_agent_toolkit.agents",
        dist_name="demo-pkg",
        dist_version="1.0.0",
        ok=True,
        required_present=("__call__",),
        required_missing=(),
        optional_present=("languages",),
        optional_missing=("version",),
        version_constraint=None,
        version_satisfied=True,
        errors=(),
    )

    def fake_verify(name: str, group: str) -> Any:  # noqa: ARG001
        return rep

    monkeypatch.setattr("jw_cli.commands.plugins.verify_plugin", fake_verify)
    result = runner.invoke(app, ["plugins", "verify", "demo"])
    assert result.exit_code == 0
    assert "ok" in result.stdout.lower()


def test_plugins_verify_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    rep = VerifyReport(
        name="bad",
        group="jw_agent_toolkit.agents",
        dist_name="bad-pkg",
        dist_version="1.0.0",
        ok=False,
        required_present=(),
        required_missing=("__call__",),
        optional_present=(),
        optional_missing=("languages",),
        version_constraint=None,
        version_satisfied=True,
        errors=(),
    )
    monkeypatch.setattr(
        "jw_cli.commands.plugins.verify_plugin", lambda n, g: rep  # noqa: ARG005
    )
    result = runner.invoke(app, ["plugins", "verify", "bad"])
    assert result.exit_code == 2  # non-zero on failure


def test_plugins_disable_writes_config(tmp_path: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "plugins.toml"
    result = runner.invoke(
        app, ["plugins", "disable", "spammy", "--config", str(cfg)]
    )
    assert result.exit_code == 0
    assert cfg.exists()
    text = cfg.read_text()
    assert "spammy" in text
    assert "[deny]" in text or "deny" in text


def test_plugins_disable_appends(tmp_path: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "plugins.toml"
    runner.invoke(app, ["plugins", "disable", "a", "--config", str(cfg)])
    runner.invoke(app, ["plugins", "disable", "b", "--config", str(cfg)])
    text = cfg.read_text()
    assert "a" in text and "b" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_plugins_cli.py -v`
Expected: FAIL — `plugins` subcommand missing.

- [ ] **Step 3: Implement the command module**

```python
# packages/jw-cli/src/jw_cli/commands/plugins.py
"""`jw plugins` — list / verify / disable community plugins."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from jw_core.plugins import get_plugins, verify_plugin
from jw_core.plugins.errors import PluginError
from jw_core.plugins.registry import GROUPS

app = typer.Typer(help="Manage community plugins (Fase 41).", no_args_is_help=True)

DEFAULT_CONFIG = Path.home() / ".jw-agent-toolkit" / "plugins.toml"


@app.command("list")
def list_plugins(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List all discovered plugins, grouped by extension point."""
    by_group: dict[str, list[dict[str, str]]] = {}
    for group in GROUPS:
        try:
            specs = get_plugins(group)
        except PluginError:
            specs = {}
        by_group[group] = [
            {
                "name": s.name,
                "dist": s.dist_name,
                "version": s.dist_version,
                "module": s.module,
                "attr": s.attr,
            }
            for s in specs.values()
        ]

    if json_out:
        typer.echo(json.dumps(by_group, indent=2, sort_keys=True))
        return

    for group, items in by_group.items():
        typer.echo(f"\n## {group}")
        if not items:
            typer.echo("  (no plugins)")
            continue
        for it in items:
            typer.echo(
                f"  {it['name']:30s}  {it['dist']:25s} v{it['version']}  {it['module']}:{it['attr']}"
            )


@app.command("verify")
def verify_plugin_cmd(
    name: str = typer.Argument(..., help="Plugin name (or dist:name for disambiguation)."),
    group: str = typer.Option(
        "jw_agent_toolkit.agents",
        "--group",
        help="Entry-point group to look the plugin up in.",
    ),
) -> None:
    """Run the contract + version check on a plugin and print the report."""
    try:
        rep = verify_plugin(name, group)
    except PluginError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"plugin: {rep.name}  ({rep.dist_name} v{rep.dist_version})")
    typer.echo(f"  group:              {rep.group}")
    typer.echo(f"  required present:   {list(rep.required_present)}")
    typer.echo(f"  required missing:   {list(rep.required_missing)}")
    typer.echo(f"  optional present:   {list(rep.optional_present)}")
    typer.echo(f"  optional missing:   {list(rep.optional_missing)}")
    typer.echo(f"  version constraint: {rep.version_constraint}")
    typer.echo(f"  version satisfied:  {rep.version_satisfied}")
    typer.echo(f"  status:             {'OK' if rep.ok else 'FAIL'}")

    if not rep.ok:
        raise typer.Exit(code=2)


@app.command("disable")
def disable(
    name: str = typer.Argument(..., help="Plugin name to deny-list persistently."),
    config: Path = typer.Option(
        DEFAULT_CONFIG, "--config", help="Path to persistent deny-list TOML."
    ),
) -> None:
    """Append a plugin name to the persistent deny list."""
    config = Path(config)
    config.parent.mkdir(parents=True, exist_ok=True)

    existing: list[str] = []
    if config.exists():
        for line in config.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" in line:
                continue
            existing.append(line.strip('"').strip("'"))
            continue
        # Naive parser — we keep it dependency-free.
        for line in config.read_text().splitlines():
            if line.strip().startswith('"') and line.strip().endswith('",'):
                existing.append(line.strip().strip('"').rstrip(",").strip('"'))

    if name in existing:
        typer.echo(f"plugin {name!r} already in deny list at {config}")
        return

    existing.append(name)
    body = '[deny]\nplugins = [\n' + "".join(f'    "{n}",\n' for n in existing) + "]\n"
    config.write_text(body)
    typer.echo(f"plugin {name!r} added to {config}")
```

- [ ] **Step 4: Wire the subcommand into the umbrella CLI**

Edit `packages/jw-cli/src/jw_cli/commands/__init__.py`. Append:

```python
from jw_cli.commands.plugins import app as plugins_app  # noqa: F401
```

Edit `packages/jw-cli/src/jw_cli/main.py`. Add (after other `app.add_typer(...)` calls):

```python
from jw_cli.commands.plugins import app as plugins_app

app.add_typer(plugins_app, name="plugins")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_plugins_cli.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/plugins.py packages/jw-cli/src/jw_cli/commands/__init__.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_plugins_cli.py
git commit -m "feat(jw-cli): add jw plugins list/verify/disable subcommand"
```

---

### Task 14: CI job `plugin-sdk` (offline)

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Find existing jobs in ci.yml**

Run: `grep -n "^  [a-z-]*:" .github/workflows/ci.yml | head -10` to see job names.

- [ ] **Step 2: Append the new job**

Append (or insert near other test jobs) the following snippet inside the `jobs:` block:

```yaml
  plugin-sdk:
    needs: test
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install uv
        run: pipx install uv
      - name: Sync workspace
        run: uv sync --all-packages --frozen
      - name: Install plugin fixture (editable)
        run: uv pip install -e packages/jw-core/tests/fixtures/plugin_sample
      - name: Run plugin SDK tests
        run: uv run pytest packages/jw-core/tests/test_plugins_*.py -v
      - name: Smoke: jw plugins list --json
        run: |
          uv run jw plugins list --json > plugins.json
          test -s plugins.json
          uv run python -c "import json; d=json.load(open('plugins.json')); assert any('plugin_sample_agent' in [p['name'] for p in g] for g in d.values()), d"
      - name: Smoke: JW_PLUGINS_DISABLED=1 empties registry
        env:
          JW_PLUGINS_DISABLED: "1"
        run: |
          uv run jw plugins list --json > plugins_off.json
          uv run python -c "import json; d=json.load(open('plugins_off.json')); assert all(v==[] for v in d.values()), d"
```

- [ ] **Step 3: Validate CI YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` — must exit 0.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(plugin-sdk): offline job installing plugin_sample fixture + smoke checks"
```

---

### Task 15: Docs — `overview / security / capabilities / authoring`

**Files:**
- Create: `docs/plugin-sdk/overview.md`
- Create: `docs/plugin-sdk/security.md`
- Create: `docs/plugin-sdk/capabilities.md`
- Create: `docs/plugin-sdk/authoring.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write `overview.md`**

```markdown
# Plugin SDK — overview

> Tier 2 (comunidad). Fase 41. Habilita Fase 42 (scaffolding).

El plugin SDK convierte cinco puntos de extensión del toolkit en superficies de
contribución externa: terceros publican un paquete Python con un entry point
declarado en `pyproject.toml` y el toolkit lo descubre en runtime.

## Grupos de entry points

| Group | Contrato | Ejemplo |
|---|---|---|
| `jw_agent_toolkit.agents` | async callable `(**kwargs) -> AgentResult` | nuevo agente |
| `jw_agent_toolkit.parsers` | `(raw, *, source_url=None) -> ParsedDocument` | parser de formato exótico |
| `jw_agent_toolkit.embedders` | `EmbedProvider` (Fase 33) | embedder dedicado |
| `jw_agent_toolkit.vlm_providers` | `VLMProvider` | proveedor VLM extra |
| `jw_agent_toolkit.gen_providers` | `GenerationProvider` (Fase 38) | proveedor Gen extra |

## Uso desde el toolkit

```python
from jw_core.plugins import get_plugins, verify_plugin

agents = get_plugins("jw_agent_toolkit.agents")
print(agents["my_agent"].dist_name, agents["my_agent"].dist_version)

report = verify_plugin("my_agent", "jw_agent_toolkit.agents")
print(report.ok, report.required_missing)
```

## CLI

```bash
uv run jw plugins list          # human
uv run jw plugins list --json   # CI-friendly
uv run jw plugins verify foo --group jw_agent_toolkit.agents
uv run jw plugins disable bar
```

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_PLUGINS_DISABLED` | unset | si `=1`, ningún plugin se descubre |
| `JW_PLUGINS_STRICT` | unset | si `=1`, errores de contrato/versión abortan |
| `JW_PLUGINS_ALLOW_LIST` | unset | CSV; sólo estos se cargan |
| `JW_PLUGINS_DENY_LIST` | unset | CSV; estos no se cargan |
| `JW_PLUGINS_CONFLICT_POLICY` | `namespaced` | `first_wins` \| `last_wins` \| `namespaced` \| `reject` |
```

- [ ] **Step 2: Write `security.md`**

```markdown
# Plugin SDK — seguridad

> Instalar un plugin del SDK = ejecutar código arbitrario. Verifica la fuente.

## Modelo de confianza

El plugin corre en el proceso del host con todos los privilegios. No hay
sandboxing real (sin subprocesos / WASM / seccomp). El modelo es **igual que
`pip install`**: cualquier paquete Python instalable puede:
- leer secretos del entorno (`os.environ`)
- escribir y leer archivos
- hacer red

El SDK no mitiga esto. Lo que sí ofrece:

| Mitigación | Cómo |
|---|---|
| Desactivar discovery completo | `JW_PLUGINS_DISABLED=1` |
| Allow-list explícito | `JW_PLUGINS_ALLOW_LIST="trusted_a,trusted_b"` |
| Deny-list (post-incident) | `JW_PLUGINS_DENY_LIST="bad"` o `jw plugins disable bad` |
| Trazabilidad | `verify_plugin` reporta `dist_name`, `dist_version` |
| Reject de duplicados | `JW_PLUGINS_CONFLICT_POLICY=reject` |

## Recomendaciones por entorno

- **Dev local**: default permisivo + `verify_plugin` antes de producir.
- **CI público**: `JW_PLUGINS_DISABLED=1` por defecto. Tests propios usan
  `uv pip install -e` explícito.
- **Auditoría / producción sensible**: `JW_PLUGINS_ALLOW_LIST` cerrado +
  `JW_PLUGINS_STRICT=1` para forzar fail-hard.

## Lo que NO ofrecemos

- Bloqueo de red por plugin.
- Bloqueo de filesystem por plugin.
- Sandbox de imports.

Esas mitigaciones requieren subprocesos + IPC y no entran en Fase 41. Queda
documentado en el ROADMAP.
```

- [ ] **Step 3: Write `capabilities.md`**

```markdown
# Plugin SDK — capability matrix

| Group | Required attrs | Optional attrs |
|---|---|---|
| `jw_agent_toolkit.agents` | `__call__` | `languages`, `version`, `cost_estimate` |
| `jw_agent_toolkit.parsers` | `__call__` | `extensions`, `mime_types` |
| `jw_agent_toolkit.embedders` | `name`, `target`, `dim`, `is_available`, `embed` | `max_tokens` |
| `jw_agent_toolkit.vlm_providers` | `name`, `is_available`, `describe` | `languages` |
| `jw_agent_toolkit.gen_providers` | `name`, `is_available`, `generate` | `max_tokens`, `supports_streaming` |

## Política de evolución

- Los Protocols son **aditivos** por contrato dentro de un major.
- Atributos opcionales se detectan vía `hasattr`, **no** isinstance check.
- Cualquier nuevo método **requerido** fuerza un bump de major del toolkit.
- `verify_plugin` reporta `optional_present` / `optional_missing` para que el
  autor sepa qué features puede activar.
```

- [ ] **Step 4: Write `authoring.md`**

```markdown
# Plugin SDK — authoring guide

## 1. Esqueleto mínimo (agente)

```
my-jw-plugin/
├── pyproject.toml
└── src/my_jw_plugin/
    ├── __init__.py
    └── agent.py
```

`pyproject.toml`:

```toml
[project]
name = "my-jw-plugin"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "jw-agent-toolkit>=1.0,<2.0",  # capability matrix de la major actual
]

[project.entry-points."jw_agent_toolkit.agents"]
translation_helper = "my_jw_plugin.agent:translation_helper"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_jw_plugin"]
```

`agent.py`:

```python
from typing import Any

async def translation_helper(**kwargs: Any) -> dict[str, Any]:
    text = kwargs.get("text", "")
    return {"findings": [], "translation": text.upper()}

translation_helper.languages = ["en", "es", "pt"]
```

## 2. Instalar local

```bash
uv pip install -e ./my-jw-plugin
uv run jw plugins list
uv run jw plugins verify translation_helper
uv run jw eval --layer 1 --filter agent=translation_helper
```

## 3. Convenciones

- Nombre del entry point: snake_case, descriptivo, único en tu paquete.
- Si tu nombre choca con uno core, queda accesible como `<dist>:<name>`.
- No hagas side-effects en import time del módulo entry point.
- No hagas red durante `is_available()`.

## 4. Versión constraint

Declara `jw-agent-toolkit>=X,<Y` para asegurar compatibilidad. `verify_plugin`
y el SDK rechazan tu plugin si la versión instalada cae fuera del rango.
```

- [ ] **Step 5: Link the new docs from `docs/README.md`**

Append to the "Guías por tema" list:

```markdown
- [Plugin SDK — overview](plugin-sdk/overview.md) — 5 extension points para terceros.
- [Plugin SDK — seguridad](plugin-sdk/security.md) — modelo de confianza y mitigaciones.
- [Plugin SDK — capability matrix](plugin-sdk/capabilities.md) — required vs optional por grupo.
- [Plugin SDK — authoring](plugin-sdk/authoring.md) — guía para publicar un plugin.
```

- [ ] **Step 6: Commit**

```bash
git add docs/plugin-sdk docs/README.md
git commit -m "docs(plugin-sdk): overview/security/capabilities/authoring (Fase 41)"
```

---

### Task 16: Final audit — full suite green + no regressions

**Files:** none (verification only).

- [ ] **Step 1: Run lint + format**

Run:
```bash
uv run ruff check packages/jw-core packages/jw-eval packages/jw-rag packages/jw-mcp packages/jw-cli
uv run ruff format --check packages/jw-core packages/jw-eval packages/jw-rag packages/jw-mcp packages/jw-cli
```
Expected: zero violations.

- [ ] **Step 2: Run mypy (best-effort)**

Run: `uv run mypy packages/jw-core/src/jw_core/plugins`
Expected: errors only on `# type: ignore` lines.

- [ ] **Step 3: Run the entire test suite**

Run: `uv run pytest packages/ -v --tb=short`
Expected: all previous tests + ~47 new plugin-SDK tests + ~6 e2e tests + per-package integration tests = green. No regressions.

- [ ] **Step 4: End-to-end CLI smoke (with fixture installed)**

Run:
```bash
uv pip install -e packages/jw-core/tests/fixtures/plugin_sample
uv run jw plugins list
uv run jw plugins verify plugin_sample_agent
uv run jw plugins verify plugin_sample_embedder --group jw_agent_toolkit.embedders
JW_PLUGINS_DISABLED=1 uv run jw plugins list --json | python -c "import json,sys; d=json.load(sys.stdin); assert all(v==[] for v in d.values()); print('disabled OK')"
```
Expected: list shows `plugin_sample_*` in each group; verify is OK on both; disabled returns empty groups.

- [ ] **Step 5: Append Fase 41 to VISION_AUDIT and ROADMAP**

Edit `docs/VISION_AUDIT.md`. Append row to the summary table:

```markdown
| Fase 41 (plugin SDK) | ✅ Nuevo | `jw_core.plugins` — 5 groups + verify + CLI |
```

Edit `docs/ROADMAP.md`. Append section:

```markdown
## Fase 41 — Plugin SDK ✅

> Tier 2 comunidad. Spec: `docs/superpowers/specs/2026-05-31-fase-41-plugin-sdk-design.md`.

- ✅ Subpaquete nuevo `packages/jw-core/src/jw_core/plugins/`.
- ✅ 5 Protocols + EntryPointSpec + VerifyReport.
- ✅ Discovery via `importlib.metadata.entry_points`, cached con `lru_cache`.
- ✅ Conflict policy: `namespaced` (default), `first_wins`, `last_wins`, `reject`.
- ✅ Env opt-out: `JW_PLUGINS_DISABLED`, `JW_PLUGINS_ALLOW_LIST`, `JW_PLUGINS_DENY_LIST`.
- ✅ Fail-soft default; `JW_PLUGINS_STRICT=1` para fail-hard.
- ✅ Fixture `plugin_sample/` con entry points en los 5 groups.
- ✅ Integración: `jw-eval`, `jw-rag`, `jw-mcp`, `jw-cli`.
- ✅ CLI `jw plugins {list,verify,disable}`.
- ✅ CI job `plugin-sdk` offline.
- ✅ Docs `docs/plugin-sdk/{overview,security,capabilities,authoring}.md`.

### Cobertura de tests

- ✅ ~47 tests nuevos del módulo `jw_core.plugins`.
- ✅ ~6 tests e2e subprocess + fixture install.
- ✅ Integración: `jw-eval`, `jw-rag`, `jw-mcp`, `jw-cli`.
- ✅ Sin regresiones en la suite global.
```

- [ ] **Step 6: Final commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 41 — plugin SDK"
```

---

## Self-review summary

- **Spec coverage**: every spec section maps to a task above:
  - Architecture / module layout → Task 1
  - Errors → Task 1
  - Protocols + EntryPointSpec → Task 2
  - Conflict policy + env helpers → Task 3
  - Discovery (`registry.py`) → Task 4
  - Verify + VerifyReport + version constraint → Task 5
  - Cached factory → Task 6
  - Fixture package → Task 7
  - E2E subprocess install → Task 8
  - `jw_core` re-export → Task 9
  - jw-eval integration → Task 10
  - jw-rag integration → Task 11
  - jw-mcp integration → Task 12
  - CLI integration → Task 13
  - CI offline job → Task 14
  - Docs en español (overview/security/capabilities/authoring) → Task 15
  - VISION_AUDIT + ROADMAP rows → Task 16
- **No placeholders**: every Python and YAML block is fully written, every CLI command has its exact invocation and expected output.
- **Type consistency**: `EntryPointSpec` is the single source-of-truth dataclass returned by `get_plugins` and consumed by `verify_plugin`, jw-eval, jw-rag, jw-mcp, jw-cli. `VerifyReport` is frozen dataclass with explicit `ok: bool` field used identically by CLI and tests. All Protocols are `runtime_checkable` and mirror existing toolkit contracts (`EmbedProvider`, `VLMProvider`, `GenerationProvider`).
- **Test-first discipline**: every task starts with a failing test before implementation. Task 4 introduces the autouse `clear_plugin_cache` fixture so `lru_cache` cannot leak across tests.
- **Determinism**: the fixture package is installed editable from a local path (no network). The e2e test creates an ephemeral venv per test module so the host venv stays untouched. CI mirrors the same pattern.
- **No-objective enforcement**: no sandboxing, no marketplace, no hot-reload, no JS plugins — every "non-goal" from the spec stays absent and is called out explicitly in `security.md` (Task 15).

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`).
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
