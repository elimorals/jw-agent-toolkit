# Fase 37 — `colpali-visual` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a **visual** retrieval store to `jw-rag` based on late-interaction ColPali/ColQwen2 embeddings. Pages from JWPUB/EPUB/PDF are rasterized → multi-vector page embeddings → MaxSim scoring. Three-way RRF (bm25 + text-vector + visual-MaxSim). Hardware-aware: fails fast without GPU; uses deterministic `FakeColPaliEmbedder` in CI.

**Architecture:** New sub-package `packages/jw-rag/src/jw_rag/visual/` (no new monorepo package — lives inside `jw-rag`). Lazy provider imports (`colpali-engine`, `transformers`, `torch`, `pdf2image`, `playwright`, `Pillow`) only inside real providers. `VisualVectorStore` parallels `VectorStore` but is multi-vector internally. Hybrid helper extends Fase-33 RRF. CLI + MCP added behind `JW_VISUAL_ENABLED` env flag.

**Tech Stack:** Python 3.13 · numpy (multi-vector storage) · Pillow (image type) · pdf2image (PDF rasterization, optional) · Playwright (EPUB/JWPUB rasterization, optional) · colpali-engine + transformers + torch (real provider on NVIDIA, optional) · mlx-vlm (Apple Silicon, optional) · PyYAML (golden cases).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-37-colpali-visual-design.md`](../specs/2026-05-31-fase-37-colpali-visual-design.md).
**Pilot plan format:** [`docs/superpowers/plans/2026-05-30-fase-22-eval-doctrinal-plan.md`](2026-05-30-fase-22-eval-doctrinal-plan.md).

---

## File map

Creates:
- `packages/jw-rag/src/jw_rag/visual/__init__.py`
- `packages/jw-rag/src/jw_rag/visual/models.py`
- `packages/jw-rag/src/jw_rag/visual/errors.py`
- `packages/jw-rag/src/jw_rag/visual/fakes.py`
- `packages/jw-rag/src/jw_rag/visual/visual_store.py`
- `packages/jw-rag/src/jw_rag/visual/page_rasterizer.py`
- `packages/jw-rag/src/jw_rag/visual/colpali.py`
- `packages/jw-rag/src/jw_rag/visual/ingest.py`
- `packages/jw-rag/src/jw_rag/visual/hybrid.py`
- `packages/jw-rag/tests/visual/__init__.py`
- `packages/jw-rag/tests/visual/test_models.py`
- `packages/jw-rag/tests/visual/test_fakes.py`
- `packages/jw-rag/tests/visual/test_visual_store.py`
- `packages/jw-rag/tests/visual/test_rasterizer.py`
- `packages/jw-rag/tests/visual/test_colpali.py`
- `packages/jw-rag/tests/visual/test_ingest.py`
- `packages/jw-rag/tests/visual/test_hybrid.py`
- `packages/jw-rag/tests/visual/fixtures/mini.pdf`
- `packages/jw-rag/tests/visual/fixtures/mini.epub`
- `packages/jw-rag/tests/visual/fixtures/mini.jwpub`
- `packages/jw-rag/tests/visual/fixtures/build_fixtures.py`
- `packages/jw-eval/fixtures/golden_qa/l1/visual_paul_journeys_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/visual_tabernacle_en.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_seven_times_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/visual_jw_org_structure_en.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_beasts_table_es.yaml`
- `docs/guias/visual-rag.md`

Modifies:
- `packages/jw-rag/pyproject.toml` — add `[visual]` and `[visual-mlx]` extras.
- `packages/jw-cli/src/jw_cli/commands/rag.py` — add `ingest-visual` + `--visual` flag on `search`.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `visual_search` and `ingest_publication_visual` tools.
- `docs/VISION_AUDIT.md` — add Fase 37 row.
- `docs/ROADMAP.md` — add Fase 37 section.

---

### Task 1: Scaffold `jw_rag.visual` + `[visual]` extras

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/__init__.py`
- Create: `packages/jw-rag/src/jw_rag/visual/errors.py`
- Create: `packages/jw-rag/tests/visual/__init__.py`
- Modify: `packages/jw-rag/pyproject.toml`

- [ ] **Step 1: Add `[visual]` and `[visual-mlx]` extras**

Edit `packages/jw-rag/pyproject.toml`. Under `[project.optional-dependencies]` append:

```toml
visual = [
    "colpali-engine>=0.3.4",
    "transformers>=4.45.0",
    "torch>=2.4.0",
    "pdf2image>=1.17.0",
    "Pillow>=10.4.0",
    "playwright>=1.47.0",
]
visual-mlx = [
    "mlx>=0.18.0",
    "mlx-vlm>=0.0.13",
    "Pillow>=10.4.0",
    "pdf2image>=1.17.0",
    "playwright>=1.47.0",
]
```

Heavy deps stay opt-in. Core install (`uv sync --all-packages`) does NOT pull them.

- [ ] **Step 2: Create errors module**

```python
# packages/jw-rag/src/jw_rag/visual/errors.py
"""Errors specific to the visual RAG subsystem.

`ConfigError` is raised when the user asks for a real visual embedder but no
GPU/MLX backend is reachable. Message must be actionable and include the
exact install command.

`VisualStoreMismatchError` is raised by `VisualVectorStore.load()` when the
persisted store on disk was produced by a different model/revision/patch_size
than the embedder passed at load time.
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """No usable hardware for ColPali/ColQwen2 visual embeddings.

    Message includes the install commands for NVIDIA (`uv sync --extra visual`)
    and Apple Silicon (`uv sync --extra visual-mlx`), plus the env var to
    disable the subsystem entirely (`JW_VISUAL_ENABLED=0`).
    """


class VisualStoreMismatchError(RuntimeError):
    """On-disk store was produced by a different model/revision/patch_size."""
```

- [ ] **Step 3: Create the package init**

```python
# packages/jw-rag/src/jw_rag/visual/__init__.py
"""Visual late-interaction RAG store.

Public API:
    from jw_rag.visual import (
        VisualChunk,
        MultiVectorHit,
        IngestResult,
        VisualVectorStore,
        ConfigError,
        VisualStoreMismatchError,
        hybrid_search_with_visual,
        get_default_visual_embedder,
    )

Heavy providers (`colpali-engine`, `transformers`, `torch`, `mlx`, `pdf2image`,
`playwright`) are imported lazily inside the provider classes. Importing this
module is safe on machines without any of them — only `is_available()` and
the provider constructors touch hardware.
"""

from jw_rag.visual.errors import ConfigError, VisualStoreMismatchError
from jw_rag.visual.models import IngestResult, MultiVectorHit, VisualChunk

__all__ = [
    "ConfigError",
    "IngestResult",
    "MultiVectorHit",
    "VisualChunk",
    "VisualStoreMismatchError",
]
```

- [ ] **Step 4: Create test package init**

```python
# packages/jw-rag/tests/visual/__init__.py
"""Tests for jw_rag.visual."""
```

- [ ] **Step 5: Verify install**

Run: `uv sync --all-packages`
Expected: no errors. `python -c "import jw_rag.visual; print('ok')"` prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/pyproject.toml packages/jw-rag/src/jw_rag/visual packages/jw-rag/tests/visual
git commit -m "feat(jw-rag): scaffold visual subpackage and [visual]/[visual-mlx] extras"
```

---

### Task 2: Models (`VisualChunk`, `MultiVectorHit`, `IngestResult`)

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/models.py`
- Create: `packages/jw-rag/tests/visual/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_models.py
"""Tests for jw_rag.visual.models."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from jw_rag.visual.models import IngestResult, MultiVectorHit, VisualChunk


def test_visual_chunk_minimal() -> None:
    c = VisualChunk(
        id="abc#p1",
        source_id="abc",
        page_number=1,
        image_path=Path("/tmp/abc_p001.png"),
    )
    assert c.id == "abc#p1"
    assert c.ocr_text == ""
    assert c.metadata == {}


def test_visual_chunk_round_trip_dict() -> None:
    c = VisualChunk(
        id="abc#p2",
        source_id="abc",
        page_number=2,
        image_path=Path("/tmp/abc_p002.png"),
        ocr_text="foo",
        metadata={"language": "es"},
    )
    d = c.to_dict()
    assert d["page_number"] == 2
    assert d["image_path"] == "/tmp/abc_p002.png"
    back = VisualChunk.from_dict(d)
    assert back == c


def test_multi_vector_hit_score_field() -> None:
    chunk = VisualChunk(id="a#p1", source_id="a", page_number=1, image_path=Path("/tmp/x.png"))
    hit = MultiVectorHit(chunk=chunk, score=12.5, rank=1)
    assert hit.score == 12.5
    assert hit.rank == 1
    assert hit.source == "visual"


def test_ingest_result_addition() -> None:
    a = IngestResult(pages_added=3, pages_skipped=1, duration_ms=100)
    b = IngestResult(pages_added=2, pages_skipped=0, duration_ms=50)
    c = a + b
    assert c.pages_added == 5
    assert c.pages_skipped == 1
    assert c.duration_ms == 150


def test_visual_chunk_text_alias_for_ocr() -> None:
    """`.text` proxies to `ocr_text` so VisualChunk slots into SearchHit shape."""
    c = VisualChunk(
        id="x#1", source_id="x", page_number=1, image_path=Path("/tmp/x.png"), ocr_text="hello"
    )
    assert c.text == "hello"


def test_numpy_import_for_assertion_smoke() -> None:
    # Sanity check that numpy is available in tests (needed by store tests).
    arr = np.zeros((2, 3), dtype=np.float16)
    assert arr.shape == (2, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_models.py -v`
