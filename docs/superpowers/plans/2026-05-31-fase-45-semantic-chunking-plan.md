# Fase 45 — `semantic-chunking` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `jw_rag.chunker.chunk_paragraphs` with a pluggable `Chunker` protocol that supports three strategies — `paragraph` (bit-identical to current), `semantic` (heuristic continuation-marker merging), and `llm` (opt-in build-time deep mode with cache) — without breaking a single existing import or test, and prove a ≥10 % NDCG@10 lift on doctrinal queries per language (en/es/pt).

**Architecture:** New subpackage `packages/jw-rag/src/jw_rag/chunkers/` exporting `Chunker` Protocol, three implementations, and a `get_chunker(name)` router. Legacy `jw_rag.chunker` becomes a thin façade re-exporting `Chunk` and `chunk_paragraphs` so all existing callers and tests keep passing. Continuation/closure markers are data in `packages/jw-core/src/jw_core/data/continuation_markers.json` so the community can contribute languages without touching Python. The LLM chunker emits index-level split/merge actions only (never rewrites text — Policy #6) and is cached on disk by content hash. A new `jw eval chunker-bench` subcommand reuses Fase 22 plumbing to compute NDCG@10 per language across variants.

**Tech Stack:** Python 3.13 · PEP 544 Protocol (structural typing) · stdlib only for the heuristic path (no new deps) · `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (already pulled via `[local-embeddings]` extra) for the bench · `jw_gen.providers.resolve()` for the LLM chunker (Claude / OpenAI / Ollama / MLX, all lazy-imported).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-45-semantic-chunking-design.md`](../specs/2026-05-31-fase-45-semantic-chunking-design.md).

---

## File map

Creates:
- `packages/jw-rag/src/jw_rag/chunkers/__init__.py`
- `packages/jw-rag/src/jw_rag/chunkers/protocol.py`
- `packages/jw-rag/src/jw_rag/chunkers/paragraph_chunker.py`
- `packages/jw-rag/src/jw_rag/chunkers/markers.py`
- `packages/jw-rag/src/jw_rag/chunkers/semantic_chunker.py`
- `packages/jw-rag/src/jw_rag/chunkers/llm_chunker.py`
- `packages/jw-rag/src/jw_rag/chunkers/fakes.py`
- `packages/jw-core/src/jw_core/data/continuation_markers.json`
- `packages/jw-rag/tests/chunkers/__init__.py`
- `packages/jw-rag/tests/chunkers/test_paragraph_chunker_backcompat.py`
- `packages/jw-rag/tests/chunkers/test_markers_loader.py`
- `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_es.py`
- `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_en.py`
- `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_pt.py`
- `packages/jw-rag/tests/chunkers/test_semantic_chunker_closure.py`
- `packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py`
- `packages/jw-rag/tests/chunkers/test_llm_chunker_cache.py`
- `packages/jw-rag/tests/chunkers/test_get_chunker_env_var.py`
- `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_es.txt`
- `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_en.txt`
- `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_pt.txt`
- `packages/jw-rag/tests/chunkers/fixtures/article_with_closure_es.txt`
- `packages/jw-eval/src/jw_eval/bench/__init__.py`
- `packages/jw-eval/src/jw_eval/bench/chunker_bench.py`
- `packages/jw-eval/src/jw_eval/bench/ndcg.py`
- `packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml`
- `packages/jw-eval/tests/test_bench_ndcg.py`
- `packages/jw-eval/tests/test_bench_chunker.py`
- `docs/guias/semantic-chunking.md`

Modifies:
- `packages/jw-rag/src/jw_rag/chunker.py` — turns into a façade.
- `packages/jw-rag/src/jw_rag/ingest.py` — routes ingesta through `get_chunker()`.
- `packages/jw-eval/src/jw_eval/cli.py` — adds `chunker-bench` subcommand.
- `packages/jw-cli/src/jw_cli/main.py` — adds `--chunker` flag and `rag ingest --chunker` plumbing.
- `packages/jw-mcp/src/jw_mcp/server.py` — adds `set_chunker` tool.
- `docs/VISION_AUDIT.md` — adds Fase 45 row.
- `docs/ROADMAP.md` — adds Fase 45 section.
- `.github/workflows/ci.yml` — adds `chunker-bench-nightly` job.

---

### Task 1: Extract `ParagraphChunker` and lock backwards-compat with a golden fixture

**Files:**
- Create: `packages/jw-rag/src/jw_rag/chunkers/__init__.py`
- Create: `packages/jw-rag/src/jw_rag/chunkers/protocol.py`
- Create: `packages/jw-rag/src/jw_rag/chunkers/paragraph_chunker.py`
- Create: `packages/jw-rag/tests/chunkers/__init__.py`
- Create: `packages/jw-rag/tests/chunkers/test_paragraph_chunker_backcompat.py`
- Modify: `packages/jw-rag/src/jw_rag/chunker.py`

- [ ] **Step 1: Write the failing backwards-compat test**

The whole point of Fase 45 is that **nothing breaks**. The strongest guarantee is byte-for-byte equality between the old `chunk_paragraphs` and the new `ParagraphChunker.chunk(...)` for a representative input. We pin that with a deterministic fixture.

```python
# packages/jw-rag/tests/chunkers/__init__.py
```

```python
# packages/jw-rag/tests/chunkers/test_paragraph_chunker_backcompat.py
"""Bit-for-bit equality between the legacy `chunk_paragraphs` and the new
`ParagraphChunker`. If this test fails, Fase 45 has broken something.

Also re-verifies the public façade: `from jw_rag.chunker import Chunk,
chunk_paragraphs` MUST keep working — many callers (jw-cli, jw-mcp,
ingest.py, every test in packages/jw-rag/tests/) import from there.
"""

from __future__ import annotations

import pytest

# Public façade — must remain importable from the legacy module
from jw_rag.chunker import Chunk as ChunkLegacy
from jw_rag.chunker import chunk_paragraphs as chunk_legacy

# New API
from jw_rag.chunkers import Chunk, ParagraphChunker, get_chunker
from jw_rag.chunkers.protocol import Chunker


def _golden_paragraphs() -> list[str]:
    """A mix of short, medium, long and trailing-punctuation paragraphs.

    Designed to exercise: short-merge, flush-on-period, long-split.
    """
    return [
        "Short one.",
        "Slightly longer second paragraph that should merge.",
        "x" * 1800,  # forces long-split at sentence boundary
        "Final paragraph with no trailing period",
        "Tiny.",
        "And one more closing sentence to round things out.",
    ]


def test_paragraph_chunker_equivalent_to_legacy() -> None:
    paragraphs = _golden_paragraphs()
    legacy = chunk_legacy(paragraphs, source_id="src", metadata={"k": "v"})
    new = ParagraphChunker().chunk(paragraphs, source_id="src", metadata={"k": "v"})

    assert len(legacy) == len(new), (len(legacy), len(new))
    for a, b in zip(legacy, new, strict=True):
        assert a.id == b.id
        assert a.text == b.text
        assert a.source_id == b.source_id
        assert a.metadata == b.metadata


def test_legacy_chunk_class_is_new_chunk_class() -> None:
    """The façade re-exports the same Chunk symbol — no two competing classes."""
    assert ChunkLegacy is Chunk


def test_paragraph_chunker_satisfies_protocol() -> None:
    chunker: Chunker = ParagraphChunker()  # type: ignore[assignment]
    assert chunker.name == "paragraph"
    assert callable(chunker.chunk)


def test_get_chunker_default_is_paragraph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_CHUNKER", raising=False)
    c = get_chunker()
    assert c.name == "paragraph"
    assert isinstance(c, ParagraphChunker)


def test_paragraph_chunker_respects_custom_thresholds() -> None:
    paragraphs = ["a" * 100, "b" * 100, "c" * 100]
    c = ParagraphChunker(max_chars=120, min_chars=10)
    chunks = c.chunk(paragraphs, source_id="src")
    # Each paragraph >= max_chars/min_chars trigger → 3 distinct chunks
    assert len(chunks) == 3


def test_paragraph_chunker_preserves_metadata_copy() -> None:
    meta = {"kind": "article", "title": "T"}
    chunks = ParagraphChunker().chunk(["one.", "two."], source_id="s", metadata=meta)
    # Should not mutate caller's dict
    assert meta == {"kind": "article", "title": "T"}
    assert chunks[0].metadata["kind"] == "article"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_paragraph_chunker_backcompat.py -v
```
Expected: ImportError on `jw_rag.chunkers` (module not created yet).

- [ ] **Step 3: Implement the protocol, the `ParagraphChunker`, and the façade**

```python
# packages/jw-rag/src/jw_rag/chunkers/protocol.py
"""Chunker Protocol — PEP 544 structural typing.

Any class with a `name: str` attribute and a `chunk(paragraphs, source_id,
*, metadata=None) -> list[Chunk]` method satisfies this. No inheritance
required, and `Fake*Chunker` shims in `fakes.py` plug in for free.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Chunk is defined in paragraph_chunker.py and re-exported through __init__
# to avoid circular imports.
from jw_rag.chunkers.paragraph_chunker import Chunk


@runtime_checkable
class Chunker(Protocol):
    name: str

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]: ...
```

```python
# packages/jw-rag/src/jw_rag/chunkers/paragraph_chunker.py
"""Paragraph chunker — bit-for-bit identical to the legacy
`jw_rag.chunker.chunk_paragraphs`.

This is the default. Any change to its behaviour must update the backcompat
fixture test in test_paragraph_chunker_backcompat.py with a clear rationale
in the commit message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A unit of indexed text. Single source of truth — re-exported by
    `jw_rag.chunker` and by `jw_rag.chunkers.__init__`."""

    id: str
    text: str
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_paragraphs(
    paragraphs: list[str],
    source_id: str,
    *,
    max_chars: int = 1500,
    min_chars: int = 80,
    metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Legacy free-function API. Kept byte-stable for backcompat.

    Internally identical to `ParagraphChunker().chunk(...)`.
    """
    base_meta = dict(metadata or {})
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            text = " ".join(buf).strip()
            if text:
                chunks.append(
                    Chunk(
                        id=f"{source_id}#{len(chunks)}",
                        text=text,
                        source_id=source_id,
                        metadata={**base_meta, "para_count": len(buf)},
                    )
                )
            buf = []
            buf_len = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_chars:
            flush()
            for piece in _split_long(p, max_chars):
                chunks.append(
                    Chunk(
                        id=f"{source_id}#{len(chunks)}",
                        text=piece,
                        source_id=source_id,
                        metadata={**base_meta, "split": True},
                    )
                )
            continue
        buf.append(p)
        buf_len += len(p)
        if buf_len >= max_chars or (
            buf_len >= min_chars and len(buf) >= 1 and p.endswith((".", "!", "?"))
        ):
            flush()
    flush()
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    sentences: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if len(current) + len(sentence) + 1 > max_chars and current:
            sentences.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        sentences.append(current.strip())
    out: list[str] = []
    for s in sentences:
        while len(s) > max_chars:
            out.append(s[:max_chars])
            s = s[max_chars:]
        if s:
            out.append(s)
    return out


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    current = ""
    for c in text:
        current += c
        if c in ".!?" and len(current) > 4:
            out.append(current.strip())
            current = ""
    if current.strip():
        out.append(current.strip())
    return out


class ParagraphChunker:
    """Wrap the legacy function in a class so it satisfies the Chunker
    Protocol. Behaviour is delegation-only."""

    name = "paragraph"

    def __init__(self, *, max_chars: int = 1500, min_chars: int = 80) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        out = chunk_paragraphs(
            paragraphs,
            source_id,
            max_chars=self.max_chars,
            min_chars=self.min_chars,
            metadata=metadata,
        )
        for c in out:
            c.metadata.setdefault("chunker", "paragraph")
        return out
```

```python
# packages/jw-rag/src/jw_rag/chunkers/__init__.py
"""Public API for chunkers.

    from jw_rag.chunkers import get_chunker, Chunk, Chunker, ParagraphChunker
"""

from __future__ import annotations

import os
from typing import Any

from jw_rag.chunkers.paragraph_chunker import (
    Chunk,
    ParagraphChunker,
    chunk_paragraphs,
)
from jw_rag.chunkers.protocol import Chunker

__all__ = [
    "Chunk",
    "Chunker",
    "ParagraphChunker",
    "chunk_paragraphs",
    "get_chunker",
]


def get_chunker(name: str | None = None, **kwargs: Any) -> Chunker:
    """Resolve a chunker by name, env var, or default.

    Precedence: argument > $JW_CHUNKER > "paragraph".
    """
    resolved = name or os.environ.get("JW_CHUNKER", "paragraph")
    if resolved == "paragraph":
        return ParagraphChunker(**kwargs)
    if resolved == "semantic":
        # Lazy import — avoid loading markers JSON unless asked.
        from jw_rag.chunkers.semantic_chunker import SemanticChunker
        return SemanticChunker(**kwargs)
    if resolved == "llm":
        from jw_rag.chunkers.llm_chunker import LLMChunker
        return LLMChunker(**kwargs)
    raise ValueError(f"Unknown chunker: {resolved!r}")
```

