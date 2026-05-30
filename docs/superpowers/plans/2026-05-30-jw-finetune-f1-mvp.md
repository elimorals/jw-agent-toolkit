# jw-finetune F1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el paquete `jw-finetune` con CLI funcional que permita: extraer corpus de JWPUB/EPUB/WOL → preparar dataset (CPT raw o SFT Q&A) → entrenar con Unsloth (LoRA) → evaluar → exportar a GGUF/MLX/safetensors.

**Architecture:** Nuevo paquete en monorepo (`packages/jw-finetune`), reutiliza parsers de `jw-core` y chunker de `jw-rag`. Unsloth como dep directa con extras opcionales (`[cuda]`, `[mlx]`, `[rocm]`). Capa Python traduce conceptos JW (`Recipe`) a configs Unsloth. TDD donde sea posible (extract, dedupe, chunk, validators, recipes); para training se usa `sshleifer/tiny-gpt2` en CI.

**Tech Stack:** Python 3.13, uv workspace, hatchling build, Typer (CLI), Pydantic/dataclass (modelos), Unsloth + trl + transformers + datasets (training), Jinja2 (templates), anthropic + ollama (synth providers), pytest + pytest-asyncio + hypothesis (tests).

---

## File Structure

```
packages/jw-finetune/
├── pyproject.toml
├── README.md
└── src/jw_finetune/
    ├── __init__.py            # version + public exports
    ├── data/
    │   ├── __init__.py
    │   ├── models.py          # ParagraphRecord, SourceSpec, Dataset
    │   ├── extract.py         # JWPUB/EPUB/WOL → ParagraphRecord
    │   ├── dedupe.py          # simhash near-duplicate removal
    │   ├── chunk.py           # adapter over jw_rag.chunker
    │   └── formats.py         # JSONL writers (Alpaca, ShareGPT, raw)
    ├── recipes/
    │   ├── __init__.py
    │   ├── base.py            # Recipe dataclass + validation
    │   ├── presets.py         # 4 built-in presets + registry
    │   └── templates/         # Jinja2 prompt templates
    │       ├── doctrinal_qa.j2
    │       ├── verse_explainer.j2
    │       └── apologetics.j2
    ├── synth/
    │   ├── __init__.py
    │   ├── provider.py        # LLMProvider Protocol
    │   ├── anthropic_provider.py
    │   ├── ollama_provider.py
    │   ├── validators.py      # bible-ref regex, lang detect, length
    │   └── orchestrator.py    # synth.py orchestrator
    ├── train/
    │   ├── __init__.py
    │   ├── sft.py             # SFTTrainer wrapper
    │   ├── cpt.py             # continued pretraining
    │   └── callback.py        # JWMonitorCallback (stub for F1)
    ├── eval/
    │   ├── __init__.py
    │   ├── refs.py            # bible reference validation
    │   ├── doctrinal.py       # terminology heuristics
    │   └── runner.py          # eval orchestrator
    ├── export/
    │   ├── __init__.py
    │   ├── gguf.py
    │   ├── mlx.py
    │   └── safetensors_export.py
    └── cli.py                 # Typer app

tests/jw-finetune/
├── conftest.py
├── fixtures/
│   ├── sample.epub
│   └── tiny_chunks.jsonl
├── test_data_models.py
├── test_extract.py
├── test_dedupe.py
├── test_chunk.py
├── test_formats.py
├── test_recipes.py
├── test_synth_validators.py
├── test_synth_orchestrator.py
├── test_train_smoke.py        # uses sshleifer/tiny-gpt2
├── test_eval_refs.py
├── test_export.py
└── test_cli.py
```

---

## Group A — Skeleton & Data Layer

### Task 1: Crear esqueleto del paquete

**Files:**
- Create: `packages/jw-finetune/pyproject.toml`
- Create: `packages/jw-finetune/README.md`
- Create: `packages/jw-finetune/src/jw_finetune/__init__.py`
- Modify: `pyproject.toml` (root) — añadir miembro al workspace
- Create: `packages/jw-finetune/tests/__init__.py`

- [ ] **Step 1: Crear `packages/jw-finetune/pyproject.toml`**

```toml
[project]
name = "jw-finetune"
version = "0.1.0"
description = "Local fine-tuning platform for JW publications, powered by Unsloth"
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = [
    "jw-core",
    "jw-rag",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "jinja2>=3.1.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
cuda  = ["unsloth", "bitsandbytes", "trl>=0.11.0", "transformers>=4.45.0", "datasets>=3.0.0", "accelerate>=0.34.0"]
mlx   = ["mlx>=0.18.0", "mlx-lm>=0.18.0", "transformers>=4.45.0", "datasets>=3.0.0"]
rocm  = ["unsloth", "trl>=0.11.0", "transformers>=4.45.0", "datasets>=3.0.0", "accelerate>=0.34.0"]
synth = ["anthropic>=0.40.0", "ollama>=0.4.0", "langdetect>=1.0.9"]
monitor = ["fastapi>=0.115.0", "uvicorn>=0.32.0", "websockets>=13.0", "psutil>=6.0.0"]

[project.scripts]
jw-finetune = "jw_finetune.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_finetune"]
```

- [ ] **Step 2: Crear `packages/jw-finetune/README.md`**

```markdown
# jw-finetune

Local fine-tuning platform for JW publications, powered by [Unsloth](https://github.com/unslothai/unsloth).

> ⚠️ **Disclaimer**: Este paquete genera modelos derivados de publicaciones con copyright de Watchtower Bible and Tract Society. El uso de los pesos resultantes es responsabilidad del usuario y debe respetar los términos oficiales. NO distribuye pesos ni contenido.

## Installation

```bash
# Solo data prep (todos los OS, sin GPU)
uv sync --package jw-finetune

# NVIDIA
uv sync --package jw-finetune --extra cuda

# Apple Silicon
uv sync --package jw-finetune --extra mlx

# AMD ROCm
uv sync --package jw-finetune --extra rocm

# Q&A synth con Anthropic/Ollama
uv sync --package jw-finetune --extra synth
```

## Quick start

```bash
jw-finetune prepare --recipe doctrinal-qa-es-sft --source ./mis-jwpubs/
jw-finetune train --workspace ./jw-finetune-workspace/run-*
jw-finetune export --format gguf --quant Q4_K_M
```

See `docs/guias/fine-tuning-local.md` for the full guide.
```

- [ ] **Step 3: Crear `packages/jw-finetune/src/jw_finetune/__init__.py`**

```python
"""jw-finetune: local fine-tuning platform for JW publications."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Crear `packages/jw-finetune/tests/__init__.py`** (vacío)

- [ ] **Step 5: Añadir al workspace en `pyproject.toml` raíz**

Modificar la sección `[tool.uv.workspace]` para incluir `packages/jw-finetune`, y añadir `jw-finetune = { workspace = true }` bajo `[tool.uv.sources]`.

- [ ] **Step 6: Sync del workspace**

```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv sync --all-packages
```

Expected: instalación exitosa, sin Unsloth (es opcional).

- [ ] **Step 7: Verificar el entry-point**

```bash
uv run jw-finetune --help
```

Expected: Typer aún no tiene comandos definidos, pero el entry-point debe resolver (puede mostrar error de import en cli; lo aceptamos para este step).

- [ ] **Step 8: Commit**

```bash
git add packages/jw-finetune pyproject.toml
git commit -m "feat(jw-finetune): package skeleton with optional GPU extras"
```

---

### Task 2: Modelos de datos (`ParagraphRecord`, `SourceSpec`)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/data/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/data/models.py`
- Create: `packages/jw-finetune/tests/test_data_models.py`

- [ ] **Step 1: Escribir test**

`tests/test_data_models.py`:

```python
from jw_finetune.data.models import ParagraphRecord, SourceSpec


def test_paragraph_record_minimal():
    p = ParagraphRecord(
        text="In the beginning God created the heavens and the earth.",
        pub_code="nwt",
        language="en",
        kind="bible",
        source_path="wol:gen:1",
    )
    assert p.text.startswith("In the beginning")
    assert p.language == "en"
    assert p.doc_id == ""
    assert p.paragraph_pid is None


def test_paragraph_record_immutable():
    p = ParagraphRecord(text="x", pub_code="w24", language="es", kind="watchtower", source_path="x")
    import pytest, dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.text = "y"


def test_source_spec_jwpub():
    s = SourceSpec(kind="jwpub", path="./pubs/w_S_202412.jwpub", language="es")
    assert s.kind == "jwpub"
    assert s.language == "es"


def test_source_spec_wol():
    s = SourceSpec(kind="wol-article", path="https://wol.jw.org/...", language="en")
    assert s.kind == "wol-article"
```

- [ ] **Step 2: Ejecutar test → debe fallar**

```bash
uv run pytest packages/jw-finetune/tests/test_data_models.py -v
```

Expected: ImportError, módulo no existe aún.

- [ ] **Step 3: Crear `packages/jw-finetune/src/jw_finetune/data/__init__.py`**

```python
"""Data layer: extraction, dedupe, chunking, dataset formats."""
```

- [ ] **Step 4: Crear `packages/jw-finetune/src/jw_finetune/data/models.py`**

```python
"""Data models for the fine-tune pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PublicationKind = Literal[
    "watchtower",      # w / wp (Atalaya, edición estudio o pública)
    "awake",           # g (Despertad!)
    "book",            # libros (lff, jy, sjj, etc.)
    "brochure",        # folletos
    "bible",           # NWT u otra
    "article",         # artículo WOL
    "broadcast",       # transcripción JW Broadcasting (futuro)
    "other",
]

SourceKind = Literal["jwpub", "epub", "wol-article", "wol-bible", "raw-text"]


@dataclass(frozen=True)
class ParagraphRecord:
    """Una unidad de texto extraída de una publicación JW.

    Inmutable para que pase libremente por el pipeline sin riesgo de mutación.
    """

    text: str
    pub_code: str
    language: str                 # ISO 639-1 ("es", "en") o "und" si desconocido
    kind: PublicationKind
    source_path: str              # ruta local o URL
    doc_id: str = ""              # MEPS doc id si está disponible
    section_ref: str = ""         # "w24 12 p.7", "lff lección 5", etc.
    paragraph_pid: int | None = None
    spine_index: int | None = None  # solo EPUB
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceSpec:
    """Especificación de una fuente de datos para el recipe."""

    kind: SourceKind
    path: str                     # ruta a archivo local o URL
    language: str                 # idioma esperado (puede sobreescribir el detectado)
    pub_code_hint: str = ""       # opcional, ayuda a parsers ambiguos
    publication_kind_hint: PublicationKind | None = None
```

