# Fase 62 — `marker` + `markitdown` loaders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir dos loaders nuevos a `jw-rag` que ingestan (a) **PDFs históricos JW pre-EPUB** (Atalayas/Awake escaneadas, Estudio Perspicaz histórico, papeles compartidos en hermandades) vía `datalab-to/marker`, y (b) **documentos Office** (`.docx`/`.pptx`/`.xlsx`) compartidos por hermanos (guiones de discursos, programas de circuito, hojas asistencia) vía `microsoft/markitdown`. Ambos se convierten a markdown estructurado y se pasan por el pipeline existente de chunking + embedding del `VectorStore` de F33.

**Architecture:** Dos nuevos módulos `jw_rag.loaders.pdf_marker` y `jw_rag.loaders.docs_markitdown` que siguen el patrón de los `ingest_*` existentes (`ingest_epub`, `ingest_jwpub`): leen archivo → producen `paragraphs: list[str]` + metadata → llaman `chunk_paragraphs` + `store.add(chunks)`. Cada uno detrás de su propio `extras_require` (`[pdf-marker]`, `[doc-markitdown]`) para no inflar la instalación base. Detección de duplicación con `sha256` del archivo para idempotencia.

**Tech Stack:** Python 3.13 · `marker-pdf >= 1.0` (opt-in) · `markitdown[all] >= 0.0.x` (opt-in) · resto del stack `jw-rag` ya existente.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) §"Re-evaluación honesta", puntos 3 y 4 (TIER S, único gap real de OCR + Office docs hermanos).

**Depende de:** F45 (chunkers semantic), F33 (embed/rerank). NO depende de F58.

---

## File map

Crea (jw-rag):
- `packages/jw-rag/src/jw_rag/loaders/__init__.py` — si no existe, crea con docstring
- `packages/jw-rag/src/jw_rag/loaders/pdf_marker.py` — adapter marker → ingest
- `packages/jw-rag/src/jw_rag/loaders/docs_markitdown.py` — adapter markitdown → ingest
- `packages/jw-rag/tests/test_loaders_pdf_marker.py`
- `packages/jw-rag/tests/test_loaders_docs_markitdown.py`
- `packages/jw-rag/tests/fixtures/pdf/atalaya_sample.pdf` — PDF mini (10 KB) generado por script
- `packages/jw-rag/tests/fixtures/pdf/build_sample_pdf.py` — script reproducible
- `packages/jw-rag/tests/fixtures/docs/programa_circuito.docx` — docx mini generado por script
- `packages/jw-rag/tests/fixtures/docs/build_sample_docs.py` — script reproducible

Modifica (jw-rag):
- `packages/jw-rag/pyproject.toml` — añadir extras `pdf-marker` y `doc-markitdown`
- `packages/jw-rag/src/jw_rag/__init__.py` — re-export public loaders

Modifica (jw-mcp — exponer como tools):
- `packages/jw-mcp/src/jw_mcp/server.py` — añadir tools `ingest_pdf` y `ingest_office_doc`
- `packages/jw-mcp/tests/test_protocol.py` — registrar las 2 tools en `_EXPECTED_TOOLS`

Crea (CLI):
- Modify `packages/jw-cli/src/jw_cli/main.py` (o equivalente) — añadir subcomandos `jw rag ingest-pdf <path>` y `jw rag ingest-office <path>`

Doc:
- `docs/guias/historical-pdf-ingest.md` — guía operativa
- `docs/ROADMAP.md` — entrada F62
- `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md` — marcar F62 ✅

---

## Decisiones clave de diseño (anti-placeholder)

### Loader patrón: paragraphs → chunk_paragraphs → store.add
El patrón existente en `jw_rag/ingest.py` para EPUB/JWPUB es:
```python
def ingest_epub(store, path, *, language, publication_code):
    epub = parse_epub(path)
    paragraphs = [...flatten...]
    source_id = f"epub:{publication_code}"
    chunks = chunk_paragraphs(paragraphs, source_id=source_id, metadata={...})
    store.add(chunks)
    return len(chunks)
```
F62 lo replica para PDF/Office. No se reinventa la API.

### `source_id` convención
- PDF: `pdf:<sha256_first8>` — los PDFs no tienen "publication code" canónico.
- Docs: `doc:<filetype>:<sha256_first8>` — diferenciar docx/pptx/xlsx.

Razón: los archivos son user-provided y heterogéneos. Hash del contenido garantiza idempotencia (re-ingest = no-op).