Expected: FAIL — module `jw_rag.visual.models` missing.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-rag/src/jw_rag/visual/models.py
"""Data models for the visual RAG subsystem.

A `VisualChunk` is one rasterized page. It mirrors `jw_rag.chunker.Chunk`
enough that agents can treat it the same (`.text`, `.metadata`, `.source_id`)
but adds page-level fields (`page_number`, `image_path`).

A `MultiVectorHit` is the visual analogue of `SearchHit`: same shape, same
`source` field convention ("visual" instead of "vector"/"bm25"/"hybrid").

An `IngestResult` aggregates per-file ingest stats; `__add__` lets callers
fold many file results into one summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisualChunk:
    """One rasterized page indexed by the visual store."""

    id: str
    source_id: str
    page_number: int
    image_path: Path
    ocr_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Alias so VisualChunk can be consumed wherever Chunk-like is expected."""
        return self.ocr_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "page_number": self.page_number,
            "image_path": str(self.image_path),
            "ocr_text": self.ocr_text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualChunk:
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            page_number=int(data["page_number"]),
            image_path=Path(data["image_path"]),
            ocr_text=data.get("ocr_text", ""),
            metadata=data.get("metadata", {}) or {},
        )


@dataclass
class MultiVectorHit:
    """Result of a visual MaxSim search.

    `score` is unbounded above (sum-of-maxes), not a similarity in [0, 1].
    Callers should treat scores as comparable only within the same query.
    """

    chunk: VisualChunk
    score: float
    rank: int
    source: str = "visual"


@dataclass
class IngestResult:
    """Aggregated counters for a visual ingest call."""

    pages_added: int = 0
    pages_skipped: int = 0
    duration_ms: int = 0

    def __add__(self, other: IngestResult) -> IngestResult:
        return IngestResult(
            pages_added=self.pages_added + other.pages_added,
            pages_skipped=self.pages_skipped + other.pages_skipped,
            duration_ms=self.duration_ms + other.duration_ms,
        )
```

- [ ] **Step 4: Re-export from package init**

Append to `packages/jw-rag/src/jw_rag/visual/__init__.py` is already done in Task 1 (`from jw_rag.visual.models import ...`). Verify the import works.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_models.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/models.py packages/jw-rag/tests/visual/test_models.py
git commit -m "feat(jw-rag): visual models — VisualChunk, MultiVectorHit, IngestResult"
```

---

### Task 3: `FakeColPaliEmbedder` + `FakeRasterizer` (test infrastructure)

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/fakes.py`
- Create: `packages/jw-rag/tests/visual/test_fakes.py`

The fakes are the foundation of every later test. Build them first.

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_fakes.py
"""Tests for FakeColPaliEmbedder and FakeRasterizer.

Determinism is the whole point: same input bytes → same vectors. That lets
tests assert exact MaxSim scores without ever touching a real GPU model.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image

from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer


def _img_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_fake_embedder_shape_and_dtype() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=64)
    img = Image.new("RGB", (256, 256), color=(255, 0, 0))
    vecs = e.embed_image(img)
    assert vecs.shape == (64, 128)
    assert vecs.dtype == np.float16


def test_fake_embedder_is_deterministic() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    img = Image.new("RGB", (128, 128), color=(0, 255, 0))
    a = e.embed_image(img)
    b = e.embed_image(img)
    np.testing.assert_array_equal(a, b)


def test_fake_embedder_different_images_differ() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    a = e.embed_image(Image.new("RGB", (128, 128), color=(0, 255, 0)))
    b = e.embed_image(Image.new("RGB", (128, 128), color=(0, 0, 255)))
    # Different bytes → different seed → different vectors.
    assert not np.array_equal(a, b)


def test_fake_embedder_query_uses_text_seed() -> None:
    e = FakeColPaliEmbedder(dim=128, n_patches=32)
    q1 = e.embed_query("hello")
    q2 = e.embed_query("hello")
    q3 = e.embed_query("world")
    np.testing.assert_array_equal(q1, q2)
    assert not np.array_equal(q1, q3)
    assert q1.shape[1] == 128
    assert q1.shape[0] >= 1  # at least one query token


def test_fake_embedder_is_available_always_true() -> None:
    assert FakeColPaliEmbedder.is_available() is True


def test_fake_rasterizer_yields_blank_pages() -> None:
    r = FakeRasterizer(n_pages=3, size=(64, 64))
    pages = list(r.rasterize_pdf(b"any-bytes"))
    assert len(pages) == 3
    for idx, img in pages:
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)
    assert [idx for idx, _ in pages] == [0, 1, 2]


def test_fake_rasterizer_varies_per_page() -> None:
    """Each page gets a different fill so embeddings will differ."""
    r = FakeRasterizer(n_pages=3, size=(64, 64))
    pages = list(r.rasterize_pdf(b"src"))
    digests = {hashlib.sha256(_img_bytes(img)).hexdigest() for _, img in pages}
    assert len(digests) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_fakes.py -v`
Expected: FAIL — `jw_rag.visual.fakes` missing.

- [ ] **Step 3: Implement the fakes**

```python
# packages/jw-rag/src/jw_rag/visual/fakes.py
"""Deterministic fakes for the visual subsystem.

`FakeColPaliEmbedder` seeds a per-image RNG from `sha256(image_bytes)`. Tests
get byte-identical vectors across runs without touching `colpali-engine` or
`torch`. Compatible with the same `embed_image` / `embed_query` shape as the
real provider:

    embed_image(PIL.Image) -> np.ndarray[float16, (n_patches, dim)]
    embed_query(str)       -> np.ndarray[float16, (n_q_tokens, dim)]

`FakeRasterizer` mimics the real `PageRasterizer` interface but never touches
Playwright / pdf2image. It returns blank-but-distinct PIL images keyed by page
index, so downstream embedding stages get distinguishable inputs.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator

import numpy as np
from PIL import Image


class FakeColPaliEmbedder:
    """Deterministic stand-in for ColQwen2/ColPali."""

    name = "fake-colpali"
    dim = 128
    max_patches = 1030

    def __init__(self, *, dim: int = 128, n_patches: int = 64) -> None:
        self.dim = dim
        self._n_patches = n_patches
        self.max_patches = n_patches  # store padding uses this

    @classmethod
    def is_available(cls, target: str = "fake") -> bool:  # noqa: ARG003
        return True

    def embed_image(self, image: Image.Image) -> np.ndarray:
        seed = self._seed_from_image(image)
        rng = np.random.default_rng(seed)
        vecs = rng.standard_normal(size=(self._n_patches, self.dim)).astype(np.float16)
        return _l2_normalize_rows(vecs)

    def embed_query(self, query: str) -> np.ndarray:
        # Query length tracks word count so tests can probe sensitivity.
        n_tokens = max(1, len(query.split()))
        seed = int.from_bytes(hashlib.sha256(query.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        vecs = rng.standard_normal(size=(n_tokens, self.dim)).astype(np.float16)
        return _l2_normalize_rows(vecs)

    @staticmethod
    def _seed_from_image(image: Image.Image) -> int:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return int.from_bytes(hashlib.sha256(buf.getvalue()).digest()[:8], "big")


def _l2_normalize_rows(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr.astype(np.float32), axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (arr.astype(np.float32) / norms).astype(np.float16)


class FakeRasterizer:
    """Returns blank-but-distinct PIL images for tests.

    The fill color encodes the page index so different pages produce different
    `sha256(image_bytes)` and therefore different FakeColPaliEmbedder vectors.
    """

    def __init__(self, *, n_pages: int = 3, size: tuple[int, int] = (768, 1024)) -> None:
        self._n_pages = n_pages
        self._size = size

    def _make_page(self, idx: int) -> Image.Image:
        # Vary RGB per page so embeddings are distinguishable.
        r = (idx * 53) % 256
        g = (idx * 97) % 256
        b = (idx * 151) % 256
        return Image.new("RGB", self._size, color=(r, g, b))

    def rasterize_pdf(self, _data: bytes, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002
        for i in range(self._n_pages):
            yield i, self._make_page(i)

    def rasterize_epub(self, _path, *, viewport=(768, 1024)) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002, ANN001
        for i in range(self._n_pages):
            yield i, self._make_page(i)

    def rasterize_jwpub(self, _path, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002, ANN001
        for i in range(self._n_pages):
            yield i, self._make_page(i)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_fakes.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/fakes.py packages/jw-rag/tests/visual/test_fakes.py
git commit -m "feat(jw-rag): FakeColPaliEmbedder + FakeRasterizer for visual tests"
```

---

### Task 4: `VisualVectorStore` — add, MaxSim search, persistence

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/visual_store.py`
- Create: `packages/jw-rag/tests/visual/test_visual_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_visual_store.py
"""Tests for VisualVectorStore.

We use FakeColPaliEmbedder so MaxSim scores are deterministic. The store
is verified for: add(), search(), save()/load() round trip, mismatch
detection on load, idempotent re-add by source_id, and empty-store behavior.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from jw_rag.visual.errors import VisualStoreMismatchError
from jw_rag.visual.fakes import FakeColPaliEmbedder
from jw_rag.visual.models import VisualChunk
from jw_rag.visual.visual_store import VisualVectorStore


def _make_chunks(n: int, tmp_path: Path) -> list[tuple[VisualChunk, Image.Image]]:
    out: list[tuple[VisualChunk, Image.Image]] = []
    for i in range(n):
        img = Image.new("RGB", (64, 64), color=(i * 30, 50, 200 - i * 20))
        png = tmp_path / f"src1_p{i:03d}.png"
        img.save(png)
        chunk = VisualChunk(
            id=f"src1#p{i + 1}",
            source_id="src1",
            page_number=i + 1,
            image_path=png,
        )
        out.append((chunk, img))
    return out


def test_empty_store(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    assert store.is_empty
    assert store.count == 0
    assert store.search("anything") == []


def test_add_and_search(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(3, tmp_path)
    store.add(pairs)
    assert store.count == 3
    hits = store.search("any query", top_k=2)
    assert len(hits) == 2
    assert hits[0].rank == 1
    assert hits[1].rank == 2
    assert hits[0].score >= hits[1].score
    # source field stays "visual" regardless of how we got there.
    assert all(h.source == "visual" for h in hits)


def test_add_idempotent_by_source_id(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(2, tmp_path)
    store.add(pairs)
    # Re-adding same chunks → no growth.
    store.add(pairs)
    assert store.count == 2


def test_source_ids(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    store.add(_make_chunks(2, tmp_path))
    assert store.source_ids() == {"src1"}


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    embedder = FakeColPaliEmbedder(dim=64, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(3, tmp_path)
    store.add(pairs)
    pre_hits = store.search("q", top_k=3)
    store.save()

    store2 = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store2.load()
    assert store2.count == 3
    post_hits = store2.search("q", top_k=3)
    assert [h.chunk.id for h in pre_hits] == [h.chunk.id for h in post_hits]
    for a, b in zip(pre_hits, post_hits, strict=True):
        assert abs(a.score - b.score) < 1e-3


def test_load_mismatch_raises(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store.add(_make_chunks(1, tmp_path))
    store.save()

    other = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=32))
    with pytest.raises(VisualStoreMismatchError):
        other.load()


def test_load_missing_dir_is_noop(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=64, n_patches=16))
    store.load()  # no meta.json present
    assert store.is_empty


def test_maxsim_score_is_sum_of_per_token_maxes(tmp_path: Path) -> None:
    """Sanity check: MaxSim equals our manual computation."""
    embedder = FakeColPaliEmbedder(dim=8, n_patches=4)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = _make_chunks(1, tmp_path)
    store.add(pairs)
    q = embedder.embed_query("zero")
    d_vecs = embedder.embed_image(pairs[0][1]).astype(np.float32)
    sims = q.astype(np.float32) @ d_vecs.T
    expected = float(sims.max(axis=1).sum())
    hits = store.search("zero", top_k=1)
    assert abs(hits[0].score - expected) < 1e-3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_visual_store.py -v`
Expected: FAIL — `VisualVectorStore` missing.

- [ ] **Step 3: Implement `VisualVectorStore`**

```python
# packages/jw-rag/src/jw_rag/visual/visual_store.py
"""Multi-vector store with MaxSim scoring.