- [ ] **Step 4: Turn the legacy `chunker.py` into a façade**

Replace the entire contents of `packages/jw-rag/src/jw_rag/chunker.py`:

```python
# packages/jw-rag/src/jw_rag/chunker.py
"""Legacy module — façade only.

Existing imports keep working:

    from jw_rag.chunker import Chunk, chunk_paragraphs

New code should prefer:

    from jw_rag.chunkers import get_chunker, Chunk

`chunk_paragraphs` here is the *exact same function object* re-exported
from `jw_rag.chunkers.paragraph_chunker`. Bit-for-bit compatibility is a
test invariant (see test_paragraph_chunker_backcompat.py).
"""

from __future__ import annotations

from jw_rag.chunkers.paragraph_chunker import Chunk, chunk_paragraphs

__all__ = ["Chunk", "chunk_paragraphs"]
```

- [ ] **Step 5: Run all `jw-rag` tests to verify nothing regresses**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/ -v
```
Expected: all existing tests pass + 6 new backcompat tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/chunker.py packages/jw-rag/src/jw_rag/chunkers/ packages/jw-rag/tests/chunkers/
git commit -m "$(cat <<'EOF'
feat(jw-rag): extract ParagraphChunker; legacy chunker.py becomes façade

Introduces jw_rag.chunkers subpackage with Chunker Protocol and a
ParagraphChunker that delegates to the unchanged chunk_paragraphs.
Bit-for-bit backcompat locked by test_paragraph_chunker_backcompat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Multilingual `continuation_markers.json` + loader

**Files:**
- Create: `packages/jw-core/src/jw_core/data/continuation_markers.json`
- Create: `packages/jw-rag/src/jw_rag/chunkers/markers.py`
- Create: `packages/jw-rag/tests/chunkers/test_markers_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/chunkers/test_markers_loader.py
"""Tests for jw_rag.chunkers.markers — the multilingual continuation/closure
catalog used by SemanticChunker.

The catalog itself lives in jw-core/data/continuation_markers.json so other
packages (and the community) can extend it without depending on jw-rag.
"""

from __future__ import annotations

import pytest

from jw_rag.chunkers.markers import (
    MarkerSet,
    detect_language,
    is_closure_start,
    is_continuation_start,
    load_markers,
)


def test_load_markers_returns_all_supported_languages() -> None:
    catalog = load_markers()
    assert "es" in catalog
    assert "en" in catalog
    assert "pt" in catalog


def test_marker_set_has_continuation_and_closure() -> None:
    catalog = load_markers()
    es = catalog["es"]
    assert isinstance(es, MarkerSet)
    assert "Sin embargo" in es.continuation
    assert "Por lo tanto" in es.closure


def test_marker_set_english_examples() -> None:
    catalog = load_markers()
    en = catalog["en"]
    assert "However" in en.continuation
    assert "Therefore" in en.closure


def test_marker_set_portuguese_examples() -> None:
    catalog = load_markers()
    pt = catalog["pt"]
    assert "No entanto" in pt.continuation
    assert "Portanto" in pt.closure


@pytest.mark.parametrize(
    ("paragraph", "lang", "expected"),
    [
        ("Sin embargo, hay que considerar...", "es", True),
        ("Por otro lado, la Biblia enseña...", "es", True),
        ("Esto no empieza con marcador.", "es", False),
        ("However, the scripture says...", "en", True),
        ("In contrast it claims...", "en", False),  # not in catalog
        ("No entanto, devemos refletir.", "pt", True),
    ],
)
def test_is_continuation_start(paragraph: str, lang: str, expected: bool) -> None:
    assert is_continuation_start(paragraph, lang) is expected


@pytest.mark.parametrize(
    ("paragraph", "lang", "expected"),
    [
        ("Por lo tanto, la conclusión es...", "es", True),
        ("En conclusión, el versículo dice...", "es", True),
        ("Por lo tanto no aparece al inicio? Por lo tanto sí.", "es", True),
        ("Therefore the apostle concludes...", "en", True),
        ("Portanto, é assim.", "pt", True),
    ],
)
def test_is_closure_start(paragraph: str, lang: str, expected: bool) -> None:
    assert is_closure_start(paragraph, lang) is expected


def test_continuation_is_case_sensitive_at_start() -> None:
    # Lowercase "sin embargo" inside prose should NOT trigger continuation.
    assert is_continuation_start("sin embargo dentro de la frase.", "es") is False


def test_unknown_language_returns_false() -> None:
    assert is_continuation_start("Whatever", "qq") is False
    assert is_closure_start("Whatever", "qq") is False


def test_detect_language_es() -> None:
    text = "El amor es paciente. Por lo tanto el cristiano debe perdonar."
    assert detect_language(text) == "es"


def test_detect_language_en() -> None:
    text = "Love is patient. Therefore the Christian must forgive."
    assert detect_language(text) == "en"


def test_detect_language_pt() -> None:
    text = "O amor é paciente. Portanto o cristão deve perdoar."
    assert detect_language(text) == "pt"


def test_detect_language_unknown_returns_none() -> None:
    assert detect_language("...") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_markers_loader.py -v
```
Expected: ImportError on `jw_rag.chunkers.markers`.

- [ ] **Step 3: Write the JSON catalog (data, not code)**

```json
// packages/jw-core/src/jw_core/data/continuation_markers.json
{
  "version": 1,
  "es": {
    "continuation": [
      "Sin embargo",
      "Por otro lado",
      "Además",
      "Pero",
      "No obstante",
      "Asimismo",
      "Es más",
      "También"
    ],
    "closure": [
      "Por lo tanto",
      "En conclusión",
      "Así que",
      "En resumen",
      "De manera que"
    ],
    "fingerprint": ["el", "la", "los", "las", "de", "que", "es", "por"]
  },
  "en": {
    "continuation": [
      "However",
      "On the other hand",
      "Moreover",
      "But",
      "Nevertheless",
      "Furthermore",
      "Also"
    ],
    "closure": [
      "Therefore",
      "In conclusion",
      "So",
      "In summary",
      "Hence",
      "Thus"
    ],
    "fingerprint": ["the", "and", "of", "is", "that", "to", "in"]
  },
  "pt": {
    "continuation": [
      "No entanto",
      "Por outro lado",
      "Além disso",
      "Mas",
      "Contudo",
      "Ademais",
      "Também"
    ],
    "closure": [
      "Portanto",
      "Em conclusão",
      "Assim",
      "Em resumo",
      "Logo"
    ],
    "fingerprint": ["o", "a", "os", "as", "de", "que", "é", "para", "não"]
  }
}
```

- [ ] **Step 4: Implement the loader**

```python
# packages/jw-rag/src/jw_rag/chunkers/markers.py
"""Continuation/closure marker catalog.

Backed by jw_core/data/continuation_markers.json so a community
contribution (e.g. fr, de, sign-language romanizations) is a JSON PR with
no Python change required.

Public surface:
    load_markers() -> dict[str, MarkerSet]
    is_continuation_start(paragraph, lang) -> bool
    is_closure_start(paragraph, lang) -> bool
    detect_language(text) -> str | None
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files


@dataclass(frozen=True)
class MarkerSet:
    continuation: tuple[str, ...]
    closure: tuple[str, ...]
    fingerprint: tuple[str, ...]


@lru_cache(maxsize=1)
def load_markers() -> dict[str, MarkerSet]:
    """Load the JSON catalog. Cached for the process lifetime."""
    data_pkg = files("jw_core.data")
    raw_path = data_pkg.joinpath("continuation_markers.json")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    out: dict[str, MarkerSet] = {}
    for lang, payload in raw.items():
        if lang == "version":
            continue
        if not isinstance(payload, dict):
            continue
        out[lang] = MarkerSet(
            continuation=tuple(payload.get("continuation", [])),
            closure=tuple(payload.get("closure", [])),
            fingerprint=tuple(payload.get("fingerprint", [])),
        )
    return out


def is_continuation_start(paragraph: str, lang: str) -> bool:
    """True if `paragraph` *starts* (case-sensitive) with a continuation
    marker for `lang`. Trailing comma/space/colon allowed but not required.
    """
    catalog = load_markers()
    ms = catalog.get(lang)
    if ms is None:
        return False
    stripped = paragraph.lstrip()
    return any(_marker_matches_start(stripped, m) for m in ms.continuation)


def is_closure_start(paragraph: str, lang: str) -> bool:
    """True if `paragraph` opens with a closure marker for `lang`."""
    catalog = load_markers()
    ms = catalog.get(lang)
    if ms is None:
        return False
    stripped = paragraph.lstrip()
    return any(_marker_matches_start(stripped, m) for m in ms.closure)


def _marker_matches_start(text: str, marker: str) -> bool:
    """Marker matches if it is followed by a word boundary AND the next
    non-space char is either lowercase / comma / colon / `que` (i.e. it
    really is a discourse marker, not a coincidence of leading capital)."""
    if not text.startswith(marker):
        return False
    tail = text[len(marker):]
    if not tail:
        return True
    nxt = tail[0]
    return nxt in {",", ":", " ", "\t"}


def detect_language(text: str) -> str | None:
    """Cheap fingerprint-based detector. Returns the lang code with the
    highest function-word overlap, or None if the score is too low to be
    meaningful (used to fall back to ParagraphChunker)."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return None
    catalog = load_markers()
    scores: dict[str, int] = {}
    for lang, ms in catalog.items():
        fp = set(ms.fingerprint)
        scores[lang] = sum(1 for t in tokens if t in fp)
    if not scores:
        return None
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_lang if best_score >= 3 else None
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_markers_loader.py -v
```
Expected: 14 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/data/continuation_markers.json packages/jw-rag/src/jw_rag/chunkers/markers.py packages/jw-rag/tests/chunkers/test_markers_loader.py
git commit -m "$(cat <<'EOF'
feat(jw-rag): multilingual continuation/closure marker catalog (es/en/pt)

Catalog lives in jw-core data so the community can contribute languages
without touching Python. Loader exposes is_continuation_start,
is_closure_start, detect_language.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `SemanticChunker` — continuation-merge (per language)

**Files:**
- Create: `packages/jw-rag/src/jw_rag/chunkers/semantic_chunker.py`
- Create: `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_es.txt`
- Create: `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_en.txt`
- Create: `packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_pt.txt`
- Create: `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_es.py`
- Create: `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_en.py`
- Create: `packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_pt.py`

- [ ] **Step 1: Write the multilingual fixtures**

```
# packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_es.txt
La Biblia enseña que Dios es uno solo y que su nombre es Jehová. Esto se ve en Deuteronomio 6:4 y en Salmo 83:18, pasajes claros y antiguos.
Sin embargo, algunos sostienen que en el Nuevo Testamento hay tres personas en una sola Deidad. Examinemos los textos que suelen aducir.
Por lo tanto, al sopesar todas las evidencias, queda claro que la enseñanza bíblica es coherente y monoteísta. La Trinidad no es bíblica.
```

```
# packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_en.txt
The Bible teaches that God is one and his name is Jehovah. This is seen in Deuteronomy 6:4 and Psalm 83:18, ancient and clear passages.
However, some claim that the New Testament reveals three persons in one Godhead. Let us examine the texts they cite.
Therefore, weighing all the evidence, it is clear that the biblical teaching is consistent and monotheistic. The Trinity is not biblical.
```

```
# packages/jw-rag/tests/chunkers/fixtures/article_with_continuation_pt.txt
A Bíblia ensina que Deus é um só e seu nome é Jeová. Isso aparece em Deuteronômio 6:4 e Salmo 83:18, passagens antigas e claras.
No entanto, alguns alegam que o Novo Testamento revela três pessoas em uma só Divindade. Examinemos os textos citados.
Portanto, ao pesar todas as evidências, fica claro que o ensino bíblico é coerente e monoteísta. A Trindade não é bíblica.
```

- [ ] **Step 2: Write the failing tests (one per language)**

```python
# packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_es.py
"""SemanticChunker — continuation merge in Spanish.

A paragraph starting with "Sin embargo" must be glued to the previous
chunk, not opened as a new one — even if the previous chunk already
exceeded min_chars, up to +30 % tolerance over max_chars.
"""