### Modo `marker` por defecto: CPU + sin VLM remoto
`marker` puede usar GPU + LLM remoto para mejorar OCR. Default para JW: CPU-only, sin LLM (`use_llm=False`) — coherente con local-first. Usuario opta-in con env var `JW_MARKER_USE_GPU=1` y `JW_MARKER_USE_LLM=1` (último requiere también `OPENAI_API_KEY` o `ANTHROPIC_API_KEY`).

### `markitdown[all]` con `[all]` extras
markitdown tiene extras por filetype (`[docx]`, `[pptx]`, `[xlsx]`, `[pdf]`, `[image]`, `[audio]`). `[all]` incluye todos — el extra del toolkit `doc-markitdown` lo prende:
```toml
doc-markitdown = ["markitdown[all]>=0.0.1a"]
```
Es lo más conservador. Si el usuario quiere granular, puede `pip install markitdown[docx]` y forzar via `JW_MARKITDOWN_FORMAT_ALLOWLIST=docx,pptx`.

### Detección de "is JW publication" → metadata enrichment
Cuando el PDF/docx contiene **frases-firma JW** (p.ej. "Watch Tower Bible and Tract Society", "JW.ORG", "Atalaya", "The Watchtower"), el loader **anota** `metadata.is_jw=True`. Esto permite filtrar al hacer retrieval (`jw_rag.search(filter={"is_jw": True})`). NO bloquea ingest si es False — el RAG personal del usuario puede tener docs no-JW.

### Tabla/figuras del PDF: a markdown, no a JSON
`marker` puede emitir tablas como JSON estructurado. F62 lo convierte a markdown table inline en el flow de paragraphs — un chunk de tabla es un chunk normal. Razón: el RAG existente ranking-by-text + BM25 funciona mejor con markdown que con JSON random.

### Tests con fixtures mini construidos en CI
PDF real de Atalaya pesa MB y tiene copyright. Para tests deterministas:
- `build_sample_pdf.py` genera un PDF de 1 página con **texto sintético no-JW** (Lorem ipsum + tabla mini) usando `reportlab`. ~10 KB.
- `build_sample_docs.py` genera `.docx` con `python-docx` con headers + bullets.
- Ambos scripts son reproducibles y el binario se versiona junto al script.

---

### Task 1: Añadir extras a `pyproject.toml` y skeleton de loaders

**Files:**
- Modify: `packages/jw-rag/pyproject.toml`
- Create: `packages/jw-rag/src/jw_rag/loaders/__init__.py`

- [ ] **Step 1: Añadir extras**

En `packages/jw-rag/pyproject.toml`, dentro de `[project.optional-dependencies]`:
```toml
pdf-marker = ["marker-pdf>=1.0.0"]
doc-markitdown = ["markitdown[all]>=0.0.1a"]
loaders-all = ["jw-rag[pdf-marker,doc-markitdown]"]
```

- [ ] **Step 2: Crear `loaders/__init__.py`**

```python
# packages/jw-rag/src/jw_rag/loaders/__init__.py
"""Loaders externos para fuentes no-JWPUB/no-EPUB.

Cada loader es opt-in: la dependencia pesada vive detrás de un extra
del paquete (`[pdf-marker]`, `[doc-markitdown]`, `[loaders-all]`).

Public API:
    ingest_pdf(store, path, *, language, **metadata) -> int
    ingest_office_doc(store, path, *, language, **metadata) -> int
"""
from jw_rag.loaders.docs_markitdown import ingest_office_doc
from jw_rag.loaders.pdf_marker import ingest_pdf

__all__ = ["ingest_pdf", "ingest_office_doc"]
```