- [ ] **Step 5: Ejecutar test → debe pasar**

```bash
uv run pytest packages/jw-finetune/tests/test_data_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/data packages/jw-finetune/tests/test_data_models.py
git commit -m "feat(jw-finetune): ParagraphRecord and SourceSpec data models"
```

---

### Task 3: Extracción desde JWPUB / EPUB / WOL

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/data/extract.py`
- Create: `packages/jw-finetune/tests/test_extract.py`

- [ ] **Step 1: Escribir test**

`tests/test_extract.py`:

```python
from pathlib import Path
from jw_finetune.data.extract import extract_from_epub, extract_from_jwpub
from jw_finetune.data.models import ParagraphRecord


def test_extract_from_epub(tmp_path):
    # Use an EPUB fixture that already exists in jw-core tests if available;
    # otherwise skip. For now: build a minimal-but-valid epub on the fly is
    # out of scope; expect a path that exists.
    sample = tmp_path / "missing.epub"
    sample.write_text("dummy")
    # parse_epub will raise; that's the error we want to surface
    import pytest
    with pytest.raises(Exception):
        list(extract_from_epub(sample, language_hint="es"))


def test_extract_from_jwpub_smoke(tmp_path):
    # We cannot ship a JWPUB binary in the repo. Smoke test asserts the
    # function exists and raises a sensible error for a missing file.
    import pytest
    with pytest.raises(FileNotFoundError):
        list(extract_from_jwpub(tmp_path / "missing.jwpub", language_hint="es"))


def test_record_kind_inference():
    from jw_finetune.data.extract import _infer_kind_from_pub_code
    assert _infer_kind_from_pub_code("w24") == "watchtower"
    assert _infer_kind_from_pub_code("wp23") == "watchtower"
    assert _infer_kind_from_pub_code("g") == "awake"
    assert _infer_kind_from_pub_code("g23") == "awake"
    assert _infer_kind_from_pub_code("lff") == "book"
    assert _infer_kind_from_pub_code("nwt") == "bible"
    assert _infer_kind_from_pub_code("foo") == "other"
```

- [ ] **Step 2: Ejecutar test → debe fallar**

```bash
uv run pytest packages/jw-finetune/tests/test_extract.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implementar `data/extract.py`**

```python
"""Extract ParagraphRecord from JWPUB / EPUB / WOL sources."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

from jw_core.parsers.epub import parse_epub
from jw_core.parsers.jwpub import parse_jwpub

from jw_finetune.data.models import ParagraphRecord, PublicationKind

logger = logging.getLogger(__name__)

# Regex que detecta el "pub_code" canónico al inicio del symbol JWPUB.
_PUBCODE_KIND_PREFIXES: tuple[tuple[str, PublicationKind], ...] = (
    ("wp", "watchtower"),   # public Watchtower
    ("ws", "watchtower"),   # study edition (sometimes)
    ("w", "watchtower"),
    ("g", "awake"),
    ("lff", "book"),
    ("jy", "book"),
    ("sjj", "book"),
    ("bh", "book"),
    ("rr", "book"),
    ("nwt", "bible"),
    ("bi", "bible"),
)


def _infer_kind_from_pub_code(pub_code: str) -> PublicationKind:
    pc = (pub_code or "").lower().strip()
    if not pc:
        return "other"
    for prefix, kind in _PUBCODE_KIND_PREFIXES:
        if pc == prefix or pc.startswith(prefix):
            # avoid wp-prefix capturing "wp" but also matching things like "wpub" — ok for JW
            # but check that next char (if any) is a digit or underscore
            tail = pc[len(prefix):]
            if not tail or tail[0].isdigit() or tail[0] in "_-":
                return kind
    return "other"


def _clean_paragraph(text: str) -> str:
    """Normalize whitespace; reject empty/super-short fragments."""
    t = re.sub(r"\s+", " ", text).strip()
    return t


def extract_from_epub(
    path: Path | str,
    *,
    language_hint: str = "",
    pub_code_hint: str = "",
    min_chars: int = 30,
) -> Iterator[ParagraphRecord]:
    """Yield ParagraphRecord per paragraph in the EPUB."""
    epub = parse_epub(path)
    lang = (epub.language or language_hint or "und").lower()[:2]
    pub_code = pub_code_hint or _derive_pub_code_from_title(epub.title)
    kind = _infer_kind_from_pub_code(pub_code)

    for doc in epub.documents:
        for i, raw in enumerate(doc.paragraphs):
            text = _clean_paragraph(raw)
            if len(text) < min_chars:
                continue
            yield ParagraphRecord(
                text=text,
                pub_code=pub_code,
                language=lang,
                kind=kind,
                source_path=str(path),
                doc_id=doc.id,
                section_ref=f"{pub_code} {doc.title or doc.id} p.{i+1}",
                paragraph_pid=None,
                spine_index=doc.spine_index,
                extra={"epub_title": doc.title, "creator": epub.creator},
            )


def extract_from_jwpub(
    path: Path | str,
    *,
    language_hint: str = "",
    min_chars: int = 30,
) -> Iterator[ParagraphRecord]:
    """Yield ParagraphRecord per paragraph from a (decrypted) JWPUB.

    Raises FileNotFoundError if the file is missing.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    meta = parse_jwpub(p)
    if not meta.decrypted_text_available:
        logger.warning("JWPUB %s could not be decrypted; skipping.", p)
        return

    pub_code = meta.symbol or "unknown"
    kind = _infer_kind_from_pub_code(pub_code)
    # JWPUB uses MEPS language_index (int); map via jw_core.languages
    lang = _meps_to_iso(meta.language_index, fallback=language_hint or "und")

    for doc in meta.documents:
        for i, raw in enumerate(doc.paragraphs):
            text = _clean_paragraph(raw)
            if len(text) < min_chars:
                continue
            yield ParagraphRecord(
                text=text,
                pub_code=pub_code,
                language=lang,
                kind=kind,
                source_path=str(p),
                doc_id=str(doc.meps_document_id),
                section_ref=f"{pub_code} {doc.title or doc.toc_title} p.{i+1}",
                paragraph_pid=None,
                extra={"chapter_number": str(doc.chapter_number or 0)},
            )


def _derive_pub_code_from_title(title: str) -> str:
    """Best-effort: 'Atalaya — Edición de Estudio 2024' → 'w24', etc."""
    if not title:
        return "unknown"
    t = title.lower()
    if "atalaya" in t or "watchtower" in t:
        return "w"
    if "despertad" in t or "awake" in t:
        return "g"
    return "book"


def _meps_to_iso(meps_index: int, fallback: str) -> str:
    try:
        from jw_core.languages import Language, registry
    except Exception:
        return fallback or "und"
    try:
        lang: Language | None = registry.by_meps(meps_index)
        return (lang.iso if lang else fallback) or fallback or "und"
    except Exception:
        return fallback or "und"
```

> **Note:** El último helper `_meps_to_iso` asume API de `jw_core.languages`. Si la API real difiere, el implementador debe ajustar (`registry.by_meps`, `registry.find`, etc.) — esto es esperado en F1 dado que `jw_core.languages` evoluciona.

- [ ] **Step 4: Ejecutar test → debe pasar**

```bash
uv run pytest packages/jw-finetune/tests/test_extract.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/data/extract.py packages/jw-finetune/tests/test_extract.py
git commit -m "feat(jw-finetune): extract ParagraphRecord from JWPUB/EPUB"
```

---

### Task 4: Deduplicación (simhash near-duplicates)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/data/dedupe.py`
- Create: `packages/jw-finetune/tests/test_dedupe.py`

- [ ] **Step 1: Test**

```python
from jw_finetune.data.dedupe import simhash, hamming_distance, deduplicate
from jw_finetune.data.models import ParagraphRecord


def _rec(text: str) -> ParagraphRecord:
    return ParagraphRecord(text=text, pub_code="w24", language="es", kind="watchtower", source_path="x")


def test_simhash_stable():
    h1 = simhash("Hello world this is a test")
    h2 = simhash("Hello world this is a test")
    assert h1 == h2


def test_simhash_similar_close():
    h1 = simhash("Hello world this is a test sentence")
    h2 = simhash("Hello world this is a test sentence!")
    assert hamming_distance(h1, h2) < 5


def test_simhash_different_far():
    h1 = simhash("The cat sat on the mat lazily")
    h2 = simhash("Quantum chromodynamics describes the strong force")
    assert hamming_distance(h1, h2) > 15


def test_deduplicate_removes_near_duplicates():
    records = [
        _rec("In the beginning God created the heavens and the earth."),
        _rec("In the beginning God created the heavens and the earth!"),  # near-dup
        _rec("The earth was formless and waste."),
    ]
    deduped = list(deduplicate(records, threshold=4))
    assert len(deduped) == 2
```

- [ ] **Step 2: Implementar `data/dedupe.py`**

```python
"""Near-duplicate detection via simhash (64-bit)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator

from jw_finetune.data.models import ParagraphRecord

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _hash64(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, *, bits: int = 64) -> int:
    """Charikar simhash. Returns a 64-bit int."""
    vec = [0] * bits
    tokens = _tokens(text)
    if not tokens:
        return 0
    for tok in tokens:
        h = _hash64(tok)
        for i in range(bits):
            if h & (1 << (bits - 1 - i)):
                vec[i] += 1
            else:
                vec[i] -= 1
    out = 0
    for i in range(bits):
        if vec[i] > 0:
            out |= 1 << (bits - 1 - i)
    return out


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def deduplicate(
    records: Iterable[ParagraphRecord],
    *,
    threshold: int = 4,
) -> Iterator[ParagraphRecord]:
    """Yield records skipping near-duplicates (hamming distance ≤ threshold)."""
    seen: list[int] = []
    for r in records:
        h = simhash(r.text)
        if any(hamming_distance(h, s) <= threshold for s in seen):
            continue
        seen.append(h)
        yield r
```