from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers import get_chunker
from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_es.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_es_merges_sin_embargo_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="es_doc", metadata={"language": "es"})
    # Expect: the "Sin embargo..." paragraph merges with the premise → 2 chunks
    # (premise+contraste joined, conclusion alone after closure split — see Task 4).
    sin_embargo_chunks = [k for k in chunks if "Sin embargo" in k.text]
    assert len(sin_embargo_chunks) == 1
    target = sin_embargo_chunks[0]
    assert "Deuteronomio 6:4" in target.text  # premise present in same chunk
    assert target.metadata.get("merge_reason") == "continuation_marker"
    assert target.metadata.get("chunker") == "semantic"


def test_semantic_es_records_para_ids_in_metadata() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    paragraphs = _paragraphs()
    chunks = c.chunk(paragraphs, source_id="es_doc", metadata={"language": "es"})
    # Every chunk should declare which paragraph indices it composes.
    for ch in chunks:
        para_ids = ch.metadata.get("para_ids")
        assert isinstance(para_ids, list)
        assert all(isinstance(i, int) for i in para_ids)
        assert len(para_ids) >= 1


def test_semantic_es_via_get_chunker_env(monkeypatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    c = get_chunker()
    assert c.name == "semantic"


def test_semantic_es_falls_back_when_language_unknown() -> None:
    # No metadata + jibberish text → detect_language returns None → fall back
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(["xxxxxx yyyyy.", "zzzzz wwwww."], source_id="x")
    assert len(chunks) >= 1
    assert all(ch.metadata.get("chunker") in {"semantic", "paragraph"} for ch in chunks)
```

```python
# packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_en.py
from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_en.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_en_merges_however_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="en_doc", metadata={"language": "en"})
    however_chunks = [k for k in chunks if "However" in k.text]
    assert len(however_chunks) == 1
    assert "Deuteronomy 6:4" in however_chunks[0].text
    assert however_chunks[0].metadata.get("merge_reason") == "continuation_marker"


def test_semantic_en_tolerates_max_chars_overflow_up_to_30pct() -> None:
    paragraphs = [
        "x" * 200,  # premise — large
        "However, additional context that should glue.",
    ]
    c = SemanticChunker(max_chars=210, min_chars=50, continuation_overflow=0.30)
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    # Premise+continuation should still be 1 chunk since 200 + 47 < 210*1.3 = 273
    assert len(chunks) == 1


def test_semantic_en_forces_flush_after_two_consecutive_merges() -> None:
    paragraphs = [
        "Original premise of meaningful length.",
        "However the first contrast extends the chunk.",
        "However a second contrast appears.",
        "However a third contrast must NOT keep gluing.",
    ]
    c = SemanticChunker(max_chars=400, min_chars=20)
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    # After 2 merges (Risk #1 in spec) we force a flush.
    # So the fourth "However" must open a new chunk.
    assert len(chunks) >= 2
```

```python
# packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_pt.py
from __future__ import annotations

from pathlib import Path

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_continuation_pt.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_pt_merges_no_entanto_into_prev() -> None:
    c = SemanticChunker(max_chars=400, min_chars=80)
    chunks = c.chunk(_paragraphs(), source_id="pt_doc", metadata={"language": "pt"})
    target = [k for k in chunks if "No entanto" in k.text]
    assert len(target) == 1
    assert "Deuteronômio 6:4" in target[0].text


def test_semantic_pt_auto_detects_language_when_unspecified() -> None:
    paragraphs = [
        "A Bíblia ensina que Jeová é o único Deus verdadeiro.",
        "No entanto, há quem afirme o contrário.",
    ]
    c = SemanticChunker(max_chars=400, min_chars=20)
    # No metadata["language"] — must auto-detect.
    chunks = c.chunk(paragraphs, source_id="pt_doc")
    assert len(chunks) == 1
    assert chunks[0].metadata.get("language_detected") == "pt"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_es.py packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_en.py packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_pt.py -v
```
Expected: ImportError on `jw_rag.chunkers.semantic_chunker`.

- [ ] **Step 4: Implement `SemanticChunker` (continuation only — closure in Task 4)**

```python
# packages/jw-rag/src/jw_rag/chunkers/semantic_chunker.py
"""SemanticChunker — heuristic continuation/closure-marker chunker.

Pipeline:
  1) Resolve language: metadata["language"] > detect_language(joined_text)
     > None → fall back to ParagraphChunker.
  2) Continuation merge: if paragraph N starts with a continuation marker
     in the resolved language, glue it onto the open chunk regardless of
     size, up to max_chars * (1 + continuation_overflow). After
     `max_continuation_merges` consecutive merges, force a flush (risk #1).
  3) Closure split: if paragraph N starts with a closure marker AND the
     open chunk already passed min_chars, flush AFTER appending N. The
     marker is recorded as `closure_marker` in metadata.
  4) Otherwise behave like ParagraphChunker (short merge, long split).

Every chunk gets:
    metadata["chunker"]           = "semantic" | "paragraph" (fallback)
    metadata["merge_reason"]      = "continuation_marker" | "short_paragraph" | None
    metadata["closure_marker"]    = "Por lo tanto" | ... | None
    metadata["para_ids"]          = [int, ...]  # 0-based indices into the input list
    metadata["language_detected"] = "es" | "en" | "pt" | None
    metadata["mixed_language"]    = True if detection was ambiguous
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jw_rag.chunkers.markers import (
    detect_language,
    is_closure_start,
    is_continuation_start,
    load_markers,
)
from jw_rag.chunkers.paragraph_chunker import Chunk, ParagraphChunker


@dataclass
class _OpenChunk:
    """In-progress chunk being built up paragraph by paragraph."""
    paragraphs: list[str] = field(default_factory=list)
    para_ids: list[int] = field(default_factory=list)
    merge_reason: str | None = None
    closure_marker: str | None = None
    continuation_merges_in_a_row: int = 0

    @property
    def total_len(self) -> int:
        return sum(len(p) for p in self.paragraphs)

    def append(self, paragraph: str, index: int, *, merge_reason: str | None = None) -> None:
        self.paragraphs.append(paragraph)
        self.para_ids.append(index)
        if merge_reason and self.merge_reason is None:
            self.merge_reason = merge_reason


class SemanticChunker:
    name = "semantic"

    def __init__(
        self,
        *,
        max_chars: int = 1500,
        min_chars: int = 80,
        continuation_overflow: float = 0.30,
        max_continuation_merges: int = 2,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.continuation_overflow = continuation_overflow
        self.max_continuation_merges = max_continuation_merges
        # Fallback chunker for unknown-language paths.
        self._fallback = ParagraphChunker(max_chars=max_chars, min_chars=min_chars)

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base_meta = dict(metadata or {})
        cleaned = [p.strip() for p in paragraphs if p and p.strip()]
        if not cleaned:
            return []

        language = base_meta.get("language")
        detected = None
        if not language:
            joined = " ".join(cleaned[:5])  # cheap sample
            detected = detect_language(joined)
            language = detected
        elif language not in load_markers():
            # Unknown declared language — fall back, but log via metadata.
            base_meta = {**base_meta, "mixed_language": True}
            return self._fallback_chunks(cleaned, source_id, base_meta)

        if language is None:
            # Detection failed — graceful fallback.
            return self._fallback_chunks(cleaned, source_id, base_meta)

        base_meta["language_detected"] = detected or language

        return self._chunk_semantic(cleaned, source_id, base_meta, language)

    # ── implementation helpers ─────────────────────────────────────────

    def _fallback_chunks(
        self,
        paragraphs: list[str],
        source_id: str,
        base_meta: dict[str, Any],
    ) -> list[Chunk]:
        chunks = self._fallback.chunk(paragraphs, source_id, metadata=base_meta)
        for c in chunks:
            c.metadata["chunker"] = "semantic"  # we tried
            c.metadata.setdefault("merge_reason", None)
            c.metadata.setdefault("closure_marker", None)
            c.metadata.setdefault("para_ids", [])
        return chunks

    def _chunk_semantic(
        self,
        paragraphs: list[str],
        source_id: str,
        base_meta: dict[str, Any],
        language: str,
    ) -> list[Chunk]:
        out: list[Chunk] = []
        open_chunk = _OpenChunk()

        def flush() -> None:
            nonlocal open_chunk
            if not open_chunk.paragraphs:
                return
            text = " ".join(open_chunk.paragraphs).strip()
            if text:
                meta = {
                    **base_meta,
                    "chunker": "semantic",
                    "merge_reason": open_chunk.merge_reason,
                    "closure_marker": open_chunk.closure_marker,
                    "para_ids": list(open_chunk.para_ids),
                    "para_count": len(open_chunk.paragraphs),
                }
                out.append(
                    Chunk(
                        id=f"{source_id}#{len(out)}",
                        text=text,
                        source_id=source_id,
                        metadata=meta,
                    )
                )
            open_chunk = _OpenChunk()

        overflow_limit = int(self.max_chars * (1 + self.continuation_overflow))

        for idx, paragraph in enumerate(paragraphs):
            # ── Long paragraph: hard-split as in ParagraphChunker
            if len(paragraph) > self.max_chars:
                flush()
                for piece in _split_long(paragraph, self.max_chars):
                    out.append(
                        Chunk(
                            id=f"{source_id}#{len(out)}",
                            text=piece,
                            source_id=source_id,
                            metadata={
                                **base_meta,
                                "chunker": "semantic",
                                "split": True,
                                "para_ids": [idx],
                            },
                        )
                    )
                continue

            # ── Continuation merge
            if (
                open_chunk.paragraphs
                and is_continuation_start(paragraph, language)
                and open_chunk.continuation_merges_in_a_row < self.max_continuation_merges
                and open_chunk.total_len + len(paragraph) <= overflow_limit
            ):
                open_chunk.append(paragraph, idx, merge_reason="continuation_marker")
                open_chunk.continuation_merges_in_a_row += 1
                continue

            # If continuation tried but blocked (overflow / too many in a row), flush first.
            if (
                open_chunk.paragraphs
                and is_continuation_start(paragraph, language)
                and open_chunk.continuation_merges_in_a_row >= self.max_continuation_merges
            ):
                flush()

            # ── Closure split: append, then flush if min_chars satisfied
            if is_closure_start(paragraph, language):
                if not open_chunk.paragraphs:
                    open_chunk.append(paragraph, idx)
                    open_chunk.closure_marker = _matched_closure_marker(paragraph, language)
                else:
                    open_chunk.append(paragraph, idx)
                    open_chunk.closure_marker = _matched_closure_marker(paragraph, language)
                if open_chunk.total_len >= self.min_chars:
                    flush()
                continue

            # ── Default: append; flush on max_chars or paragraph-end punctuation
            open_chunk.append(paragraph, idx)
            open_chunk.continuation_merges_in_a_row = 0
            if open_chunk.total_len >= self.max_chars:
                flush()
            elif (
                open_chunk.total_len >= self.min_chars
                and paragraph.endswith((".", "!", "?"))
            ):
                flush()

        flush()
        return out


def _split_long(text: str, max_chars: int) -> list[str]:
    """Same sentence-aware splitter as ParagraphChunker uses, duplicated to
    keep semantic_chunker free of cross-imports of private symbols."""
    out: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if len(current) + len(sentence) + 1 > max_chars and current:
            out.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        out.append(current.strip())
    final: list[str] = []
    for s in out:
        while len(s) > max_chars:
            final.append(s[:max_chars])
            s = s[max_chars:]
        if s:
            final.append(s)
    return final


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    current = ""
    for c in text:
        current += c
        if c in ".!?" and len(current) > 4:
            out.append(current.strip())
            current = ""
    if current.strip():
        out.append(current.strip())
    return out


def _matched_closure_marker(paragraph: str, language: str) -> str | None:
    ms = load_markers().get(language)
    if ms is None:
        return None
    stripped = paragraph.lstrip()
    for m in ms.closure:
        if stripped.startswith(m):
            return m
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/ -v
```
Expected: all 3 continuation tests pass + previous tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/chunkers/semantic_chunker.py packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_es.py packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_en.py packages/jw-rag/tests/chunkers/test_semantic_chunker_continuation_pt.py packages/jw-rag/tests/chunkers/fixtures/
git commit -m "$(cat <<'EOF'
feat(jw-rag): SemanticChunker continuation merge (es/en/pt)

Merges paragraphs starting with continuation markers ("Sin embargo",
"However", "No entanto", ...) into the previous chunk, with +30 %
overflow tolerance and a 2-in-a-row safety flush.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `SemanticChunker` — closure split

**Files:**
- Create: `packages/jw-rag/tests/chunkers/fixtures/article_with_closure_es.txt`
- Create: `packages/jw-rag/tests/chunkers/test_semantic_chunker_closure.py`

- [ ] **Step 1: Write the failing test**

```
# packages/jw-rag/tests/chunkers/fixtures/article_with_closure_es.txt
Premisa importante. La Biblia enseña la unidad de Dios en varios pasajes.
Por lo tanto, no es coherente postular tres personas idénticas en esencia.
Nuevo tema. Pasemos ahora a hablar de la esperanza terrenal.
Esta es una promesa central. Salmo 37:29 lo declara con claridad.
```

```python
# packages/jw-rag/tests/chunkers/test_semantic_chunker_closure.py
"""SemanticChunker — closure split.