- [ ] **Step 3: Smoke fail (loaders no implementados)**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run python -c "from jw_rag.loaders import ingest_pdf"`
Expected: `ImportError: cannot import name 'ingest_pdf' from 'jw_rag.loaders.pdf_marker'` (lo crearemos en Task 2).

- [ ] **Step 4: Commit**

```bash
git add packages/jw-rag/pyproject.toml packages/jw-rag/src/jw_rag/loaders/__init__.py
git commit -m "feat(jw-rag): F62.1 scaffold loaders module plus pdf-marker doc-markitdown extras"
```

---

### Task 2: Fixture PDF sintético

**Files:**
- Create: `packages/jw-rag/tests/fixtures/pdf/build_sample_pdf.py`
- Create: `packages/jw-rag/tests/fixtures/pdf/atalaya_sample.pdf` (generado por el script)

- [ ] **Step 1: Script `build_sample_pdf.py`**

```python
# packages/jw-rag/tests/fixtures/pdf/build_sample_pdf.py
"""Genera un PDF de 1-2 páginas con texto sintético + 1 tabla mini
para tests del marker loader.

Para regenerar:
    cd packages/jw-rag/tests/fixtures/pdf
    uv run python build_sample_pdf.py

Requiere reportlab (dep dev). El PDF resultante simula el layout de
una página de Atalaya histórica (2 columnas, tabla simple) pero el
contenido es Lorem-ipsum-style para evitar issues de copyright en tests.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

HERE = Path(__file__).parent
OUTPUT = HERE / "atalaya_sample.pdf"

LOREM_HEADER = "Sample Article Heading (synthetic, not JW content)"
LOREM_P1 = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate."
)
LOREM_P2 = (
    "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis "
    "praesentiunt voluptatum deleniti atque corrupti quos dolores et quas "
    "molestias excepturi sint occaecati cupiditate non provident."
)


def main() -> None:
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=LETTER, title="Sample fixture")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(LOREM_HEADER, styles["Heading1"]),
        Spacer(1, 12),
        Paragraph(LOREM_P1, styles["BodyText"]),
        Spacer(1, 12),
        Paragraph(LOREM_P2, styles["BodyText"]),
        Spacer(1, 18),
        Paragraph("Table 1 — example", styles["Heading3"]),
    ]
    table_data = [
        ["Year", "Event", "Reference"],
        ["1914", "World War I begins", "Lorem 1:1"],
        ["1919", "Treaty signed", "Lorem 1:2"],
        ["1925", "Sample event", "Lorem 1:3"],
    ]
    t = Table(table_data, colWidths=[60, 250, 100])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(t)
    doc.build(story)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generar PDF**

Run:
```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv run --with reportlab python packages/jw-rag/tests/fixtures/pdf/build_sample_pdf.py
```
Expected: `Wrote .../atalaya_sample.pdf (NNNN bytes)`. Verifica que el archivo existe y abre.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-rag/tests/fixtures/pdf/
git commit -m "test(jw-rag): F62.2 add synthetic PDF fixture plus reproducible build script"
```

---

### Task 3: Loader `pdf_marker.py` — failing test primero

**Files:**
- Create: `packages/jw-rag/tests/test_loaders_pdf_marker.py`
- Create: `packages/jw-rag/src/jw_rag/loaders/pdf_marker.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-rag/tests/test_loaders_pdf_marker.py
"""F62 — loader marker_pdf. Test usa fixture PDF sintético; si marker
no está instalado, el test se skipa (no falla CI)."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "pdf" / "atalaya_sample.pdf"

pytest.importorskip("marker", reason="marker-pdf not installed; opt-in extra [pdf-marker]")