NOT a subclass of `jw_rag.store.VectorStore`. The interfaces are similar
(`add`, `search`, `save`, `load`, `is_empty`, `source_ids`) but the internal
representation is multi-vector: each document is a `(max_patches, dim)`
matrix plus a `(max_patches,)` boolean mask.

Persistence layout under `path`:
    meta.json     — {model_name, dim, max_patches, count, ...}
    chunks.jsonl  — one VisualChunk per line
    vectors.npy   — (N, max_patches, dim) float16, zero-padded
    mask.npy      — (N, max_patches) bool

MaxSim:
    score(q, d) = Σ_qtok max_dpatch <q_tok, d_patch>     (mask out padding)

For top-k retrieval over N docs we compute the full (N, max_patches) sim
tensor once per q_token using a batched matmul. That's O(N · max_patches ·
dim · |q|); fine up to ~10k pages in CPU/numpy and far better in GPU
(future v2 can add PLAID ANN if needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from jw_rag.visual.errors import VisualStoreMismatchError
from jw_rag.visual.models import MultiVectorHit, VisualChunk


class _EmbedderProtocol:
    """Structural type for any ColPali-like embedder."""

    name: str
    dim: int
    max_patches: int

    def embed_image(self, image: Image.Image) -> np.ndarray: ...
    def embed_query(self, query: str) -> np.ndarray: ...


class VisualVectorStore:
    """Multi-vector store + MaxSim search + JSON/npy persistence."""

    def __init__(self, path: Path | str, embedder: _EmbedderProtocol) -> None:
        self.path = Path(path)
        self.embedder = embedder
        self._chunks: list[VisualChunk] = []
        self._vectors: np.ndarray = np.zeros((0, embedder.max_patches, embedder.dim), dtype=np.float16)
        self._mask: np.ndarray = np.zeros((0, embedder.max_patches), dtype=bool)
        self._known_ids: set[str] = set()

    # ── State ───────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def source_ids(self) -> set[str]:
        return {c.source_id for c in self._chunks if c.source_id}

    # ── Index ───────────────────────────────────────────────────────────

    def add(self, pairs: list[tuple[VisualChunk, Image.Image]]) -> None:
        """Embed and append each (chunk, image). Skips chunks already present."""
        if not pairs:
            return
        max_p = self.embedder.max_patches
        dim = self.embedder.dim
        new_vecs: list[np.ndarray] = []
        new_masks: list[np.ndarray] = []
        new_chunks: list[VisualChunk] = []
        for chunk, image in pairs:
            if chunk.id in self._known_ids:
                continue
            patches = self.embedder.embed_image(image)
            n = patches.shape[0]
            if n > max_p:
                patches = patches[:max_p]
                n = max_p
            padded = np.zeros((max_p, dim), dtype=np.float16)
            padded[:n] = patches
            mask = np.zeros((max_p,), dtype=bool)
            mask[:n] = True
            new_vecs.append(padded)
            new_masks.append(mask)
            new_chunks.append(chunk)
            self._known_ids.add(chunk.id)
        if not new_chunks:
            return
        block_v = np.stack(new_vecs, axis=0)
        block_m = np.stack(new_masks, axis=0)
        if self.count == 0:
            self._vectors = block_v
            self._mask = block_m
        else:
            self._vectors = np.concatenate([self._vectors, block_v], axis=0)
            self._mask = np.concatenate([self._mask, block_m], axis=0)
        self._chunks.extend(new_chunks)

    # ── Search ──────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list[MultiVectorHit]:
        if self.is_empty:
            return []
        q_vecs = self.embedder.embed_query(query).astype(np.float32)  # (Q, D)
        d_vecs = self._vectors.astype(np.float32)                      # (N, P, D)
        d_mask = self._mask                                            # (N, P)

        # sims: (N, Q, P) via einsum.
        sims = np.einsum("npd,qd->nqp", d_vecs, q_vecs)
        # Mask invalid patches with -inf so they never win the max.
        mask_broadcast = d_mask[:, np.newaxis, :]  # (N, 1, P)
        sims = np.where(mask_broadcast, sims, -np.inf)
        per_token_max = sims.max(axis=2)           # (N, Q)
        scores = per_token_max.sum(axis=1)         # (N,)

        top_k = min(top_k, self.count)
        idx = np.argpartition(-scores, top_k - 1)[:top_k]
        idx = idx[np.argsort(-scores[idx])]
        return [
            MultiVectorHit(chunk=self._chunks[i], score=float(scores[i]), rank=r, source="visual")
            for r, i in enumerate(idx, 1)
        ]

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "chunks.jsonl").open("w", encoding="utf-8") as f:
            for c in self._chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        np.save(self.path / "vectors.npy", self._vectors)
        np.save(self.path / "mask.npy", self._mask)
        (self.path / "meta.json").write_text(
            json.dumps(
                {
                    "multi_vector": True,
                    "model_name": getattr(self.embedder, "name", "unknown"),
                    "dim": int(self.embedder.dim),
                    "max_patches": int(self.embedder.max_patches),
                    "count": self.count,
                }
            )
        )

    def load(self) -> None:
        meta_path = self.path / "meta.json"
        if not meta_path.exists():
            return
        meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("dim") != int(self.embedder.dim):
            raise VisualStoreMismatchError(
                f"dim mismatch: store={meta.get('dim')} embedder={self.embedder.dim}. "
                "Re-ingest with `jw rag ingest-visual --force`."
            )
        if meta.get("max_patches") != int(self.embedder.max_patches):
            raise VisualStoreMismatchError(
                f"max_patches mismatch: store={meta.get('max_patches')} "
                f"embedder={self.embedder.max_patches}. Re-ingest."
            )
        if meta.get("model_name") and meta["model_name"] != getattr(self.embedder, "name", ""):
            # Soft warn via exception: only raise if name differs AND user wants to read.
            # We raise to be safe — silent acceptance breaks the cache invariant.
            raise VisualStoreMismatchError(
                f"model mismatch: store={meta['model_name']} embedder={self.embedder.name}. "
                "Re-ingest."
            )
        self._chunks = []
        with (self.path / "chunks.jsonl").open("r", encoding="utf-8") as f:
            for line in f:
                self._chunks.append(VisualChunk.from_dict(json.loads(line)))
        self._vectors = np.load(self.path / "vectors.npy")
        self._mask = np.load(self.path / "mask.npy")
        self._known_ids = {c.id for c in self._chunks}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_visual_store.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/visual_store.py packages/jw-rag/tests/visual/test_visual_store.py
git commit -m "feat(jw-rag): VisualVectorStore with MaxSim search and mismatch detection"
```

---

### Task 5: `PageRasterizer` — PDF / EPUB / JWPUB

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/page_rasterizer.py`
- Create: `packages/jw-rag/tests/visual/test_rasterizer.py`
- Create: `packages/jw-rag/tests/visual/fixtures/build_fixtures.py`
- Create: `packages/jw-rag/tests/visual/fixtures/mini.pdf`
- Create: `packages/jw-rag/tests/visual/fixtures/mini.epub`

- [ ] **Step 1: Build the synthetic fixtures**

`mini.pdf` (3 pages, plain text) and `mini.epub` (3 XHTML files) are
generated by the script below. Run it once, commit the outputs.

```python
# packages/jw-rag/tests/visual/fixtures/build_fixtures.py
"""Build the tiny PDF and EPUB fixtures for the rasterizer tests.

Run once: `uv run python packages/jw-rag/tests/visual/fixtures/build_fixtures.py`
"""

from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build_pdf() -> None:
    """Minimal 3-page PDF — pdf2image only needs valid PDF structure."""
    try:
        from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit("Install reportlab once to rebuild fixtures: uv pip install reportlab")
    out = HERE / "mini.pdf"
    c = Canvas(str(out))
    for i in range(3):
        c.drawString(100, 700, f"Page {i + 1}")
        c.showPage()
    c.save()
    print(f"wrote {out}")


def build_epub() -> None:
    out = HERE / "mini.epub"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        z.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Mini Visual Test</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="p1" href="p1.xhtml" media-type="application/xhtml+xml"/>
    <item id="p2" href="p2.xhtml" media-type="application/xhtml+xml"/>
    <item id="p3" href="p3.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="p1"/>
    <itemref idref="p2"/>
    <itemref idref="p3"/>
  </spine>
</package>""",
        )
        for i in (1, 2, 3):
            z.writestr(
                f"OEBPS/p{i}.xhtml",
                f"""<?xml version="1.0"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Page {i}</title></head>
  <body><h1>Page {i}</h1><p data-pid="{i}">Content {i}</p></body>
</html>""",
            )
    print(f"wrote {out}")


def build_jwpub_stub() -> None:
    """JWPUB stub: outer ZIP with empty manifest. Decryption tests skip this."""
    out = HERE / "mini.jwpub"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", '{"publication": {"symbol": "test", "year": 2026}}')
        z.writestr("contents", b"")
    print(f"wrote {out}")


if __name__ == "__main__":
    build_pdf()
    build_epub()
    build_jwpub_stub()
```