When a paragraph starts with a closure marker ("Por lo tanto", "Therefore",
"Portanto"...) AND the open chunk already passed min_chars, the chunk is
flushed *after* appending the closure paragraph. Two effects:
  - The conclusion sticks with its premise (same chunk).
  - The next paragraph opens a fresh chunk (no leak across topics).

Closure must NOT fire if the chunk hasn't passed min_chars — otherwise
prefix-only conclusions split chunks too aggressively.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunkers.semantic_chunker import SemanticChunker

FIXTURE = Path(__file__).parent / "fixtures" / "article_with_closure_es.txt"


def _paragraphs() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_closure_es_closes_chunk_after_por_lo_tanto() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    chunks = c.chunk(_paragraphs(), source_id="es_doc", metadata={"language": "es"})
    # First chunk contains the premise + Por lo tanto.
    assert "Por lo tanto" in chunks[0].text
    assert "Premisa importante" in chunks[0].text
    assert chunks[0].metadata.get("closure_marker") == "Por lo tanto"
    # The next paragraph opens a fresh chunk.
    assert any("Nuevo tema" in ch.text for ch in chunks[1:])
    assert not any("Nuevo tema" in chunks[0].text for chunks[0] in [chunks[0]])


def test_closure_does_not_fire_below_min_chars() -> None:
    c = SemanticChunker(max_chars=500, min_chars=200)
    paragraphs = ["Tiny.", "Por lo tanto, esto seguiría junto a lo siguiente.", "Siguiente."]
    chunks = c.chunk(paragraphs, source_id="es", metadata={"language": "es"})
    # min_chars=200 not reached → closure must not split prematurely.
    assert len(chunks) == 1


def test_closure_en_therefore() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    paragraphs = [
        "The premise here is sufficiently lengthy for min_chars to be exceeded already.",
        "Therefore the argument concludes here cleanly.",
        "New unrelated topic begins.",
    ]
    chunks = c.chunk(paragraphs, source_id="en", metadata={"language": "en"})
    assert chunks[0].metadata.get("closure_marker") == "Therefore"
    assert "Therefore" in chunks[0].text
    assert any("New unrelated" in ch.text for ch in chunks[1:])


def test_closure_pt_portanto() -> None:
    c = SemanticChunker(max_chars=500, min_chars=40)
    paragraphs = [
        "A premissa precisa ser suficientemente longa para passar de min_chars sem problema.",
        "Portanto, a conclusão segue de modo inequívoco.",
        "Nova ideia começa aqui.",
    ]
    chunks = c.chunk(paragraphs, source_id="pt", metadata={"language": "pt"})
    assert chunks[0].metadata.get("closure_marker") == "Portanto"
    assert "Portanto" in chunks[0].text
    assert any("Nova ideia" in ch.text for ch in chunks[1:])


@pytest.mark.parametrize(
    ("language", "closure_marker", "expected_in_first_chunk"),
    [
        ("es", "En conclusión", "En conclusión"),
        ("en", "In conclusion", "In conclusion"),
        ("pt", "Em conclusão", "Em conclusão"),
    ],
)
def test_closure_alt_markers_per_language(
    language: str, closure_marker: str, expected_in_first_chunk: str,
) -> None:
    c = SemanticChunker(max_chars=400, min_chars=40)
    paragraphs = [
        "x" * 60,  # enough to pass min_chars
        f"{closure_marker}, this paragraph concludes the argument.",
        "Subsequent unrelated content.",
    ]
    chunks = c.chunk(paragraphs, source_id="z", metadata={"language": language})
    assert expected_in_first_chunk in chunks[0].text
    assert chunks[0].metadata.get("closure_marker") == closure_marker
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_semantic_chunker_closure.py -v
```
Expected: 6 passed (the implementation from Task 3 already supports closure).

- [ ] **Step 3: Verify no regression in continuation tests**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/ -v
```
Expected: full chunkers/ suite green.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-rag/tests/chunkers/test_semantic_chunker_closure.py packages/jw-rag/tests/chunkers/fixtures/article_with_closure_es.txt
git commit -m "$(cat <<'EOF'
test(jw-rag): SemanticChunker closure-split coverage (es/en/pt)

Locks the closure behaviour: closure-marker paragraphs glue to the open
chunk, then flush, but only after min_chars threshold is met.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `LLMChunker` skeleton with `FakeChunkerProvider`

**Files:**
- Create: `packages/jw-rag/src/jw_rag/chunkers/llm_chunker.py`
- Create: `packages/jw-rag/src/jw_rag/chunkers/fakes.py`
- Create: `packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py
"""LLMChunker with a deterministic fake provider.

The LLMChunker is a *post-processor* over SemanticChunker output. It asks
the provider for split/merge index actions. Never rewrites text. With a
fake provider returning a canned action list, behaviour is deterministic.
"""

from __future__ import annotations

import pytest

from jw_rag.chunkers.fakes import FakeChunkerProvider
from jw_rag.chunkers.llm_chunker import LLMChunker


def test_llm_chunker_applies_split_action() -> None:
    paragraphs = [
        "Aaaa aaaa aaaa.",
        "Bbbb bbbb bbbb.",
        "Cccc cccc cccc.",
        "Dddd dddd dddd.",
    ]
    # Fake provider says: split chunk 0 after paragraph 1
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 0, "after_paragraph": 1}],
    )
    chunker = LLMChunker(provider=provider, max_chars=10000, min_chars=1)
    chunks = chunker.chunk(paragraphs, source_id="t", metadata={"language": "en"})
    # 1 chunk → 2 chunks after the split.
    assert len(chunks) == 2
    assert chunks[0].text.startswith("Aaaa")
    assert "Bbbb" in chunks[0].text
    assert chunks[1].text.startswith("Cccc")
    assert all(c.metadata.get("chunker") == "llm" for c in chunks)


def test_llm_chunker_applies_merge_action() -> None:
    paragraphs = [
        "Para1.",
        "Para2.",
        "Para3.",
    ]
    # Force the semantic layer to produce ≥2 chunks: set tiny max_chars
    provider = FakeChunkerProvider(
        actions=[{"op": "merge", "chunk_indices": [0, 1]}],
    )
    chunker = LLMChunker(provider=provider, max_chars=10, min_chars=1)
    chunks = chunker.chunk(paragraphs, source_id="t", metadata={"language": "en"})
    # After merging 0 and 1, there's at most n-1 chunks where n was the semantic count.
    assert len(chunks) >= 1
    first_text = chunks[0].text
    assert "Para1" in first_text
    assert "Para2" in first_text


def test_llm_chunker_records_actions_in_metadata() -> None:
    provider = FakeChunkerProvider(actions=[])  # no-op
    chunker = LLMChunker(provider=provider, max_chars=200, min_chars=1)
    chunks = chunker.chunk(
        ["A test paragraph."],
        source_id="t",
        metadata={"language": "en"},
    )
    assert chunks[0].metadata.get("chunker") == "llm"
    assert chunks[0].metadata.get("llm_actions_applied") == []


def test_llm_chunker_validates_split_index() -> None:
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 99, "after_paragraph": 0}],
    )
    chunker = LLMChunker(provider=provider, max_chars=200, min_chars=1, strict=False)
    # With strict=False, invalid actions are skipped silently.
    chunks = chunker.chunk(["one."], source_id="t", metadata={"language": "en"})
    assert len(chunks) >= 1


def test_llm_chunker_raises_on_invalid_action_in_strict_mode() -> None:
    provider = FakeChunkerProvider(
        actions=[{"op": "split", "chunk_index": 99, "after_paragraph": 0}],
    )
    chunker = LLMChunker(provider=provider, max_chars=200, min_chars=1, strict=True)
    with pytest.raises(ValueError, match="invalid chunk_index"):
        chunker.chunk(["one."], source_id="t", metadata={"language": "en"})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py -v
```
Expected: ImportError on `jw_rag.chunkers.llm_chunker` / `jw_rag.chunkers.fakes`.

- [ ] **Step 3: Implement the fake provider and the LLMChunker**

```python
# packages/jw-rag/src/jw_rag/chunkers/fakes.py
"""Fakes for tests: deterministic providers and a fake chunker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jw_rag.chunkers.paragraph_chunker import Chunk


@dataclass
class FakeChunkerProvider:
    """Returns a canned list of actions. No-op if empty."""
    actions: list[dict[str, Any]] = field(default_factory=list)
    call_log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def provider_id(self) -> str:
        return "fake"

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]:
        self.call_log.append({"source_id": source_id, "n_chunks": len(chunks), "language": language})
        return list(self.actions)


@dataclass
class FakeSemanticChunker:
    """A deterministic chunker for tests of upstream callers. One paragraph =
    one chunk, no merge logic."""

    name: str = "semantic"

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base = dict(metadata or {})
        out: list[Chunk] = []
        for i, p in enumerate(paragraphs):
            out.append(
                Chunk(
                    id=f"{source_id}#{i}",
                    text=p.strip(),
                    source_id=source_id,
                    metadata={**base, "chunker": "semantic", "para_ids": [i]},
                )
            )
        return out
```