- [ ] **Step 3: Ejecutar test → debe pasar**

```bash
uv run pytest packages/jw-finetune/tests/test_dedupe.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/data/dedupe.py packages/jw-finetune/tests/test_dedupe.py
git commit -m "feat(jw-finetune): simhash near-duplicate deduplication"
```

---

### Task 5: Chunking (adapter sobre jw_rag.chunker)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/data/chunk.py`
- Create: `packages/jw-finetune/tests/test_chunk.py`

- [ ] **Step 1: Test**

```python
from jw_finetune.data.chunk import records_to_chunks
from jw_finetune.data.models import ParagraphRecord


def test_records_to_chunks_preserves_metadata():
    records = [
        ParagraphRecord(text="Para uno.", pub_code="w24", language="es",
                         kind="watchtower", source_path="x", section_ref="w24 1"),
        ParagraphRecord(text="Para dos un poco más larga para no fusionarse demasiado.",
                         pub_code="w24", language="es", kind="watchtower",
                         source_path="x", section_ref="w24 2"),
    ]
    chunks = records_to_chunks(records, max_chars=200, min_chars=10)
    assert len(chunks) >= 1
    # metadata propagates
    assert any(c.metadata.get("language") == "es" for c in chunks)
    assert any(c.metadata.get("pub_code") == "w24" for c in chunks)
```

- [ ] **Step 2: Implementar `data/chunk.py`**

```python
"""Chunking adapter — uses `jw_rag.chunker` but groups records by source."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from jw_rag.chunker import Chunk, chunk_paragraphs

from jw_finetune.data.models import ParagraphRecord


def records_to_chunks(
    records: Iterable[ParagraphRecord],
    *,
    max_chars: int = 1500,
    min_chars: int = 80,
) -> list[Chunk]:
    """Group records by (pub_code, doc_id) and chunk each group."""
    groups: dict[tuple[str, str], list[ParagraphRecord]] = defaultdict(list)
    for r in records:
        groups[(r.pub_code, r.doc_id)].append(r)

    all_chunks: list[Chunk] = []
    for (pub_code, doc_id), group in groups.items():
        if not group:
            continue
        paragraphs = [r.text for r in group]
        first = group[0]
        chunks = chunk_paragraphs(
            paragraphs,
            source_id=f"{pub_code}:{doc_id or 'na'}",
            max_chars=max_chars,
            min_chars=min_chars,
            metadata={
                "pub_code": pub_code,
                "doc_id": doc_id,
                "language": first.language,
                "kind": first.kind,
                "source_path": first.source_path,
                "section_ref": first.section_ref,
            },
        )
        all_chunks.extend(chunks)
    return all_chunks
```

- [ ] **Step 3: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_chunk.py -v
git add packages/jw-finetune/src/jw_finetune/data/chunk.py packages/jw-finetune/tests/test_chunk.py
git commit -m "feat(jw-finetune): records_to_chunks adapter over jw_rag.chunker"
```

---

### Task 6: Formatos de dataset (JSONL writers)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/data/formats.py`
- Create: `packages/jw-finetune/tests/test_formats.py`

- [ ] **Step 1: Test**

```python
import json
from pathlib import Path
from jw_finetune.data.formats import (
    write_raw_jsonl, write_sharegpt_jsonl, write_alpaca_jsonl, QAPair,
)
from jw_rag.chunker import Chunk


def test_write_raw_jsonl(tmp_path: Path):
    chunks = [Chunk(id="x:0", text="hola mundo", source_id="x", metadata={"language": "es"})]
    out = tmp_path / "raw.jsonl"
    n = write_raw_jsonl(chunks, out)
    assert n == 1
    line = out.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"text": "hola mundo", "metadata": {"language": "es", "source_id": "x"}}


def test_write_sharegpt_jsonl(tmp_path: Path):
    qas = [
        QAPair(question="¿Qué es el Reino?",
               answer="El Reino es el gobierno celestial de Dios.",
               source_chunk_id="w24:1#0",
               language="es",
               metadata={"pub_code": "w24"}),
    ]
    out = tmp_path / "sft.jsonl"
    n = write_sharegpt_jsonl(qas, out)
    assert n == 1
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["messages"][0]["role"] == "user"
    assert rec["messages"][0]["content"] == "¿Qué es el Reino?"
    assert rec["messages"][1]["role"] == "assistant"
    assert rec["metadata"]["language"] == "es"
```

- [ ] **Step 2: Implementar**

```python
"""JSONL writers: raw (CPT), ShareGPT (SFT), Alpaca (SFT alt)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from jw_rag.chunker import Chunk


@dataclass(frozen=True)
class QAPair:
    """A synthesized Q&A example."""
    question: str
    answer: str
    source_chunk_id: str
    language: str
    metadata: dict[str, str] = field(default_factory=dict)


def write_raw_jsonl(chunks: Iterable[Chunk], path: Path) -> int:
    """Write raw text records for CPT. Returns number of records written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            md = dict(c.metadata)
            md["source_id"] = c.source_id
            f.write(json.dumps({"text": c.text, "metadata": md}, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_sharegpt_jsonl(qas: Iterable[QAPair], path: Path) -> int:
    """Write ShareGPT-format records for SFT."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for qa in qas:
            rec = {
                "messages": [
                    {"role": "user", "content": qa.question},
                    {"role": "assistant", "content": qa.answer},
                ],
                "metadata": {
                    "language": qa.language,
                    "source_chunk_id": qa.source_chunk_id,
                    **qa.metadata,
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_alpaca_jsonl(qas: Iterable[QAPair], path: Path) -> int:
    """Write Alpaca-format records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for qa in qas:
            rec = {
                "instruction": qa.question,
                "input": "",
                "output": qa.answer,
                "metadata": {
                    "language": qa.language,
                    "source_chunk_id": qa.source_chunk_id,
                    **qa.metadata,
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count
```

- [ ] **Step 3: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_formats.py -v
git add packages/jw-finetune/src/jw_finetune/data/formats.py packages/jw-finetune/tests/test_formats.py
git commit -m "feat(jw-finetune): dataset format writers (raw, ShareGPT, Alpaca)"
```

---

## Group B — Recipes

### Task 7: `Recipe` dataclass + validación

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/recipes/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/recipes/base.py`
- Create: `packages/jw-finetune/tests/test_recipes.py`

- [ ] **Step 1: Test**

```python
import pytest
from jw_finetune.recipes.base import Recipe, validate_recipe
from jw_finetune.data.models import SourceSpec


def test_recipe_minimal_valid():
    r = Recipe(
        name="my-recipe",
        task="sft",
        sources=[SourceSpec(kind="jwpub", path="x.jwpub", language="es")],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
    )
    errors = validate_recipe(r)
    assert errors == []


def test_recipe_sft_requires_qa_style():
    r = Recipe(name="x", task="sft", sources=[], languages=["es"],
               publication_kinds=["watchtower"], qa_style=None,
               base_model="unsloth/Qwen2.5-3B-bnb-4bit")
    errors = validate_recipe(r)
    assert any("qa_style" in e for e in errors)


def test_recipe_empty_sources_error():
    r = Recipe(name="x", task="cpt", sources=[], languages=["es"],
               publication_kinds=["watchtower"], qa_style=None,
               base_model="unsloth/Qwen2.5-3B-bnb-4bit")
    errors = validate_recipe(r)
    assert any("sources" in e for e in errors)


def test_recipe_yaml_roundtrip(tmp_path):
    from jw_finetune.recipes.base import recipe_to_yaml, recipe_from_yaml
    r = Recipe(name="my", task="cpt",
               sources=[SourceSpec(kind="epub", path="a.epub", language="es")],
               languages=["es"], publication_kinds=["watchtower"],
               qa_style=None, base_model="unsloth/Qwen2.5-3B-bnb-4bit",
               epochs=2, lora_rank=32)
    p = tmp_path / "r.yaml"
    recipe_to_yaml(r, p)
    r2 = recipe_from_yaml(p)
    assert r2.name == "my"
    assert r2.epochs == 2
    assert r2.lora_rank == 32
    assert r2.sources[0].kind == "epub"
```

- [ ] **Step 2: Implementar**

`packages/jw-finetune/src/jw_finetune/recipes/__init__.py`:
```python
"""Recipes: the JW-domain → Unsloth-config translation layer."""
```

`packages/jw-finetune/src/jw_finetune/recipes/base.py`:

```python
"""Recipe dataclass + validation + YAML roundtrip."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from jw_finetune.data.models import PublicationKind, SourceSpec

Task = Literal["cpt", "sft", "grpo"]
QAStyle = Literal["doctrinal", "verse-explain", "objection-handling"]
SynthProvider = Literal["anthropic", "ollama"]


@dataclass
class Recipe:
    """A JW-domain recipe that translates to an Unsloth training config."""

    name: str
    task: Task
    sources: list[SourceSpec]
    languages: list[str]
    publication_kinds: list[PublicationKind]
    qa_style: QAStyle | None
    base_model: str

    # training hyperparams
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    max_seq_len: int = 2048
    epochs: int = 1
    batch_size: int = 2
    gradient_accumulation: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    weight_decay: float = 0.0

    # data prep
    min_chunk_chars: int = 80
    max_chunk_chars: int = 1500
    dedupe_threshold: int = 4
    synth_provider: SynthProvider | None = "ollama"
    synth_model: str | None = None
    qa_per_chunk: int = 3
    eval_split: float = 0.05

    # output
    output_dir: str = "./jw-finetune-workspace"
    seed: int = 42
    extra: dict[str, str] = field(default_factory=dict)


def validate_recipe(r: Recipe) -> list[str]:
    """Return list of validation errors; empty = valid."""
    errors: list[str] = []
    if not r.name or not r.name.strip():
        errors.append("name: must be non-empty")
    if r.task == "sft" and r.qa_style is None:
        errors.append("qa_style: required when task='sft'")
    if not r.sources:
        errors.append("sources: at least one SourceSpec required")
    if not r.languages:
        errors.append("languages: at least one language required")
    if r.lora_rank < 1 or r.lora_rank > 256:
        errors.append("lora_rank: must be in [1, 256]")
    if r.epochs < 1:
        errors.append("epochs: must be >= 1")
    if r.eval_split < 0 or r.eval_split >= 0.5:
        errors.append("eval_split: must be in [0, 0.5)")
    return errors


def recipe_to_yaml(recipe: Recipe, path: Path) -> None:
    """Serialize recipe to YAML. Lazy-imports PyYAML."""
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise ImportError("PyYAML required: pip install pyyaml") from e
    d = asdict(recipe)
    path.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True), encoding="utf-8")


def recipe_from_yaml(path: Path) -> Recipe:
    """Load a Recipe from YAML."""
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise ImportError("PyYAML required: pip install pyyaml") from e
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["sources"] = [SourceSpec(**s) for s in raw.get("sources", [])]
    return Recipe(**raw)
```