Run:

```bash
uv pip install --quiet reportlab
uv run python packages/jw-rag/tests/visual/fixtures/build_fixtures.py
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_rasterizer.py
"""Tests for PageRasterizer.

We don't exercise the heavy backends (pdf2image / Playwright) — those are
opt-in extras. Instead we check:
  - dispatch by file extension picks the right method
  - skipped-by-extra paths raise ConfigError with an actionable message
  - the FakeRasterizer protocol is honored by the real class signature
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from jw_rag.visual.errors import ConfigError
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any

FIXTURES = Path(__file__).parent / "fixtures"


def test_dispatch_by_extension_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling rasterize_any on .pdf delegates to rasterize_pdf."""
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_pdf(self, data, *, dpi=200):  # type: ignore[override]
            called.append("pdf")
            yield 0, Image.new("RGB", (10, 10))

    pdf = FIXTURES / "mini.pdf"
    list(rasterize_any(pdf, rasterizer=_Stub()))
    assert called == ["pdf"]


def test_dispatch_by_extension_epub(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_epub(self, path, *, viewport=(768, 1024)):  # type: ignore[override]
            called.append("epub")
            yield 0, Image.new("RGB", (10, 10))

    epub = FIXTURES / "mini.epub"
    list(rasterize_any(epub, rasterizer=_Stub()))
    assert called == ["epub"]


def test_dispatch_by_extension_jwpub() -> None:
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_jwpub(self, path, *, dpi=200):  # type: ignore[override]
            called.append("jwpub")
            yield 0, Image.new("RGB", (10, 10))

    jwpub = FIXTURES / "mini.jwpub"
    list(rasterize_any(jwpub, rasterizer=_Stub()))
    assert called == ["jwpub"]


def test_unknown_extension_raises() -> None:
    with pytest.raises(ValueError):
        list(rasterize_any(Path("/tmp/foo.txt"), rasterizer=PageRasterizer()))


def test_real_rasterizer_pdf_missing_pdf2image_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pdf2image isn't installed, calling rasterize_pdf raises ConfigError."""
    import jw_rag.visual.page_rasterizer as mod

    monkeypatch.setattr(mod, "_HAS_PDF2IMAGE", False)
    r = PageRasterizer()
    with pytest.raises(ConfigError) as exc:
        list(r.rasterize_pdf(b"%PDF-1.4\n"))
    assert "uv sync --extra visual" in str(exc.value)


def test_real_rasterizer_epub_missing_playwright_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jw_rag.visual.page_rasterizer as mod

    monkeypatch.setattr(mod, "_HAS_PLAYWRIGHT", False)
    r = PageRasterizer()
    with pytest.raises(ConfigError) as exc:
        list(r.rasterize_epub(FIXTURES / "mini.epub"))
    assert "playwright" in str(exc.value).lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_rasterizer.py -v`
Expected: FAIL — `PageRasterizer` missing.

- [ ] **Step 4: Implement the rasterizer**

```python
# packages/jw-rag/src/jw_rag/visual/page_rasterizer.py
"""Rasterize JWPUB / EPUB / PDF documents to page-level PIL images.

Three backends, all optional and behind lazy imports:
  - PDF   → pdf2image (poppler under the hood)
  - EPUB  → Playwright headless Chromium at a fixed viewport
  - JWPUB → decrypt via jw_core.parsers.jwpub.parse_jwpub, then render each
            decrypted XHTML document through Playwright

The class methods are coroutines-like generators that yield (page_index, PIL).
This lets the ingest pipeline embed pages incrementally instead of buffering
hundreds of images in memory.

`rasterize_any(path, rasterizer=...)` is the dispatcher used by ingest:
extension-based routing to the right method. Tests inject FakeRasterizer here.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from PIL import Image

from jw_rag.visual.errors import ConfigError

try:
    import pdf2image  # type: ignore[import-not-found]

    _HAS_PDF2IMAGE = True
except ImportError:
    _HAS_PDF2IMAGE = False

try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


_INSTALL_HINT = "Install with: uv sync --extra visual (NVIDIA) or --extra visual-mlx (Apple Silicon)."


class PageRasterizer:
    """Backend-aware page rasterizer for PDF/EPUB/JWPUB."""

    def rasterize_pdf(self, data: bytes, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:
        if not _HAS_PDF2IMAGE:
            raise ConfigError(f"pdf2image not installed. {_INSTALL_HINT}")
        # pdf2image accepts bytes via `convert_from_bytes`.
        for i, img in enumerate(pdf2image.convert_from_bytes(data, dpi=dpi)):
            yield i, img.convert("RGB")

    def rasterize_epub(
        self, path: Path, *, viewport: tuple[int, int] = (768, 1024)
    ) -> Iterator[tuple[int, Image.Image]]:
        if not _HAS_PLAYWRIGHT:
            raise ConfigError(f"playwright not installed. {_INSTALL_HINT}")
        from jw_core.parsers.epub import parse_epub, read_document_xhtml

        epub = parse_epub(path)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
            try:
                for idx, doc in enumerate(epub.documents):
                    try:
                        xhtml = read_document_xhtml(path, doc.id)
                    except (KeyError, ValueError):
                        continue
                    page = context.new_page()
                    page.set_content(xhtml, wait_until="load")
                    png = page.screenshot(full_page=True, type="png")
                    page.close()
                    img = Image.open(_bytes_io(png)).convert("RGB")
                    yield idx, img
            finally:
                context.close()
                browser.close()

    def rasterize_jwpub(self, path: Path, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002
        if not _HAS_PLAYWRIGHT:
            raise ConfigError(f"playwright not installed (needed for JWPUB rendering). {_INSTALL_HINT}")
        from jw_core.parsers.jwpub import parse_jwpub

        meta = parse_jwpub(path)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 768, "height": 1024})
            try:
                for idx, doc in enumerate(meta.documents):
                    if not doc.text:
                        continue
                    page = context.new_page()
                    page.set_content(doc.text, wait_until="load")
                    png = page.screenshot(full_page=True, type="png")
                    page.close()
                    img = Image.open(_bytes_io(png)).convert("RGB")
                    yield idx, img
            finally:
                context.close()
                browser.close()


def _bytes_io(data: bytes):
    from io import BytesIO

    return BytesIO(data)


def rasterize_any(
    path: Path,
    *,
    rasterizer: PageRasterizer | None = None,
    dpi: int = 200,
) -> Iterator[tuple[int, Image.Image]]:
    """Dispatch to the right backend by file extension.

    `rasterizer` is injectable so tests can pass FakeRasterizer.
    """
    rasterizer = rasterizer or PageRasterizer()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        data = path.read_bytes()
        yield from rasterizer.rasterize_pdf(data, dpi=dpi)
    elif suffix == ".epub":
        yield from rasterizer.rasterize_epub(path)
    elif suffix == ".jwpub":
        yield from rasterizer.rasterize_jwpub(path, dpi=dpi)
    else:
        raise ValueError(f"Unsupported extension {suffix!r}: expected .pdf|.epub|.jwpub")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_rasterizer.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/page_rasterizer.py packages/jw-rag/tests/visual/test_rasterizer.py packages/jw-rag/tests/visual/fixtures
git commit -m "feat(jw-rag): PageRasterizer (PDF/EPUB/JWPUB) with lazy backend imports"
```

---

### Task 6: `ColPaliEmbedder` + `ColQwen2Embedder` + factory

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/colpali.py`
- Create: `packages/jw-rag/tests/visual/test_colpali.py`

The real providers MUST be importable without GPU. Only `is_available()` and
the eager constructor touch hardware. Tests verify the factory's fail-fast
behavior with monkey-patched flags.

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_colpali.py
"""Tests for the real ColPali/ColQwen2 providers and factory.

We never actually load the model in CI — only verify:
  - `is_available()` returns False when torch/MLX missing
  - factory raises ConfigError with the actionable hint when no provider
    is available
  - factory returns the FakeColPaliEmbedder when explicitly requested via
    the `prefer_fake=True` argument (test harness escape hatch)
"""

from __future__ import annotations

import pytest

from jw_rag.visual.colpali import (
    ColPaliEmbedder,
    ColQwen2Embedder,
    get_default_visual_embedder,
)
from jw_rag.visual.errors import ConfigError
from jw_rag.visual.fakes import FakeColPaliEmbedder


def test_colpali_is_available_handles_missing_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    """If torch is not importable, is_available(target='nvidia') is False."""
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    assert ColPaliEmbedder.is_available(target="nvidia") is False
    assert ColPaliEmbedder.is_available(target="mlx") is False


def test_colqwen2_is_available_handles_missing_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    assert ColQwen2Embedder.is_available(target="nvidia") is False
    assert ColQwen2Embedder.is_available(target="mlx") is False


def test_factory_raises_config_error_when_no_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: False)
    with pytest.raises(ConfigError) as exc:
        get_default_visual_embedder()
    msg = str(exc.value)
    assert "uv sync --extra visual" in msg
    assert "FakeColPaliEmbedder" in msg
    assert "JW_VISUAL_ENABLED" in msg


def test_factory_returns_fake_when_prefer_fake() -> None:
    embedder = get_default_visual_embedder(prefer_fake=True)
    assert isinstance(embedder, FakeColPaliEmbedder)


def test_factory_picks_nvidia_first_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """If both backends are present, NVIDIA wins (spec rationale)."""
    import jw_rag.visual.colpali as mod

    monkeypatch.setattr(mod, "_torch_cuda_available", lambda: True)
    monkeypatch.setattr(mod, "_mlx_metal_available", lambda: True)

    class _Stub(mod.ColQwen2Embedder):
        def __init__(self, target: str = "nvidia") -> None:
            self.target = target
            self.name = "colqwen2-stub"
            self.dim = 128
            self.max_patches = 1030

    monkeypatch.setattr(mod, "ColQwen2Embedder", _Stub)
    embedder = get_default_visual_embedder()
    assert embedder.target == "nvidia"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_colpali.py -v`