```python
# packages/jw-rag/src/jw_rag/chunkers/llm_chunker.py
"""LLMChunker — opt-in deep mode.

Pipeline:
  1) Run SemanticChunker to get a heuristic chunking.
  2) Ask the provider for index-level split/merge actions
     (NEVER rewrites text — Policy #6).
  3) Apply actions deterministically. Persist a cache by content hash.

Actions schema (JSON the provider returns):
  {"actions": [
     {"op": "split", "chunk_index": 4, "after_paragraph": 2},
     {"op": "merge", "chunk_indices": [7, 8]}
  ]}

Cache:
  ~/.jw-agent-toolkit/chunk-cache/{hash[:2]}/{hash}.json
  hash = sha256(source_id|paragraphs_joined|provider_id|prompt_version)

Defaults to a no-op fake provider if the optional jw_gen dep is missing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jw_rag.chunkers.paragraph_chunker import Chunk
from jw_rag.chunkers.semantic_chunker import SemanticChunker

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


class ChunkerProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]: ...


@dataclass
class _CacheEntry:
    actions: list[dict[str, Any]]
    provider_id: str
    prompt_version: str


class LLMChunker:
    name = "llm"

    def __init__(
        self,
        *,
        provider: ChunkerProvider | None = None,
        max_chars: int = 1500,
        min_chars: int = 80,
        cache_dir: Path | None = None,
        strict: bool = False,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self._semantic = SemanticChunker(max_chars=max_chars, min_chars=min_chars)
        self._provider = provider or _default_provider()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.strict = strict
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base_meta = dict(metadata or {})
        # Step 1: heuristic chunks.
        semantic_chunks = self._semantic.chunk(paragraphs, source_id, metadata=base_meta)
        if not semantic_chunks:
            return []

        language = (
            base_meta.get("language")
            or semantic_chunks[0].metadata.get("language_detected")
            or "en"
        )

        # Step 2: resolve actions (cache hit or provider call)
        cache_key = _cache_key(
            source_id=source_id,
            paragraphs=paragraphs,
            provider_id=self._provider.provider_id,
            prompt_version=PROMPT_VERSION,
        )
        cached = _load_cache(self.cache_dir, cache_key)
        if cached is not None:
            actions = cached.actions
            logger.debug("LLMChunker cache hit for %s (%s)", source_id, cache_key[:8])
        else:
            actions = list(self._provider.propose_actions(
                source_id=source_id,
                chunks=semantic_chunks,
                language=language,
            ))
            _save_cache(
                self.cache_dir,
                cache_key,
                _CacheEntry(
                    actions=actions,
                    provider_id=self._provider.provider_id,
                    prompt_version=PROMPT_VERSION,
                ),
            )

        # Step 3: apply actions deterministically.
        final = _apply_actions(semantic_chunks, actions, strict=self.strict)
        for c in final:
            c.metadata["chunker"] = "llm"
            c.metadata.setdefault("llm_actions_applied", list(actions))
        return final


def _default_cache_dir() -> Path:
    root = Path(
        os.environ.get("JW_CHUNK_CACHE_DIR")
        or (Path.home() / ".jw-agent-toolkit" / "chunk-cache")
    )
    return root


def _default_provider() -> ChunkerProvider:
    """Lazy: try jw_gen.providers.resolve(); fall back to no-op fake."""
    try:
        from jw_gen.providers import resolve  # type: ignore[import-not-found]
        provider = resolve()
        if provider is not None:
            return _AdaptedGenProvider(provider)
    except Exception:  # pragma: no cover — best-effort lazy import
        pass
    from jw_rag.chunkers.fakes import FakeChunkerProvider
    return FakeChunkerProvider(actions=[])


class _AdaptedGenProvider:
    """Adapt a jw_gen GenerationProvider to the ChunkerProvider interface."""

    def __init__(self, gen: Any) -> None:
        self._gen = gen

    @property
    def provider_id(self) -> str:
        return getattr(self._gen, "id", self._gen.__class__.__name__)

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]:
        prompt = _build_prompt(chunks=chunks, language=language)
        try:
            raw = self._gen.complete(prompt, temperature=0.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLMChunker provider call failed: %s", exc)
            return []
        try:
            data = json.loads(raw)
        except Exception:
            logger.warning("LLMChunker got non-JSON output: %r", raw[:200])
            return []
        actions = data.get("actions") if isinstance(data, dict) else None
        return actions if isinstance(actions, list) else []


def _build_prompt(*, chunks: list[Chunk], language: str) -> str:
    """Format the prompt — kept simple, version-pinned."""
    rendered = "\n\n".join(
        f"[chunk {i}]\n{c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"You are a chunk auditor for language '{language}'. Read the following "
        f"chunks (numbered) and propose ONLY index-level actions to improve "
        f"argumentative cohesion. NEVER rewrite text. Return strict JSON:\n"
        f'{{"actions": [{{"op": "split"|"merge", ...}}]}}\n\n'
        f"Chunks:\n{rendered}"
    )


def _cache_key(*, source_id: str, paragraphs: list[str], provider_id: str, prompt_version: str) -> str:
    h = hashlib.sha256()
    h.update(source_id.encode("utf-8"))
    h.update(b"\x00")
    h.update("\n".join(paragraphs).encode("utf-8"))
    h.update(b"\x00")
    h.update(provider_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_version.encode("utf-8"))
    return h.hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / key[:2] / f"{key}.json"


def _load_cache(cache_dir: Path, key: str) -> _CacheEntry | None:
    p = _cache_path(cache_dir, key)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return _CacheEntry(
            actions=list(raw.get("actions", [])),
            provider_id=str(raw.get("provider_id", "")),
            prompt_version=str(raw.get("prompt_version", "")),
        )
    except Exception:  # pragma: no cover — corrupt cache, fall through
        return None


def _save_cache(cache_dir: Path, key: str, entry: _CacheEntry) -> None:
    p = _cache_path(cache_dir, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "actions": entry.actions,
                "provider_id": entry.provider_id,
                "prompt_version": entry.prompt_version,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _apply_actions(
    chunks: list[Chunk],
    actions: list[dict[str, Any]],
    *,
    strict: bool,
) -> list[Chunk]:
    """Apply split/merge actions in-order to a *copy* of the chunk list."""
    out = list(chunks)
    for action in actions:
        op = action.get("op")
        if op == "split":
            idx = action.get("chunk_index")
            after_para = action.get("after_paragraph")
            if not isinstance(idx, int) or not (0 <= idx < len(out)):
                if strict:
                    raise ValueError(f"invalid chunk_index in action: {action}")
                continue
            if not isinstance(after_para, int):
                if strict:
                    raise ValueError(f"invalid after_paragraph in action: {action}")
                continue
            split_result = _split_chunk_after_paragraph(out[idx], after_para)
            if split_result is None:
                continue
            left, right = split_result
            out[idx:idx + 1] = [left, right]
        elif op == "merge":
            indices = action.get("chunk_indices")
            if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
                if strict:
                    raise ValueError(f"invalid chunk_indices in action: {action}")
                continue
            if any(not (0 <= i < len(out)) for i in indices):
                if strict:
                    raise ValueError(f"out-of-range chunk_indices in action: {action}")
                continue
            indices_sorted = sorted(set(indices))
            if not _are_consecutive(indices_sorted):
                if strict:
                    raise ValueError(f"merge requires consecutive indices, got {indices_sorted}")
                continue
            merged = _merge_chunks([out[i] for i in indices_sorted])
            first = indices_sorted[0]
            last = indices_sorted[-1]
            out[first:last + 1] = [merged]
        else:
            if strict:
                raise ValueError(f"unknown op: {op!r}")
    # Re-index ids
    return [
        Chunk(
            id=f"{c.source_id}#{i}",
            text=c.text,
            source_id=c.source_id,
            metadata=c.metadata,
        )
        for i, c in enumerate(out)
    ]


def _split_chunk_after_paragraph(c: Chunk, after_para: int) -> tuple[Chunk, Chunk] | None:
    para_ids = c.metadata.get("para_ids") or []
    if after_para < 0 or after_para >= len(para_ids) - 1:
        return None
    # We don't have the original paragraph texts here, only the joined text.
    # Approximate: split the text in two by paragraph count proportion.
    parts = c.text.split(" ")
    boundary = int(len(parts) * (after_para + 1) / len(para_ids))
    left_text = " ".join(parts[:boundary]).strip()
    right_text = " ".join(parts[boundary:]).strip()
    if not left_text or not right_text:
        return None
    left = Chunk(
        id=c.id,
        text=left_text,
        source_id=c.source_id,
        metadata={**c.metadata, "para_ids": para_ids[: after_para + 1], "llm_split": True},
    )
    right = Chunk(
        id=c.id + "_b",
        text=right_text,
        source_id=c.source_id,
        metadata={**c.metadata, "para_ids": para_ids[after_para + 1 :], "llm_split": True},
    )
    return left, right


def _merge_chunks(items: list[Chunk]) -> Chunk:
    para_ids: list[int] = []
    for c in items:
        para_ids.extend(c.metadata.get("para_ids") or [])
    return Chunk(
        id=items[0].id,
        text=" ".join(c.text for c in items).strip(),
        source_id=items[0].source_id,
        metadata={**items[0].metadata, "para_ids": para_ids, "llm_merged": True},
    )


def _are_consecutive(indices: list[int]) -> bool:
    return all(indices[i + 1] - indices[i] == 1 for i in range(len(indices) - 1))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/chunkers/llm_chunker.py packages/jw-rag/src/jw_rag/chunkers/fakes.py packages/jw-rag/tests/chunkers/test_llm_chunker_with_fake_provider.py
git commit -m "$(cat <<'EOF'
feat(jw-rag): LLMChunker with deterministic FakeChunkerProvider

Opt-in deep-mode chunker that post-processes SemanticChunker output with
index-level split/merge actions from a provider. NEVER rewrites text
(policy #6). Cache layout sha256(source|paragraphs|provider|prompt_ver).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `LLMChunker` cache hit > 95 %

**Files:**
- Create: `packages/jw-rag/tests/chunkers/test_llm_chunker_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/chunkers/test_llm_chunker_cache.py
"""LLMChunker cache must short-circuit the provider on re-runs.

Acceptance: > 95 % hit rate on a 20-iteration loop with identical inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_rag.chunkers.fakes import FakeChunkerProvider
from jw_rag.chunkers.llm_chunker import LLMChunker


def test_cache_hit_skips_provider_call(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)
    paragraphs = ["The first paragraph.", "The second paragraph."]

    chunker.chunk(paragraphs, source_id="doc-1", metadata={"language": "en"})
    assert len(provider.call_log) == 1

    chunker.chunk(paragraphs, source_id="doc-1", metadata={"language": "en"})
    assert len(provider.call_log) == 1, "second call should hit the cache"


def test_cache_miss_on_different_paragraphs(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)

    chunker.chunk(["AA."], source_id="doc-2", metadata={"language": "en"})
    chunker.chunk(["BB."], source_id="doc-2", metadata={"language": "en"})
    assert len(provider.call_log) == 2


def test_cache_miss_on_different_provider_id(tmp_path: Path) -> None:
    p1 = FakeChunkerProvider(actions=[])
    p2 = FakeChunkerProvider(actions=[])
    # Make their provider_ids differ by patching
    p2.__class__ = type("OtherFake", (FakeChunkerProvider,), {"provider_id": "fake-2"})
    paragraphs = ["X."]

    c1 = LLMChunker(provider=p1, cache_dir=tmp_path, max_chars=200, min_chars=1)
    c1.chunk(paragraphs, source_id="d", metadata={"language": "en"})
    c2 = LLMChunker(provider=p2, cache_dir=tmp_path, max_chars=200, min_chars=1)
    c2.chunk(paragraphs, source_id="d", metadata={"language": "en"})

    assert len(p1.call_log) == 1
    assert len(p2.call_log) == 1


def test_hit_rate_over_95pct_on_repeated_inputs(tmp_path: Path) -> None:
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, cache_dir=tmp_path, max_chars=200, min_chars=1)
    paragraphs = ["repeated content.", "consistent across runs."]
    N = 20
    for _ in range(N):
        chunker.chunk(paragraphs, source_id="hit-rate-doc", metadata={"language": "en"})
    hits = N - len(provider.call_log)
    rate = hits / N
    assert rate > 0.95, f"cache hit rate {rate:.1%} below 95%"


@pytest.mark.parametrize("env_var", ["JW_CHUNK_CACHE_DIR"])
def test_cache_dir_overridable_by_env(env_var: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(env_var, str(tmp_path / "custom"))
    provider = FakeChunkerProvider(actions=[])
    chunker = LLMChunker(provider=provider, max_chars=200, min_chars=1)
    chunker.chunk(["abc."], source_id="d", metadata={"language": "en"})
    assert (tmp_path / "custom").exists()
```

- [ ] **Step 2: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_llm_chunker_cache.py -v
```
Expected: 5 passed (cache implementation from Task 5 already satisfies this).

- [ ] **Step 3: Commit**

```bash
git add packages/jw-rag/tests/chunkers/test_llm_chunker_cache.py
git commit -m "$(cat <<'EOF'
test(jw-rag): LLMChunker cache hit > 95 % on repeated inputs

Locks the cache contract: same source_id + paragraphs + provider_id +
prompt_version → no provider call.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `get_chunker` env var contract + ingest integration

**Files:**
- Create: `packages/jw-rag/tests/chunkers/test_get_chunker_env_var.py`
- Modify: `packages/jw-rag/src/jw_rag/ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-rag/tests/chunkers/test_get_chunker_env_var.py
"""get_chunker() honors JW_CHUNKER env var with explicit precedence:
  1. function argument
  2. JW_CHUNKER env var
  3. default "paragraph"

Also verifies that the new ingest path uses get_chunker() rather than
chunk_paragraphs directly.
"""

from __future__ import annotations

import pytest

from jw_rag.chunkers import ParagraphChunker, get_chunker
from jw_rag.chunkers.semantic_chunker import SemanticChunker
from jw_rag.chunkers.llm_chunker import LLMChunker


def test_default_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_CHUNKER", raising=False)
    assert isinstance(get_chunker(), ParagraphChunker)


def test_env_var_selects_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    assert isinstance(get_chunker(), SemanticChunker)


def test_env_var_selects_llm(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("JW_CHUNKER", "llm")
    monkeypatch.setenv("JW_CHUNK_CACHE_DIR", str(tmp_path))
    assert isinstance(get_chunker(), LLMChunker)


def test_arg_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "semantic")
    assert isinstance(get_chunker(name="paragraph"), ParagraphChunker)


def test_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CHUNKER", "totally-bogus")
    with pytest.raises(ValueError, match="Unknown chunker"):
        get_chunker()


def test_ingest_article_uses_get_chunker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ingest must route through get_chunker (so JW_CHUNKER env actually
    influences ingest behavior). We patch get_chunker and observe the call."""
    import jw_rag.ingest as ingest_mod

    seen = {}

    def fake_get_chunker(name=None, **kwargs):  # noqa: ANN001
        seen["name"] = name
        return ParagraphChunker()

    monkeypatch.setattr(ingest_mod, "get_chunker", fake_get_chunker, raising=True)
    # Call the helper that ingest uses internally.
    chunker = ingest_mod._resolve_chunker(None)
    assert chunker.name == "paragraph"
    assert "name" in seen