def test_pdf_marker_ingest_returns_chunk_count(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count = ingest_pdf(store, FIXTURE, language="en")
    assert count > 0


def test_pdf_marker_source_id_uses_hash(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en")
    all_chunks = store.list_chunks()
    source_ids = {c.source_id for c in all_chunks}
    assert any(sid.startswith("pdf:") for sid in source_ids)


def test_pdf_marker_idempotent(tmp_path):
    """Re-ingest mismo PDF no duplica chunks (idempotente por hash)."""
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count1 = ingest_pdf(store, FIXTURE, language="en")
    count2 = ingest_pdf(store, FIXTURE, language="en")
    assert count1 > 0
    assert count2 == 0  # No nuevos chunks en segunda pasada


def test_pdf_marker_metadata_includes_source_kind(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en", custom_meta={"sender": "hermano_pablo"})
    chunks = store.list_chunks()
    assert any(c.metadata.get("source_kind") == "pdf_marker" for c in chunks)
    assert any(c.metadata.get("sender") == "hermano_pablo" for c in chunks)


def test_pdf_marker_detects_jw_signature(tmp_path):
    """Si el PDF contiene frases-firma JW, metadata.is_jw=True."""
    # El fixture sintético NO contiene firma JW → is_jw debe ser False
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.pdf_marker import ingest_pdf

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_pdf(store, FIXTURE, language="en")
    chunks = store.list_chunks()
    assert all(c.metadata.get("is_jw", False) is False for c in chunks)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest packages/jw-rag/tests/test_loaders_pdf_marker.py -v`
Expected: tests fallan en import o en assertions porque no existe `pdf_marker.py` aún. Si marker no instalado, todos skipped (también ok — el test del loader interno solo corre con marker disponible).

> **Si marker NO está instalado en dev env**: instala con `uv pip install --group dev marker-pdf` o añade a un grupo `[tool.uv]` dev-dependencies.

- [ ] **Step 3: Implementar loader**

```python
# packages/jw-rag/src/jw_rag/loaders/pdf_marker.py
"""Loader PDF → markdown → chunks usando datalab-to/marker.

NO importa `marker` en module-level; lo hace lazy dentro de `ingest_pdf`
para que el monorepo arranque aunque el extra `[pdf-marker]` no esté
instalado (graceful degrade: la función falla con ModuleNotFoundError
con un mensaje claro, no falla en import).

Idempotencia por hash sha256 del contenido del PDF.
Detección de "is JW publication" por sustring matching contra signatures
conocidas (Watch Tower, JW.ORG, etc.).
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from jw_rag.chunkers import get_chunker
from jw_rag.store import VectorStore

_JW_SIGNATURES_RE = re.compile(
    r"(watch\s*tower|jw\.org|atalaya|the\s*watchtower|awake!|despertad!|"
    r"kingdom\s*hall|jehovah'?s\s*witnesses|testigos\s*de\s*jehov[áa])",
    re.IGNORECASE,
)


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_is_jw(markdown_text: str) -> bool:
    return bool(_JW_SIGNATURES_RE.search(markdown_text))


def ingest_pdf(
    store: VectorStore,
    pdf_path: Path | str,
    *,
    language: str,
    chunker: str | None = None,
    custom_meta: dict[str, Any] | None = None,
) -> int:
    """Ingiere un PDF al VectorStore.

    Pipeline:
        1. Compute sha256 del archivo (para source_id + idempotencia).
        2. Si el store ya tiene chunks con ese source_id → return 0 (no-op).
        3. Llamar marker para producir markdown estructurado.
        4. Split markdown en párrafos.
        5. Detectar firmas JW → set metadata.is_jw.
        6. chunk_paragraphs(...) + store.add(...).

    Args:
        store: VectorStore destino.
        pdf_path: ruta al PDF.
        language: código de idioma (E/S/T) para enrutar chunker semántico F45.
        chunker: nombre del chunker (None usa el default).
        custom_meta: metadata extra que se mergea con la del loader.

    Returns:
        int — número de chunks añadidos (0 si ya estaba ingerido).

    Raises:
        ModuleNotFoundError: si `marker-pdf` no está instalado (mensaje
            sugiere `uv add 'jw-rag[pdf-marker]'`).
    """
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError as exc:
        raise ModuleNotFoundError(
            "marker-pdf is not installed. Run: uv add 'jw-rag[pdf-marker]'"
        ) from exc

    pdf_path = Path(pdf_path)
    file_hash = _file_hash(pdf_path)
    source_id = f"pdf:{file_hash[:8]}"

    if store.has_source(source_id):
        return 0

    use_gpu = os.environ.get("JW_MARKER_USE_GPU", "0") == "1"
    use_llm = os.environ.get("JW_MARKER_USE_LLM", "0") == "1"

    converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config={"use_llm": use_llm, "device": "cuda" if use_gpu else "cpu"},
    )
    rendered = converter(str(pdf_path))
    markdown_text, _ = text_from_rendered(rendered)

    paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]
    is_jw = _detect_is_jw(markdown_text)

    metadata: dict[str, Any] = {
        "source_kind": "pdf_marker",
        "source_path": str(pdf_path.resolve()),
        "file_hash": file_hash,
        "is_jw": is_jw,
        "language": language,
    }
    if custom_meta:
        metadata.update(custom_meta)

    chunker_obj = get_chunker(chunker)
    chunks = chunker_obj.chunk_paragraphs(
        paragraphs=paragraphs,
        source_id=source_id,
        metadata=metadata,
    )
    store.add(chunks)
    return len(chunks)
```

- [ ] **Step 4: Verificar que `VectorStore.has_source()` y `list_chunks()` existen**

Si no existen como métodos públicos:
```python
# packages/jw-rag/src/jw_rag/store.py — añadir:
def has_source(self, source_id: str) -> bool:
    """Devuelve True si el store ya tiene al menos un chunk con ese source_id."""
    return any(c.source_id == source_id for c in self._chunks)

def list_chunks(self) -> list[Chunk]:
    """Devuelve copia ligera de todos los chunks (read-only, para tests)."""
    return list(self._chunks)
```
(Si la API ya tiene equivalentes con otro nombre, adapta el loader y los tests para usar la nomenclatura correcta.)

- [ ] **Step 5: Run tests, expect PASS (o skip si marker no instalado)**

Run: `uv run pytest packages/jw-rag/tests/test_loaders_pdf_marker.py -v`
Expected: 5 passed (o skipped si marker NO instalado en env).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-rag/src/jw_rag/loaders/pdf_marker.py packages/jw-rag/tests/test_loaders_pdf_marker.py packages/jw-rag/src/jw_rag/store.py
git commit -m "feat(jw-rag): F62.3 marker PDF loader with JW signature detection plus hash idempotency"
```

---

### Task 4: Fixture Office sintético

**Files:**
- Create: `packages/jw-rag/tests/fixtures/docs/build_sample_docs.py`
- Create: `packages/jw-rag/tests/fixtures/docs/programa_circuito.docx` (generado)

- [ ] **Step 1: Script generador**

```python
# packages/jw-rag/tests/fixtures/docs/build_sample_docs.py
"""Genera un .docx de prueba simulando un 'Programa de Circuito' breve.
Contenido sintético, sin texto JW real, para evitar copyright en tests.

Requires: python-docx (dep dev)
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Inches

HERE = Path(__file__).parent
OUTPUT = HERE / "programa_circuito.docx"


def main() -> None:
    doc = Document()
    doc.add_heading("Programa de Circuito — Sample Fixture", level=1)
    doc.add_paragraph(
        "Documento sintético para testing. NO contiene contenido JW real."
    )
    doc.add_heading("Reunión 1", level=2)
    doc.add_paragraph(
        "Discurso público: Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    )
    doc.add_paragraph(
        "Estudio de la Atalaya: Sed do eiusmod tempor incididunt ut labore."
    )
    doc.add_heading("Reunión 2", level=2)
    doc.add_paragraph(
        "Vida y Ministerio Cristianos: Ut enim ad minim veniam, quis nostrud."
    )
    table = doc.add_table(rows=3, cols=2)
    table.style = "Light Grid"
    table.rows[0].cells[0].text = "Hora"
    table.rows[0].cells[1].text = "Parte"
    table.rows[1].cells[0].text = "10:00"
    table.rows[1].cells[1].text = "Cántico y oración"
    table.rows[2].cells[0].text = "10:15"
    table.rows[2].cells[1].text = "Discurso público"
    doc.save(OUTPUT)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generar**

Run:
```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv run --with python-docx python packages/jw-rag/tests/fixtures/docs/build_sample_docs.py
```
Expected: `Wrote .../programa_circuito.docx (NNNN bytes)`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-rag/tests/fixtures/docs/
git commit -m "test(jw-rag): F62.4 add synthetic docx fixture plus build script"
```

---

### Task 5: Loader `docs_markitdown.py` con tests

**Files:**
- Create: `packages/jw-rag/tests/test_loaders_docs_markitdown.py`
- Create: `packages/jw-rag/src/jw_rag/loaders/docs_markitdown.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-rag/tests/test_loaders_docs_markitdown.py
"""F62 — loader markitdown para docx/pptx/xlsx. Skip si dep ausente."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DOCX = Path(__file__).parent / "fixtures" / "docs" / "programa_circuito.docx"

pytest.importorskip("markitdown", reason="markitdown not installed; opt-in [doc-markitdown]")


def test_ingest_docx(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    assert count > 0


def test_docx_source_id_format(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    ingest_office_doc(store, FIXTURE_DOCX, language="es")
    chunks = store.list_chunks()
    assert any(c.source_id.startswith("doc:docx:") for c in chunks)


def test_docx_idempotent(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc

    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    count1 = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    count2 = ingest_office_doc(store, FIXTURE_DOCX, language="es")
    assert count1 > 0 and count2 == 0


def test_unsupported_extension_raises(tmp_path):
    from jw_rag.store import VectorStore
    from jw_rag.embedders import FakeEmbedder
    from jw_rag.loaders.docs_markitdown import ingest_office_doc

    fake_file = tmp_path / "thing.xyz"
    fake_file.write_text("nope")
    store = VectorStore(path=tmp_path / "store", embedder=FakeEmbedder())
    with pytest.raises(ValueError, match="unsupported extension"):
        ingest_office_doc(store, fake_file, language="es")
```

- [ ] **Step 2: Implementar loader**

```python
# packages/jw-rag/src/jw_rag/loaders/docs_markitdown.py
"""Loader Office docs → markdown → chunks usando microsoft/markitdown.

Soporta .docx, .pptx, .xlsx. Otros formatos (.pdf via markitdown) los
deja a `pdf_marker.py` (markitdown PDF es inferior a marker para layout
complejo).

Lazy import como `pdf_marker.py`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jw_rag.chunkers import get_chunker
from jw_rag.store import VectorStore

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".xlsx"})


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_office_doc(
    store: VectorStore,
    doc_path: Path | str,
    *,
    language: str,
    chunker: str | None = None,
    custom_meta: dict[str, Any] | None = None,
) -> int:
    """Ingiere un docx/pptx/xlsx al VectorStore vía markitdown.

    Pipeline igual que `ingest_pdf`: hash → idempotency check → convert →
    paragraphs → chunk → store.

    Raises:
        ValueError: si la extensión no está en SUPPORTED_EXTENSIONS.
        ModuleNotFoundError: si markitdown no está instalado.
    """
    doc_path = Path(doc_path)
    ext = doc_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"unsupported extension {ext!r}; supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ModuleNotFoundError(
            "markitdown is not installed. Run: uv add 'jw-rag[doc-markitdown]'"
        ) from exc

    file_hash = _file_hash(doc_path)
    source_id = f"doc:{ext.lstrip('.')}:{file_hash[:8]}"
    if store.has_source(source_id):
        return 0

    md = MarkItDown()
    result = md.convert(str(doc_path))
    markdown_text = result.text_content
    paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]

    metadata: dict[str, Any] = {
        "source_kind": "office_markitdown",
        "source_format": ext.lstrip("."),
        "source_path": str(doc_path.resolve()),
        "file_hash": file_hash,
        "language": language,
    }
    if custom_meta:
        metadata.update(custom_meta)

    chunker_obj = get_chunker(chunker)
    chunks = chunker_obj.chunk_paragraphs(
        paragraphs=paragraphs,
        source_id=source_id,
        metadata=metadata,
    )
    store.add(chunks)
    return len(chunks)