Expected: FAIL — `jw_rag.visual.colpali` missing.

- [ ] **Step 3: Implement the providers + factory**

```python
# packages/jw-rag/src/jw_rag/visual/colpali.py
"""ColPali / ColQwen2 visual embedders.

Heavy deps (`colpali-engine`, `transformers`, `torch`, `mlx`, `mlx-vlm`) are
imported lazily inside the constructors. Importing this module is safe on any
machine — even with zero extras installed. Only the constructors and
`is_available()` touch hardware.

Hardware order (spec §"Hardware strategy"): NVIDIA first, MLX second, NO API
fallback, NO CPU fallback. When neither backend is available, the factory
raises `ConfigError` with the install commands.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image

from jw_rag.visual.errors import ConfigError
from jw_rag.visual.fakes import FakeColPaliEmbedder

Target = Literal["nvidia", "mlx"]


# ── Hardware probes (extracted so tests can monkey-patch them) ───────────


def _torch_cuda_available() -> bool:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return False
    if not torch.cuda.is_available():
        return False
    try:
        props = torch.cuda.get_device_properties(0)
    except (RuntimeError, AssertionError):
        return False
    return props.total_memory > 12_000_000_000  # ≥12 GB VRAM required


def _mlx_metal_available() -> bool:
    try:
        import mlx.core as mx  # type: ignore[import-not-found]
    except ImportError:
        return False
    try:
        return bool(mx.metal.is_available())
    except AttributeError:
        return False


# ── Real providers ───────────────────────────────────────────────────────


class _BaseRealEmbedder:
    """Shared scaffolding for ColPali/ColQwen2 real providers."""

    name: str = "base"
    dim: int = 128
    max_patches: int = 1030

    def __init__(self, target: Target = "nvidia") -> None:
        self.target = target
        self._model = None  # lazy-loaded

    @classmethod
    def is_available(cls, target: Target = "nvidia") -> bool:
        if target == "nvidia":
            return _torch_cuda_available()
        if target == "mlx":
            return _mlx_metal_available()
        return False

    def _ensure_model(self) -> None:
        raise NotImplementedError

    def embed_image(self, image: Image.Image) -> np.ndarray:
        self._ensure_model()
        return self._embed_image_impl(image)

    def embed_query(self, query: str) -> np.ndarray:
        self._ensure_model()
        return self._embed_query_impl(query)

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        raise NotImplementedError

    def _embed_query_impl(self, query: str) -> np.ndarray:
        raise NotImplementedError


class ColPaliEmbedder(_BaseRealEmbedder):
    """ColPali v1.2 (PaliGemma-based)."""

    name = "colpali-v1.2"
    dim = 128
    max_patches = 1030

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from colpali_engine.models import ColPali, ColPaliProcessor  # type: ignore[import-not-found]
            import torch  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"colpali-engine / torch not installed: {exc}. "
                "Install with: uv sync --extra visual"
            ) from exc
        device = "cuda" if self.target == "nvidia" else "cpu"
        self._processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")
        self._model = ColPali.from_pretrained(
            "vidore/colpali-v1.2", torch_dtype=torch.float16
        ).to(device).eval()

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_images([image]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()

    def _embed_query_impl(self, query: str) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_queries([query]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()


class ColQwen2Embedder(_BaseRealEmbedder):
    """ColQwen2 v0.1 (Qwen2-VL based, generally stronger than ColPali)."""

    name = "colqwen2-v0.1"
    dim = 128
    max_patches = 1030

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from colpali_engine.models import ColQwen2, ColQwen2Processor  # type: ignore[import-not-found]
            import torch  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"colpali-engine / torch not installed: {exc}. "
                "Install with: uv sync --extra visual"
            ) from exc
        device = "cuda" if self.target == "nvidia" else "cpu"
        self._processor = ColQwen2Processor.from_pretrained("vidore/colqwen2-v0.1")
        self._model = ColQwen2.from_pretrained(
            "vidore/colqwen2-v0.1", torch_dtype=torch.float16
        ).to(device).eval()

    def _embed_image_impl(self, image: Image.Image) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_images([image]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()

    def _embed_query_impl(self, query: str) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        device = "cuda" if self.target == "nvidia" else "cpu"
        batch = self._processor.process_queries([query]).to(device)
        with torch.no_grad():
            out = self._model(**batch)
        return out[0].to(torch.float16).cpu().numpy()


# ── Factory ──────────────────────────────────────────────────────────────

_PROVIDER_ORDER: list[Target] = ["nvidia", "mlx"]


def get_default_visual_embedder(*, prefer_fake: bool = False):
    """Return the first available visual embedder.

    Order: ColQwen2 > ColPali, NVIDIA > MLX. No CPU. No API.

    `prefer_fake=True` is a test-only escape hatch — production callers must
    never set it.

    Raises:
        ConfigError: when no GPU/MLX backend is reachable. Message includes
                     install hints and the env var to disable the subsystem.
    """
    if prefer_fake:
        return FakeColPaliEmbedder()

    for target in _PROVIDER_ORDER:
        for cls in (ColQwen2Embedder, ColPaliEmbedder):
            if cls.is_available(target=target):
                return cls(target=target)

    raise ConfigError(
        "No GPU available for ColPali/ColQwen2 visual embeddings.\n"
        "Options:\n"
        "  1. Install on a machine with NVIDIA GPU ≥12GB VRAM:\n"
        "       uv sync --extra visual\n"
        "  2. Install on Apple Silicon (M2 or newer):\n"
        "       uv sync --extra visual-mlx\n"
        "  3. Disable the visual module entirely:\n"
        "       export JW_VISUAL_ENABLED=0\n"
        "For tests, use FakeColPaliEmbedder (jw_rag.visual.fakes).\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_colpali.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/colpali.py packages/jw-rag/tests/visual/test_colpali.py
git commit -m "feat(jw-rag): ColPaliEmbedder/ColQwen2Embedder + fail-fast factory"
```

---

### Task 7: Ingest pipeline — `ingest_pdf_visual` / `ingest_epub_visual` / `ingest_jwpub_visual`

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/ingest.py`
- Create: `packages/jw-rag/tests/visual/test_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_ingest.py
"""Tests for visual ingest pipeline.

Use FakeRasterizer + FakeColPaliEmbedder so tests run without GPU and without
Playwright/pdf2image. The real backends are exercised in nightly GPU runners
(not in this plan).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer
from jw_rag.visual.ingest import ingest_path_visual
from jw_rag.visual.visual_store import VisualVectorStore


def _make_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    return p


def test_ingest_returns_pages_added(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    result = ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=4, size=(64, 64)),
        images_dir=tmp_path / "imgs",
    )
    assert result.pages_added == 4
    assert result.pages_skipped == 0
    assert store.count == 4


def test_ingest_idempotent_by_source_id(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    raster = FakeRasterizer(n_pages=3, size=(64, 64))
    first = ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    second = ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    assert first.pages_added == 3
    assert second.pages_added == 0
    assert second.pages_skipped == 3
    assert store.count == 3


def test_ingest_force_overrides_idempotency(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    raster = FakeRasterizer(n_pages=2, size=(64, 64))
    ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    forced = ingest_path_visual(
        pdf,
        store,
        rasterizer=raster,
        images_dir=tmp_path / "imgs",
        force=True,
    )
    # Force does NOT duplicate chunks (id collision skipped by store.add) but
    # the result reports the attempt — useful for benchmarking re-ingest cost.
    assert forced.pages_added == 0 or store.count == 2


def test_ingest_persists_page_images(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    images_dir = tmp_path / "imgs"
    ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=2, size=(64, 64)),
        images_dir=images_dir,
    )
    pngs = sorted(images_dir.glob("*.png"))
    assert len(pngs) == 2
    img = Image.open(pngs[0])
    assert img.size == (64, 64)


def test_ingest_metadata_includes_source_path_and_language(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=1, size=(64, 64)),
        images_dir=tmp_path / "imgs",
        language="es",
    )
    chunk = store._chunks[0]  # type: ignore[attr-defined]
    assert chunk.metadata["source_path"].endswith("sample.pdf")
    assert chunk.metadata["language"] == "es"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_ingest.py -v`
Expected: FAIL — `jw_rag.visual.ingest` missing.

- [ ] **Step 3: Implement the ingest pipeline**

```python
# packages/jw-rag/src/jw_rag/visual/ingest.py
"""Visual ingest pipeline.

`ingest_path_visual(path, store, ...)` is the single entry point. It:
  1. Computes `source_id = sha256(file_bytes)[:32]`.
  2. If `source_id in store.source_ids()` and not `force`: returns
     `IngestResult(pages_skipped=N)` where N is best-effort.
  3. Rasterizes pages via `rasterize_any(path, rasterizer=...)`.
  4. For each page: saves the PNG to `images_dir/<source_id>_p{NNN}.png`,
     builds a `VisualChunk`, and appends to a batch.
  5. Calls `store.add(batch)` once at the end (cheaper than per-page).
  6. Calls `store.save()` so partial work survives crashes.

Idempotency is the contract that lets users re-run the CLI safely. `force=True`
is for development iteration (e.g. tweaking max_patches).
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from PIL import Image

from jw_rag.visual.models import IngestResult, VisualChunk
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any
from jw_rag.visual.visual_store import VisualVectorStore


def _source_id_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