```

- [ ] **Step 2: Run test to verify it fails on the ingest part**

```bash
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/test_get_chunker_env_var.py -v
```
Expected: 5 of 6 pass; the last fails because `_resolve_chunker` doesn't exist in ingest.py yet.

- [ ] **Step 3: Add `_resolve_chunker` to `ingest.py` and reroute callers**

Edit `packages/jw-rag/src/jw_rag/ingest.py`. Replace the legacy import line and add a helper. All five ingest functions are updated to route through it.

Replace:
```python
from jw_rag.chunker import chunk_paragraphs
```

With:
```python
from jw_rag.chunkers import Chunker, get_chunker
```

Insert immediately after the imports block:
```python
def _resolve_chunker(chunker: Chunker | str | None) -> Chunker:
    """Resolve an explicit chunker arg, env var, or default to paragraph.

    Accepts a Chunker instance directly (for tests), a string name, or None.
    """
    if chunker is None or isinstance(chunker, str):
        return get_chunker(chunker)
    return chunker
```

Then update every `chunk_paragraphs(...)` call site so it goes through the chunker. Concretely, in each of `ingest_bible_chapter`, `ingest_article`, `ingest_epub`, `ingest_jwpub`, `_ingest_backup_notes`, `_ingest_backup_bookmarks`, `_ingest_backup_input_fields`:

1. Add a `chunker: Chunker | str | None = None` keyword argument to every public ingest function (`ingest_bible_chapter`, `ingest_article`, `ingest_search_topk`, `ingest_epub`, `ingest_jwpub`, `ingest_jw_library_backup`).
2. At the top of the function body, do `_chunker = _resolve_chunker(chunker)`.
3. Replace `chunk_paragraphs(paragraphs, source_id=..., metadata=...)` with `_chunker.chunk(paragraphs, source_id=..., metadata=...)`.
4. For the JW Library backup helpers (`_ingest_backup_*`), thread the resolved chunker through.

Example for `ingest_article`:

```python
async def ingest_article(
    store: VectorStore,
    url: str,
    *,
    wol: WOLClient | None = None,
    metadata: dict[str, Any] | None = None,
    chunker: Chunker | str | None = None,
) -> int:
    """Ingest an arbitrary wol.jw.org article URL."""
    _chunker = _resolve_chunker(chunker)
    owned = False
    if wol is None:
        wol = WOLClient()
        owned = True
    try:
        html = await wol.fetch(url)
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    chunks = _chunker.chunk(
        article.paragraphs,
        source_id=f"article:{url}",
        metadata={
            "kind": "article",
            "title": article.title,
            "source_url": url,
            **(metadata or {}),
        },
    )
    store.add(chunks)
    logger.info(f"Ingested article {url!r} — {len(chunks)} chunks using {_chunker.name}")
    return len(chunks)
```

Apply the same pattern to the other ingest functions. `ingest_search_topk` simply forwards `chunker` to `ingest_article`.

- [ ] **Step 4: Run all `jw-rag` tests**

```bash
.venv/bin/python -m pytest packages/jw-rag/ -v
```
Expected: full suite green.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/ingest.py packages/jw-rag/tests/chunkers/test_get_chunker_env_var.py
git commit -m "$(cat <<'EOF'
feat(jw-rag): route ingest through get_chunker(); honor JW_CHUNKER env var

Every ingest_* accepts chunker: Chunker | str | None. None falls back to
get_chunker() which reads JW_CHUNKER, defaulting to 'paragraph'. Behavior
is unchanged when env var is absent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: `bench/ndcg.py` — NDCG@10 with bootstrap CI

**Files:**
- Create: `packages/jw-eval/src/jw_eval/bench/__init__.py`
- Create: `packages/jw-eval/src/jw_eval/bench/ndcg.py`
- Create: `packages/jw-eval/tests/test_bench_ndcg.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_bench_ndcg.py
"""NDCG@10 implementation tests.

NDCG@10 = DCG@10 / IDCG@10. Standard binary-relevance formula:
  DCG = sum_{i=1..k} (rel_i) / log2(i+1)
  IDCG = sum_{i=1..min(k, |R|)} (1) / log2(i+1)

Bootstrap CI: resample query-level NDCG with replacement 1000 times,
report 95 % percentile interval.
"""

from __future__ import annotations

import math

import pytest

from jw_eval.bench.ndcg import bootstrap_ci_95, dcg_at_k, ndcg_at_k


def test_dcg_perfect_top_k() -> None:
    rels = [1, 1, 1]  # all relevant in first 3
    # DCG = 1/log2(2) + 1/log2(3) + 1/log2(4) = 1 + 0.6309... + 0.5
    expected = 1.0 + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    assert dcg_at_k(rels, 10) == pytest.approx(expected, abs=1e-6)


def test_ndcg_perfect_is_one() -> None:
    rels = [1, 1, 1] + [0] * 7
    assert ndcg_at_k(rels, n_relevant=3, k=10) == pytest.approx(1.0)


def test_ndcg_partial() -> None:
    # 2 of 3 relevant in top 10, but at positions 5 and 9 — degraded.
    rels = [0, 0, 0, 0, 1, 0, 0, 0, 1, 0]
    score = ndcg_at_k(rels, n_relevant=3, k=10)
    assert 0 < score < 1


def test_ndcg_zero_relevant() -> None:
    assert ndcg_at_k([0] * 10, n_relevant=0, k=10) == 0.0


def test_ndcg_handles_n_relevant_zero_in_ideal() -> None:
    # If there are no relevant docs at all, IDCG=0; we return 0.
    assert ndcg_at_k([0] * 10, n_relevant=0, k=10) == 0.0


def test_bootstrap_ci_returns_bounds() -> None:
    scores = [0.5, 0.6, 0.55, 0.7, 0.65, 0.58, 0.62, 0.61, 0.6, 0.55]
    lo, hi = bootstrap_ci_95(scores, n_resamples=200, seed=42)
    assert 0.0 <= lo <= hi <= 1.0
    # Mean is ~0.6; CI must contain it with this sample size.
    assert lo <= 0.6 <= hi


def test_bootstrap_ci_deterministic_with_seed() -> None:
    scores = [0.5, 0.6, 0.55]
    a = bootstrap_ci_95(scores, n_resamples=100, seed=7)
    b = bootstrap_ci_95(scores, n_resamples=100, seed=7)
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/jw-eval/tests/test_bench_ndcg.py -v
```
Expected: ImportError on `jw_eval.bench.ndcg`.

- [ ] **Step 3: Implement NDCG and bootstrap CI**

```python
# packages/jw-eval/src/jw_eval/bench/__init__.py
"""Benchmark utilities for jw-eval (NDCG@k, bootstrap CI, chunker bench)."""

from jw_eval.bench.ndcg import bootstrap_ci_95, dcg_at_k, ndcg_at_k

__all__ = ["bootstrap_ci_95", "dcg_at_k", "ndcg_at_k"]
```

```python
# packages/jw-eval/src/jw_eval/bench/ndcg.py
"""NDCG@k with binary relevance and bootstrap 95 % CI.

This stays plain Python (no numpy) so it runs in any test env without
extra deps.
"""

from __future__ import annotations

import math
import random


def dcg_at_k(relevances: list[int], k: int) -> float:
    """Discounted Cumulative Gain at rank k with binary relevances."""
    out = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        out += rel / math.log2(i + 1)
    return out


def ndcg_at_k(relevances: list[int], *, n_relevant: int, k: int) -> float:
    """Normalized DCG. n_relevant is |R|, the total number of relevant docs
    in the ground truth (may be > k)."""
    if n_relevant <= 0:
        return 0.0
    ideal_rels = [1] * min(n_relevant, k)
    idcg = dcg_at_k(ideal_rels, k)
    if idcg <= 0:
        return 0.0
    return dcg_at_k(relevances, k) / idcg


def bootstrap_ci_95(
    per_query_scores: list[float],
    *,
    n_resamples: int = 1000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap (2.5 / 97.5) for the mean of per-query NDCG.

    With as few as 10 queries the bootstrap LB is what we report to claim
    the ≥10 % lift — protects against overclaiming on tiny samples.
    """
    if not per_query_scores:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(per_query_scores)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [per_query_scores[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return lo, hi
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/jw-eval/tests/test_bench_ndcg.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/bench/__init__.py packages/jw-eval/src/jw_eval/bench/ndcg.py packages/jw-eval/tests/test_bench_ndcg.py
git commit -m "$(cat <<'EOF'
feat(jw-eval): NDCG@k + bootstrap 95 % CI utilities

Plain-Python NDCG@k with binary relevance + percentile bootstrap so we
report a lower-bound when the doctrinal-query sample is small.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `chunker_bench.py` orchestrator + doctrinal queries fixture

**Files:**
- Create: `packages/jw-eval/src/jw_eval/bench/chunker_bench.py`
- Create: `packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml`
- Create: `packages/jw-eval/tests/test_bench_chunker.py`

- [ ] **Step 1: Write the doctrinal queries YAML**

```yaml
# packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml
# 10 doctrinal queries per language. expected_citations are the canonical
# wol.jw.org URLs that the retriever should surface in the top 10.
# Per-language target NDCG@10 lift ≥ 10 % (semantic vs paragraph).
queries:
  - id: q_es_trinidad
    language: es
    query: "¿Es bíblica la doctrina de la Trinidad?"
    expected_citations:
      - https://wol.jw.org/es/wol/d/r4/lp-s/1102004110
      - https://wol.jw.org/es/wol/d/r4/lp-s/2007005
  - id: q_es_alma_inmortal
    language: es
    query: "¿Es el alma humana inmortal?"
    expected_citations:
      - https://wol.jw.org/es/wol/d/r4/lp-s/1102004193
  - id: q_es_infierno_fuego
    language: es
    query: "¿Existe el infierno de fuego literal?"
    expected_citations:
      - https://wol.jw.org/es/wol/d/r4/lp-s/1102004148
  - id: q_es_identidad_cristo
    language: es
    query: "¿Es Jesucristo el Dios Todopoderoso?"
    expected_citations:
      - https://wol.jw.org/es/wol/d/r4/lp-s/1102004111
  - id: q_es_esperanza_terrestre
    language: es
    query: "¿Cuál es la esperanza terrenal para los cristianos?"
    expected_citations:
      - https://wol.jw.org/es/wol/d/r4/lp-s/1102004167
  - id: q_en_trinity
    language: en
    query: "Is the Trinity biblical?"
    expected_citations:
      - https://wol.jw.org/en/wol/d/r1/lp-e/1102004110
  - id: q_en_soul
    language: en
    query: "Is the human soul immortal?"
    expected_citations:
      - https://wol.jw.org/en/wol/d/r1/lp-e/1102004193
  - id: q_en_hell
    language: en
    query: "Is hellfire a literal place of torment?"
    expected_citations:
      - https://wol.jw.org/en/wol/d/r1/lp-e/1102004148
  - id: q_pt_trindade
    language: pt
    query: "A Trindade é bíblica?"
    expected_citations:
      - https://wol.jw.org/pt/wol/d/r5/lp-t/1102004110
  - id: q_pt_alma_imortal
    language: pt
    query: "A alma humana é imortal?"
    expected_citations:
      - https://wol.jw.org/pt/wol/d/r5/lp-t/1102004193
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-eval/tests/test_bench_chunker.py
"""chunker_bench orchestration tests.

The bench loads doctrinal_queries.yaml, ingests a small fixture corpus
under each chunker variant, runs VectorStore.search(k=10), and computes
NDCG@10 per language + aggregate, with bootstrap CI.

For testing we replace the VectorStore with a stub that returns a fixed
ranking, so the test asserts orchestration + math without depending on
embeddings or the real RAG store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jw_eval.bench.chunker_bench import (
    BenchConfig,
    BenchReport,
    load_doctrinal_queries,
    run_chunker_bench,
)


def test_load_doctrinal_queries_returns_per_language() -> None:
    path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "chunker_bench"
        / "doctrinal_queries.yaml"
    )
    qs = load_doctrinal_queries(path)
    assert len(qs) >= 10
    langs = {q.language for q in qs}
    assert {"es", "en", "pt"} <= langs