```

- [ ] **Step 3: Run tests, expect PASS (o skipped)**

Run: `uv run pytest packages/jw-rag/tests/test_loaders_docs_markitdown.py -v`
Expected: 4 passed o 4 skipped si markitdown ausente.

- [ ] **Step 4: Re-export en `__init__.py` (ya hecho en Task 1) — verificar import**

Run: `uv run python -c "from jw_rag.loaders import ingest_pdf, ingest_office_doc; print('OK')"`
Expected: `OK` sin error.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-rag/src/jw_rag/loaders/docs_markitdown.py packages/jw-rag/tests/test_loaders_docs_markitdown.py
git commit -m "feat(jw-rag): F62.5 markitdown office docs loader (docx pptx xlsx)"
```

---

### Task 6: Exponer como MCP tools

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_protocol.py`

- [ ] **Step 1: Añadir 2 tools al server**

```python
@mcp.tool
async def ingest_pdf(
    pdf_path: str,
    language: str = "en",
    chunker: str | None = None,
) -> dict[str, Any]:
    """Ingiere un PDF al RAG store usando marker (CPU local por default).

    Útil para Atalayas históricas escaneadas, libros JW pre-EPUB,
    o cualquier PDF compartido por hermanos. La detección automática
    de firmas JW marca `metadata.is_jw=True` cuando aplica.

    Args:
        pdf_path: ruta absoluta al PDF.
        language: código de idioma (en/es/pt).
        chunker: nombre del chunker; None usa el default.

    Returns:
        Dict con `chunks_added`, `source_id`, `is_jw`.
    """
    try:
        from jw_rag.loaders.pdf_marker import ingest_pdf as _impl
    except ImportError as exc:
        return {"error": f"{exc}"}
    try:
        from pathlib import Path
        store = _get_rag_store()
        n = _impl(store, Path(pdf_path), language=language, chunker=chunker)
        return {"chunks_added": n, "pdf_path": pdf_path, "language": language}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def ingest_office_doc(
    doc_path: str,
    language: str = "en",
    chunker: str | None = None,
) -> dict[str, Any]:
    """Ingiere un .docx/.pptx/.xlsx al RAG store usando markitdown.

    Útil para guiones de discursos, programas de circuito, hojas de
    asistencia, materiales compartidos en hermandad.

    Args:
        doc_path: ruta absoluta al documento.
        language: código de idioma.
        chunker: nombre del chunker; None usa default.

    Returns:
        Dict con `chunks_added`, `source_id`, `source_format`.
    """
    try:
        from jw_rag.loaders.docs_markitdown import ingest_office_doc as _impl
    except ImportError as exc:
        return {"error": f"{exc}"}
    try:
        from pathlib import Path
        store = _get_rag_store()
        n = _impl(store, Path(doc_path), language=language, chunker=chunker)
        return {"chunks_added": n, "doc_path": doc_path, "language": language}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