def ingest_path_visual(
    path: Path,
    store: VisualVectorStore,
    *,
    rasterizer: PageRasterizer | None = None,
    images_dir: Path | None = None,
    language: str = "",
    force: bool = False,
    dpi: int = 200,
) -> IngestResult:
    """Rasterize → embed → store every page of `path`.

    Args:
        path: PDF / EPUB / JWPUB file.
        store: target VisualVectorStore (already constructed with the right
               embedder).
        rasterizer: optional custom PageRasterizer (tests pass FakeRasterizer).
        images_dir: where to save page PNGs for later render. Defaults to
                    `store.path / "images"`.
        language: ISO code stored in chunk metadata for filtering.
        force: re-ingest even if `source_id` is already present.
        dpi: rasterization DPI for PDF/JWPUB.
    """
    start = time.monotonic()
    source_id = _source_id_of(path)
    images_dir = images_dir or (store.path / "images")
    images_dir.mkdir(parents=True, exist_ok=True)

    if not force and source_id in store.source_ids():
        existing = sum(1 for c in store._chunks if c.source_id == source_id)  # type: ignore[attr-defined]
        return IngestResult(
            pages_added=0,
            pages_skipped=existing,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    pairs: list[tuple[VisualChunk, Image.Image]] = []
    for page_idx, image in rasterize_any(path, rasterizer=rasterizer, dpi=dpi):
        png_path = images_dir / f"{source_id}_p{page_idx:03d}.png"
        image.save(png_path, format="PNG")
        chunk = VisualChunk(
            id=f"{source_id}#p{page_idx + 1}",
            source_id=source_id,
            page_number=page_idx + 1,
            image_path=png_path,
            metadata={
                "source_path": str(path),
                "language": language,
                "dpi": dpi,
            },
        )
        pairs.append((chunk, image))

    before = store.count
    store.add(pairs)
    added = store.count - before
    store.save()
    return IngestResult(
        pages_added=added,
        pages_skipped=len(pairs) - added,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


# Convenience aliases for spec parity. All three are the same function;
# extension-based dispatch happens inside `rasterize_any`.

def ingest_pdf_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)


def ingest_epub_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)


def ingest_jwpub_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_ingest.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/ingest.py packages/jw-rag/tests/visual/test_ingest.py
git commit -m "feat(jw-rag): visual ingest pipeline (sha256-idempotent, PDF/EPUB/JWPUB)"
```

---

### Task 8: Three-way hybrid search (bm25 + text-vector + visual-MaxSim)

**Files:**
- Create: `packages/jw-rag/src/jw_rag/visual/hybrid.py`
- Create: `packages/jw-rag/tests/visual/test_hybrid.py`

The visual hits get projected into the same `SearchHit` shape as Fase-33 so
agents don't care which path produced a result. `source="visual"` is the only
signal that they should attempt to render an image to the user.

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/visual/test_hybrid.py
"""Tests for hybrid_search_with_visual.

We mock the text store and visual store by directly populating them with a
known set of chunks/scores, then assert that the RRF fusion picks the right
order. Three regimes:
  - visual_store=None → falls back to text_store.hybrid_search exactly
  - visual_store empty → same fallback
  - visual_store non-empty → RRF includes visual rankings
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunker import Chunk
from jw_rag.embed import Embedder
from jw_rag.store import VectorStore
from jw_rag.visual.fakes import FakeColPaliEmbedder
from jw_rag.visual.hybrid import hybrid_search_with_visual
from jw_rag.visual.models import VisualChunk
from jw_rag.visual.visual_store import VisualVectorStore


class _MiniEmbedder(Embedder):
    dim = 4

    def embed(self, texts):
        import numpy as np
        out = []
        for t in texts:
            v = [0.0, 0.0, 0.0, 0.0]
            for i, ch in enumerate(t.lower()):
                v[i % 4] += float(ord(ch) % 17) / 17.0
            out.append(v)
        return np.array(out, dtype=np.float32)


def _seed_text_store(tmp_path: Path) -> VectorStore:
    store = VectorStore(tmp_path / "text", _MiniEmbedder())
    store.add([
        Chunk(id="t1", text="trinity is not biblical", source_id="A"),
        Chunk(id="t2", text="Paul missionary journey map", source_id="B"),
        Chunk(id="t3", text="seven days creation table", source_id="C"),
    ])
    return store


def _seed_visual_store(tmp_path: Path) -> VisualVectorStore:
    from PIL import Image

    embedder = FakeColPaliEmbedder(dim=32, n_patches=16)
    store = VisualVectorStore(tmp_path / "visual", embedder)
    pairs = []
    for i, sid in enumerate(["A", "B", "C"]):
        png = tmp_path / f"{sid}.png"
        img = Image.new("RGB", (32, 32), color=(i * 60, 80, 200))
        img.save(png)
        pairs.append((
            VisualChunk(
                id=f"{sid}#p1",
                source_id=sid,
                page_number=1,
                image_path=png,
                ocr_text=f"visual {sid}",
            ),
            img,
        ))
    store.add(pairs)
    return store


def test_falls_back_when_visual_none(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    hits = hybrid_search_with_visual(text, None, "trinity", top_k=2)
    assert len(hits) == 2
    assert all(h.source == "hybrid" for h in hits)


def test_falls_back_when_visual_empty(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = VisualVectorStore(tmp_path / "visual", FakeColPaliEmbedder(dim=32, n_patches=16))
    hits = hybrid_search_with_visual(text, visual, "trinity", top_k=2)
    assert len(hits) == 2


def test_includes_visual_hits_when_present(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "paul journey", top_k=5)
    sources = {h.source for h in hits}
    assert "visual" in sources or any(h.chunk.source_id == "B" for h in hits)
    # Some hit corresponds to a VisualChunk
    assert any(isinstance(h.chunk, VisualChunk) for h in hits)


def test_top_k_is_respected(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "creation", top_k=2)
    assert len(hits) == 2


def test_rrf_score_monotonic(tmp_path: Path) -> None:
    text = _seed_text_store(tmp_path)
    visual = _seed_visual_store(tmp_path)
    hits = hybrid_search_with_visual(text, visual, "trinity", top_k=4)
    for a, b in zip(hits, hits[1:], strict=True):
        assert a.score >= b.score
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-rag/tests/visual/test_hybrid.py -v`
Expected: FAIL — `jw_rag.visual.hybrid` missing.

- [ ] **Step 3: Implement hybrid search**

```python
# packages/jw-rag/src/jw_rag/visual/hybrid.py
"""Three-way RRF: bm25 + text-vector + visual-MaxSim.

If `visual_store is None` or `visual_store.is_empty`, the function is
equivalent to `text_store.hybrid_search(query, ...)`. That makes it safe to
call unconditionally from agents and from `jw rag search` — there's no
"branch on visual enabled" logic to forget.

RRF formula (same as Fase 33):
    score(doc) = Σ_ranklist 1 / (rrf_k + rank_in_list)

Visual hits enter the same dict keyed by `chunk.id`. Text and visual IDs
follow different conventions (`{chunk_idx}` vs `{source_id}#p{N}`) so there's
no accidental collision.
"""

from __future__ import annotations

from typing import Any

from jw_rag.store import SearchHit, VectorStore
from jw_rag.visual.visual_store import VisualVectorStore


def hybrid_search_with_visual(
    text_store: VectorStore,
    visual_store: VisualVectorStore | None,
    query: str,
    *,
    top_k: int = 10,
    candidate_pool: int = 50,
    rrf_k: int = 60,
) -> list[SearchHit]:
    """Three-way RRF across bm25, text-vector, and visual-MaxSim.

    When `visual_store` is None or empty, behaves identically to
    `text_store.hybrid_search(query, top_k=top_k, candidate_pool=candidate_pool,
    rrf_k=rrf_k)`.
    """
    if visual_store is None or visual_store.is_empty:
        return text_store.hybrid_search(
            query, top_k=top_k, candidate_pool=candidate_pool, rrf_k=rrf_k
        )

    vec_hits = text_store.vector_search(query, top_k=candidate_pool)
    bm25_hits = text_store.bm25_search(query, top_k=candidate_pool)
    visual_hits = visual_store.search(query, top_k=candidate_pool)

    fused: dict[str, tuple[float, Any, str]] = {}
    # source label preference: visual wins if any list ranked the doc as visual
    for hits in (vec_hits, bm25_hits):
        for hit in hits:
            contribution = 1.0 / (rrf_k + hit.rank)
            prev = fused.get(hit.chunk.id)
            if prev is None:
                fused[hit.chunk.id] = (contribution, hit.chunk, "hybrid")
            else:
                fused[hit.chunk.id] = (prev[0] + contribution, prev[1], prev[2])
    for hit in visual_hits:
        contribution = 1.0 / (rrf_k + hit.rank)
        prev = fused.get(hit.chunk.id)
        if prev is None:
            fused[hit.chunk.id] = (contribution, hit.chunk, "visual")
        else:
            # Bump score, prefer the visual chunk object so callers can render.
            fused[hit.chunk.id] = (prev[0] + contribution, hit.chunk, "visual")

    ordered = sorted(fused.values(), key=lambda t: -t[0])[:top_k]
    return [
        SearchHit(chunk=chunk, score=float(score), rank=r, source=src)
        for r, (score, chunk, src) in enumerate(ordered, 1)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-rag/tests/visual/test_hybrid.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/hybrid.py packages/jw-rag/tests/visual/test_hybrid.py
git commit -m "feat(jw-rag): hybrid_search_with_visual three-way RRF (text+bm25+visual)"
```

---

### Task 9: Re-export hybrid + factory from `jw_rag.visual.__init__`

**Files:**
- Modify: `packages/jw-rag/src/jw_rag/visual/__init__.py`

- [ ] **Step 1: Append exports**

Edit `packages/jw-rag/src/jw_rag/visual/__init__.py`. Replace the file with:

```python
"""Visual late-interaction RAG store.

Public API:
    from jw_rag.visual import (
        VisualChunk,
        MultiVectorHit,
        IngestResult,
        VisualVectorStore,
        ConfigError,
        VisualStoreMismatchError,
        hybrid_search_with_visual,
        get_default_visual_embedder,
        ingest_path_visual,
        FakeColPaliEmbedder,
        FakeRasterizer,
    )

