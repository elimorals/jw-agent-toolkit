# Fase 33 — embed-rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox `- [ ]` syntax.

**Goal:** Replace the placeholder `FakeEmbedder` with a real, multilingual SOTA embed-and-rerank stack — provider-protocol based, opt-in extras for API/local backends, zero breakage of the 1649 existing tests — and wire a cross-encoder reranker into `VectorStore.hybrid_search` with backwards-compatible defaults.

**Architecture:** Add `embed_providers/` and `rerank_providers/` subpackages under `packages/jw-rag/src/jw_rag/`. Each subpackage exposes a `Protocol` (`EmbedProvider`, `Reranker`), a `factory.py` that auto-detects (`api > mlx > nvidia > cpu`) with env override, real provider classes (lazy SDK imports), and deterministic Fake siblings used by tests. `hybrid_search` gains `rerank=True` / `reranker=None` / `candidate_pool=50` knobs with NoOp fallback when nothing is available.

**Tech Stack:** Python 3.13 · numpy · httpx (Jina/Ollama/Jina-rerank) · sentence-transformers (BGE-M3, E5, BGE-reranker-v2-m3) · cohere SDK · voyageai SDK · MLX (Apple Silicon detection) · torch.cuda (NVIDIA detection) — all behind lazy imports + pyproject extras `[embeddings-local]`, `[embeddings-api]`, `[rerank-local]`, `[rerank-api]`.

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-33-embed-rerank-design.md`](../specs/2026-05-31-fase-33-embed-rerank-design.md).

---

## File map

Creates:
- `packages/jw-rag/src/jw_rag/embed_providers/__init__.py`
- `packages/jw-rag/src/jw_rag/embed_providers/factory.py`
- `packages/jw-rag/src/jw_rag/embed_providers/fakes.py`
- `packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py`
- `packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py`
- `packages/jw-rag/src/jw_rag/embed_providers/jina.py`
- `packages/jw-rag/src/jw_rag/embed_providers/cohere.py`
- `packages/jw-rag/src/jw_rag/embed_providers/voyage.py`
- `packages/jw-rag/src/jw_rag/embed_providers/ollama.py`
- `packages/jw-rag/src/jw_rag/rerank.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/__init__.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/factory.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/fakes.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/cohere_rerank.py`
- `packages/jw-rag/src/jw_rag/rerank_providers/jina_rerank.py`
- `packages/jw-rag/tests/test_embed_providers_protocol.py`
- `packages/jw-rag/tests/test_embed_providers_fakes.py`
- `packages/jw-rag/tests/test_embed_providers_factory.py`
- `packages/jw-rag/tests/test_embed_providers_bge_m3.py`
- `packages/jw-rag/tests/test_embed_providers_jina.py`
- `packages/jw-rag/tests/test_embed_providers_cohere.py`
- `packages/jw-rag/tests/test_embed_providers_voyage.py`
- `packages/jw-rag/tests/test_embed_providers_ollama.py`
- `packages/jw-rag/tests/test_embed_providers_multilingual_e5.py`
- `packages/jw-rag/tests/test_rerank_protocol.py`
- `packages/jw-rag/tests/test_rerank_fakes.py`
- `packages/jw-rag/tests/test_rerank_bge_v2_m3.py`
- `packages/jw-rag/tests/test_rerank_cohere.py`
- `packages/jw-rag/tests/test_rerank_jina.py`
- `packages/jw-rag/tests/test_store_rerank_integration.py`
- `docs/guias/embeddings-y-rerank.md`

Modifies:
- `packages/jw-rag/pyproject.toml` — add `[embeddings-local]`, `[embeddings-api]`, `[rerank-local]`, `[rerank-api]`, and `httpx>=0.27` to base deps.
- `packages/jw-rag/src/jw_rag/store.py` — `hybrid_search(rerank=True, reranker=None, candidate_pool=50)`.
- `packages/jw-rag/src/jw_rag/__init__.py` — re-export `EmbedProvider`, `Reranker`, factories.
- `packages/jw-cli/src/jw_cli/commands/rag.py` — flags `--no-rerank`, `--provider`.
- `packages/jw-mcp/src/jw_mcp/server.py` — `semantic_search(rerank: bool = True)`.
- `docs/VISION_AUDIT.md` — Fase 33 row.
- `docs/ROADMAP.md` — Fase 33 section.
- `docs/README.md` — link new guide.
- `.github/workflows/ci.yml` — optional `test-rag-embeddings` job (non-blocking).

---

### Task 1: pyproject extras + scaffold subpackages

**Files:**
- Modify: `packages/jw-rag/pyproject.toml`
- Create: `packages/jw-rag/src/jw_rag/embed_providers/__init__.py`
- Create: `packages/jw-rag/src/jw_rag/rerank_providers/__init__.py`

- [ ] **Step 1: Add extras to `packages/jw-rag/pyproject.toml`**

Replace the `[project.optional-dependencies]` block with the new one. Also add `httpx` to base deps (needed by Jina + Ollama + Jina-rerank):

```toml
[project]
name = "jw-rag"
version = "0.1.0"
description = "Vector indexing and retrieval over jw.org corpus"
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = [
    "jw-core",
    "numpy>=2.0.0",
    "rank-bm25>=0.2.2",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
# Legacy aliases kept for backwards compat with Fase 6 docs:
openai = ["openai>=1.50.0"]
local = ["sentence-transformers>=3.0.0"]

# Fase 33: real embed + rerank stack.
embeddings-local = [
    "sentence-transformers>=3.0.0",
]
embeddings-api = [
    "cohere>=5.5.0",
    "voyageai>=0.2.3",
]
rerank-local = [
    "sentence-transformers>=3.0.0",
]
rerank-api = [
    "cohere>=5.5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_rag"]
```

- [ ] **Step 2: Create empty subpackage inits**

```python
# packages/jw-rag/src/jw_rag/embed_providers/__init__.py
"""Embed providers for jw-rag.

Public surface:
    from jw_rag.embed_providers import (
        EmbedProvider, Target,
        get_default_embedder, list_available_embedders,
    )

Providers are imported lazily — touching this module does NOT import any
heavy SDK (sentence-transformers, cohere, voyageai). The factory probes
availability with `importlib.util.find_spec` + env-var presence.
"""

from __future__ import annotations

from jw_rag.embed_providers.factory import (
    EmbedProvider,
    Target,
    get_default_embedder,
    list_available_embedders,
)

__all__ = [
    "EmbedProvider",
    "Target",
    "get_default_embedder",
    "list_available_embedders",
]
```

```python
# packages/jw-rag/src/jw_rag/rerank_providers/__init__.py
"""Rerank providers for jw-rag.

Public surface:
    from jw_rag.rerank_providers import (
        Reranker, Target,
        get_default_reranker, list_available_rerankers,
    )
"""

from __future__ import annotations

from jw_rag.rerank_providers.factory import (
    Reranker,
    Target,
    get_default_reranker,
    list_available_rerankers,
)

__all__ = [
    "Reranker",
    "Target",
    "get_default_reranker",
    "list_available_rerankers",
]
```

- [ ] **Step 3: Verify install**

Run:
```bash
uv sync --all-packages
uv pip list | grep -E "(jw-rag|httpx)"
```
Expected: `jw-rag 0.1.0` and `httpx >= 0.27.0` listed; no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-rag/pyproject.toml packages/jw-rag/src/jw_rag/embed_providers packages/jw-rag/src/jw_rag/rerank_providers
git commit -m "feat(jw-rag): scaffold embed_providers/ + rerank_providers/ and add extras"
```

---

### Task 2: `EmbedProvider` Protocol + `Target` Literal

**Files:**
- Create: `packages/jw-rag/src/jw_rag/embed_providers/factory.py` (partial — Protocol + Target only)
- Create: `packages/jw-rag/tests/test_embed_providers_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_protocol.py
"""Tests for EmbedProvider Protocol + Target literal."""

from __future__ import annotations

import typing

import numpy as np
import pytest

from jw_rag.embed_providers import EmbedProvider, Target


def test_target_literal_values() -> None:
    values = typing.get_args(Target)
    assert set(values) == {"api", "mlx", "nvidia", "cpu"}


def test_embed_provider_is_runtime_checkable() -> None:
    class Dummy:
        name = "dummy"
        target: Target = "cpu"
        dim = 8

        def is_available(self) -> bool:
            return True

        def embed(self, texts: list[str]) -> np.ndarray:
            return np.zeros((len(texts), self.dim), dtype=np.float32)

    assert isinstance(Dummy(), EmbedProvider)


def test_embed_provider_rejects_non_conforming() -> None:
    class Missing:
        name = "missing"
        target: Target = "cpu"
        dim = 8

        # no embed() and no is_available()

    assert not isinstance(Missing(), EmbedProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_protocol.py -v`
Expected: FAIL — `cannot import name 'EmbedProvider'`.

- [ ] **Step 3: Implement the Protocol + Target**

```python
# packages/jw-rag/src/jw_rag/embed_providers/factory.py
"""Embed provider Protocol, Target literal, and default-resolution factory.

Resolution order: env JW_EMBED_PROVIDER overrides everything; otherwise we
scan PROVIDER_ORDER (api, mlx, nvidia, cpu) and pick the first provider
that reports `is_available()` True. Fallback: FakeEmbedder with a warning.
"""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class EmbedProvider(Protocol):
    """Canonical embed provider contract.

    Implementations MUST:
      - expose `.name`, `.target`, `.dim` as instance/class attributes
      - return L2-normalized float32 vectors from `.embed()`
      - never touch the network or load heavy SDKs at __init__ time
      - return True from `.is_available()` only when calling `.embed()` would
        succeed in the current environment
    """

    name: str
    target: Target
    dim: int

    def is_available(self) -> bool: ...

    def embed(self, texts: list[str]) -> np.ndarray: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_protocol.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/factory.py packages/jw-rag/tests/test_embed_providers_protocol.py
git commit -m "feat(jw-rag): EmbedProvider Protocol + Target literal"
```

---

### Task 3: Fake embed providers (siblings of real ones)

**Files:**
- Create: `packages/jw-rag/src/jw_rag/embed_providers/fakes.py`
- Create: `packages/jw-rag/tests/test_embed_providers_fakes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_fakes.py
"""Tests for deterministic Fake embed providers."""

from __future__ import annotations

import numpy as np
import pytest

from jw_rag.embed_providers import EmbedProvider
from jw_rag.embed_providers.fakes import (
    FakeBGEM3,
    FakeCohereEmbed,
    FakeJinaEmbed,
    FakeMultilingualE5,
    FakeOllamaEmbed,
    FakeVoyageEmbed,
)


@pytest.mark.parametrize(
    "cls,expected_dim,expected_name,expected_target",
    [
        (FakeBGEM3, 1024, "bge-m3", "cpu"),
        (FakeMultilingualE5, 1024, "multilingual-e5", "cpu"),
        (FakeJinaEmbed, 1024, "jina", "api"),
        (FakeCohereEmbed, 1024, "cohere", "api"),
        (FakeVoyageEmbed, 1024, "voyage", "api"),
        (FakeOllamaEmbed, 768, "ollama", "cpu"),
    ],
)
def test_fakes_satisfy_protocol(
    cls: type, expected_dim: int, expected_name: str, expected_target: str
) -> None:
    p = cls()
    assert isinstance(p, EmbedProvider)
    assert p.name == expected_name
    assert p.target == expected_target
    assert p.dim == expected_dim
    assert p.is_available() is True


@pytest.mark.parametrize(
    "cls", [FakeBGEM3, FakeMultilingualE5, FakeJinaEmbed, FakeCohereEmbed, FakeVoyageEmbed, FakeOllamaEmbed]
)
def test_fake_embed_shape_and_normalization(cls: type) -> None:
    p = cls()
    out = p.embed(["hello", "world", "tres"])
    assert out.shape == (3, p.dim)
    assert out.dtype == np.float32
    # L2-normalized
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_fake_embed_is_deterministic() -> None:
    p1 = FakeBGEM3()
    p2 = FakeBGEM3()
    a = p1.embed(["doctrine", "trinidad"])
    b = p2.embed(["doctrine", "trinidad"])
    np.testing.assert_array_equal(a, b)


def test_fake_embed_empty_input() -> None:
    p = FakeJinaEmbed()
    out = p.embed([])
    assert out.shape == (0, p.dim)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_fakes.py -v`
Expected: FAIL — `cannot import name 'FakeBGEM3'`.

- [ ] **Step 3: Implement the Fakes**

```python
# packages/jw-rag/src/jw_rag/embed_providers/fakes.py
"""Deterministic Fake embed providers — one per real provider.

These are used by tests to exercise the Protocol + factory wiring without
loading any real model or touching the network. They piggy-back on the
existing FakeEmbedder hash trick but expose the same name/dim/target shape
as their real siblings, so factory code can be tested against them.
"""

from __future__ import annotations

import hashlib

import numpy as np

from jw_rag.embed_providers.factory import Target


def _hash_embed(texts: list[str], dim: int, salt: str) -> np.ndarray:
    """Deterministic L2-normalized embeddings using SHA-256 seed bytes."""
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)
    out = np.empty((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        seeds: list[int] = []
        for offset in range((dim * 4 + 31) // 32):
            digest = hashlib.sha256(f"{salt}|{offset}|{text}".encode()).digest()
            for j in range(0, 32, 4):
                seeds.append(int.from_bytes(digest[j : j + 4], "big"))
        arr = np.array(seeds[:dim], dtype=np.float64)
        arr = (arr / (2**32 - 1)) * 2.0 - 1.0
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        out[i] = arr.astype(np.float32)
    return out


class _BaseFake:
    name: str
    target: Target
    dim: int

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> np.ndarray:
        return _hash_embed(texts, self.dim, salt=self.name)


class FakeBGEM3(_BaseFake):
    name = "bge-m3"
    target: Target = "cpu"
    dim = 1024


class FakeMultilingualE5(_BaseFake):
    name = "multilingual-e5"
    target: Target = "cpu"
    dim = 1024


class FakeJinaEmbed(_BaseFake):
    name = "jina"
    target: Target = "api"
    dim = 1024


class FakeCohereEmbed(_BaseFake):
    name = "cohere"
    target: Target = "api"
    dim = 1024


class FakeVoyageEmbed(_BaseFake):
    name = "voyage"
    target: Target = "api"
    dim = 1024


class FakeOllamaEmbed(_BaseFake):
    name = "ollama"
    target: Target = "cpu"
    dim = 768
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_fakes.py -v`
Expected: 11 passed (parametrized).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/fakes.py packages/jw-rag/tests/test_embed_providers_fakes.py
git commit -m "feat(jw-rag): Fake embed providers (bge-m3/e5/jina/cohere/voyage/ollama)"
```

---

### Task 4: `get_default_embedder()` factory with env override + auto-detect

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/factory.py` (append factory)
- Create: `packages/jw-rag/tests/test_embed_providers_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_factory.py
"""Tests for embed provider factory: env override + auto-detect + fallback."""

from __future__ import annotations

import pytest

from jw_rag.embed import FakeEmbedder
from jw_rag.embed_providers import EmbedProvider, get_default_embedder, list_available_embedders


def test_env_override_picks_named_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_EMBED_PROVIDER", "fake-bge-m3")
    p = get_default_embedder()
    assert p.name == "bge-m3"
    assert p.dim == 1024


def test_env_override_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_EMBED_PROVIDER", "nope-xyz")
    with pytest.raises(ValueError, match="unknown"):
        get_default_embedder()


def test_default_falls_back_to_fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strip every relevant env var + force the registry to "no real provider available"
    for var in ("JW_EMBED_PROVIDER", "COHERE_API_KEY", "JINA_API_KEY", "VOYAGE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")  # api only; no keys → none available
    p = get_default_embedder()
    assert isinstance(p, FakeEmbedder)


def test_list_available_returns_only_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "VOYAGE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JINA_API_KEY", "test-key")
    names = [p.name for p in list_available_embedders()]
    assert "jina" in names
    assert "cohere" not in names


def test_provider_order_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_PROVIDER_ORDER", "cpu,api")
    monkeypatch.delenv("JW_EMBED_PROVIDER", raising=False)
    # With cpu first and no SDKs installed, we still expect fake fallback
    # but list_available_embedders should put cpu providers before api.
    targets = [p.target for p in list_available_embedders()]
    if "cpu" in targets and "api" in targets:
        assert targets.index("cpu") < targets.index("api")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_factory.py -v`
Expected: FAIL — `cannot import 'get_default_embedder'`.

- [ ] **Step 3: Implement the factory**

Append to `packages/jw-rag/src/jw_rag/embed_providers/factory.py`:

```python
# Append below the EmbedProvider class:

PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]

ENV_EMBED = "JW_EMBED_PROVIDER"
ENV_PROVIDER_ORDER = "JW_PROVIDER_ORDER"


def _provider_order() -> list[Target]:
    raw = os.getenv(ENV_PROVIDER_ORDER, "")
    if not raw.strip():
        return PROVIDER_ORDER_DEFAULT
    parts: list[Target] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece in {"api", "mlx", "nvidia", "cpu"}:
            parts.append(piece)  # type: ignore[arg-type]
    return parts or PROVIDER_ORDER_DEFAULT


def _instantiate_registry() -> list[EmbedProvider]:
    """Build the full provider registry (real + fakes), without calling is_available()."""
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

    return [
        # Real providers
        CohereEmbedV3Provider(),
        JinaEmbeddingsV3Provider(),
        VoyageMultilingualProvider(),
        BGEM3Provider(),
        MultilingualE5Provider(),
        OllamaEmbedProvider(),
        # Fakes — always considered available, used by tests via JW_EMBED_PROVIDER=fake-*
        FakeBGEM3(),
        FakeMultilingualE5(),
        FakeJinaEmbed(),
        FakeCohereEmbed(),
        FakeVoyageEmbed(),
        FakeOllamaEmbed(),
    ]


def _named_lookup(name: str) -> EmbedProvider | None:
    """Resolve JW_EMBED_PROVIDER name. Accepts both 'jina' and 'fake-jina'."""
    is_fake = name.startswith("fake-")
    bare = name.removeprefix("fake-")
    for p in _instantiate_registry():
        if p.name != bare:
            continue
        # Fake-prefixed name must hit a Fake instance
        if is_fake and type(p).__module__.endswith(".fakes"):
            return p
        if not is_fake and not type(p).__module__.endswith(".fakes"):
            return p
    return None


def list_available_embedders() -> list[EmbedProvider]:
    """Return registry filtered by `is_available()` and sorted per PROVIDER_ORDER."""
    order = _provider_order()
    registry = [p for p in _instantiate_registry() if p.is_available()]
    return sorted(registry, key=lambda p: order.index(p.target) if p.target in order else len(order))


def get_default_embedder() -> EmbedProvider:
    """Resolve default embed provider.

    Order:
      1. JW_EMBED_PROVIDER env (exact name match, raises if unknown)
      2. First provider in PROVIDER_ORDER whose is_available() == True
      3. FakeEmbedder (legacy fallback, with WARNING log)
    """
    env_name = os.getenv(ENV_EMBED, "").strip()
    if env_name:
        provider = _named_lookup(env_name)
        if provider is None:
            raise ValueError(f"unknown JW_EMBED_PROVIDER={env_name!r}")
        return provider

    available = list_available_embedders()
    if available:
        return available[0]

    from jw_rag.embed import FakeEmbedder

    logger.warning(
        "No real embed provider available — falling back to FakeEmbedder (semantically empty). "
        "Install an extra (e.g. `pip install jw-rag[embeddings-local]`) or set an API key."
    )
    return FakeEmbedder()
```

- [ ] **Step 4: Stub the real providers so the factory imports**

The factory imports six real provider classes that don't exist yet — Tasks 5-10 implement them. To keep this task green, create one-line stub files now; they get fleshed out later. Each stub satisfies the Protocol but returns `is_available() = False`.

Create the following six stub files (each with this same shape, swapping name/target/dim):

```python
# packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py
"""Stub for BGE-M3 — implemented in Task 5."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class BGEM3Provider:
    name = "bge-m3"
    target: Target = "cpu"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("BGEM3Provider not implemented yet (Task 5)")
```

```python
# packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py
"""Stub for multilingual E5 — implemented in Task 6."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class MultilingualE5Provider:
    name = "multilingual-e5"
    target: Target = "cpu"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("MultilingualE5Provider not implemented yet (Task 6)")
```

```python
# packages/jw-rag/src/jw_rag/embed_providers/jina.py
"""Stub for Jina embeddings — implemented in Task 7."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class JinaEmbeddingsV3Provider:
    name = "jina"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("JinaEmbeddingsV3Provider not implemented yet (Task 7)")
```

```python
# packages/jw-rag/src/jw_rag/embed_providers/cohere.py
"""Stub for Cohere embeddings — implemented in Task 8."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class CohereEmbedV3Provider:
    name = "cohere"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("CohereEmbedV3Provider not implemented yet (Task 8)")
```

```python
# packages/jw-rag/src/jw_rag/embed_providers/voyage.py
"""Stub for Voyage embeddings — implemented in Task 9."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class VoyageMultilingualProvider:
    name = "voyage"
    target: Target = "api"
    dim = 1024

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("VoyageMultilingualProvider not implemented yet (Task 9)")
```

```python
# packages/jw-rag/src/jw_rag/embed_providers/ollama.py
"""Stub for Ollama embeddings — implemented in Task 10."""

from __future__ import annotations

import numpy as np

from jw_rag.embed_providers.factory import Target


class OllamaEmbedProvider:
    name = "ollama"
    target: Target = "cpu"
    dim = 768

    def is_available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError("OllamaEmbedProvider not implemented yet (Task 10)")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_factory.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers packages/jw-rag/tests/test_embed_providers_factory.py
git commit -m "feat(jw-rag): get_default_embedder factory + env override + stubs"
```

---

### Task 5: Real `BGEM3Provider` (sentence-transformers, MLX/CUDA/CPU detection)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py`
- Create: `packages/jw-rag/tests/test_embed_providers_bge_m3.py`

- [ ] **Step 1: Write the failing test (no real model — only the available-detection path)**

```python
# packages/jw-rag/tests/test_embed_providers_bge_m3.py
"""Tests for BGEM3Provider — gated by sentence-transformers availability."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from jw_rag.embed_providers.bge_m3 import BGEM3Provider, _detect_target


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert BGEM3Provider().is_available() is False


def test_detect_target_prefers_mlx_on_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.processor", lambda: "arm")
    monkeypatch.setattr("importlib.util.find_spec", lambda name: object() if name == "mlx" else None)
    assert _detect_target() == "mlx"


def test_detect_target_falls_back_to_cpu_on_x86_no_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.processor", lambda: "x86_64")
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    assert _detect_target() == "cpu"


@pytest.mark.embeddings_local
def test_real_embed_returns_normalized_1024_vectors() -> None:
    p = BGEM3Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed; run with [embeddings-local] extra")
    out = p.embed(["hello world", "hola mundo"])
    assert out.shape == (2, 1024)
    assert out.dtype == np.float32
    norms = np.linalg.norm(out, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_bge_m3.py -v -m "not embeddings_local"`
Expected: FAIL — `_detect_target` not importable.

- [ ] **Step 3: Implement the real provider**

Replace the stub at `packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py`:

```python
# packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py
"""BGE-M3 dense embed provider.

Lazy-loads `sentence-transformers`. Auto-detects target:
  - mlx if Apple Silicon + mlx installed (runs ST with device='mps')
  - nvidia if torch.cuda.is_available()
  - cpu otherwise
"""

from __future__ import annotations

import importlib.util
import logging
import platform
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-m3"


def _detect_target() -> Target:
    if platform.processor() == "arm" and importlib.util.find_spec("mlx") is not None:
        return "mlx"
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is not None:
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                return "nvidia"
        except Exception:  # noqa: BLE001
            pass
    return "cpu"


class BGEM3Provider:
    name = "bge-m3"
    dim = 1024

    def __init__(self) -> None:
        self.target: Target = _detect_target()
        self._model: Any = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            device = "mps" if self.target == "mlx" else ("cuda" if self.target == "nvidia" else "cpu")
            self._model = SentenceTransformer(_MODEL_NAME, device=device)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        model = self._ensure_model()
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return l2_normalize(vecs.astype(np.float32))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_bge_m3.py -v -m "not embeddings_local"`
Expected: 3 passed (the `@pytest.mark.embeddings_local` test is filtered out).

- [ ] **Step 5: Register the marker so `-m` works without warnings**

Append to `packages/jw-rag/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "embeddings_local: tests that require sentence-transformers + a local model download",
    "rerank_local: tests that require a local cross-encoder model download",
]
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/bge_m3.py packages/jw-rag/tests/test_embed_providers_bge_m3.py packages/jw-rag/pyproject.toml
git commit -m "feat(jw-rag): BGEM3Provider (sentence-transformers, MLX/CUDA/CPU detect)"
```

---

### Task 6: Real `MultilingualE5Provider`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py`
- Create: `packages/jw-rag/tests/test_embed_providers_multilingual_e5.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_multilingual_e5.py
from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from jw_rag.embed_providers.multilingual_e5 import MultilingualE5Provider


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert MultilingualE5Provider().is_available() is False


def test_name_and_dim() -> None:
    p = MultilingualE5Provider()
    assert p.name == "multilingual-e5"
    assert p.dim == 1024


@pytest.mark.embeddings_local
def test_real_embed_uses_query_passage_prefix() -> None:
    p = MultilingualE5Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed")
    # E5 expects "query: ..." or "passage: ..." prefixes. Provider must add them transparently.
    out = p.embed(["hello world"])
    assert out.shape == (1, 1024)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_multilingual_e5.py -v -m "not embeddings_local"`
Expected: FAIL — stub returns `is_available()=False` correctly but the test asserts the call structure; the new monkeypatch test confirms behavior. Actually it passes already on the stub for the first test — that's fine, we still need to upgrade it.

- [ ] **Step 3: Implement the real provider**

Replace `packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py`:

```python
# packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py
"""intfloat/multilingual-e5-large dense embed provider.

E5 requires a 'query: ' or 'passage: ' prefix per text. Since the provider
contract is text-in-text-out and the caller doesn't know whether a string
is a query or a passage, we default to 'passage:' (corpus side), and the
calling layer can re-embed queries explicitly when needed.

For jw-rag's VectorStore use case, both indexing and querying paths route
through the same Embedder, so this is consistent across both sides.
"""

from __future__ import annotations

import importlib.util
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.bge_m3 import _detect_target
from jw_rag.embed_providers.factory import Target

_MODEL_NAME = "intfloat/multilingual-e5-large"


class MultilingualE5Provider:
    name = "multilingual-e5"
    dim = 1024

    def __init__(self) -> None:
        self.target: Target = _detect_target()
        self._model: Any = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            device = "mps" if self.target == "mlx" else ("cuda" if self.target == "nvidia" else "cpu")
            self._model = SentenceTransformer(_MODEL_NAME, device=device)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        prefixed = [f"passage: {t}" for t in texts]
        model = self._ensure_model()
        vecs = model.encode(prefixed, normalize_embeddings=True, convert_to_numpy=True)
        return l2_normalize(vecs.astype(np.float32))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_multilingual_e5.py -v -m "not embeddings_local"`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/multilingual_e5.py packages/jw-rag/tests/test_embed_providers_multilingual_e5.py
git commit -m "feat(jw-rag): MultilingualE5Provider (passage prefix, MLX/CUDA/CPU detect)"
```

---

### Task 7: Real `JinaEmbeddingsV3Provider` (httpx, API key)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/jina.py`
- Create: `packages/jw-rag/tests/test_embed_providers_jina.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_jina.py
"""Tests for Jina v3 embed provider — uses respx to stub HTTPX."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from jw_rag.embed_providers.jina import JinaEmbeddingsV3Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert JinaEmbeddingsV3Provider().is_available() is False


def test_is_available_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")
    assert JinaEmbeddingsV3Provider().is_available() is True


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "abcdefgh1234")
    p = JinaEmbeddingsV3Provider()
    rep = repr(p)
    assert "abcdefgh1234" not in rep
    assert "***" in rep


def test_embed_returns_normalized_vectors_with_stub_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        # Return two unnormalized vectors; provider must normalize.
        data = {
            "data": [
                {"embedding": [3.0, 4.0] + [0.0] * 1022},
                {"embedding": [0.0, 0.0, 5.0] + [0.0] * 1021},
            ]
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    p = JinaEmbeddingsV3Provider(transport=transport)
    out = p.embed(["hola", "mundo"])

    assert out.shape == (2, 1024)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
    assert "api.jina.ai" in captured["url"]
    assert captured["json"]["input"] == ["hola", "mundo"]


def test_embed_empty_input_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake-key")
    out = JinaEmbeddingsV3Provider().embed([])
    assert out.shape == (0, 1024)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_jina.py -v`
Expected: FAIL — stub doesn't accept `transport=` and doesn't read env.

- [ ] **Step 3: Implement the real provider**

```python
# packages/jw-rag/src/jw_rag/embed_providers/jina.py
"""Jina v3 embed provider (HTTPS, no SDK)."""

from __future__ import annotations

import os

import httpx
import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_API_URL = "https://api.jina.ai/v1/embeddings"
_MODEL = "jina-embeddings-v3"


class JinaEmbeddingsV3Provider:
    name = "jina"
    target: Target = "api"
    dim = 1024

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def is_available(self) -> bool:
        return bool(os.getenv("JINA_API_KEY"))

    def __repr__(self) -> str:
        key = os.getenv("JINA_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"JinaEmbeddingsV3Provider(key={masked})"

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        key = os.getenv("JINA_API_KEY")
        if not key:
            raise RuntimeError("JINA_API_KEY not set")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": _MODEL, "input": texts}
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            r = client.post(_API_URL, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        rows = [np.array(item["embedding"], dtype=np.float32) for item in data["data"]]
        matrix = np.stack(rows, axis=0)
        return l2_normalize(matrix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_jina.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/jina.py packages/jw-rag/tests/test_embed_providers_jina.py
git commit -m "feat(jw-rag): JinaEmbeddingsV3Provider (httpx, safe_repr, normalize)"
```

---

### Task 8: Real `CohereEmbedV3Provider` (lazy SDK)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/cohere.py`
- Create: `packages/jw-rag/tests/test_embed_providers_cohere.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_cohere.py
from __future__ import annotations

import importlib.util
import sys
import types

import numpy as np
import pytest

from jw_rag.embed_providers.cohere import CohereEmbedV3Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    assert CohereEmbedV3Provider().is_available() is False


def test_is_available_false_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "x")
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "cohere" else importlib.util.find_spec(name),
    )
    assert CohereEmbedV3Provider().is_available() is False


def test_embed_uses_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "fake")
    calls: dict = {}

    class StubResponse:
        embeddings = [[3.0, 4.0] + [0.0] * 1022, [0.0, 0.0, 5.0] + [0.0] * 1021]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            calls["init_key"] = api_key

        def embed(self, *, texts: list[str], model: str, input_type: str) -> StubResponse:
            calls["texts"] = texts
            calls["model"] = model
            calls["input_type"] = input_type
            return StubResponse()

    fake_module = types.ModuleType("cohere")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cohere", fake_module)

    p = CohereEmbedV3Provider()
    out = p.embed(["hola", "mundo"])
    assert out.shape == (2, 1024)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
    assert calls["model"] == "embed-multilingual-v3.0"
    assert calls["input_type"] == "search_document"


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(CohereEmbedV3Provider())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_cohere.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the real provider**

```python
# packages/jw-rag/src/jw_rag/embed_providers/cohere.py
"""Cohere embed-multilingual-v3.0 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_MODEL = "embed-multilingual-v3.0"


class CohereEmbedV3Provider:
    name = "cohere"
    target: Target = "api"
    dim = 1024

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("COHERE_API_KEY"):
            return False
        return importlib.util.find_spec("cohere") is not None

    def __repr__(self) -> str:
        key = os.getenv("COHERE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"CohereEmbedV3Provider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import cohere  # type: ignore[import-not-found]

            self._client = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        client = self._ensure_client()
        resp = client.embed(texts=texts, model=_MODEL, input_type="search_document")
        matrix = np.array(resp.embeddings, dtype=np.float32)
        return l2_normalize(matrix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_cohere.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/cohere.py packages/jw-rag/tests/test_embed_providers_cohere.py
git commit -m "feat(jw-rag): CohereEmbedV3Provider (lazy cohere SDK)"
```

---

### Task 9: Real `VoyageMultilingualProvider`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/voyage.py`
- Create: `packages/jw-rag/tests/test_embed_providers_voyage.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_voyage.py
from __future__ import annotations

import importlib.util
import sys
import types

import numpy as np
import pytest

from jw_rag.embed_providers.voyage import VoyageMultilingualProvider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    assert VoyageMultilingualProvider().is_available() is False


def test_is_available_false_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "x")
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "voyageai" else importlib.util.find_spec(name),
    )
    assert VoyageMultilingualProvider().is_available() is False


def test_embed_uses_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "fake")

    class StubResp:
        embeddings = [[1.0, 0.0] + [0.0] * 1022, [0.0, 2.0] + [0.0] * 1022]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def embed(self, texts: list[str], model: str, input_type: str) -> StubResp:
            return StubResp()

    fake_module = types.ModuleType("voyageai")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "voyageai", fake_module)

    out = VoyageMultilingualProvider().embed(["a", "b"])
    assert out.shape == (2, 1024)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_voyage.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the real provider**

```python
# packages/jw-rag/src/jw_rag/embed_providers/voyage.py
"""Voyage AI voyage-multilingual-2 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_MODEL = "voyage-multilingual-2"


class VoyageMultilingualProvider:
    name = "voyage"
    target: Target = "api"
    dim = 1024

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("VOYAGE_API_KEY"):
            return False
        return importlib.util.find_spec("voyageai") is not None

    def __repr__(self) -> str:
        key = os.getenv("VOYAGE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"VoyageMultilingualProvider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import voyageai  # type: ignore[import-not-found]

            self._client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        client = self._ensure_client()
        resp = client.embed(texts, model=_MODEL, input_type="document")
        matrix = np.array(resp.embeddings, dtype=np.float32)
        return l2_normalize(matrix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_voyage.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/voyage.py packages/jw-rag/tests/test_embed_providers_voyage.py
git commit -m "feat(jw-rag): VoyageMultilingualProvider (lazy voyageai SDK)"
```

---

### Task 10: Real `OllamaEmbedProvider` (httpx → localhost:11434)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/embed_providers/ollama.py`
- Create: `packages/jw-rag/tests/test_embed_providers_ollama.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_embed_providers_ollama.py
from __future__ import annotations

import httpx
import numpy as np
import pytest

from jw_rag.embed_providers.ollama import OllamaEmbedProvider


def test_is_available_false_when_server_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    assert p.is_available() is False


def test_is_available_true_when_tags_returns_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    assert p.is_available() is True


def test_embed_returns_normalized_768_dim_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        assert request.url.path == "/api/embeddings"
        return httpx.Response(200, json={"embedding": [3.0, 4.0] + [0.0] * 766})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    out = p.embed(["hello"])
    assert out.shape == (1, 768)
    assert out.dtype == np.float32
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)


def test_embed_loops_per_text() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        import json as _json

        body = _json.loads(request.content)
        calls.append(body["prompt"])
        return httpx.Response(200, json={"embedding": [1.0] + [0.0] * 767})

    p = OllamaEmbedProvider(transport=httpx.MockTransport(handler))
    p.embed(["a", "b", "c"])
    assert calls == ["a", "b", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_ollama.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the real provider**

```python
# packages/jw-rag/src/jw_rag/embed_providers/ollama.py
"""Ollama local embed provider (httpx → http://localhost:11434).

Requires `ollama serve` running + `ollama pull nomic-embed-text`. Detected
by GET /api/tags returning 200 within 0.5s. Embeds via POST /api/embeddings
one text at a time (Ollama API doesn't batch).
"""

from __future__ import annotations

import os

import httpx
import numpy as np

from jw_rag.embed import l2_normalize
from jw_rag.embed_providers.factory import Target

_DEFAULT_BASE = "http://localhost:11434"
_DEFAULT_MODEL = "nomic-embed-text"


class OllamaEmbedProvider:
    name = "ollama"
    target: Target = "cpu"
    dim = 768

    def __init__(self, *, base_url: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE)
        self.model = os.getenv("OLLAMA_EMBED_MODEL", _DEFAULT_MODEL)
        self._transport = transport

    def is_available(self) -> bool:
        try:
            with httpx.Client(transport=self._transport, timeout=0.5) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        rows: list[np.ndarray] = []
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            for text in texts:
                r = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                r.raise_for_status()
                rows.append(np.array(r.json()["embedding"], dtype=np.float32))
        return l2_normalize(np.stack(rows, axis=0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_embed_providers_ollama.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/embed_providers/ollama.py packages/jw-rag/tests/test_embed_providers_ollama.py
git commit -m "feat(jw-rag): OllamaEmbedProvider (httpx, /api/tags probe, per-text /api/embeddings)"
```

---

### Task 11: `Reranker` Protocol + `NoOpReranker` + Fakes + factory

**Files:**
- Create: `packages/jw-rag/src/jw_rag/rerank.py`
- Create: `packages/jw-rag/src/jw_rag/rerank_providers/factory.py`
- Create: `packages/jw-rag/src/jw_rag/rerank_providers/fakes.py`
- Create: `packages/jw-rag/tests/test_rerank_protocol.py`
- Create: `packages/jw-rag/tests/test_rerank_fakes.py`

- [ ] **Step 1: Write the failing test (protocol + fakes + factory)**

```python
# packages/jw-rag/tests/test_rerank_protocol.py
from __future__ import annotations

import typing

import pytest

from jw_rag.rerank_providers import Reranker, Target, get_default_reranker, list_available_rerankers


def test_target_literal_values() -> None:
    assert set(typing.get_args(Target)) == {"api", "mlx", "nvidia", "cpu"}


def test_protocol_is_runtime_checkable() -> None:
    class Dummy:
        name = "dummy"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True

        def rerank(self, query: str, candidates: list[str]) -> list[float]:
            return [1.0] * len(candidates)

    assert isinstance(Dummy(), Reranker)


def test_default_fallbacks_to_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "JW_RERANK_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")
    r = get_default_reranker()
    assert r.name == "noop"
    # NoOp preserves order — every score == 1.0
    scores = r.rerank("q", ["a", "b", "c"])
    assert scores == [1.0, 1.0, 1.0]


def test_env_override_picks_named_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_RERANK_PROVIDER", "fake-bge-v2-m3")
    r = get_default_reranker()
    assert r.name == "bge-v2-m3"


def test_list_available_returns_only_ready() -> None:
    names = [r.name for r in list_available_rerankers()]
    # NoOp is always available
    assert "noop" in names
```

```python
# packages/jw-rag/tests/test_rerank_fakes.py
from __future__ import annotations

import pytest

from jw_rag.rerank_providers import Reranker
from jw_rag.rerank_providers.fakes import FakeBGEReranker, FakeCohereReranker, FakeJinaReranker


@pytest.mark.parametrize("cls,expected_name", [
    (FakeBGEReranker, "bge-v2-m3"),
    (FakeCohereReranker, "cohere-rerank"),
    (FakeJinaReranker, "jina-rerank"),
])
def test_fake_satisfies_protocol(cls: type, expected_name: str) -> None:
    r = cls()
    assert isinstance(r, Reranker)
    assert r.name == expected_name
    assert r.is_available() is True


def test_fake_rerank_returns_deterministic_scores_per_query() -> None:
    r = FakeBGEReranker()
    s1 = r.rerank("trinidad", ["candidate-a", "candidate-b"])
    s2 = r.rerank("trinidad", ["candidate-a", "candidate-b"])
    assert s1 == s2
    assert len(s1) == 2


def test_fake_rerank_empty_candidates() -> None:
    r = FakeJinaReranker()
    assert r.rerank("q", []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_protocol.py packages/jw-rag/tests/test_rerank_fakes.py -v`
Expected: FAIL — `cannot import name 'Reranker'`.

- [ ] **Step 3: Implement Protocol module**

```python
# packages/jw-rag/src/jw_rag/rerank.py
"""Public re-exports for the rerank stack.

Mirror of `jw_rag.embed` (which holds the `Embedder` Protocol + FakeEmbedder)
but for the rerank side. The full Protocol lives in `rerank_providers.factory`
so the factory can use it without circular imports.
"""

from __future__ import annotations

from jw_rag.rerank_providers import (
    Reranker,
    Target,
    get_default_reranker,
    list_available_rerankers,
)

__all__ = ["Reranker", "Target", "get_default_reranker", "list_available_rerankers"]
```

- [ ] **Step 4: Implement the rerank factory**

```python
# packages/jw-rag/src/jw_rag/rerank_providers/factory.py
"""Reranker Protocol + factory."""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

Target = Literal["api", "mlx", "nvidia", "cpu"]

PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]
ENV_RERANK = "JW_RERANK_PROVIDER"
ENV_PROVIDER_ORDER = "JW_PROVIDER_ORDER"


@runtime_checkable
class Reranker(Protocol):
    """Canonical reranker contract.

    `rerank(query, candidates)` returns one score per candidate where higher
    means more relevant. Scores are NOT required to be probabilities; consumers
    only use them for sorting.
    """

    name: str
    target: Target

    def is_available(self) -> bool: ...

    def rerank(self, query: str, candidates: list[str]) -> list[float]: ...


class NoOpReranker:
    """Passthrough reranker — every candidate gets the same score.

    Used as the always-available fallback so `hybrid_search(rerank=True)` is
    bit-identical to `rerank=False` when no real reranker is configured.
    """

    name = "noop"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [1.0] * len(candidates)


def _provider_order() -> list[Target]:
    raw = os.getenv(ENV_PROVIDER_ORDER, "")
    if not raw.strip():
        return PROVIDER_ORDER_DEFAULT
    parts: list[Target] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece in {"api", "mlx", "nvidia", "cpu"}:
            parts.append(piece)  # type: ignore[arg-type]
    return parts or PROVIDER_ORDER_DEFAULT


def _instantiate_registry() -> list[Reranker]:
    from jw_rag.rerank_providers.bge_v2_m3 import BGERerankerV2M3Provider
    from jw_rag.rerank_providers.cohere_rerank import CohereRerankV35Provider
    from jw_rag.rerank_providers.fakes import (
        FakeBGEReranker,
        FakeCohereReranker,
        FakeJinaReranker,
    )
    from jw_rag.rerank_providers.jina_rerank import JinaRerankerV2Provider

    return [
        CohereRerankV35Provider(),
        JinaRerankerV2Provider(),
        BGERerankerV2M3Provider(),
        FakeBGEReranker(),
        FakeCohereReranker(),
        FakeJinaReranker(),
        NoOpReranker(),
    ]


def _named_lookup(name: str) -> Reranker | None:
    is_fake = name.startswith("fake-")
    bare = name.removeprefix("fake-")
    for r in _instantiate_registry():
        if r.name != bare:
            continue
        if is_fake and type(r).__module__.endswith(".fakes"):
            return r
        if not is_fake and not type(r).__module__.endswith(".fakes"):
            return r
    return None


def list_available_rerankers() -> list[Reranker]:
    order = _provider_order()
    rs = [r for r in _instantiate_registry() if r.is_available()]
    return sorted(rs, key=lambda r: order.index(r.target) if r.target in order else len(order))


def get_default_reranker() -> Reranker:
    env_name = os.getenv(ENV_RERANK, "").strip()
    if env_name:
        r = _named_lookup(env_name)
        if r is None:
            raise ValueError(f"unknown JW_RERANK_PROVIDER={env_name!r}")
        return r
    # Pick first available that's NOT the NoOp passthrough — NoOp is the fallback.
    for r in list_available_rerankers():
        if r.name != "noop":
            return r
    return NoOpReranker()
```

- [ ] **Step 5: Implement fakes**

```python
# packages/jw-rag/src/jw_rag/rerank_providers/fakes.py
"""Deterministic Fake rerankers."""

from __future__ import annotations

import hashlib

from jw_rag.rerank_providers.factory import Target


def _hash_score(query: str, candidate: str, salt: str) -> float:
    h = hashlib.sha256(f"{salt}|{query}|{candidate}".encode()).digest()
    raw = int.from_bytes(h[:4], "big") / (2**32 - 1)
    return float(raw)


class _BaseFakeReranker:
    name: str
    target: Target

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [_hash_score(query, c, self.name) for c in candidates]


class FakeBGEReranker(_BaseFakeReranker):
    name = "bge-v2-m3"
    target: Target = "cpu"


class FakeCohereReranker(_BaseFakeReranker):
    name = "cohere-rerank"
    target: Target = "api"


class FakeJinaReranker(_BaseFakeReranker):
    name = "jina-rerank"
    target: Target = "api"
```

- [ ] **Step 6: Add three real-provider stubs (filled in Tasks 12-14)**

```python
# packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py
"""Stub for BGE reranker v2 m3 — implemented in Task 12."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class BGERerankerV2M3Provider:
    name = "bge-v2-m3"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("BGERerankerV2M3Provider not implemented yet (Task 12)")
```

```python
# packages/jw-rag/src/jw_rag/rerank_providers/cohere_rerank.py
"""Stub for Cohere rerank v3.5 — implemented in Task 13."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class CohereRerankV35Provider:
    name = "cohere-rerank"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("CohereRerankV35Provider not implemented yet (Task 13)")
```

```python
# packages/jw-rag/src/jw_rag/rerank_providers/jina_rerank.py
"""Stub for Jina reranker v2 — implemented in Task 14."""

from __future__ import annotations

from jw_rag.rerank_providers.factory import Target


class JinaRerankerV2Provider:
    name = "jina-rerank"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def rerank(self, query: str, candidates: list[str]) -> list[float]:  # pragma: no cover
        raise RuntimeError("JinaRerankerV2Provider not implemented yet (Task 14)")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_protocol.py packages/jw-rag/tests/test_rerank_fakes.py -v`
Expected: 5 + 5 = 10 passed.

- [ ] **Step 8: Commit**

```bash
git add packages/jw-rag/src/jw_rag/rerank.py packages/jw-rag/src/jw_rag/rerank_providers packages/jw-rag/tests/test_rerank_protocol.py packages/jw-rag/tests/test_rerank_fakes.py
git commit -m "feat(jw-rag): Reranker Protocol + NoOpReranker + fakes + factory"
```

---

### Task 12: Real `BGERerankerV2M3Provider` (CrossEncoder)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py`
- Create: `packages/jw-rag/tests/test_rerank_bge_v2_m3.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_rerank_bge_v2_m3.py
from __future__ import annotations

import importlib.util

import pytest

from jw_rag.rerank_providers.bge_v2_m3 import BGERerankerV2M3Provider


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert BGERerankerV2M3Provider().is_available() is False


def test_name_and_target() -> None:
    p = BGERerankerV2M3Provider()
    assert p.name == "bge-v2-m3"


@pytest.mark.rerank_local
def test_real_rerank_returns_one_score_per_candidate() -> None:
    p = BGERerankerV2M3Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed")
    scores = p.rerank("trinidad", ["el trino", "una manzana", "doctrina cristiana"])
    assert len(scores) == 3
    assert all(isinstance(s, float) for s in scores)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_bge_v2_m3.py -v -m "not rerank_local"`
Expected: PASS for 2 (stub already returns False) — but the implementation file is stub-only, so we still need to upgrade.

- [ ] **Step 3: Implement the real reranker**

Replace `packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py`:

```python
# packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py
"""BAAI/bge-reranker-v2-m3 cross-encoder reranker (sentence-transformers)."""

from __future__ import annotations

import importlib.util
from typing import Any

from jw_rag.embed_providers.bge_m3 import _detect_target
from jw_rag.rerank_providers.factory import Target

_MODEL = "BAAI/bge-reranker-v2-m3"


class BGERerankerV2M3Provider:
    name = "bge-v2-m3"

    def __init__(self) -> None:
        self.target: Target = _detect_target()
        self._model: Any = None

    def is_available(self) -> bool:
        return importlib.util.find_spec("sentence_transformers") is not None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

            device = "mps" if self.target == "mlx" else ("cuda" if self.target == "nvidia" else "cpu")
            self._model = CrossEncoder(_MODEL, device=device)
        return self._model

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        model = self._ensure_model()
        pairs = [(query, c) for c in candidates]
        scores = model.predict(pairs)
        return [float(s) for s in scores]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_bge_v2_m3.py -v -m "not rerank_local"`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/rerank_providers/bge_v2_m3.py packages/jw-rag/tests/test_rerank_bge_v2_m3.py
git commit -m "feat(jw-rag): BGERerankerV2M3Provider (CrossEncoder, MLX/CUDA/CPU detect)"
```

---

### Task 13: Real `CohereRerankV35Provider`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/rerank_providers/cohere_rerank.py`
- Create: `packages/jw-rag/tests/test_rerank_cohere.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_rerank_cohere.py
from __future__ import annotations

import sys
import types

import pytest

from jw_rag.rerank_providers.cohere_rerank import CohereRerankV35Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    assert CohereRerankV35Provider().is_available() is False


def test_rerank_with_stub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "fake")

    class StubResult:
        def __init__(self, idx: int, score: float) -> None:
            self.index = idx
            self.relevance_score = score

    class StubResponse:
        results = [StubResult(0, 0.9), StubResult(1, 0.2), StubResult(2, 0.5)]

    class StubClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def rerank(self, *, model: str, query: str, documents: list[str], top_n: int) -> StubResponse:
            assert top_n == len(documents)
            return StubResponse()

    fake_module = types.ModuleType("cohere")
    fake_module.Client = StubClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cohere", fake_module)

    scores = CohereRerankV35Provider().rerank("q", ["a", "b", "c"])
    # Scores must be ordered to match original document order, not response order.
    assert scores == [0.9, 0.2, 0.5]


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(CohereRerankV35Provider())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_cohere.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the real reranker**

```python
# packages/jw-rag/src/jw_rag/rerank_providers/cohere_rerank.py
"""Cohere rerank-multilingual-v3.5 provider (lazy SDK import)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from jw_rag.rerank_providers.factory import Target

_MODEL = "rerank-multilingual-v3.5"


class CohereRerankV35Provider:
    name = "cohere-rerank"
    target: Target = "api"

    def __init__(self) -> None:
        self._client: Any = None

    def is_available(self) -> bool:
        if not os.getenv("COHERE_API_KEY"):
            return False
        return importlib.util.find_spec("cohere") is not None

    def __repr__(self) -> str:
        key = os.getenv("COHERE_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"CohereRerankV35Provider(key={masked})"

    def _ensure_client(self) -> Any:
        if self._client is None:
            import cohere  # type: ignore[import-not-found]

            self._client = cohere.Client(api_key=os.environ["COHERE_API_KEY"])
        return self._client

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        client = self._ensure_client()
        resp = client.rerank(
            model=_MODEL,
            query=query,
            documents=candidates,
            top_n=len(candidates),
        )
        # API returns scores indexed by reordered position; map back to input order.
        scores = [0.0] * len(candidates)
        for r in resp.results:
            scores[r.index] = float(r.relevance_score)
        return scores
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_cohere.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/rerank_providers/cohere_rerank.py packages/jw-rag/tests/test_rerank_cohere.py
git commit -m "feat(jw-rag): CohereRerankV35Provider (lazy cohere SDK, index remap)"
```

---

### Task 14: Real `JinaRerankerV2Provider` (httpx)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/rerank_providers/jina_rerank.py`
- Create: `packages/jw-rag/tests/test_rerank_jina.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/test_rerank_jina.py
from __future__ import annotations

import json

import httpx
import pytest

from jw_rag.rerank_providers.jina_rerank import JinaRerankerV2Provider


def test_is_available_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert JinaRerankerV2Provider().is_available() is False


def test_is_available_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake")
    assert JinaRerankerV2Provider().is_available() is True


def test_rerank_remaps_index_to_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "fake")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["query"] == "q"
        assert body["documents"] == ["a", "b", "c"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 2, "relevance_score": 0.1},
                    {"index": 0, "relevance_score": 0.9},
                    {"index": 1, "relevance_score": 0.5},
                ]
            },
        )

    p = JinaRerankerV2Provider(transport=httpx.MockTransport(handler))
    assert p.rerank("q", ["a", "b", "c"]) == [0.9, 0.5, 0.1]


def test_safe_repr_truncates_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JINA_API_KEY", "abcdefgh1234")
    assert "abcdefgh1234" not in repr(JinaRerankerV2Provider())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_jina.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the real reranker**

```python
# packages/jw-rag/src/jw_rag/rerank_providers/jina_rerank.py
"""Jina jina-reranker-v2-base-multilingual (HTTPS, no SDK)."""

from __future__ import annotations

import os

import httpx

from jw_rag.rerank_providers.factory import Target

_API_URL = "https://api.jina.ai/v1/rerank"
_MODEL = "jina-reranker-v2-base-multilingual"


class JinaRerankerV2Provider:
    name = "jina-rerank"
    target: Target = "api"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def is_available(self) -> bool:
        return bool(os.getenv("JINA_API_KEY"))

    def __repr__(self) -> str:
        key = os.getenv("JINA_API_KEY", "")
        masked = f"{key[:4]}***" if key else "<unset>"
        return f"JinaRerankerV2Provider(key={masked})"

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        key = os.getenv("JINA_API_KEY")
        if not key:
            raise RuntimeError("JINA_API_KEY not set")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": _MODEL, "query": query, "documents": candidates, "top_n": len(candidates)}
        with httpx.Client(transport=self._transport, timeout=30.0) as client:
            r = client.post(_API_URL, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        scores = [0.0] * len(candidates)
        for item in data["results"]:
            scores[int(item["index"])] = float(item["relevance_score"])
        return scores
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_rerank_jina.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/rerank_providers/jina_rerank.py packages/jw-rag/tests/test_rerank_jina.py
git commit -m "feat(jw-rag): JinaRerankerV2Provider (httpx, index remap, safe_repr)"
```

---

### Task 15: Integrate reranker into `VectorStore.hybrid_search` (backwards compat)

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/store.py`
- Create: `packages/jw-rag/tests/test_store_rerank_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-rag/tests/test_store_rerank_integration.py
"""Verify hybrid_search(rerank=True/False, reranker=...) integration.

Critical guarantees:
  1. Default call (no kwargs) with NoOpReranker output == pre-rerank top_k order.
  2. A Reranker that scores by candidate text length reorders the results.
  3. source string flips to "hybrid+rerank" when reranker active.
  4. Empty index returns [] without invoking the reranker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunker import Chunk
from jw_rag.embed import FakeEmbedder
from jw_rag.rerank_providers.factory import NoOpReranker, Reranker, Target
from jw_rag.store import VectorStore


def _store(tmp_path: Path) -> VectorStore:
    s = VectorStore(tmp_path, FakeEmbedder())
    s.add(
        [
            Chunk(id="a", text="trinity short", source_id="s1", metadata={}),
            Chunk(id="b", text="the doctrine of the trinity is taught only by humans not the bible itself", source_id="s2", metadata={}),
            Chunk(id="c", text="trinity is biblical", source_id="s3", metadata={}),
        ]
    )
    return s


class LengthReranker:
    name = "length-rerank"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        return [float(len(c)) for c in candidates]


def test_backwards_compat_with_noop_reranker(tmp_path: Path) -> None:
    s = _store(tmp_path)
    no_rerank = s.hybrid_search("trinity", top_k=3, rerank=False)
    with_noop = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=NoOpReranker())
    assert [h.chunk.id for h in no_rerank] == [h.chunk.id for h in with_noop]
    assert all(h.source == "hybrid" for h in no_rerank)
    assert all(h.source == "hybrid+rerank" for h in with_noop)


def test_reranker_reorders_candidates(tmp_path: Path) -> None:
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=LengthReranker())
    # LengthReranker scores by text length; longest text should be first.
    assert out[0].chunk.id == "b"
    assert out[0].source == "hybrid+rerank"


def test_reranker_protocol_isinstance() -> None:
    assert isinstance(NoOpReranker(), Reranker)


def test_empty_store_returns_empty(tmp_path: Path) -> None:
    s = VectorStore(tmp_path, FakeEmbedder())
    assert s.hybrid_search("trinity", top_k=3, rerank=True, reranker=LengthReranker()) == []


def test_candidate_pool_respected(tmp_path: Path) -> None:
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=2, candidate_pool=2, rerank=True, reranker=LengthReranker())
    assert len(out) <= 2


def test_reranker_default_falls_back_to_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When reranker=None and JW_RERANK_PROVIDER unset, fall back to NoOp behavior."""
    for var in ("COHERE_API_KEY", "JINA_API_KEY", "JW_RERANK_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_PROVIDER_ORDER", "api")
    s = _store(tmp_path)
    out = s.hybrid_search("trinity", top_k=3, rerank=True, reranker=None)
    assert len(out) == 3
    # NoOp leaves order intact and tags as hybrid+rerank.
    assert all(h.source == "hybrid+rerank" for h in out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/test_store_rerank_integration.py -v`
Expected: FAIL — `hybrid_search()` doesn't accept `rerank=` kwarg.

- [ ] **Step 3: Modify `hybrid_search`**

Replace the `hybrid_search` method body in `packages/jw-rag/src/jw_rag/store.py` with:

```python
    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        *,
        candidate_pool: int = 50,
        rrf_k: int = 60,
        rerank: bool = True,
        reranker: object | None = None,  # Reranker — typed as object to avoid import cycle
    ) -> list[SearchHit]:
        """Reciprocal Rank Fusion across BM25 and vector results, then optional rerank.

        Backwards compat: with `rerank=False`, output is bit-identical to the
        pre-Fase-33 behavior. With `rerank=True` and no real reranker
        available, the factory returns NoOpReranker (passthrough) so the order
        stays the same but `source` becomes "hybrid+rerank" — this is the only
        observable change for offline callers.
        """
        vec_hits = self.vector_search(query, top_k=candidate_pool)
        bm25_hits = self.bm25_search(query, top_k=candidate_pool)
        fused: dict[str, tuple[float, Chunk]] = {}
        for hits in (vec_hits, bm25_hits):
            for hit in hits:
                contribution = 1.0 / (rrf_k + hit.rank)
                if hit.chunk.id in fused:
                    prev_score, _ = fused[hit.chunk.id]
                    fused[hit.chunk.id] = (prev_score + contribution, hit.chunk)
                else:
                    fused[hit.chunk.id] = (contribution, hit.chunk)

        ordered = sorted(fused.values(), key=lambda t: -t[0])
        if not ordered:
            return []

        if not rerank:
            return [
                SearchHit(chunk=c, score=float(s), rank=r, source="hybrid")
                for r, (s, c) in enumerate(ordered[:top_k], 1)
            ]

        # Resolve reranker lazily to avoid touching factory on cold paths.
        if reranker is None:
            from jw_rag.rerank_providers.factory import get_default_reranker

            reranker = get_default_reranker()

        texts = [c.text for _, c in ordered]
        scores = reranker.rerank(query, texts)  # type: ignore[union-attr]
        reranked = sorted(zip(scores, ordered, strict=True), key=lambda t: -t[0])

        return [
            SearchHit(chunk=c, score=float(s), rank=r, source="hybrid+rerank")
            for r, (s, (_, c)) in enumerate(reranked[:top_k], 1)
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/test_store_rerank_integration.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the existing jw-rag suite — no regressions**

Run: `uv run pytest packages/jw-rag/tests -v`
Expected: every pre-existing test still green PLUS the new ones; total grows by ~50.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/store.py packages/jw-rag/tests/test_store_rerank_integration.py
git commit -m "feat(jw-rag): hybrid_search rerank=True/False with backwards-compat default"
```

---

### Task 16: Re-export public API from `jw_rag/__init__.py`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/__init__.py`

- [ ] **Step 1: Read current init**

Run: `cat packages/jw-rag/src/jw_rag/__init__.py`

- [ ] **Step 2: Append re-exports**

Add to the end of `packages/jw-rag/src/jw_rag/__init__.py`:

```python
# Fase 33 public re-exports
from jw_rag.embed_providers import (  # noqa: E402
    EmbedProvider,
    get_default_embedder,
    list_available_embedders,
)
from jw_rag.rerank import (  # noqa: E402
    Reranker,
    get_default_reranker,
    list_available_rerankers,
)

__all__ = [
    *globals().get("__all__", []),
    "EmbedProvider",
    "Reranker",
    "get_default_embedder",
    "get_default_reranker",
    "list_available_embedders",
    "list_available_rerankers",
]
```

- [ ] **Step 3: Verify import works**

Run:
```bash
uv run python -c "from jw_rag import EmbedProvider, Reranker, get_default_embedder, get_default_reranker; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-rag/src/jw_rag/__init__.py
git commit -m "feat(jw-rag): re-export EmbedProvider/Reranker/factories from top-level"
```

---

### Task 17: CLI flags (`jw rag search --no-rerank --provider`) + MCP tool param

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/rag.py`
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Locate the CLI command and inspect**

Run: `cat packages/jw-cli/src/jw_cli/commands/rag.py | head -120`

Identify the `search` command signature; it should take a query + `--top-k`. Note its current Typer decorator.

- [ ] **Step 2: Add `--no-rerank` and `--provider` flags**

Edit the `search` function — locate the `def search(` definition and update it. Append the new parameters before existing kwargs:

```python
# packages/jw-cli/src/jw_cli/commands/rag.py
# Inside the existing `search` command:
import os
import typer

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(10, "--top-k", help="Number of results"),
    no_rerank: bool = typer.Option(
        False, "--no-rerank", help="Skip the cross-encoder reranker (Fase 33)."
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Embed provider name (sets JW_EMBED_PROVIDER for this run).",
    ),
    rerank_provider: str | None = typer.Option(
        None,
        "--rerank-provider",
        help="Reranker name (sets JW_RERANK_PROVIDER for this run).",
    ),
) -> None:
    """Search the RAG index. Defaults match pre-Fase-33 behavior."""

    if provider:
        os.environ["JW_EMBED_PROVIDER"] = provider
    if rerank_provider:
        os.environ["JW_RERANK_PROVIDER"] = rerank_provider

    # ... existing store-loading code (unchanged) ...
    # When calling hybrid_search, pass rerank=not no_rerank:
    hits = store.hybrid_search(query, top_k=top_k, rerank=not no_rerank)
    # ... existing rendering code (unchanged) ...
```

> **Note for the implementer:** Keep all other CLI logic exactly as-is. The only edits are: add the 3 new Typer options, set env vars early, pass `rerank=not no_rerank` to `hybrid_search`. Do NOT rewrite the rendering or store-loading code.

- [ ] **Step 3: Update the MCP `semantic_search` tool**

Edit `packages/jw-mcp/src/jw_mcp/server.py`: locate the `semantic_search` tool definition and add a `rerank: bool = True` kwarg, passed straight to `store.hybrid_search`.

```python
# packages/jw-mcp/src/jw_mcp/server.py
# Inside the existing semantic_search tool:

@mcp.tool()
def semantic_search(
    query: str,
    top_k: int = 10,
    rerank: bool = True,
) -> list[dict]:
    """Search the RAG index. `rerank` toggles the Fase 33 cross-encoder pass."""

    # ... existing code that loads the store ...
    hits = store.hybrid_search(query, top_k=top_k, rerank=rerank)
    return [
        {
            "chunk_id": h.chunk.id,
            "text": h.chunk.text,
            "score": h.score,
            "source": h.source,
        }
        for h in hits
    ]
```

- [ ] **Step 4: Smoke-test the CLI without --no-rerank breakage**

Run:
```bash
uv run jw rag search --help
```
Expected: help output shows the 3 new flags.

- [ ] **Step 5: Run the full CLI + MCP test suites**

Run: `uv run pytest packages/jw-cli/tests packages/jw-mcp/tests -v`
Expected: no regressions in existing tests.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/rag.py packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-cli,jw-mcp): expose --no-rerank/--provider flags and rerank tool param"
```

---

### Task 18: Documentation + ROADMAP + VISION_AUDIT + optional CI job

**Files:**
- Create: `docs/guias/embeddings-y-rerank.md`
- Modify: `docs/README.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the user guide**

```markdown
# Embeddings y reranking (`jw-rag`)

> Fase 33 — núcleo RAG real. Spec: `docs/superpowers/specs/2026-05-31-fase-33-embed-rerank-design.md`.

## Para qué sirve

Hasta Fase 32 el embedding del corpus era `FakeEmbedder` (hash determinístico, semánticamente vacío) y todo el peso recaía en BM25 + RRF. Fase 33 sustituye eso por una **familia real** de providers con **auto-detect** (`api > mlx > nvidia > cpu`) más un **cross-encoder reranker** que reordena el top-50 antes de devolver el top-10.

## Defaults zero-config

- **Sin extras instalados / sin keys**: factory devuelve `FakeEmbedder` + `NoOpReranker`. Bit-idéntico al comportamiento previo. CI sigue verde.
- **Con `jw-rag[embeddings-local]`** (sentence-transformers): factory escoge `BGEM3Provider` (MLX en Apple Silicon, CUDA en NVIDIA, CPU si no).
- **Con `COHERE_API_KEY` / `JINA_API_KEY` / `VOYAGE_API_KEY`**: factory prioriza la API correspondiente (orden por defecto: `api > mlx > nvidia > cpu`).

## Override manual

```bash
# Forzar provider concreto
JW_EMBED_PROVIDER=bge-m3 JW_RERANK_PROVIDER=bge-v2-m3 uv run jw rag rebuild

# Cambiar prioridad
JW_PROVIDER_ORDER="mlx,nvidia,api,cpu" uv run jw rag search "trinidad"

# Desactivar rerank en una query puntual
uv run jw rag search "trinidad" --no-rerank
```

## Instalación de extras

```bash
# Local embeddings + reranker (sentence-transformers, ~2.3GB para BGE-M3)
uv pip install -e packages/jw-rag[embeddings-local,rerank-local]

# APIs (cohere, voyageai)
uv pip install -e packages/jw-rag[embeddings-api,rerank-api]
```

## Cambiar de dim → re-ingesta

El `VectorStore` rechaza cargar un índice con `dim` distinto al embedder. Cuando cambies de provider, re-ingesta:

```bash
JW_EMBED_PROVIDER=bge-m3 uv run jw rag rebuild --corpus tests/fixtures/sample_corpus
```

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `dim mismatch` al cargar | índice creado con otro embedder | `jw rag rebuild` con el provider deseado |
| `FakeEmbedder` log de warning | ningún provider disponible | instala extras o pon API key |
| Rerank lento (>1s) | CrossEncoder en CPU | extra `[rerank-local]` + GPU o Cohere API |
| Ollama no detectado | `ollama serve` no corre | `ollama serve` + `ollama pull nomic-embed-text` |
| API key filtrada en logs | safe_repr fallido | reporta bug — repr SIEMPRE debe truncar |

## Cómo añadir un provider nuevo

1. Añade módulo `embed_providers/<nombre>.py` con la clase que satisfaga `EmbedProvider`.
2. Añade `Fake<Nombre>` en `embed_providers/fakes.py` (tests).
3. Registra la clase en `_instantiate_registry()` dentro de `factory.py`.
4. Añade extra al `pyproject.toml` si requiere SDK.
5. Mínimo 3 tests: protocol-conform, key/SDK detection, embed shape.
```

- [ ] **Step 2: Add link in `docs/README.md`**

In the "Guías por tema" alphabetical list:

```markdown
- [Embeddings y reranking](guias/embeddings-y-rerank.md) — Fase 33: providers reales (BGE-M3, Cohere, Jina, Voyage, Ollama, E5) + cross-encoder reranker con auto-detect.
```

- [ ] **Step 3: Append to `docs/VISION_AUDIT.md`**

Insert above the closing summary paragraph:

```markdown
| Fase 33 (embed-rerank) | ✅ Nuevo | `jw-rag.embed_providers` + `jw-rag.rerank_providers` — 6 embed + 4 rerank providers + factory |
```

- [ ] **Step 4: Append Fase 33 section to `docs/ROADMAP.md`**

After Fase 22, before any footer:

```markdown
## Fase 33 — embed-rerank: núcleo RAG al SOTA ✅

> Tier 1 núcleo. Spec: `docs/superpowers/specs/2026-05-31-fase-33-embed-rerank-design.md`.

- ✅ `EmbedProvider` Protocol + `Target` literal (api/mlx/nvidia/cpu).
- ✅ 6 embed providers: BGE-M3, Multilingual-E5, Jina-v3, Cohere-v3, Voyage-multilingual-2, Ollama (nomic-embed-text).
- ✅ Fake sibling por cada provider — deterministic, used by tests.
- ✅ `Reranker` Protocol + `NoOpReranker` fallback.
- ✅ 3 rerank providers reales: BGE-reranker-v2-m3, Cohere-rerank-v3.5, Jina-reranker-v2.
- ✅ Factory con auto-detect + env override (`JW_EMBED_PROVIDER`, `JW_RERANK_PROVIDER`, `JW_PROVIDER_ORDER`).
- ✅ `VectorStore.hybrid_search(rerank=True, reranker=None, candidate_pool=50)` — backwards-compatible.
- ✅ Flags CLI `--no-rerank`, `--provider`, `--rerank-provider`.
- ✅ Param MCP `semantic_search(rerank: bool = True)`.
- ✅ Lazy SDK loading; cero red en import time; safe_repr para API keys.
- ✅ Extras pyproject: `[embeddings-local]`, `[embeddings-api]`, `[rerank-local]`, `[rerank-api]`.
- ✅ Guía `docs/guias/embeddings-y-rerank.md`.

### Cobertura de tests

- ✅ ~50 tests nuevos en `packages/jw-rag/tests/`.
- ✅ 1649 tests previos sin regresión.
- ✅ Markers `@pytest.mark.embeddings_local` y `@pytest.mark.rerank_local` para tests con descargas reales.
```

- [ ] **Step 5: Add optional non-blocking CI job**

Edit `.github/workflows/ci.yml`. Append below the existing `test` job:

```yaml
  test-rag-embeddings:
    name: jw-rag embeddings-local (optional)
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-packages
      - run: uv pip install -e packages/jw-rag[embeddings-local,rerank-local]
      - run: uv run pytest packages/jw-rag/tests -m embeddings_local -v
```

- [ ] **Step 6: Validate YAML**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no exception.

- [ ] **Step 7: Commit docs + CI**

```bash
git add docs/guias/embeddings-y-rerank.md docs/README.md docs/VISION_AUDIT.md docs/ROADMAP.md .github/workflows/ci.yml
git commit -m "docs(fase-33): user guide + roadmap + audit row + optional CI job"
```

---

### Task 19: Final audit — full suite green + no regressions

**Files:** none (verification only).

- [ ] **Step 1: Lint + format**

```bash
uv run ruff check packages/jw-rag packages/jw-cli packages/jw-mcp
uv run ruff format --check packages/jw-rag packages/jw-cli packages/jw-mcp
```
Expected: zero violations.

- [ ] **Step 2: mypy (best-effort)**

```bash
uv run mypy packages/jw-rag/src
```
Expected: only `# type: ignore` annotated lines flagged; no unrelated regressions.

- [ ] **Step 3: Full test suite**

```bash
uv run pytest packages/ -v --tb=short -m "not embeddings_local and not rerank_local"
```
Expected: 1649 previous + ~50 new = ~1699 tests, all green.

- [ ] **Step 4: Backwards-compat smoke**

```bash
uv run python -c "
from pathlib import Path
from jw_rag.embed import FakeEmbedder
from jw_rag.chunker import Chunk
from jw_rag.store import VectorStore
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    s = VectorStore(Path(tmp), FakeEmbedder())
    s.add([Chunk(id='a', text='trinity is biblical', source_id='s1', metadata={})])
    # Old call signature still works
    out = s.hybrid_search('trinity')
    assert len(out) == 1
    print('Backwards-compat: OK', out[0].source)
"
```
Expected: `Backwards-compat: OK hybrid+rerank` (NoOp passthrough adds the `+rerank` tag but preserves order).

- [ ] **Step 5: End-to-end CLI smoke**

```bash
uv run jw rag search --help
```
Expected: help text shows `--no-rerank`, `--provider`, `--rerank-provider`.

- [ ] **Step 6: Final summary commit (if anything was polished)**

If any minor doc tweaks during audit, commit them: `docs(fase-33): polish`. Otherwise nothing to do.

---

## Self-review summary

- **Spec coverage**: every section of the spec maps to tasks — architecture/Protocol → Tasks 2+11; fakes → Tasks 3+11; factory + env → Tasks 4+11; real embed providers (BGE-M3, E5, Jina, Cohere, Voyage, Ollama) → Tasks 5/6/7/8/9/10; real rerankers (BGE-v2-m3, Cohere, Jina) → Tasks 12/13/14; `VectorStore.hybrid_search` integration + backwards-compat → Task 15; public API re-exports → Task 16; CLI + MCP → Task 17; guide + ROADMAP + VISION_AUDIT + CI → Task 18; final audit → Task 19. Boundaries honored: BM25 stays, `Chunk`/`VectorStore` on-disk format untouched, no quantization, no sparse/colbert exposed.
- **No placeholders**: every code block is fully written; every YAML/TOML diff is fully written; every command shows exact invocation + expected output.
- **Type consistency**: `Target = Literal["api","mlx","nvidia","cpu"]` defined once per side (embed/rerank), reused via import. Both `EmbedProvider` and `Reranker` are `@runtime_checkable Protocol`s with identical attribute shape (`name: str`, `target: Target`, plus `is_available()`). `VectorStore.hybrid_search` types the reranker parameter as `object | None` to avoid the embed↔rerank circular import; the runtime contract is enforced by Protocol-conforming tests in Task 15.
- **Backwards compat**: `hybrid_search(query)` with no kwargs returns the same top-k order as before. The only observable change in offline CI is `source="hybrid+rerank"` (vs `"hybrid"`); Task 15's `test_backwards_compat_with_noop_reranker` pins this exact contract. Callers can pass `rerank=False` to recover the original `source="hybrid"` string.
- **No network in import time**: all heavy SDKs (`sentence_transformers`, `cohere`, `voyageai`) are imported inside `_ensure_*` methods. `is_available()` uses `importlib.util.find_spec` + env presence + 0.5s probe for Ollama — never touches the model.
- **CI safety**: existing offline job keeps `FakeEmbedder` + `NoOpReranker`. New non-blocking `test-rag-embeddings` job exercises `[embeddings-local]` with `-m embeddings_local`.

## Execution choice

Plan completo, 19 tareas TDD bite-sized. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`).
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