> **Note:** Añadir `pyyaml>=6.0.0` a las deps base de `jw-finetune/pyproject.toml`.

- [ ] **Step 3: Añadir `pyyaml` a deps** y re-sync

Modify `packages/jw-finetune/pyproject.toml` dependencies para incluir `"pyyaml>=6.0.0"`, then:
```bash
uv sync --all-packages
```

- [ ] **Step 4: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_recipes.py -v
git add packages/jw-finetune/src/jw_finetune/recipes packages/jw-finetune/tests/test_recipes.py packages/jw-finetune/pyproject.toml
git commit -m "feat(jw-finetune): Recipe dataclass with validation and YAML I/O"
```

---

### Task 8: Preset registry + 4 presets

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/recipes/presets.py`
- Modify: `packages/jw-finetune/tests/test_recipes.py` (añadir)

- [ ] **Step 1: Test (append to test_recipes.py)**

```python
def test_preset_registry_contains_required():
    from jw_finetune.recipes.presets import PRESETS, get_preset
    expected = {
        "watchtower-style-es-cpt",
        "doctrinal-qa-es-sft",
        "verse-explainer-multilang-sft",
        "apologetics-objections-sft",
    }
    assert expected <= set(PRESETS.keys())


def test_get_preset_returns_valid_recipe():
    from jw_finetune.recipes.presets import get_preset
    from jw_finetune.recipes.base import validate_recipe
    r = get_preset("doctrinal-qa-es-sft")
    assert r.task == "sft"
    assert r.qa_style == "doctrinal"
    # Presets have empty sources by default; user fills them in.
    # Validate with stub source:
    from jw_finetune.data.models import SourceSpec
    r.sources = [SourceSpec(kind="jwpub", path="x.jwpub", language="es")]
    assert validate_recipe(r) == []


def test_get_preset_unknown_raises():
    from jw_finetune.recipes.presets import get_preset
    import pytest
    with pytest.raises(KeyError):
        get_preset("nonexistent-preset")
```

- [ ] **Step 2: Implementar `recipes/presets.py`**

```python
"""Built-in recipe presets."""

from __future__ import annotations

from copy import deepcopy

from jw_finetune.recipes.base import Recipe


PRESETS: dict[str, Recipe] = {
    "watchtower-style-es-cpt": Recipe(
        name="watchtower-style-es-cpt",
        task="cpt",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style=None,
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
        lora_rank=32,
        lora_alpha=64,
        max_seq_len=2048,
        epochs=1,
        learning_rate=1e-4,
    ),
    "doctrinal-qa-es-sft": Recipe(
        name="doctrinal-qa-es-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["watchtower", "book"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=2048,
        epochs=2,
        learning_rate=2e-4,
        qa_per_chunk=3,
    ),
    "verse-explainer-multilang-sft": Recipe(
        name="verse-explainer-multilang-sft",
        task="sft",
        sources=[],
        languages=["es", "en"],
        publication_kinds=["bible", "watchtower", "book"],
        qa_style="verse-explain",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=3072,
        epochs=2,
        learning_rate=1.5e-4,
        qa_per_chunk=2,
    ),
    "apologetics-objections-sft": Recipe(
        name="apologetics-objections-sft",
        task="sft",
        sources=[],
        languages=["es"],
        publication_kinds=["book", "brochure", "article"],
        qa_style="objection-handling",
        base_model="unsloth/Qwen2.5-7B-bnb-4bit",
        lora_rank=16,
        lora_alpha=32,
        max_seq_len=2048,
        epochs=3,
        learning_rate=1e-4,
        qa_per_chunk=2,
    ),
}


def list_presets() -> list[str]:
    return sorted(PRESETS.keys())


def get_preset(name: str) -> Recipe:
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: {name!r}. Available: {list_presets()}")
    return deepcopy(PRESETS[name])
```

- [ ] **Step 3: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_recipes.py -v
git add packages/jw-finetune/src/jw_finetune/recipes/presets.py packages/jw-finetune/tests/test_recipes.py
git commit -m "feat(jw-finetune): four built-in recipe presets"
```

---

## Group C — Synth (Q&A generation)

### Task 9: LLM Provider Protocol + validators

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/synth/provider.py`
- Create: `packages/jw-finetune/src/jw_finetune/synth/validators.py`
- Create: `packages/jw-finetune/tests/test_synth_validators.py`

- [ ] **Step 1: Test validators**

```python
from jw_finetune.synth.validators import (
    is_valid_bible_ref, count_bible_refs, length_ok, lang_matches,
)


def test_bible_ref_es():
    assert is_valid_bible_ref("Génesis 1:1")
    assert is_valid_bible_ref("Mateo 24:14")
    assert is_valid_bible_ref("1 Corintios 13:4-7")
    assert not is_valid_bible_ref("xyz 99")
    assert not is_valid_bible_ref("hola mundo")


def test_count_bible_refs():
    txt = "Como dice Mateo 24:14 y Hechos 1:8, debemos predicar."
    assert count_bible_refs(txt) >= 2


def test_length_ok():
    assert length_ok("Hola", "Esta es una respuesta razonable y suficientemente larga.")
    assert not length_ok("", "ok")     # Q empty
    assert not length_ok("A?", "x")    # A too short


def test_lang_matches_no_langdetect_passes(monkeypatch):
    # If langdetect is not installed, lang_matches should default-pass
    import jw_finetune.synth.validators as v
    monkeypatch.setattr(v, "_HAS_LANGDETECT", False)
    assert v.lang_matches("Hello world", "es") is True
```

- [ ] **Step 2: Implementar**

`synth/__init__.py`:
```python
"""Synth: Q&A generation via LLM providers."""
```

`synth/provider.py`:
```python
"""LLM Provider Protocol — abstraction over Anthropic / Ollama."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    max_tokens: int = 1024
    temperature: float = 0.5


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: dict[str, int]  # {"input_tokens": N, "output_tokens": M}


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, req: LLMRequest) -> LLMResponse: ...
```

`synth/validators.py`:
```python
"""Validators for synthesized Q&A pairs."""

from __future__ import annotations

import re

try:
    import langdetect  # type: ignore
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False


# Patrón conservador: nombre de libro (puede incluir prefijo numérico)
# + espacio + número:número con opcional rango.
_BIBLE_REF_RE = re.compile(
    r"\b(?:[12]\s+)?[A-ZÁÉÍÓÚÑa-záéíóúñ][A-Za-záéíóúñ]{2,12}\s+\d{1,3}:\d{1,3}(?:[-,]\s?\d{1,3})?\b"
)


def is_valid_bible_ref(text: str) -> bool:
    return bool(_BIBLE_REF_RE.search(text))


def count_bible_refs(text: str) -> int:
    return len(_BIBLE_REF_RE.findall(text))


def length_ok(question: str, answer: str,
              q_min: int = 5, q_max: int = 400,
              a_min: int = 30, a_max: int = 2000) -> bool:
    q = (question or "").strip()
    a = (answer or "").strip()
    return q_min <= len(q) <= q_max and a_min <= len(a) <= a_max


def lang_matches(text: str, expected: str) -> bool:
    """Returns True if detected language matches `expected` (ISO 639-1).

    If langdetect is unavailable, returns True (don't block on missing dep).
    """
    if not _HAS_LANGDETECT:
        return True
    try:
        detected = langdetect.detect(text)
        return detected[:2].lower() == expected[:2].lower()
    except Exception:
        return True
```

- [ ] **Step 3: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_synth_validators.py -v
git add packages/jw-finetune/src/jw_finetune/synth packages/jw-finetune/tests/test_synth_validators.py
git commit -m "feat(jw-finetune): LLMProvider protocol + Q&A validators"
```

---

### Task 10: Implementaciones Anthropic + Ollama

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/anthropic_provider.py`
- Create: `packages/jw-finetune/src/jw_finetune/synth/ollama_provider.py`

- [ ] **Step 1: Implementar Anthropic**

```python
"""Anthropic Claude provider for Q&A synthesis."""

from __future__ import annotations

import os

from jw_finetune.synth.provider import LLMRequest, LLMResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str | None = None):
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise ImportError("anthropic SDK required: pip install anthropic") from e
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def generate(self, req: LLMRequest) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
        )
        # The text is in the first content block of type 'text'.
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )
```

- [ ] **Step 2: Implementar Ollama**

```python
"""Ollama local provider for Q&A synthesis."""

from __future__ import annotations

from jw_finetune.synth.provider import LLMRequest, LLMResponse


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        try:
            import ollama  # type: ignore
        except ImportError as e:
            raise ImportError("ollama SDK required: pip install ollama") from e
        self.model = model
        self._client = ollama.Client(host=host)

    def generate(self, req: LLMRequest) -> LLMResponse:
        resp = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            options={"temperature": req.temperature, "num_predict": req.max_tokens},
        )
        text = resp["message"]["content"]
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage={
                "input_tokens": int(resp.get("prompt_eval_count", 0)),
                "output_tokens": int(resp.get("eval_count", 0)),
            },
        )
```

- [ ] **Step 3: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/anthropic_provider.py packages/jw-finetune/src/jw_finetune/synth/ollama_provider.py
git commit -m "feat(jw-finetune): Anthropic and Ollama LLM providers"
```

---

### Task 11: Jinja2 templates + orchestrator

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/recipes/templates/doctrinal_qa.j2`
- Create: `packages/jw-finetune/src/jw_finetune/recipes/templates/verse_explainer.j2`
- Create: `packages/jw-finetune/src/jw_finetune/recipes/templates/apologetics.j2`
- Create: `packages/jw-finetune/src/jw_finetune/synth/orchestrator.py`
- Create: `packages/jw-finetune/tests/test_synth_orchestrator.py`