(`_get_rag_store()` es el helper existente que devuelve la singleton VectorStore — verifica el nombre exacto en server.py y ajusta.)

- [ ] **Step 2: Registrar tools en `_EXPECTED_TOOLS`**

```python
# En test_protocol.py, añadir al set:
"ingest_pdf",
"ingest_office_doc",
```

- [ ] **Step 3: Run tests, expect PASS**

Run: `uv run pytest packages/jw-mcp/tests/test_protocol.py -v`
Expected: protocol test verde.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_protocol.py
git commit -m "feat(jw-mcp): F62.6 expose ingest_pdf ingest_office_doc as MCP tools"
```

---

### Task 7: CLI subcommands

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/main.py` (o equivalente)

- [ ] **Step 1: Localizar el sub-app `rag` en CLI**

Run: `grep -rn "rag" packages/jw-cli/src/ | head -10`
Si existe `rag_app`, añade comandos a ese. Si no, crea nueva sub-app.

- [ ] **Step 2: Añadir comandos**

```python
# En el módulo CLI (jw-cli/src/jw_cli/main.py o jw_cli/rag.py):

@rag_app.command("ingest-pdf")
def cli_ingest_pdf(
    path: Path = typer.Argument(..., help="Ruta al PDF"),
    language: str = typer.Option("en", "--language", help="Código de idioma"),
    chunker: str | None = typer.Option(None, "--chunker"),
) -> None:
    """Ingiere un PDF al RAG store usando marker (F62)."""
    from jw_rag.loaders.pdf_marker import ingest_pdf
    from jw_rag.store import VectorStore
    from jw_rag.embedders import build_default_embedder
    store = VectorStore(path=Path(os.environ.get("JW_RAG_STORE_PATH",
                                                  "~/.jw-agent-toolkit/rag")).expanduser(),
                        embedder=build_default_embedder())
    store.load()
    n = ingest_pdf(store, path, language=language, chunker=chunker)
    store.save()
    typer.echo(f"Ingested {n} chunks from {path}")


@rag_app.command("ingest-office")
def cli_ingest_office(
    path: Path = typer.Argument(..., help="Ruta al .docx/.pptx/.xlsx"),
    language: str = typer.Option("en", "--language"),
    chunker: str | None = typer.Option(None, "--chunker"),
) -> None:
    """Ingiere un documento Office al RAG store usando markitdown (F62)."""
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
    from jw_rag.store import VectorStore
    from jw_rag.embedders import build_default_embedder
    store = VectorStore(path=Path(os.environ.get("JW_RAG_STORE_PATH",
                                                  "~/.jw-agent-toolkit/rag")).expanduser(),
                        embedder=build_default_embedder())
    store.load()
    n = ingest_office_doc(store, path, language=language, chunker=chunker)
    store.save()
    typer.echo(f"Ingested {n} chunks from {path}")
```