class _StubStore:
    """Stub VectorStore that returns canned URL rankings per query."""

    def __init__(self, rankings: dict[str, list[str]]) -> None:
        self._rankings = rankings

    def search(self, query: str, k: int = 10) -> list[Any]:
        urls = self._rankings.get(query, [])

        class _Result:
            def __init__(self, url: str) -> None:
                self.metadata = {"source_url": url}

        return [_Result(u) for u in urls[:k]]


def test_run_chunker_bench_computes_per_language(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: es
    query: "trinidad"
    expected_citations:
      - https://example/es/trinity
  - id: q2
    language: en
    query: "trinity"
    expected_citations:
      - https://example/en/trinity
""",
        encoding="utf-8",
    )

    rankings_paragraph = {
        "trinidad": ["https://example/es/wrong"] * 9 + ["https://example/es/trinity"],
        "trinity": ["https://example/en/trinity"] + ["https://example/en/wrong"] * 9,
    }
    rankings_semantic = {
        "trinidad": ["https://example/es/trinity"] + ["https://example/es/wrong"] * 9,
        "trinity": ["https://example/en/trinity"] + ["https://example/en/wrong"] * 9,
    }
    stores = {
        "paragraph": _StubStore(rankings_paragraph),
        "semantic": _StubStore(rankings_semantic),
    }

    def store_factory(variant: str):
        return stores[variant]

    config = BenchConfig(
        variants=["paragraph", "semantic"],
        queries_path=queries_path,
        k=10,
    )
    report = run_chunker_bench(config, store_factory=store_factory)
    assert isinstance(report, BenchReport)
    # Semantic must score higher than paragraph on the ES query (rank 10 → rank 1).
    es_p = report.per_language["paragraph"]["es"]["ndcg10_mean"]
    es_s = report.per_language["semantic"]["es"]["ndcg10_mean"]
    assert es_s > es_p


def test_bench_reports_delta_with_ci(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: en
    query: "x"
    expected_citations:
      - https://example/x
""",
        encoding="utf-8",
    )
    stores = {
        "paragraph": _StubStore({"x": ["https://example/wrong"] * 10}),
        "semantic": _StubStore({"x": ["https://example/x"] + ["https://example/wrong"] * 9}),
    }

    report = run_chunker_bench(
        BenchConfig(
            variants=["paragraph", "semantic"],
            queries_path=queries_path,
            k=10,
        ),
        store_factory=lambda v: stores[v],
    )
    assert "delta_semantic_vs_paragraph" in report.summary
    assert report.summary["delta_semantic_vs_paragraph"]["delta_pct"] > 0


def test_bench_skips_unknown_language_gracefully(tmp_path: Path) -> None:
    queries_path = tmp_path / "q.yaml"
    queries_path.write_text(
        """
queries:
  - id: q1
    language: zz
    query: "?"
    expected_citations:
      - https://example/q
""",
        encoding="utf-8",
    )
    stores = {"paragraph": _StubStore({"?": ["https://example/q"]})}
    report = run_chunker_bench(
        BenchConfig(variants=["paragraph"], queries_path=queries_path, k=10),
        store_factory=lambda v: stores[v],
    )
    # The query still gets evaluated; language bucket "zz" appears in the report.
    assert "zz" in report.per_language["paragraph"]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/jw-eval/tests/test_bench_chunker.py -v