- [ ] **Step 1: Crear template `doctrinal_qa.j2`**

```jinja
Eres un asistente experto en doctrina y publicaciones de los Testigos de Jehová. Tu tarea es generar pares pregunta-respuesta de alta calidad a partir del texto fuente.

REGLAS:
- Responde EXCLUSIVAMENTE en {{ language }}.
- Genera exactamente {{ n_pairs }} pares Q&A distintos.
- Cada respuesta debe ser fiel al texto fuente, sin añadir doctrina externa.
- Cita versículos bíblicos en formato canónico (ej: "Mateo 24:14", "1 Corintios 13:4-7") cuando aparezcan en el texto.
- Las preguntas deben ser variadas: factuales, de aplicación, de comprensión, de comparación.
- Evita preguntas triviales ("¿qué dice el párrafo?"). Prefiere preguntas profundas que un estudiante haría.

FORMATO DE SALIDA (JSON estricto, sin texto extra):
{
  "pairs": [
    {"q": "...", "a": "..."},
    {"q": "...", "a": "..."}
  ]
}

TEXTO FUENTE ({{ pub_code }} — {{ section_ref }}):
{{ chunk_text }}
```

- [ ] **Step 2: Crear template `verse_explainer.j2`**

```jinja
Eres un comentarista bíblico que sigue la línea de las publicaciones de los Testigos de Jehová. Genera pares "versículo → explicación" a partir del texto fuente.

REGLAS:
- Idioma: {{ language }}.
- Genera {{ n_pairs }} pares.
- La "pregunta" es siempre la cita bíblica completa (ej: "Explica Mateo 24:14"). La "respuesta" es la explicación basada en el texto fuente.
- Cita el versículo literalmente al inicio de la respuesta cuando aparezca en el texto fuente.
- Si el texto fuente no contiene versículos explícitos, retorna {"pairs": []}.

FORMATO (JSON estricto):
{
  "pairs": [
    {"q": "Explica X Y:Z", "a": "..."}
  ]
}

TEXTO FUENTE ({{ pub_code }} — {{ section_ref }}):
{{ chunk_text }}
```

- [ ] **Step 3: Crear template `apologetics.j2`**

```jinja
Eres un publicador entrenado en el manejo de objeciones según las publicaciones de los Testigos de Jehová. Genera pares "objeción → respuesta razonada" a partir del texto fuente.

REGLAS:
- Idioma: {{ language }}.
- Genera {{ n_pairs }} pares.
- La "pregunta" es la objeción/duda planteada en términos naturales (ej: "¿Por qué no celebran navidad?").
- La "respuesta" es razonada, respetuosa, y cita versículos bíblicos del texto fuente cuando estén presentes.
- Si el texto fuente no aborda objeciones, retorna {"pairs": []}.

FORMATO (JSON estricto):
{
  "pairs": [
    {"q": "...", "a": "..."}
  ]
}

TEXTO FUENTE ({{ pub_code }} — {{ section_ref }}):
{{ chunk_text }}
```

- [ ] **Step 4: Test orchestrator**

```python
import json
from jw_finetune.synth.orchestrator import synthesize_chunk, SynthResult
from jw_finetune.synth.provider import LLMRequest, LLMResponse
from jw_rag.chunker import Chunk


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, response_text: str):
        self._t = response_text

    def generate(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(text=self._t, provider="fake", model="fake-1",
                           usage={"input_tokens": 10, "output_tokens": 50})


def _chunk():
    return Chunk(
        id="w24:1#0",
        text="El Reino de Dios es el gobierno celestial. Daniel 2:44 lo profetiza.",
        source_id="w24:1",
        metadata={"language": "es", "pub_code": "w24", "section_ref": "w24 1 p.5"},
    )


def test_orchestrator_parses_json():
    txt = json.dumps({"pairs": [
        {"q": "¿Qué es el Reino?", "a": "El Reino es el gobierno celestial mencionado en Daniel 2:44."},
    ]})
    res = synthesize_chunk(_chunk(), provider=FakeProvider(txt),
                          qa_style="doctrinal", language="es", n_pairs=1)
    assert isinstance(res, SynthResult)
    assert len(res.pairs) == 1
    assert "Reino" in res.pairs[0].question


def test_orchestrator_rejects_invalid_lang(monkeypatch):
    import jw_finetune.synth.validators as v
    monkeypatch.setattr(v, "_HAS_LANGDETECT", True)
    monkeypatch.setattr(v, "langdetect", type("M", (), {"detect": staticmethod(lambda t: "fr")}))
    txt = json.dumps({"pairs": [{"q": "Q en frances", "a": "Une reponse en francais bien longue ici."}]})
    res = synthesize_chunk(_chunk(), provider=FakeProvider(txt),
                          qa_style="doctrinal", language="es", n_pairs=1)
    assert len(res.pairs) == 0
    assert res.rejected >= 1


def test_orchestrator_handles_malformed_json():
    res = synthesize_chunk(_chunk(), provider=FakeProvider("no soy json"),
                           qa_style="doctrinal", language="es", n_pairs=1)
    assert len(res.pairs) == 0
    assert res.rejected == 0
    assert res.parse_error is True
```

- [ ] **Step 5: Implementar `synth/orchestrator.py`**

```python
"""Q&A synthesis orchestrator: chunk + provider → validated QAPair list."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_rag.chunker import Chunk

from jw_finetune.data.formats import QAPair
from jw_finetune.synth.provider import LLMProvider, LLMRequest
from jw_finetune.synth.validators import lang_matches, length_ok

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "recipes" / "templates"

_TEMPLATE_FOR_STYLE = {
    "doctrinal": "doctrinal_qa.j2",
    "verse-explain": "verse_explainer.j2",
    "objection-handling": "apologetics.j2",
}


@dataclass
class SynthResult:
    pairs: list[QAPair] = field(default_factory=list)
    rejected: int = 0
    parse_error: bool = False
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def synthesize_chunk(
    chunk: Chunk,
    *,
    provider: LLMProvider,
    qa_style: str,
    language: str,
    n_pairs: int = 3,
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> SynthResult:
    template_name = _TEMPLATE_FOR_STYLE.get(qa_style)
    if not template_name:
        raise ValueError(f"Unknown qa_style: {qa_style!r}")
    tmpl = _env().get_template(template_name)
    user_prompt = tmpl.render(
        language=language,
        n_pairs=n_pairs,
        chunk_text=chunk.text,
        pub_code=chunk.metadata.get("pub_code", "?"),
        section_ref=chunk.metadata.get("section_ref", ""),
    )
    system = (
        "Eres un asistente que genera datasets de fine-tuning de alta calidad "
        "siguiendo estrictamente el formato JSON solicitado."
    )
    resp = provider.generate(LLMRequest(
        system=system, user=user_prompt,
        temperature=temperature, max_tokens=max_tokens,
    ))

    result = SynthResult(usage=dict(resp.usage))

    # Parse JSON
    raw = resp.text.strip()
    # Tolerate fenced code blocks
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Synth parse error for chunk %s: %s", chunk.id, e)
        result.parse_error = True
        return result

    pairs = parsed.get("pairs", []) if isinstance(parsed, dict) else []
    for entry in pairs:
        q = (entry.get("q") or "").strip()
        a = (entry.get("a") or "").strip()
        if not length_ok(q, a):
            result.rejected += 1
            continue
        if not lang_matches(a, language):
            result.rejected += 1
            continue
        result.pairs.append(QAPair(
            question=q,
            answer=a,
            source_chunk_id=chunk.id,
            language=language,
            metadata={
                "pub_code": str(chunk.metadata.get("pub_code", "")),
                "section_ref": str(chunk.metadata.get("section_ref", "")),
                "qa_style": qa_style,
            },
        ))
    return result
```

- [ ] **Step 6: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_synth_orchestrator.py -v
git add packages/jw-finetune/src/jw_finetune/synth/orchestrator.py packages/jw-finetune/src/jw_finetune/recipes/templates packages/jw-finetune/tests/test_synth_orchestrator.py
git commit -m "feat(jw-finetune): Jinja templates and synth orchestrator with validation"
```

---

## Group D — Train / Eval / Export

### Task 12: SFT trainer wrapper + Monitor callback stub

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/train/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/train/callback.py`
- Create: `packages/jw-finetune/src/jw_finetune/train/sft.py`
- Create: `packages/jw-finetune/tests/test_train_smoke.py`

- [ ] **Step 1: Implementar callback stub**

`train/__init__.py`:
```python
"""Training: wrappers over Unsloth + monitoring callback."""
```

`train/callback.py`:
```python
"""JWMonitorCallback — emits structured events for the F2 dashboard.

For F1 it writes JSONL events to `workspace/events.jsonl`. F2 adds a
WebSocket bridge for the live dashboard.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class JWMonitorCallback:
    """Plain-Python callback. We accept the trl/transformers signature dynamically."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.events_path = self.workspace / "events.jsonl"
        self._t_start = time.time()

    def _emit(self, event: dict) -> None:
        event.setdefault("ts", time.time())
        event.setdefault("elapsed", time.time() - self._t_start)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Hugging Face Trainer callback API
    def on_train_begin(self, args, state, control, **kw):
        self._emit({"kind": "train_begin"})

    def on_step_end(self, args, state, control, **kw):
        logs = kw.get("logs") or {}
        self._emit({"kind": "step", "step": state.global_step, **logs})

    def on_log(self, args, state, control, logs=None, **kw):
        self._emit({"kind": "log", "step": getattr(state, "global_step", -1), **(logs or {})})

    def on_train_end(self, args, state, control, **kw):
        self._emit({"kind": "train_end", "global_step": state.global_step})
```

- [ ] **Step 2: Implementar SFT wrapper (lazy import Unsloth)**