(Ajustar a la firma real de `VectorStore` y embedder factory del repo.)

- [ ] **Step 3: Smoke**

Run: `uv run jw rag --help`
Expected: la sección de comandos incluye `ingest-pdf` y `ingest-office`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-cli/src/jw_cli/
git commit -m "feat(jw-cli): F62.7 add jw rag ingest-pdf ingest-office commands"
```

---

### Task 8: Doc + ROADMAP + master plan

**Files:**
- Create: `docs/guias/historical-pdf-ingest.md`
- Modify: `docs/README.md`, `docs/ROADMAP.md`, master plan

- [ ] **Step 1: Guía operativa**

```markdown
# Ingest de PDFs históricos y docs Office (Fase 62)

> Cómo añadir al RAG personal Atalayas/Awake escaneadas, libros JW pre-EPUB,
> y documentos compartidos por hermanos (guiones, programas de circuito).

## Instalación

```bash
uv add 'jw-rag[loaders-all]'   # marker + markitdown
# o granular:
uv add 'jw-rag[pdf-marker]'
uv add 'jw-rag[doc-markitdown]'
```

## Uso CLI

```bash
# PDF de Atalaya 1950 (escaneo personal del usuario)
jw rag ingest-pdf ~/Documents/atalaya_1950_marzo.pdf --language es

# Programa de circuito compartido por el superintendente
jw rag ingest-office ~/Documents/programa_circuito_2026.docx --language es
```