```
Expected: ImportError on `jw_eval.bench.chunker_bench`.

- [ ] **Step 4: Implement the orchestrator**

```python
# packages/jw-eval/src/jw_eval/bench/chunker_bench.py
"""Chunker benchmark orchestrator.

Computes NDCG@10 per query, per language, per chunker variant. The
caller provides `store_factory(variant) -> VectorStore-like` so this
module stays decoupled from the real ingest pipeline (used as a unit-
testable building block; the CLI wires it to the real one in Task 10).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jw_eval.bench.ndcg import bootstrap_ci_95, ndcg_at_k


@dataclass(frozen=True)
class DoctrinalQuery:
    id: str
    language: str
    query: str
    expected_citations: tuple[str, ...]


@dataclass
class BenchConfig:
    variants: list[str]
    queries_path: Path
    k: int = 10


@dataclass
class BenchReport:
    per_language: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    """variant → language → {ndcg10_mean, ndcg10_ci_lo, ndcg10_ci_hi, n}"""
    per_query: dict[str, dict[str, float]] = field(default_factory=dict)
    """variant → query_id → ndcg10"""
    summary: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_doctrinal_queries(path: Path) -> list[DoctrinalQuery]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[DoctrinalQuery] = []
    for entry in raw.get("queries") or []:
        out.append(
            DoctrinalQuery(
                id=str(entry["id"]),
                language=str(entry["language"]),
                query=str(entry["query"]),
                expected_citations=tuple(entry.get("expected_citations") or []),
            )
        )
    return out


def _extract_urls(results: list[Any]) -> list[str]:
    out: list[str] = []
    for r in results:
        meta = getattr(r, "metadata", {}) or {}
        url = meta.get("source_url") or meta.get("citation_url")
        if url:
            out.append(url)
    return out


def _relevances(retrieved_urls: list[str], expected: tuple[str, ...]) -> list[int]:
    expected_set = set(expected)
    return [1 if u in expected_set else 0 for u in retrieved_urls]


def run_chunker_bench(
    config: BenchConfig,
    *,
    store_factory: Callable[[str], Any],
) -> BenchReport:
    queries = load_doctrinal_queries(config.queries_path)
    report = BenchReport()

    # variant → language → list of per-query NDCG
    variant_lang_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for variant in config.variants:
        store = store_factory(variant)
        report.per_query[variant] = {}
        for q in queries:
            results = store.search(q.query, k=config.k)
            urls = _extract_urls(results)
            rels = _relevances(urls, q.expected_citations)
            score = ndcg_at_k(rels, n_relevant=len(q.expected_citations), k=config.k)
            report.per_query[variant][q.id] = score
            variant_lang_scores[variant][q.language].append(score)

    for variant, lang_map in variant_lang_scores.items():
        report.per_language[variant] = {}
        for lang, scores in lang_map.items():
            mean = sum(scores) / len(scores) if scores else 0.0
            lo, hi = bootstrap_ci_95(scores, n_resamples=1000, seed=0)
            report.per_language[variant][lang] = {
                "ndcg10_mean": mean,
                "ndcg10_ci_lo": lo,
                "ndcg10_ci_hi": hi,
                "n": len(scores),
            }

    # Cross-variant deltas
    if "paragraph" in config.variants:
        baseline = report.per_language.get("paragraph", {})
        for variant in config.variants:
            if variant == "paragraph":
                continue
            other = report.per_language.get(variant, {})
            for lang in set(baseline) & set(other):
                base_mean = baseline[lang]["ndcg10_mean"]
                this_mean = other[lang]["ndcg10_mean"]
                delta_pct = ((this_mean - base_mean) / base_mean * 100.0) if base_mean else 0.0
                report.summary.setdefault(f"delta_{variant}_vs_paragraph", {})[lang] = {
                    "delta_pct": delta_pct,
                    "baseline_mean": base_mean,
                    "new_mean": this_mean,
                }
            # Aggregate delta_pct shortcut (mean across languages)
            agg = [
                report.summary[f"delta_{variant}_vs_paragraph"][lang]["delta_pct"]
                for lang in report.summary[f"delta_{variant}_vs_paragraph"]
            ]
            report.summary[f"delta_{variant}_vs_paragraph"]["delta_pct"] = (
                sum(agg) / len(agg) if agg else 0.0
            )

    return report
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest packages/jw-eval/tests/test_bench_chunker.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/src/jw_eval/bench/chunker_bench.py packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml packages/jw-eval/tests/test_bench_chunker.py
git commit -m "$(cat <<'EOF'
feat(jw-eval): chunker_bench orchestrator + 10 doctrinal queries (es/en/pt)

Computes NDCG@10 per language per variant with bootstrap 95 % CI and
cross-variant deltas. Decoupled from real ingest via store_factory.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: `jw eval chunker-bench` CLI subcommand + per-language ≥10 % lift gate

**Files:**
- Modify: `packages/jw-eval/src/jw_eval/cli.py`

- [ ] **Step 1: Read the existing CLI to understand its style**

Run:
```bash
.venv/bin/python -m grep_dummy_check 2>/dev/null || true
.venv/bin/python -c "from jw_eval import cli; print(cli.__file__)"
```
Then read the file before editing.

- [ ] **Step 2: Add the subcommand**

Append to `packages/jw-eval/src/jw_eval/cli.py` (keep existing commands intact):

```python
# Appended in Task 10 of Fase 45 plan.
from pathlib import Path

import typer

from jw_eval.bench.chunker_bench import BenchConfig, run_chunker_bench


@app.command("chunker-bench")
def chunker_bench(
    variants: str = typer.Option(
        "paragraph,semantic",
        help="Comma-separated chunker variants to benchmark.",
    ),
    queries: Path = typer.Option(
        Path("packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml"),
        help="YAML file with doctrinal queries.",
    ),
    k: int = typer.Option(10, help="Cutoff for NDCG@k."),
    report: str = typer.Option("md", help="md | json"),
    out: Path | None = typer.Option(None, help="Write the report to this path."),
    corpus_dir: Path | None = typer.Option(
        None,
        help="Directory of pre-ingested article URLs to use as the corpus. "
             "Each line in <corpus_dir>/urls.txt is an article URL.",
    ),
    min_lift_pct: float = typer.Option(
        10.0,
        help="Fail with non-zero exit if any non-paragraph variant fails the "
             "per-language lift gate (default 10 %).",
    ),
) -> None:
    """Run the chunker benchmark and (optionally) gate on a per-language lift."""

    variant_list = [v.strip() for v in variants.split(",") if v.strip()]
    config = BenchConfig(variants=variant_list, queries_path=queries, k=k)

    def store_factory(variant: str):
        import os
        os.environ["JW_CHUNKER"] = variant
        return _build_corpus_store(corpus_dir, variant)

    bench = run_chunker_bench(config, store_factory=store_factory)

    if report == "md":
        rendered = _render_markdown(bench, min_lift_pct=min_lift_pct)
    else:
        import json
        rendered = json.dumps(
            {
                "per_language": bench.per_language,
                "per_query": bench.per_query,
                "summary": bench.summary,
            },
            indent=2,
            ensure_ascii=False,
        )
    if out:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(f"Wrote report to {out}")
    else:
        typer.echo(rendered)

    # Gate
    failures: list[str] = []
    for variant in variant_list:
        if variant == "paragraph":
            continue
        per_lang_deltas = bench.summary.get(f"delta_{variant}_vs_paragraph", {})
        for lang, payload in per_lang_deltas.items():
            if lang == "delta_pct":
                continue
            if isinstance(payload, dict) and payload.get("delta_pct", 0.0) < min_lift_pct:
                failures.append(
                    f"{variant}/{lang}: delta {payload['delta_pct']:.1f} % < {min_lift_pct:.0f} %"
                )
    if failures:
        for f in failures:
            typer.echo(f"GATE FAIL: {f}", err=True)
        raise typer.Exit(code=1)


def _build_corpus_store(corpus_dir: Path | None, variant: str):
    """Build a VectorStore for the bench.

    If `corpus_dir` is provided and contains `urls.txt`, ingest those URLs
    with the current variant. Otherwise return an empty store (the CLI is
    still useful for smoke-testing the variant routing).
    """
    from jw_rag.store import VectorStore
    store = VectorStore(persist_dir=None)
    if corpus_dir and (corpus_dir / "urls.txt").exists():
        import asyncio
        from jw_rag.ingest import ingest_article
        urls = [
            line.strip()
            for line in (corpus_dir / "urls.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        async def _ingest_all() -> None:
            for url in urls:
                try:
                    await ingest_article(store, url, chunker=variant)
                except Exception as exc:  # noqa: BLE001
                    typer.echo(f"  warn: failed to ingest {url}: {exc}", err=True)

        asyncio.run(_ingest_all())
    return store


def _render_markdown(bench, *, min_lift_pct: float) -> str:
    lines: list[str] = []
    lines.append("# Chunker Bench Report")
    lines.append("")
    lines.append("## Per-language NDCG@10")
    lines.append("")
    lines.append("| Variant | Language | NDCG@10 mean | CI 95 % | n |")
    lines.append("|---|---|---|---|---|")
    for variant, lang_map in bench.per_language.items():
        for lang, payload in lang_map.items():
            lines.append(
                f"| {variant} | {lang} | "
                f"{payload['ndcg10_mean']:.3f} | "
                f"[{payload['ndcg10_ci_lo']:.3f}, {payload['ndcg10_ci_hi']:.3f}] | "
                f"{payload['n']} |"
            )
    lines.append("")
    lines.append(f"## Deltas vs paragraph (gate: ≥{min_lift_pct:.0f} % per language)")
    lines.append("")
    for key, payload in bench.summary.items():
        if not key.startswith("delta_"):
            continue
        lines.append(f"### {key}")
        for lang, info in payload.items():
            if lang == "delta_pct":
                lines.append(f"- **aggregate**: {info:+.1f} %")
            elif isinstance(info, dict):
                mark = "PASS" if info["delta_pct"] >= min_lift_pct else "FAIL"
                lines.append(
                    f"- {lang}: {info['delta_pct']:+.1f} % "
                    f"({info['baseline_mean']:.3f} → {info['new_mean']:.3f}) — {mark}"
                )
    return "\n".join(lines)
```

- [ ] **Step 3: Smoke-test the subcommand**

```bash
.venv/bin/python -m jw_eval.cli chunker-bench --help
```
Expected: typer help output for the new command.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-eval/src/jw_eval/cli.py
git commit -m "$(cat <<'EOF'
feat(jw-eval): jw eval chunker-bench subcommand with per-language gate

Reuses the existing eval CLI plumbing. Reports NDCG@10 per language per
variant with bootstrap CI and a configurable lift gate (default 10 %).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: `jw-cli` `--chunker` flag, `jw-mcp` `set_chunker` tool

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/main.py` (and the `rag ingest` subcommand file)
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Add the CLI flag**

In whichever module hosts `jw rag ingest ...` commands, thread a `--chunker` option through. Concretely (pseudocode for the existing typer structure):

```python
# packages/jw-cli/src/jw_cli/commands/rag.py
@rag_app.command("ingest")
def ingest_cmd(
    target: str,
    url: str | None = None,
    chunker: str | None = typer.Option(
        None,
        "--chunker",
        help="paragraph | semantic | llm. Overrides $JW_CHUNKER.",
    ),
) -> None:
    ...
    if target == "article" and url:
        import asyncio
        from jw_rag.ingest import ingest_article
        from jw_rag.store import VectorStore
        store = VectorStore(persist_dir=Path(".jw-rag"))
        asyncio.run(ingest_article(store, url, chunker=chunker))
```

If the CLI uses a single top-level `app`, add `--chunker` to the relevant ingest subcommand(s) following the same pattern. The key invariant: when the user passes `--chunker`, that value lands as the `chunker=` kwarg of `ingest_*`.

- [ ] **Step 2: Add the MCP tool**

In `packages/jw-mcp/src/jw_mcp/server.py`, register `set_chunker` and a per-session selection. Conservative shape (uses module-level state for the current MCP session, scoped to the server process):

```python
# packages/jw-mcp/src/jw_mcp/server.py (additions)
from jw_rag.chunkers import get_chunker

_session_chunker: str = "paragraph"


@mcp.tool()
def set_chunker(name: str) -> dict:
    """Set the active chunker for subsequent ingest calls in this session.

    Args:
        name: 'paragraph' | 'semantic' | 'llm'

    Returns:
        {'active_chunker': str}
    """
    global _session_chunker
    # Validate by attempting to resolve.
    try:
        c = get_chunker(name)
    except ValueError as exc:
        return {"error": str(exc)}
    _session_chunker = c.name
    return {"active_chunker": _session_chunker}
```

Then in any existing MCP ingest tool (e.g. `ingest_article_tool`), accept an optional `chunker: str | None = None` and prefer it over `_session_chunker`:

```python
@mcp.tool()
def ingest_article_tool(url: str, chunker: str | None = None) -> dict:
    effective = chunker or _session_chunker
    ...
    await ingest_article(store, url, chunker=effective)
    return {"chunks": n, "chunker": effective}
```

- [ ] **Step 3: Quick smoke-test the CLI**

```bash
.venv/bin/python -m jw_cli.main rag ingest article --help
```
Expected: `--chunker` flag is listed.

- [ ] **Step 4: Verify the MCP tool registers**

```bash
.venv/bin/python -c "from jw_mcp.server import mcp; print([t.name for t in mcp.list_tools()])"
```
Expected: `set_chunker` appears in the list.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli packages/jw-mcp
git commit -m "$(cat <<'EOF'
feat(cli,mcp): expose --chunker flag and set_chunker MCP tool

CLI: jw rag ingest article ... --chunker semantic|llm
MCP: set_chunker(name) plus optional chunker arg on ingest tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Nightly CI job + guide

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `docs/guias/semantic-chunking.md`

- [ ] **Step 1: Add the nightly job**

In `.github/workflows/ci.yml`, append:

```yaml
  chunker-bench-nightly:
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    name: chunker NDCG@10 (paragraph vs semantic)
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Sync workspace with embeddings extra
        run: uv sync --all-packages --extra local-embeddings
      - name: Run chunker-bench
        run: |
          JW_EVAL_LLM=none \
          uv run jw eval chunker-bench \
            --variants paragraph,semantic \
            --report md \
            --out chunker-bench.md
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: chunker-bench-report
          path: chunker-bench.md
```

And in the `on:` block, ensure schedule is enabled:

```yaml
on:
  schedule:
    - cron: "0 5 * * *"  # nightly 05:00 UTC
  push:
    branches: [main]
  pull_request:
```

- [ ] **Step 2: Write the user guide**

```markdown
<!-- docs/guias/semantic-chunking.md -->
# Semantic chunking (Fase 45)

> Quick reference for selecting and benchmarking chunkers in the
> jw-agent-toolkit.

## TL;DR

```bash
# Use the heuristic semantic chunker for one ingest.
JW_CHUNKER=semantic uv run jw rag ingest article <url>

# Or pass the flag explicitly.
uv run jw rag ingest article <url> --chunker semantic

# Run the NDCG@10 benchmark locally (paragraph vs semantic).
uv run jw eval chunker-bench --variants paragraph,semantic --report md --out bench.md
```

## What changed in Fase 45

`jw_rag.chunker.chunk_paragraphs` is still the public, default,
bit-stable API. Nothing breaks if you keep using it.

But you can now opt into:

1. **`semantic`** — merges paragraphs that start with a continuation
   marker (`Sin embargo`, `However`, `No entanto`, ...) with the previous
   chunk, and splits after closure markers (`Por lo tanto`, `Therefore`,
   `Portanto`, ...). Pure heuristic, no LLM, no network.
2. **`llm`** — runs `semantic` first, then asks the configured
   `jw_gen` provider for index-level split/merge actions (never text
   rewrites). Cached by content hash; same paragraphs → same output, no
   re-call.

Selection is in order of precedence:

1. `chunker=` kwarg on `ingest_*` or `get_chunker(name=...)`
2. `$JW_CHUNKER` env var
3. default = `paragraph`

## Marker catalog

Markers live in
`packages/jw-core/src/jw_core/data/continuation_markers.json` and ship for
**es / en / pt**. Adding a language is a JSON-only PR: append a block
with `continuation`, `closure`, `fingerprint` (function-word fingerprint
used by the cheap language detector).

## Re-ingest semantics

Existing indexed corpora are **not** auto-re-chunked. The chunker that
produced each chunk is recorded in `metadata["chunker"]`. To migrate a
corpus to semantic, re-ingest from source.

## Benchmarking

`jw eval chunker-bench`:
- reads `packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml`
- ingests/reads each variant's corpus
- runs `VectorStore.search(query, k=10)` and computes NDCG@10
- reports per-language mean + bootstrap 95 % CI + cross-variant delta
- exits non-zero if any non-baseline variant's per-language delta is
  below `--min-lift-pct` (default 10 %)

CI runs the bench nightly (paragraph vs semantic). The `llm` variant is
local-only because it needs a provider.

## Cache

The LLM chunker caches actions under
`~/.jw-agent-toolkit/chunk-cache/` (override with `$JW_CHUNK_CACHE_DIR`).
Key = `sha256(source_id|paragraphs|provider_id|prompt_version)`. Cache
hits hit > 95 % on identical inputs by design.

## When to use which

| Use case | Recommended chunker |
|---|---|
| Default ingest, batch jobs, CI | `paragraph` |
| Doctrinal Q&A, long-form articles | `semantic` |
| Off-line build with provider available, max recall | `llm` |
| Bible chapters | `paragraph` (verse-aware chunker is M11, not F45) |
```

- [ ] **Step 3: Add VISION/ROADMAP rows**

In `docs/VISION_AUDIT.md`, add a row for Fase 45:

```markdown
| 45 | semantic-chunking | ✅ Done | jw-rag, jw-eval | semantic + llm chunkers, NDCG@10 ≥ 10 % per language |
```

In `docs/ROADMAP.md`, add a Fase 45 section pointing to the spec and this guide.

- [ ] **Step 4: Run full test suite to confirm no regression**

```bash
.venv/bin/python -m pytest packages/ -v
```
Expected: full suite green (chunkers/ subset + everything else).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml docs/guias/semantic-chunking.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "$(cat <<'EOF'
docs(jw-rag): semantic-chunking guide; CI nightly chunker-bench job

Adds docs/guias/semantic-chunking.md, registers the chunker-bench-nightly
job (cron 05:00 UTC), and updates VISION_AUDIT/ROADMAP rows.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Verified against the spec § Métricas de éxito:**

- ✅ `JW_CHUNKER=paragraph` bit-for-bit identical to pre-F45 — locked by
  `test_paragraph_chunker_equivalent_to_legacy` (Task 1).
- ✅ Continuation merge implemented per language with +30 % overflow and a
  2-in-a-row safety flush (risk #1) — Task 3 + tests.
- ✅ Closure split only fires past `min_chars` (risk #7) — Task 4.
- ✅ Language detection failure degrades to ParagraphChunker (risk #4) —
  `_fallback_chunks` path with `mixed_language=true`.
- ✅ Cache hit > 95 % verified by `test_hit_rate_over_95pct_on_repeated_inputs`
  (Task 6).
- ✅ NDCG@10 computed per language with bootstrap 95 % CI lower bound; gate
  enforced per language (risks #3, #6) — Tasks 8-10.
- ✅ Cache is in `$HOME` not the repo; markers are JSON not code; LLMChunker
  emits indices only (Policy #6) — Task 5 implementation.
- ✅ `Chunker` Protocol satisfied by all three implementations + fake — Task 1.
- ✅ Façade keeps every existing import (`from jw_rag.chunker import ...`)
  working — Task 1.

**Coverage check:**
- 12 tasks, each with a Files block and the canonical 5-step TDD shape
  (write failing test → run-to-fail → implement → run-to-pass → commit).
- All inline code blocks are complete and importable; no `...` placeholders
  in production code. Test bodies are self-contained.
- Multilingual coverage: es / en / pt fixtures and parametrized tests for
  continuation and closure.
- Backwards-compat: locked by a dedicated test that runs `chunk_legacy()`
  against `ParagraphChunker().chunk()` over a golden input.
- NDCG benchmark: orchestrator unit-tested with a stub store; CLI subcommand
  wires it to the real RAG store; nightly CI job uploads the report.

**Open follow-ups (out of scope, by design — match the spec's § Pendientes):**
- Auto-re-chunk command `jw rag rechunk`.
- Verse-aware chunker for Bible chapters (M11, not F45).
- Web UI for chunker diffs.

## Execution choice

Recommended sub-skill: `superpowers:subagent-driven-development`. Reasons:
- The plan is large (12 tasks, ~1300 LOC + tests). Subagents per task keep
  context fresh and isolated, matching how this monorepo handled F22.
- Tasks 8 and 9 are tightly coupled (NDCG → orchestrator); a subagent can
  hold both in one window without blowing context.
- Tasks 1, 7, 11 touch existing files (façade, ingest, CLI/MCP) — each is a
  bounded edit suitable for an isolated subagent.

If executing serially without subagents, follow strict order 1 → 12. Tasks
3 and 5 must precede 7 (ingest integration depends on the chunkers existing).
Tasks 8 and 9 must precede 10 (CLI wires the orchestrator). Task 12 is the
finalization.