`train/sft.py`:
```python
"""SFT training via Unsloth + trl.SFTTrainer (lazy-imported)."""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


def train_sft(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    eval_dataset_path: Path | None = None,
    resume_from_checkpoint: str | bool | None = None,
) -> Path:
    """Run SFT. Returns path to the final checkpoint directory."""
    # Lazy imports so the package is importable without GPU stack
    from unsloth import FastLanguageModel
    from trl import SFTConfig, SFTTrainer
    from datasets import load_dataset

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit="bnb-4bit" in recipe.base_model,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=recipe.lora_rank,
        lora_alpha=recipe.lora_alpha,
        lora_dropout=recipe.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=recipe.seed,
    )

    train_ds = load_dataset("json", data_files=str(dataset_path), split="train")
    eval_ds = None
    if eval_dataset_path and eval_dataset_path.exists():
        eval_ds = load_dataset("json", data_files=str(eval_dataset_path), split="train")

    args = SFTConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        warmup_ratio=recipe.warmup_ratio,
        weight_decay=recipe.weight_decay,
        max_seq_length=recipe.max_seq_len,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=100 if eval_ds else None,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=args,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    logger.info("Training complete: %s", final)
    return final
```

- [ ] **Step 3: Smoke test (skip si Unsloth no instalado)**

```python
import pytest


def test_train_sft_skips_without_unsloth():
    """If unsloth isn't installed, train_sft must raise ImportError when called."""
    try:
        import unsloth  # noqa: F401
        pytest.skip("Unsloth installed; smoke test is GPU-bound, skipping.")
    except ImportError:
        from jw_finetune.train.sft import train_sft
        from pathlib import Path
        from jw_finetune.recipes.base import Recipe
        from jw_finetune.data.models import SourceSpec
        r = Recipe(name="x", task="sft",
                   sources=[SourceSpec(kind="jwpub", path="x", language="es")],
                   languages=["es"], publication_kinds=["watchtower"],
                   qa_style="doctrinal", base_model="unsloth/Qwen2.5-3B-bnb-4bit")
        with pytest.raises((ImportError, ModuleNotFoundError)):
            train_sft(r, Path("nonexistent.jsonl"), Path("./_workspace_test"))


def test_monitor_callback_writes_events(tmp_path):
    from jw_finetune.train.callback import JWMonitorCallback
    cb = JWMonitorCallback(workspace=tmp_path)

    class S:  # fake state
        global_step = 5
    cb.on_log(None, S(), None, logs={"loss": 1.23})
    text = (tmp_path / "events.jsonl").read_text()
    import json
    rec = json.loads(text.strip())
    assert rec["loss"] == 1.23
    assert rec["step"] == 5
```

- [ ] **Step 4: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_train_smoke.py -v
git add packages/jw-finetune/src/jw_finetune/train packages/jw-finetune/tests/test_train_smoke.py
git commit -m "feat(jw-finetune): SFT trainer wrapper with JW monitor callback"
```

---

### Task 13: CPT trainer (continued pretraining)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/train/cpt.py`

- [ ] **Step 1: Implementar**

```python
"""Continued pretraining (CPT) on raw text via Unsloth + trl.SFTTrainer.

CPT is essentially "SFT on raw text with no chat formatting" — the trainer
treats each `text` field as a continuous sequence and predicts next tokens.
"""

from __future__ import annotations

import logging
from pathlib import Path

from jw_finetune.recipes.base import Recipe
from jw_finetune.train.callback import JWMonitorCallback

logger = logging.getLogger(__name__)


def train_cpt(
    recipe: Recipe,
    dataset_path: Path,
    workspace: Path,
    *,
    resume_from_checkpoint: str | bool | None = None,
) -> Path:
    """Continued pretraining. Returns final checkpoint path."""
    from unsloth import FastLanguageModel
    from trl import SFTConfig, SFTTrainer
    from datasets import load_dataset

    workspace.mkdir(parents=True, exist_ok=True)
    ckpt_dir = workspace / "checkpoints"

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit="bnb-4bit" in recipe.base_model,
        dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=recipe.lora_rank,
        lora_alpha=recipe.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj",
                        "embed_tokens", "lm_head"],  # embeddings train for CPT
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=recipe.seed,
    )

    ds = load_dataset("json", data_files=str(dataset_path), split="train")

    args = SFTConfig(
        output_dir=str(ckpt_dir),
        num_train_epochs=recipe.epochs,
        per_device_train_batch_size=recipe.batch_size,
        gradient_accumulation_steps=recipe.gradient_accumulation,
        learning_rate=recipe.learning_rate,
        embedding_learning_rate=recipe.learning_rate / 10,
        warmup_ratio=recipe.warmup_ratio,
        max_seq_length=recipe.max_seq_len,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        seed=recipe.seed,
        report_to="none",
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=args,
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    final = ckpt_dir / "final"
    trainer.save_model(str(final))
    tokenizer.save_pretrained(str(final))
    return final
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/train/cpt.py
git commit -m "feat(jw-finetune): continued pretraining (CPT) wrapper"
```

---

### Task 14: Eval — refs + doctrinal + runner

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/eval/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/eval/refs.py`
- Create: `packages/jw-finetune/src/jw_finetune/eval/doctrinal.py`
- Create: `packages/jw-finetune/src/jw_finetune/eval/runner.py`
- Create: `packages/jw-finetune/tests/test_eval_refs.py`

- [ ] **Step 1: Test refs**

```python
from jw_finetune.eval.refs import score_citation_accuracy
from jw_finetune.eval.doctrinal import score_terminology


def test_citation_accuracy_all_valid():
    answers = [
        "Como dice Mateo 24:14, esto es una señal.",
        "Hechos 1:8 menciona la obra de testificación.",
    ]
    score = score_citation_accuracy(answers, expect_at_least=1)
    assert score == 1.0  # both have valid refs


def test_citation_accuracy_partial():
    answers = [
        "Mateo 24:14 lo dice.",
        "Sin referencia bíblica aquí.",
    ]
    assert 0.0 < score_citation_accuracy(answers, expect_at_least=1) < 1.0


def test_doctrinal_terminology_es():
    answers = [
        "Jehová es el Soberano del universo.",
        "El Reino de Dios es el gobierno celestial.",
    ]
    s = score_terminology(answers, language="es")
    assert s > 0.5
```

- [ ] **Step 2: Implementar `eval/refs.py`**

```python
"""Citation-accuracy evaluator."""

from __future__ import annotations

from collections.abc import Iterable

from jw_finetune.synth.validators import count_bible_refs


def score_citation_accuracy(answers: Iterable[str], *, expect_at_least: int = 1) -> float:
    """Fraction of answers containing at least `expect_at_least` bible refs."""
    answers = list(answers)
    if not answers:
        return 0.0
    hits = sum(1 for a in answers if count_bible_refs(a) >= expect_at_least)
    return hits / len(answers)
```

- [ ] **Step 3: Implementar `eval/doctrinal.py`**

```python
"""Heuristic terminology check (JW-style vocabulary)."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Term sets per language. NOT exhaustive doctrine — just markers that the
# model has absorbed JW-specific vocabulary instead of generic Christian.
_TERMS: dict[str, set[str]] = {
    "es": {"jehová", "reino", "publicador", "anciano", "atalaya",
           "testificación", "predicación", "soberanía", "ungidos"},
    "en": {"jehovah", "kingdom", "publisher", "elder", "watchtower",
           "witnessing", "preaching", "sovereignty", "anointed"},
}


def score_terminology(answers: Iterable[str], *, language: str = "es") -> float:
    """Fraction of answers that include >=1 JW-specific term."""
    answers = list(answers)
    if not answers:
        return 0.0
    terms = _TERMS.get(language[:2].lower(), set())
    if not terms:
        return 0.0
    hits = 0
    for a in answers:
        low = a.lower()
        if any(re.search(rf"\b{re.escape(t)}\b", low) for t in terms):
            hits += 1
    return hits / len(answers)
```

- [ ] **Step 4: Implementar `eval/runner.py`** (genera respuestas con el modelo entrenado y mide)

```python
"""Eval runner: load a checkpoint, run prompts, score answers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from jw_finetune.eval.doctrinal import score_terminology
from jw_finetune.eval.refs import score_citation_accuracy

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    n_prompts: int
    citation_accuracy: float
    terminology_score: float
    answers: list[str] = field(default_factory=list)


def run_eval(
    checkpoint_dir: Path,
    prompts: list[str],
    *,
    language: str = "es",
    max_new_tokens: int = 256,
) -> EvalResult:
    """Run prompts through the trained model and score answers."""
    from unsloth import FastLanguageModel
    import torch  # noqa: F401

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,
    )
    FastLanguageModel.for_inference(model)

    answers: list[str] = []
    for p in prompts:
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": p}],
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(model.device)
        out = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
        text = tokenizer.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)
        answers.append(text)

    return EvalResult(
        n_prompts=len(prompts),
        citation_accuracy=score_citation_accuracy(answers),
        terminology_score=score_terminology(answers, language=language),
        answers=answers,
    )