## Detección automática "es contenido JW?"

El loader busca firmas en el texto extraído:
`watch tower`, `jw.org`, `atalaya`, `kingdom hall`, `testigos de jehová`, etc.

Si encuentra alguna → `metadata.is_jw=True`. Permite queries filtradas:
```python
hits = store.search("trinidad", filter={"is_jw": True})
```

## Idempotencia

Re-ingest del mismo archivo (mismo `sha256`) NO duplica chunks. Útil si
el usuario reescanea o si CI re-procesa el mismo corpus.

## GPU y LLM opt-in

Por default marker corre en CPU sin LLM. Para acelerar y mejorar layout:
```bash
JW_MARKER_USE_GPU=1 JW_MARKER_USE_LLM=1 OPENAI_API_KEY=sk-... \
    jw rag ingest-pdf <path>
```

## Limitaciones

- **Tablas complejas**: marker hace su mejor esfuerzo, ocasionalmente
  pierde celdas merged. Verificar manualmente.
- **OCR de escaneos de baja resolución**: <150 DPI puede dar texto basura.
  Re-escanear a 300 DPI antes.
- **Cifrado**: PDFs cifrados con contraseña fallan — descifrar primero.
- **Office macros**: markitdown ignora macros; el contenido visible se
  extrae correctamente.
```

- [ ] **Step 2: Añadir a `docs/README.md`** (sección "Guías por tema"):
```markdown
- [Ingest de PDFs históricos](guias/historical-pdf-ingest.md) — Fase 62: añade Atalayas escaneadas y docs Office al RAG personal vía marker + markitdown, con detección automática de contenido JW.
```

- [ ] **Step 3: ROADMAP entry**

```markdown
## Fase 62 — marker + markitdown loaders ✅

- ✅ `jw_rag.loaders.pdf_marker.ingest_pdf()` con marker (CPU default, GPU/LLM opt-in).
- ✅ `jw_rag.loaders.docs_markitdown.ingest_office_doc()` para .docx/.pptx/.xlsx.
- ✅ Detección de firmas JW → metadata.is_jw.
- ✅ Idempotencia por sha256 del archivo.
- ✅ Tools MCP `ingest_pdf` + `ingest_office_doc`.
- ✅ CLI `jw rag ingest-pdf|ingest-office`.
- ✅ Fixtures sintéticos reproducibles + tests con `pytest.importorskip`.
- ⬜ Imagen-only PDF (escaneo puro sin texto extraíble): pendiente integración Tesseract fallback.
```

- [ ] **Step 4: Marcar F62 ✅ en master plan**

- [ ] **Step 5: Commit final**

```bash
git add docs/
git commit -m "docs(F62): historical PDF ingest guide plus ROADMAP entry"
```

---

## Tests resumen

```bash
uv run pytest packages/jw-rag/tests/test_loaders_pdf_marker.py \
              packages/jw-rag/tests/test_loaders_docs_markitdown.py \
              packages/jw-mcp/tests/test_protocol.py \
              -v --tb=short
```

Si deps están instaladas: ~9 passed. Si no: skipped + protocol test verde.

---

## Self-review checklist

- ✅ **Cobertura de spec**: PDF (marker) ✓, Office (markitdown) ✓, JW detection ✓, idempotencia ✓, MCP tools ✓, CLI ✓.
- ✅ **No placeholders**: cada Step tiene código completo. Donde la API del repo no se conoce 100% (`_get_rag_store`, `VectorStore.has_source`) se marca como "verificar/adaptar".
- ✅ **Consistencia de tipos**: `source_id` format `pdf:<hash8>` y `doc:<ext>:<hash8>` consistente en loaders, tools y tests. `language: str` consistente.
- ⚠️ **Dependencia externa pesada**: marker-pdf trae torch/transformers (~2 GB). Documentar en la guía que el extra `[pdf-marker]` es opt-in.