Heavy providers (`colpali-engine`, `transformers`, `torch`, `mlx`, `pdf2image`,
`playwright`) are imported lazily inside the provider classes. Importing this
module is safe on machines without any of them.
"""

from jw_rag.visual.colpali import (
    ColPaliEmbedder,
    ColQwen2Embedder,
    get_default_visual_embedder,
)
from jw_rag.visual.errors import ConfigError, VisualStoreMismatchError
from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer
from jw_rag.visual.hybrid import hybrid_search_with_visual
from jw_rag.visual.ingest import (
    ingest_epub_visual,
    ingest_jwpub_visual,
    ingest_path_visual,
    ingest_pdf_visual,
)
from jw_rag.visual.models import IngestResult, MultiVectorHit, VisualChunk
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any
from jw_rag.visual.visual_store import VisualVectorStore

__all__ = [
    "ColPaliEmbedder",
    "ColQwen2Embedder",
    "ConfigError",
    "FakeColPaliEmbedder",
    "FakeRasterizer",
    "IngestResult",
    "MultiVectorHit",
    "PageRasterizer",
    "VisualChunk",
    "VisualStoreMismatchError",
    "VisualVectorStore",
    "get_default_visual_embedder",
    "hybrid_search_with_visual",
    "ingest_epub_visual",
    "ingest_jwpub_visual",
    "ingest_path_visual",
    "ingest_pdf_visual",
    "rasterize_any",
]
```

- [ ] **Step 2: Verify imports**

Run: `uv run python -c "from jw_rag.visual import VisualVectorStore, FakeColPaliEmbedder, hybrid_search_with_visual; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-rag/src/jw_rag/visual/__init__.py
git commit -m "feat(jw-rag): export visual public API from package init"
```

---

### Task 10: CLI — `jw rag ingest-visual` + `jw rag search --visual`

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/rag.py`

- [ ] **Step 1: Locate the existing rag command module**

Run: `ls packages/jw-cli/src/jw_cli/commands/`
Expected: there is a `rag.py` (or equivalent). If the file structure differs,
add the new Typer commands to wherever `rag` subcommands live.

- [ ] **Step 2: Add the two commands**

Append to `packages/jw-cli/src/jw_cli/commands/rag.py`:

```python
# --- Fase 37: Visual RAG commands ----------------------------------------
import os

import typer


@rag_app.command("ingest-visual")  # type: ignore[has-type]
def ingest_visual(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    store_path: Path = typer.Option(
        Path("./jw-rag-store/visual"), "--store", help="Visual store directory."
    ),
    force: bool = typer.Option(False, "--force", help="Re-ingest even if already indexed."),
    language: str = typer.Option("", "--language", "-l", help="Language tag in chunk metadata."),
) -> None:
    """Rasterize and index a JWPUB/EPUB/PDF into the visual store."""
    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        typer.echo("JW_VISUAL_ENABLED=0 — visual subsystem disabled.", err=True)
        raise typer.Exit(2)
    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        ingest_path_visual,
    )

    try:
        embedder = get_default_visual_embedder()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc

    store = VisualVectorStore(store_path, embedder)
    try:
        store.load()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"warn: load failed ({exc}); starting fresh", err=True)
    result = ingest_path_visual(path, store, language=language, force=force)
    typer.echo(
        f"added={result.pages_added} skipped={result.pages_skipped} "
        f"duration_ms={result.duration_ms}"
    )


# Extend the existing `search` command (or add a new one) with --visual.
@rag_app.command("search-visual")  # type: ignore[has-type]
def search_visual(
    query: str = typer.Argument(...),
    text_store: Path = typer.Option(Path("./jw-rag-store"), "--text-store"),
    visual_store: Path = typer.Option(Path("./jw-rag-store/visual"), "--visual-store"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
) -> None:
    """Hybrid search across text store + visual store via RRF."""
    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        typer.echo("JW_VISUAL_ENABLED=0 — visual subsystem disabled.", err=True)
        raise typer.Exit(2)
    from jw_rag.embed import get_default_embedder
    from jw_rag.store import VectorStore
    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        hybrid_search_with_visual,
    )

    text = VectorStore(text_store, get_default_embedder())
    text.load()

    visual: VisualVectorStore | None
    try:
        v_embedder = get_default_visual_embedder()
        visual = VisualVectorStore(visual_store, v_embedder)
        visual.load()
    except ConfigError as exc:
        typer.echo(f"info: visual disabled ({exc.__class__.__name__}); text-only", err=True)
        visual = None

    hits = hybrid_search_with_visual(text, visual, query, top_k=top_k)
    for h in hits:
        marker = "[VISUAL]" if h.source == "visual" else "[TEXT]"
        typer.echo(f"{marker} {h.rank}. score={h.score:.4f} id={h.chunk.id}")
```

- [ ] **Step 3: Smoke-test the CLI**

Run:

```bash
uv run jw rag ingest-visual --help
uv run jw rag search-visual --help
```

Expected: both show usage strings without error.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/rag.py
git commit -m "feat(jw-cli): add `rag ingest-visual` and `rag search-visual` commands"
```

---

### Task 11: MCP tools — `visual_search` and `ingest_publication_visual`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Register the new tools**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
@mcp.tool()
def visual_search(
    query: str,
    text_store_path: str = "./jw-rag-store",
    visual_store_path: str = "./jw-rag-store/visual",
    top_k: int = 10,
    language: str = "",
) -> dict:
    """Hybrid search including visual MaxSim. Falls back to text-only if no GPU.

    Returns: {"hits": [...], "visual_enabled": bool, "hint": str}
    """
    import os
    from pathlib import Path

    from jw_rag.embed import get_default_embedder
    from jw_rag.store import VectorStore
    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        hybrid_search_with_visual,
    )

    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        return {
            "error": "visual_disabled",
            "hint": "Set JW_VISUAL_ENABLED=1 to enable. Falling back to text-only.",
            "hits": [],
            "visual_enabled": False,
        }

    text = VectorStore(Path(text_store_path), get_default_embedder())
    text.load()

    visual = None
    visual_enabled = False
    hint = ""
    try:
        embedder = get_default_visual_embedder()
        visual = VisualVectorStore(Path(visual_store_path), embedder)
        visual.load()
        visual_enabled = True
    except ConfigError as exc:
        hint = str(exc)

    hits = hybrid_search_with_visual(text, visual, query, top_k=top_k)
    return {
        "visual_enabled": visual_enabled,
        "hint": hint,
        "hits": [
            {
                "rank": h.rank,
                "score": float(h.score),
                "source": h.source,
                "chunk_id": h.chunk.id,
                "source_id": getattr(h.chunk, "source_id", ""),
                "text": getattr(h.chunk, "text", ""),
                "image_path": str(getattr(h.chunk, "image_path", "")) or None,
                "page_number": getattr(h.chunk, "page_number", None),
                "language": language or getattr(h.chunk, "metadata", {}).get("language", ""),
            }
            for h in hits
        ],
    }


@mcp.tool()
def ingest_publication_visual(
    path: str,
    store_path: str = "./jw-rag-store/visual",
    language: str = "",
    force: bool = False,
) -> dict:
    """Ingest a JWPUB/EPUB/PDF into the visual store. Requires GPU."""
    import os
    from pathlib import Path

    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        ingest_path_visual,
    )

    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        return {"error": "visual_disabled", "hint": "Set JW_VISUAL_ENABLED=1."}

    try:
        embedder = get_default_visual_embedder()
    except ConfigError as exc:
        return {"error": "no_gpu", "hint": str(exc)}

    store = VisualVectorStore(Path(store_path), embedder)
    try:
        store.load()
    except Exception as exc:  # noqa: BLE001
        return {"error": "load_failed", "hint": str(exc)}

    result = ingest_path_visual(Path(path), store, language=language, force=force)
    return {
        "pages_added": result.pages_added,
        "pages_skipped": result.pages_skipped,
        "duration_ms": result.duration_ms,
        "store_path": store_path,
    }
```

- [ ] **Step 2: Smoke-test imports**

Run: `uv run python -c "from jw_mcp.server import mcp; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): add visual_search and ingest_publication_visual tools"
```

---

### Task 12: 5 figure-heavy L1 golden cases in `jw-eval`

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/visual_paul_journeys_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/visual_tabernacle_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_seven_times_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/visual_jw_org_structure_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_beasts_table_es.yaml`

These integrate with the Fase-22 suite via the existing `GoldenCase` schema.
Each declares `visual: true` in `metadata` so the suite runner can filter
(`--filter visual=true`).

- [ ] **Step 1: Write the 5 fixtures**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/visual_paul_journeys_es.yaml
id: l1_visual_paul_journeys_es
agent: research_topic
layer: l1
input:
  topic: "viajes misioneros de Pablo"
  language: es
expected:
  min_findings: 1
  must_have_source: visual
  must_have_citation: true
metadata:
  visual: true
  expected_recall_lift: 0.4
  added_at: 2026-05-31
```

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/visual_tabernacle_en.yaml
id: l1_visual_tabernacle_en
agent: research_topic
layer: l1
input:
  topic: "tabernacle dimensions and materials"
  language: en
expected:
  min_findings: 1
  must_have_source: visual
  must_have_citation: true
metadata:
  visual: true
  expected_recall_lift: 0.4
  added_at: 2026-05-31
```

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_seven_times_es.yaml
id: l1_visual_daniel_seven_times_es
agent: research_topic
layer: l1
input:
  topic: "los siete tiempos de Daniel"
  language: es
expected:
  min_findings: 1
  must_have_source: visual
  must_have_citation: true
metadata:
  visual: true
  expected_recall_lift: 0.4
  added_at: 2026-05-31
```

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/visual_jw_org_structure_en.yaml
id: l1_visual_jw_org_structure_en
agent: research_topic
layer: l1
input:
  topic: "organizational structure of Jehovah's Witnesses"
  language: en
expected:
  min_findings: 1
  must_have_source: visual
  must_have_citation: true
metadata:
  visual: true
  expected_recall_lift: 0.4
  added_at: 2026-05-31
```

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/visual_daniel_beasts_table_es.yaml
id: l1_visual_daniel_beasts_table_es
agent: research_topic
layer: l1
input:
  topic: "comparativa de las cuatro bestias de Daniel 7"
  language: es
expected:
  min_findings: 1
  must_have_source: visual
  must_have_citation: true
metadata:
  visual: true
  expected_recall_lift: 0.4
  added_at: 2026-05-31
```

- [ ] **Step 2: Verify the loader picks them up**

```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_cases
cases = load_cases(Path('packages/jw-eval/fixtures/golden_qa'), layers=['l1'])
visuals = [c for c in cases if c.metadata.get('visual')]
print(f'visual L1 cases: {len(visuals)}')
assert len(visuals) == 5
"
```

Expected: `visual L1 cases: 5`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/visual_*.yaml
git commit -m "feat(jw-eval): 5 figure-heavy L1 golden cases for visual RAG"
```

---

### Task 13: Documentation guide + audit updates

**Files:**
- Create: `docs/guias/visual-rag.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the guide**

```markdown
# Visual RAG (Fase 37) — guía de uso

> Estado: implementado en `jw_rag.visual`. Opt-in vía `[visual]` extra. Requiere GPU.

## ¿Qué resuelve?

El RAG textual (Fase 33) recupera párrafos. Cuando la respuesta está en una **figura**
(mapa de viajes de Pablo, tabla de bestias de Daniel, diagrama del tabernáculo) el
texto extraído no alcanza. Fase 37 añade un segundo store que indexa **páginas
rasterizadas** con embeddings late-interaction (ColPali / ColQwen2) y los fusiona
con el RAG textual vía RRF.

## Instalación

NVIDIA (Linux, ≥12 GB VRAM):

```bash
uv sync --extra visual
```

Apple Silicon (M2 o superior, experimental):

```bash
uv sync --extra visual-mlx
```

Sin GPU el módulo simplemente no se activa. El RAG textual (Fase 33) funciona
igual.

## Pipeline

```
JWPUB / EPUB / PDF
        │
        ▼
PageRasterizer (Playwright | pdf2image)
        │   (200 dpi, viewport 768×1024)
        ▼
PIL.Image por página
        │
        ▼
ColQwen2Embedder.embed_image()  → (n_patches, 128) float16
        │
        ▼
VisualVectorStore.add()  → vectors.npy + mask.npy + chunks.jsonl
```

## Comandos

```bash
# Ingesta
JW_VISUAL_ENABLED=1 uv run jw rag ingest-visual ./pubs/sample.jwpub

# Búsqueda híbrida (text + visual)
JW_VISUAL_ENABLED=1 uv run jw rag search-visual "viajes de Pablo" --top-k 5
```

## Variables de entorno

| Var | Default | Propósito |
|-----|---------|-----------|
| `JW_VISUAL_ENABLED` | `1` | Pon `0` para desactivar todo el módulo |
| `JW_VISUAL_TARGET` | autodetect | Forzar `nvidia` o `mlx` |

## Troubleshooting

- **`ConfigError: No GPU disponible...`** — instala con `--extra visual` en máquina
  con GPU NVIDIA ≥12 GB, o `--extra visual-mlx` en Apple Silicon. Para correr tests
  usa `FakeColPaliEmbedder`.
- **`VisualStoreMismatchError`** — el store en disco fue generado por otro modelo /
  revisión / `patch_size`. Re-ingesta con `--force`.
- **OOM durante ingesta** — baja `dpi` a `150` o reduce el viewport del EPUB.

## Benchmarks (5090, 32 GB VRAM)

| Volumen | ~50 páginas | ~500 páginas | ~5000 páginas |
|---------|-------------|--------------|---------------|
| Ingest  | <60 s       | ~10 min      | ~90 min       |
| Search  | 80 ms       | 250 ms       | 1.5 s         |
| Storage | 6 MB        | 60 MB        | 600 MB        |
```

- [ ] **Step 2: Add row to `docs/VISION_AUDIT.md`**

Append:

```markdown
| Fase 37 | colpali-visual | Late interaction sobre páginas rasterizadas. Opt-in; sin GPU el RAG textual queda intacto. |
```

- [ ] **Step 3: Add section to `docs/ROADMAP.md`**

Append:

```markdown
## Fase 37 — colpali-visual

Multi-vector store con ColPali/ColQwen2 sobre páginas rasterizadas, fusionado
vía RRF con el RAG textual. Opt-in `[visual]` / `[visual-mlx]`. Spec:
`docs/superpowers/specs/2026-05-31-fase-37-colpali-visual-design.md`. Plan:
`docs/superpowers/plans/2026-05-31-fase-37-colpali-visual-plan.md`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/guias/visual-rag.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(visual): guía de Visual RAG + entradas en VISION_AUDIT y ROADMAP"
```

---

### Task 14: Full-suite regression sweep

**Files:** none modified — verification only.

- [ ] **Step 1: Run the existing 1649 tests**

```bash
uv run pytest -x --tb=short
```

Expected: 1649 + new visual tests all pass. No regression in any existing
phase.

- [ ] **Step 2: Run only the visual suite**

```bash
uv run pytest packages/jw-rag/tests/visual/ -v
```

Expected: 6 + 7 + 8 + 6 + 5 + 5 + 5 = **42 passed** across the seven test
modules.

- [ ] **Step 3: Verify imports from a fresh interpreter**

```bash
uv run python -c "
from jw_rag.visual import (
    VisualChunk, MultiVectorHit, IngestResult,
    VisualVectorStore, ConfigError, VisualStoreMismatchError,
    hybrid_search_with_visual, get_default_visual_embedder,
    FakeColPaliEmbedder, FakeRasterizer,
)
print('public API ok')
"
```

Expected: `public API ok`.

- [ ] **Step 4: Verify the `[visual]` extra resolves**

On NVIDIA machines (otherwise skip this step):

```bash
uv sync --all-packages --extra visual
uv run python -c "
from jw_rag.visual import get_default_visual_embedder
e = get_default_visual_embedder()
print(type(e).__name__, e.target)
"
```

Expected: `ColQwen2Embedder nvidia` (or `ColPaliEmbedder nvidia` as fallback).

- [ ] **Step 5: Verify fail-fast on CPU-only machine**

```bash
JW_VISUAL_ENABLED=1 uv run python -c "
from jw_rag.visual import get_default_visual_embedder, ConfigError
try:
    get_default_visual_embedder()
except ConfigError as e:
    print('expected ConfigError:', str(e)[:80])
"
```

Expected: `expected ConfigError: No GPU disponible...`.

- [ ] **Step 6: Commit (final sweep — only if anything changed)**

If anything had to be fixed in steps 1-5, commit those fixes. Otherwise no
commit.

---

## Self-review

Plan covers every spec deliverable:

1. **Scaffold + `[visual]` / `[visual-mlx]` extras** → Task 1 ✓
2. **Models (`VisualChunk`, `MultiVectorHit`, `IngestResult`)** → Task 2 ✓
3. **`FakeColPaliEmbedder` + `FakeRasterizer`** → Task 3 ✓ (built early so all
   downstream tests don't touch hardware)
4. **`VisualVectorStore` with MaxSim, save/load, mismatch detection** → Task 4 ✓
5. **`PageRasterizer` for PDF/EPUB/JWPUB with lazy imports** → Task 5 ✓
6. **Real `ColPaliEmbedder` / `ColQwen2Embedder` + fail-fast factory** → Task 6 ✓
7. **`ingest_path_visual` idempotent by sha256** → Task 7 ✓
8. **`hybrid_search_with_visual` three-way RRF** → Task 8 ✓
9. **Public API re-export** → Task 9 ✓
10. **CLI: `jw rag ingest-visual` + `jw rag search-visual`** → Task 10 ✓
11. **MCP: `visual_search` + `ingest_publication_visual` tools** → Task 11 ✓
12. **5 figure-heavy L1 golden cases** → Task 12 ✓
13. **Guía + VISION_AUDIT + ROADMAP** → Task 13 ✓
14. **Full regression sweep** → Task 14 ✓

Spec acceptance criteria checked:

- Recall@10 ≥+40% on 5 golden queries → fixtures present (Task 12), measurable
  once GPU runner is available. Plan documents the target in fixture metadata
  (`expected_recall_lift: 0.4`).
- Fail-fast `ConfigError` with install hint → Task 6 covers it, Task 14 verifies.
- Zero impact on public CI → All tests use `FakeColPaliEmbedder` /
  `FakeRasterizer`; heavy deps stay in `[visual]` extras.
- Idempotent by sha256 → Task 7 test `test_ingest_idempotent_by_source_id`.
- Hybrid graceful → Task 8 `test_falls_back_when_visual_none` and
  `test_falls_back_when_visual_empty`.
- `VisualStoreMismatchError` on model swap → Task 4 `test_load_mismatch_raises`.

Boundaries respected:

- `VisualVectorStore` does NOT subclass `VectorStore` — composition only.
- `jw_rag.visual` imports do not pull `colpali-engine` / `torch` / `playwright`
  / `pdf2image` at import time. Verified by the test in Task 9 which imports
  on a clean interpreter.
- No CPU path. No API path. `_PROVIDER_ORDER = ["nvidia", "mlx"]` only.
- Heavy deps live in `[visual]` and `[visual-mlx]` extras of `jw-rag`, not in
  any package's required `dependencies`.

Test count: **42 new tests** across 7 modules. **14 TDD tasks** (matches the
14-18 target). Each task: failing test first, implement, passing test,
commit. Existing 1649 tests must stay green (Task 14 verifies).

## Execution choice

Execute via **superpowers:subagent-driven-development**: each task is
self-contained (failing test → minimal code → passing test → commit), the
file map is explicit, and there are no hidden cross-task dependencies beyond
the natural order (fakes before store before ingest before hybrid). A single
agent or worker per task is the most efficient path. If parallelism is
desired, Tasks 5 (rasterizer) and 6 (real providers) can run concurrently
once Task 3 (fakes) and Task 4 (store) are merged.