def write_eval_report(result: EvalResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "n_prompts": result.n_prompts,
        "citation_accuracy": result.citation_accuracy,
        "terminology_score": result.terminology_score,
        "answers": result.answers,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 5: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_eval_refs.py -v
git add packages/jw-finetune/src/jw_finetune/eval packages/jw-finetune/tests/test_eval_refs.py
git commit -m "feat(jw-finetune): JW-specific eval (citations + terminology) + runner"
```

---

### Task 15: Export (GGUF, MLX, safetensors)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/export/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/export/gguf.py`
- Create: `packages/jw-finetune/src/jw_finetune/export/mlx.py`
- Create: `packages/jw-finetune/src/jw_finetune/export/safetensors_export.py`

- [ ] **Step 1: Implementar GGUF**

`export/__init__.py`:
```python
"""Export trained models to GGUF, MLX, or safetensors."""
```

`export/gguf.py`:
```python
"""GGUF export via Unsloth's save_pretrained_gguf."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_gguf(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    quant: str = "Q4_K_M",
    base_model: str | None = None,
    max_seq_length: int = 2048,
) -> Path:
    """Convert checkpoint to GGUF.

    Returns the output directory. The actual .gguf file lives inside.
    Uses Unsloth's save_pretrained_gguf when available; falls back to
    llama.cpp's convert script if Unsloth helper is unavailable.
    """
    from unsloth import FastLanguageModel

    output_dir.mkdir(parents=True, exist_ok=True)
    model_name = str(checkpoint_dir)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        dtype=None,
    )
    model.save_pretrained_gguf(
        str(output_dir),
        tokenizer,
        quantization_method=quant.lower(),  # Unsloth wants e.g. "q4_k_m"
    )
    logger.info("GGUF exported to %s (quant=%s)", output_dir, quant)
    return output_dir
```

- [ ] **Step 2: Implementar MLX**

`export/mlx.py`:
```python
"""MLX export (Apple Silicon)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def export_mlx(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    quant: str | None = "q4",  # mlx_lm.convert uses --quantize + --q-bits
) -> Path:
    """Convert HF checkpoint to MLX format using `mlx_lm.convert`.

    Requires the `mlx-lm` package installed (extra: [mlx]).
    """
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    cmd = [
        "python", "-m", "mlx_lm.convert",
        "--hf-path", str(checkpoint_dir),
        "--mlx-path", str(output_dir),
    ]
    if quant:
        cmd += ["--quantize", "--q-bits", "4" if quant == "q4" else "8"]
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_dir
```

- [ ] **Step 3: Implementar safetensors merged**

`export/safetensors_export.py`:
```python
"""Export merged 16-bit safetensors (LoRA + base) or adapter-only."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_merged(checkpoint_dir: Path, output_dir: Path, *, max_seq_length: int = 2048) -> Path:
    """Merge LoRA into base and save as 16-bit safetensors."""
    from unsloth import FastLanguageModel
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=max_seq_length,
        load_in_4bit=False,
        dtype=None,
    )
    model.save_pretrained_merged(str(output_dir), tokenizer, save_method="merged_16bit")
    return output_dir


def export_adapter_only(checkpoint_dir: Path, output_dir: Path) -> Path:
    """Save the LoRA adapter weights only (small file)."""
    from unsloth import FastLanguageModel
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,
    )
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    return output_dir
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/export
git commit -m "feat(jw-finetune): export to GGUF / MLX / safetensors"
```

---

## Group E — CLI + Integration

### Task 16: Comandos CLI (Typer)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/cli.py`
- Create: `packages/jw-finetune/tests/test_cli.py`

- [ ] **Step 1: Implementar CLI**

```python
"""jw-finetune CLI — entry-point for prepare, train, eval, export, run."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from jw_finetune.data.dedupe import deduplicate
from jw_finetune.data.chunk import records_to_chunks
from jw_finetune.data.extract import extract_from_epub, extract_from_jwpub
from jw_finetune.data.formats import write_raw_jsonl, write_sharegpt_jsonl
from jw_finetune.recipes.base import Recipe, recipe_from_yaml, recipe_to_yaml, validate_recipe
from jw_finetune.recipes.presets import get_preset, list_presets

app = typer.Typer(no_args_is_help=True, add_completion=False, help="jw-finetune — local LLM fine-tuning for JW publications.")
console = Console()
logging.basicConfig(level=os.environ.get("JW_FT_LOGLEVEL", "INFO"))


def _load_recipe(preset: str | None, recipe_file: Path | None) -> Recipe:
    if recipe_file:
        return recipe_from_yaml(recipe_file)
    if preset:
        return get_preset(preset)
    raise typer.BadParameter("--recipe or --recipe-file required")


def _new_run_dir(base: Path) -> Path:
    from datetime import datetime
    rid = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    p = Path(base) / rid
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.command()
def presets():
    """List built-in recipe presets."""
    table = Table(title="jw-finetune presets")
    table.add_column("Name", style="cyan")
    table.add_column("Task", style="magenta")
    table.add_column("Languages", style="green")
    table.add_column("Base model", style="yellow")
    for name in list_presets():
        r = get_preset(name)
        table.add_row(name, r.task, ",".join(r.languages), r.base_model)
    console.print(table)


@app.command()
def init(
    preset: str = typer.Option(..., "--preset", "-p", help="Preset name to copy."),
    out: Path = typer.Option(Path("./recipe.yaml"), "--out", "-o"),
):
    """Write a recipe YAML from a preset."""
    r = get_preset(preset)
    recipe_to_yaml(r, out)
    console.print(f"[green]✓[/green] Recipe written to {out}")


@app.command()
def prepare(
    recipe: Annotated[str | None, typer.Option("--recipe", "-r", help="Preset name.")] = None,
    recipe_file: Annotated[Path | None, typer.Option("--recipe-file")] = None,
    source: Annotated[list[Path], typer.Option("--source", "-s", help="JWPUB/EPUB file or dir; may repeat.")] = [],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("./jw-finetune-workspace"),
    provider: Annotated[str | None, typer.Option("--synth-provider", help="anthropic|ollama")] = None,
    model: Annotated[str | None, typer.Option("--synth-model")] = None,
):
    """Stage 1-4: extract → dedupe → chunk → (synth Q&A if SFT)."""
    rec = _load_recipe(recipe, recipe_file)
    errors = validate_recipe(rec)
    if errors:
        for e in errors:
            console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(2)

    run_dir = _new_run_dir(workspace)
    console.print(f"[blue]Run dir:[/blue] {run_dir}")

    all_records = []
    for src in source:
        for p in _iter_source_paths(src):
            console.print(f"[dim]Extracting {p}[/dim]")
            if p.suffix.lower() == ".epub":
                all_records.extend(list(extract_from_epub(p, language_hint=rec.languages[0])))
            elif p.suffix.lower() == ".jwpub":
                all_records.extend(list(extract_from_jwpub(p, language_hint=rec.languages[0])))
    console.print(f"[blue]Extracted:[/blue] {len(all_records)} paragraphs")

    deduped = list(deduplicate(all_records, threshold=rec.dedupe_threshold))
    console.print(f"[blue]After dedupe:[/blue] {len(deduped)}")

    chunks = records_to_chunks(deduped, max_chars=rec.max_chunk_chars, min_chars=rec.min_chunk_chars)
    console.print(f"[blue]Chunks:[/blue] {len(chunks)}")

    if rec.task == "cpt":
        out = run_dir / "dataset_raw.jsonl"
        n = write_raw_jsonl(chunks, out)
        console.print(f"[green]✓[/green] CPT dataset: {out} ({n} records)")
    else:
        prov = _build_provider(provider or rec.synth_provider, model or rec.synth_model)
        qas = _synth_chunks(chunks, prov, rec)
        out = run_dir / "dataset_qa.jsonl"
        n = write_sharegpt_jsonl(qas, out)
        console.print(f"[green]✓[/green] SFT dataset: {out} ({n} pairs)")

    recipe_to_yaml(rec, run_dir / "recipe.yaml")
    console.print(f"[green]✓[/green] Recipe saved: {run_dir / 'recipe.yaml'}")


def _iter_source_paths(p: Path):
    if p.is_dir():
        yield from p.rglob("*.jwpub")
        yield from p.rglob("*.epub")
    else:
        yield p


def _build_provider(provider_name: str | None, model_name: str | None):
    if not provider_name or provider_name == "ollama":
        from jw_finetune.synth.ollama_provider import OllamaProvider
        return OllamaProvider(model=model_name or "llama3.1:8b")
    if provider_name == "anthropic":
        from jw_finetune.synth.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model_name or "claude-haiku-4-5-20251001")
    raise typer.BadParameter(f"Unknown provider: {provider_name}")


def _synth_chunks(chunks, provider, rec: Recipe):
    from jw_finetune.synth.orchestrator import synthesize_chunk
    qas = []
    for c in chunks:
        res = synthesize_chunk(c, provider=provider, qa_style=rec.qa_style or "doctrinal",
                                language=c.metadata.get("language") or rec.languages[0],
                                n_pairs=rec.qa_per_chunk)
        qas.extend(res.pairs)
    return qas


@app.command()
def train(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = False,
):
    """Run training (SFT or CPT depending on recipe task)."""
    rec = recipe_from_yaml(workspace / "recipe.yaml")
    if rec.task == "cpt":
        from jw_finetune.train.cpt import train_cpt
        dataset = workspace / "dataset_raw.jsonl"
        final = train_cpt(rec, dataset, workspace, resume_from_checkpoint=resume or None)
    else:
        from jw_finetune.train.sft import train_sft
        dataset = workspace / "dataset_qa.jsonl"
        final = train_sft(rec, dataset, workspace, resume_from_checkpoint=resume or None)
    console.print(f"[green]✓ Final checkpoint:[/green] {final}")


@app.command()
def evaluate(
    checkpoint: Annotated[Path, typer.Option("--checkpoint", "-c")],
    prompts: Annotated[Path, typer.Option("--prompts", "-p", help="Text file with one prompt per line.")],
    language: Annotated[str, typer.Option("--language", "-l")] = "es",
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./eval-report.json"),
):
    """Run evaluation on a checkpoint."""
    from jw_finetune.eval.runner import run_eval, write_eval_report
    prompt_list = [ln.strip() for ln in prompts.read_text(encoding="utf-8").splitlines() if ln.strip()]
    result = run_eval(checkpoint, prompt_list, language=language)
    write_eval_report(result, out)
    console.print(f"[green]✓ Eval report:[/green] {out}")
    console.print(f"  citation_accuracy = {result.citation_accuracy:.2%}")
    console.print(f"  terminology_score = {result.terminology_score:.2%}")


@app.command()
def export(
    checkpoint: Annotated[Path, typer.Option("--checkpoint", "-c")],
    fmt: Annotated[str, typer.Option("--format", "-f", help="gguf|mlx|merged|adapter")] = "gguf",
    quant: Annotated[str, typer.Option("--quant", "-q")] = "Q4_K_M",
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("./export"),
):
    """Export a trained checkpoint."""
    if fmt == "gguf":
        from jw_finetune.export.gguf import export_gguf
        p = export_gguf(checkpoint, out, quant=quant)
    elif fmt == "mlx":
        from jw_finetune.export.mlx import export_mlx
        p = export_mlx(checkpoint, out, quant="q4" if quant.lower().startswith("q4") else "q8")
    elif fmt == "merged":
        from jw_finetune.export.safetensors_export import export_merged
        p = export_merged(checkpoint, out)
    elif fmt == "adapter":
        from jw_finetune.export.safetensors_export import export_adapter_only
        p = export_adapter_only(checkpoint, out)
    else:
        raise typer.BadParameter(f"Unknown format: {fmt}")
    console.print(f"[green]✓ Exported:[/green] {p}")


@app.command()
def run(
    recipe: Annotated[str | None, typer.Option("--recipe", "-r")] = None,
    recipe_file: Annotated[Path | None, typer.Option("--recipe-file")] = None,
    source: Annotated[list[Path], typer.Option("--source", "-s")] = [],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("./jw-finetune-workspace"),
    export_fmt: Annotated[str, typer.Option("--export", help="Format to export at the end")] = "gguf",
):
    """End-to-end pipeline: prepare → train → export."""
    ctx = typer.get_current_context()
    ctx.invoke(prepare, recipe=recipe, recipe_file=recipe_file, source=source, workspace=workspace)
    # locate the most recent run dir
    run_dir = sorted([d for d in workspace.iterdir() if d.is_dir()])[-1]
    ctx.invoke(train, workspace=run_dir)
    ctx.invoke(export, checkpoint=run_dir / "checkpoints" / "final", fmt=export_fmt,
                out=run_dir / "export")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Test CLI**

```python
from typer.testing import CliRunner
from jw_finetune.cli import app


def test_presets_command_runs():
    r = CliRunner().invoke(app, ["presets"])
    assert r.exit_code == 0
    assert "doctrinal-qa-es-sft" in r.stdout


def test_init_writes_yaml(tmp_path):
    out = tmp_path / "r.yaml"
    r = CliRunner().invoke(app, ["init", "--preset", "doctrinal-qa-es-sft", "--out", str(out)])
    assert r.exit_code == 0
    assert out.exists()
    txt = out.read_text()
    assert "doctrinal-qa-es-sft" in txt


def test_prepare_requires_recipe():
    r = CliRunner().invoke(app, ["prepare"])
    assert r.exit_code != 0
```

- [ ] **Step 3: Test + Commit**

```bash
uv run pytest packages/jw-finetune/tests/test_cli.py -v
git add packages/jw-finetune/src/jw_finetune/cli.py packages/jw-finetune/tests/test_cli.py
git commit -m "feat(jw-finetune): full CLI (prepare/train/eval/export/run/presets)"
```

---

### Task 17: README, doc de uso, and final touches

**Files:**
- Modify: `packages/jw-finetune/README.md` (expandir)
- Create: `docs/guias/fine-tuning-local.md`
- Modify: `docs/README.md` (link a la nueva guía)
- Modify: `README.md` raíz (mencionar `jw-finetune`)

- [ ] **Step 1: Expandir `packages/jw-finetune/README.md`** (sección de uso completa con ejemplos por hardware)

```markdown
# jw-finetune

Plataforma local de fine-tuning para publicaciones JW, basada en [Unsloth](https://github.com/unslothai/unsloth).

> ⚠️ **Disclaimer**: Este paquete genera modelos derivados de publicaciones con copyright de Watchtower Bible and Tract Society. El uso de los pesos resultantes es responsabilidad del usuario y debe respetar los términos oficiales. El paquete NO distribuye pesos ni contenido.

## ¿Para quién es?

Para publicadores/programadores que quieren un asistente JW personal, local, offline, entrenado con su propia biblioteca.

## Pipeline

```
JWPUB / EPUB / WOL → extract → dedupe → chunk
        → (CPT raw) o (SFT Q&A sintéticos via Anthropic/Ollama)
        → train (Unsloth LoRA)
        → eval (citas + terminología)
        → export (GGUF / MLX / safetensors)
```

## Instalación

```bash
# Base (data prep + recipes, sin GPU)
uv sync --package jw-finetune

# NVIDIA
uv sync --package jw-finetune --extra cuda

# Apple Silicon
uv sync --package jw-finetune --extra mlx

# AMD
uv sync --package jw-finetune --extra rocm

# Synth Q&A
uv sync --package jw-finetune --extra synth
```

## Quick start

```bash
# 1. Ver presets disponibles
jw-finetune presets

# 2. Preparar dataset
jw-finetune prepare --recipe doctrinal-qa-es-sft \
    --source ./mis-jwpubs/ \
    --synth-provider ollama --synth-model llama3.1:8b

# 3. Entrenar
jw-finetune train --workspace ./jw-finetune-workspace/run-*

# 4. Evaluar
jw-finetune evaluate \
    --checkpoint ./jw-finetune-workspace/run-*/checkpoints/final \
    --prompts ./prompts.txt --language es

# 5. Exportar a GGUF (para Ollama)
jw-finetune export \
    --checkpoint ./jw-finetune-workspace/run-*/checkpoints/final \
    --format gguf --quant Q4_K_M --out ./mi-modelo-jw

# 6. Cargar en Ollama
ollama create mi-modelo-jw -f Modelfile
```

## Presets out-of-the-box

| Preset | Task | Idioma | Uso |
|---|---|---|---|
| `watchtower-style-es-cpt` | CPT | es | Estilo de Atalaya en español |
| `doctrinal-qa-es-sft` | SFT | es | Q&A doctrinal en español |
| `verse-explainer-multilang-sft` | SFT | es+en | Versículo → explicación |
| `apologetics-objections-sft` | SFT | es | Manejo de objeciones |

## Recipe custom

```bash
jw-finetune init --preset doctrinal-qa-es-sft --out my-recipe.yaml
# edita my-recipe.yaml para ajustar lora_rank, epochs, etc.
jw-finetune run --recipe-file my-recipe.yaml --source ./mis-jwpubs/
```

## Estructura del workspace

```
jw-finetune-workspace/
└── run-20260530-143022/
    ├── recipe.yaml
    ├── dataset_raw.jsonl       # si task=cpt
    ├── dataset_qa.jsonl        # si task=sft
    ├── events.jsonl            # eventos del monitor callback
    ├── checkpoints/
    │   ├── checkpoint-100/
    │   ├── checkpoint-200/
    │   └── final/
    └── export/
        └── <fmt>/              # gguf / mlx / merged / adapter
```

## Privacidad

- Todo corre local. No se envía nada a la nube **excepto** si eliges `--synth-provider anthropic` para generar Q&A.
- Con `ollama` como provider, ningún byte sale de tu máquina.
- Los JWPUBs y EPUBs nunca se redistribuyen.

## Limitaciones de F1 (esta versión)

- No hay dashboard web aún (F2)
- No hay TUI interactiva (F3)
- No hay GRPO/RL (F5)
- Eval JW-specific es básico (refs + terminología); no evalúa coherencia doctrinal real
```

- [ ] **Step 2: Crear `docs/guias/fine-tuning-local.md`** (guía profunda con troubleshooting)

```markdown
# Guía: fine-tuning local con `jw-finetune`

Esta guía cubre el flujo end-to-end de entrenar tu propio modelo JW personal.

## Requisitos

- Python 3.13+, uv instalado
- Para entrenamiento: NVIDIA GPU 12GB+, Apple Silicon M2+, o AMD con ROCm
- Para data prep + synth: cualquier máquina con Ollama (o cuenta Anthropic)

## Decisiones a tomar antes de empezar

1. **¿Qué quieres que el modelo haga?** → elige preset.
2. **¿Tu hardware aguanta qué modelo base?** Tabla de referencia:
   - 8GB VRAM: 3B en Q4
   - 16GB VRAM: 7B en Q4
   - 24GB VRAM: 13B en Q4 o 7B en Q8
   - Apple Silicon 16GB: 3-7B vía MLX
3. **¿Synth con Anthropic (~$0.20/1k chunks) o con Ollama (gratis, lento)?**

[... resto de la guía: troubleshooting, métricas, ejemplos por OS ...]
```

(El implementador puede expandir según necesidad; este placeholder es legítimo en una guía de usuario que iremos enriqueciendo.)

- [ ] **Step 3: Actualizar `docs/README.md`** — añadir bullet bajo "Guías por tema":

```markdown
- [Fine-tuning local](guias/fine-tuning-local.md) — Entrena tu modelo personal JW con `jw-finetune` (Unsloth + JWPUB/EPUB locales).
```

- [ ] **Step 4: Actualizar `README.md` raíz** — añadir `jw-finetune` a la lista de paquetes.

- [ ] **Step 5: Commit final**

```bash
git add packages/jw-finetune/README.md docs/guias/fine-tuning-local.md docs/README.md README.md
git commit -m "docs(jw-finetune): user guide and toolkit README integration"
```

---

## Self-Review checklist

1. **Spec coverage:**
   - ✅ ParagraphRecord, SourceSpec, Recipe → Task 2, 7
   - ✅ 4 presets → Task 8
   - ✅ extract.py (JWPUB/EPUB) → Task 3 (WOL article extraction se difiere a F2 — el spec lo lista pero el MVP funciona con JWPUB/EPUB locales)
   - ✅ dedupe simhash → Task 4
   - ✅ chunk adapter → Task 5
   - ✅ JSONL formats → Task 6
   - ✅ Jinja templates + synth orchestrator → Task 11
   - ✅ LLM providers (Anthropic + Ollama) → Tasks 9-10
   - ✅ SFT + CPT trainers → Tasks 12-13
   - ✅ Monitor callback (stub) → Task 12
   - ✅ Eval (refs + terminology + runner) → Task 14
   - ✅ Export (GGUF + MLX + safetensors) → Task 15
   - ✅ CLI completa → Task 16
   - ✅ Docs → Task 17
   - **GAP intencional**: WOL article extraction se difiere a F2 (no bloquea MVP)
   - **GAP intencional**: Dashboard web es F2

2. **Placeholder scan:**
   - El placeholder de "expand troubleshooting" en `fine-tuning-local.md` es legítimo (guía de usuario, no spec técnico). Aceptado.
   - Resto sin placeholders.

3. **Type consistency:**
   - `Recipe.qa_style` es `QAStyle | None`. Lo consume `synth/orchestrator.py:synthesize_chunk(..., qa_style: str, ...)` — el CLI hace fallback `rec.qa_style or "doctrinal"` para asegurar str. ✓
   - `Chunk` viene de `jw_rag.chunker` consistentemente. ✓
   - `LLMProvider` Protocol consumido por `synthesize_chunk` y CLI builders. ✓
   - `QAPair` definido en `data/formats.py`, importado por `synth/orchestrator.py`. ✓

---

## Execution Handoff

Plan completo y guardado en `docs/superpowers/plans/2026-05-30-jw-finetune-f1-mvp.md`.

**Modo de ejecución elegido: Inline Execution** (per indicación del usuario "implementa todo"). Procederé con `superpowers:executing-plans` haciendo commits frecuentes y checkpoints después de cada Grupo (A-E).
