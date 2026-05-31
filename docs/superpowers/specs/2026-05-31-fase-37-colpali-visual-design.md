# Fase 37 — `colpali-visual`: late interaction sobre páginas rasterizadas

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (especializado)
> **Depende de**: Fase 33 (`embed-rerank`, reusa RRF de `VectorStore.hybrid_search`) y Fase 36 (`vlm-ocr`, comparte rasterizer y backends GPU)
> **Documento padre**: [`2026-05-31-fases-33-38-overview.md`](2026-05-31-fases-33-38-overview.md)
> **Spec hermano relevante**: [`2026-05-30-fase-22-eval-doctrinal-design.md`](2026-05-30-fase-22-eval-doctrinal-design.md) — formato golden cases

## Motivación

El stack actual de `jw-rag` indexa **texto extraído** de JWPUB/EPUB/PDF. Eso falla cuando la información relevante está codificada en la **maquetación**: tablas comparativas, recuadros laterales, ilustraciones con leyenda, líneas de tiempo de Daniel/Apocalipsis, mapas de viajes de Pablo, organigramas de la congregación, o diagramas del tabernáculo.

Casos concretos observables hoy:

- Consulta "viajes misioneros de Pablo" → recuperamos texto descriptivo, **no** el mapa donde el lector mira primero.
- Consulta "modelo del tabernáculo" → texto disperso en 6 párrafos sin la ilustración que los conecta.
- Consulta "tabla de los 7 días de la creación" → tabla se aplana a texto ilegible.

ColPali (Faysse et al., 2024) y ColQwen2 resuelven esto: rasterizan la página, generan **multi-vector embeddings por parche visual** (típicamente ~1030 parches × 128 dims por página A4), y puntúan con **MaxSim** (suma sobre tokens-de-query del máximo producto interno contra parches-de-doc). El modelo aprende posición + tipografía + diagramas a la vez que texto.

Fase 37 añade este eje visual al RAG como **store paralelo** que se fusiona con el texto vía RRF (Fase 33 ya tiene el camino). NO sustituye al store textual.

## Objetivos (en orden de prioridad)

1. **Recall@10 ≥+40%** sobre 5 queries figura-pesadas vs el RAG texto-only de Fase 33.
2. **Failure mode limpio**: sin GPU el subsistema falla en `factory.get_default_provider()` con un mensaje accionable. Nunca degrada silenciosamente a un placeholder.
3. **Cero impacto en CI público**: el módulo entero es opt-in vía extra `[visual]` y los tests usan `FakeColPaliEmbedder` determinista.
4. **Ingest incremental por sha256** de fichero fuente (JWPUB/EPUB/PDF) — re-procesar un volumen entero cuesta horas, no podemos pagarlo cada cambio.
5. **Hybrid graceful**: si el store visual está, `hybrid_search` lo añade al RRF; si no, comportamiento de Fase 33 idéntico.

## No-objetivos (boundaries vinculantes)

- **No** reemplaza `VectorStore` textual. Esta fase añade un **segundo** store, no migra.
- **No** trae modelos de PyPI/HuggingFace en `pyproject.toml` core — son extras opcionales (`[visual]`).
- **No** soporta CPU: ColQwen2 en CPU es >30s/página, inviable. Diseño explícito de fail-fast.
- **No** soporta API fallback (no existe servicio comercial estable de ColPali en 2026). Cuando el creador del proyecto está en Mac sin GPU NVIDIA y MLX no acelera lo suficiente, este módulo simplemente **no se activa** y el RAG cae al stack de Fase 33.
- **No** reescribe el `Embedder` Protocol — ColPali es multi-vector, no encaja en el contrato single-vector existente. Vive en su propia jerarquía.
- **No** soporta filtros por metadata sofisticados en v1 — sólo filtro por `source_id` y `language` como el store textual.

## Arquitectura

Nuevo módulo `packages/jw-rag/src/jw_rag/visual/`. Dependencias hacia abajo: importa `jw-core` (parsers JWPUB/EPUB para extraer imágenes/páginas) y `jw-rag` (reusa `Chunk`, `SearchHit`). Lo importa `jw-agents` (opt-in) y `jw-mcp` (herramienta nueva).

```
packages/jw-rag/src/jw_rag/visual/
├── __init__.py
├── models.py              # VisualChunk, MultiVectorHit
├── colpali.py             # ColPaliEmbedder, ColQwen2Embedder, factory
├── visual_store.py        # VisualVectorStore (multi-vector + MaxSim)
├── page_rasterizer.py     # JWPUB/EPUB/PDF → list[PIL.Image]
├── hybrid.py              # extiende RRF de Fase 33 con visual hits
├── ingest.py              # ingest_jwpub_visual / ingest_epub_visual / ingest_pdf_visual
└── fakes.py               # FakeColPaliEmbedder determinista (tests)

packages/jw-rag/tests/visual/
├── test_models.py
├── test_rasterizer.py     # con PDF/EPUB sintéticos en fixtures
├── test_visual_store.py   # con FakeColPaliEmbedder
├── test_hybrid.py
├── test_ingest.py
└── fixtures/
    ├── mini.pdf
    ├── mini.epub
    └── mini.jwpub          # JWPUB sintético sin contenido oficial
```

### Reglas duras de diseño

1. `jw_rag.visual` **no** importa `colpali_engine` / `transformers` / `torch` en import time. Los imports son perezosos dentro de los providers reales. El módulo se puede importar siempre; sólo `is_available()` toca hardware.
2. `VisualVectorStore` **no** hereda de `VectorStore` — comparte interfaz (search, save, load) pero la implementación interna es distinta. Composición vía protocolo, no herencia.
3. Multi-vector storage: `vectors.npy` es `(N_docs, max_patches, dim)` padded con ceros + máscara separada `mask.npy` `(N_docs, max_patches)` bool. Padding desperdicia espacio pero hace que MaxSim sea una sola operación BLAS.
4. **Sin red en tests**: rasterizer puede usar Playwright (red para descargar Chromium una vez) → tests usan `FakeRasterizer` que devuelve `PIL.Image.new("RGB", (768, 1024))`.
5. **Mismatch detection en load()**: `meta.json` incluye `model_name`, `model_revision`, `patch_size`, `dim`. Si carga con embedder distinto, lanza `VisualStoreMismatchError` con instrucción de re-ingesta.
6. Ingesta **incremental por sha256(file)**: si ya existe `source_id == sha256` en el store, skip. Para forzar re-ingesta hay flag `force=True`.

## Integración con `VectorStore` de Fase 33

`VectorStore.hybrid_search` queda intacto. Se añade un helper en `jw_rag.visual.hybrid`:

```python
# jw_rag/visual/hybrid.py
def hybrid_search_with_visual(
    text_store: VectorStore,
    visual_store: VisualVectorStore | None,
    query: str,
    *,
    top_k: int = 10,
    candidate_pool: int = 50,
    rrf_k: int = 60,
    rerank: bool = True,
) -> list[SearchHit]:
    """Three-way RRF: bm25 + text-vector + visual-MaxSim.

    Si `visual_store is None` o `visual_store.is_empty`, se comporta
    exactamente como `text_store.hybrid_search(query, ...)`.
    """
```

El visual hit se proyecta a `SearchHit` con `source="visual"` y `chunk` apunta a un `VisualChunk` que envuelve `(page_image_path, page_number, source_id, ocr_text_optional)`. El `chunk.text` es el OCR opcional de Fase 36 (si está) o `""`. Los agentes consumen `SearchHit` exactamente igual; el campo `source` les indica si renderizar la imagen al usuario.

### Esquema de `VisualVectorStore`

Persistencia bajo `path/visual/`:

```
visual/
├── meta.json          {"multi_vector": true, "model_name": "colqwen2-v0.1",
│                       "model_revision": "abc123", "patch_size": 14,
│                       "dim": 128, "max_patches": 1030,
│                       "count": 1234, "language": "es"}
├── chunks.jsonl       — una línea por VisualChunk (page_number, source_id, image_path)
├── vectors.npy        — (N, max_patches, dim) float16 padded
├── mask.npy           — (N, max_patches) bool
└── images/            — PNGs de las páginas (lazy-load para render al usuario)
    └── {sha256[:16]}_p{NNN}.png
```

### MaxSim scoring

```python
def maxsim(q_vecs: np.ndarray, d_vecs: np.ndarray, d_mask: np.ndarray) -> float:
    """q_vecs: (N_q_tokens, dim) — query parches/tokens.
       d_vecs: (max_patches, dim) — doc page parches padded.
       d_mask: (max_patches,) bool.

       score = sum over q_token of max over valid d_patch of <q_token, d_patch>.
    """
    sims = q_vecs @ d_vecs.T          # (N_q, max_patches)
    sims[:, ~d_mask] = -np.inf
    return float(sims.max(axis=1).sum())
```

Para top-k sobre N docs hacemos batch contra todos (N×max_patches×dim×N_q_tokens flops). Con N=10k páginas, max_patches=1030, dim=128, N_q=32 tokens: ~4·10⁹ flops por query — manejable en GPU, ~1.5s en CPU para sanity-check. En v1 corremos siempre en GPU si el store está activo.

## Pipeline de ingesta

```python
# jw_rag/visual/ingest.py
def ingest_jwpub_visual(
    path: Path,
    store: VisualVectorStore,
    *,
    rasterize_dpi: int = 200,
    force: bool = False,
) -> IngestResult:
    """Rasteriza cada página del JWPUB → embed por ColQwen2 → store.

    Idempotente por sha256(path). Si `force=False` y el source_id ya está
    indexado, salta. Devuelve `IngestResult(pages_added, pages_skipped, ms)`.
    """
```

Pasos:

1. `source_id = sha256(file_bytes)[:32]`. Si `source_id in store.source_ids()` y no `force`: skip.
2. `parse_jwpub_metadata(path)` para extraer estructura.
3. `page_rasterizer.rasterize_jwpub(path, dpi=200)` → `list[(page_idx, PIL.Image, page_metadata)]`. JWPUB usa pipeline: render XHTML→HTML→Playwright/WeasyPrint→PNG. EPUB idem. PDF directo con `pdf2image`.
4. Para cada imagen, `embedder.embed_image(image) -> (N_patches, dim) float16`.
5. Pad a `max_patches`, calcular máscara, append a `vectors.npy` + `mask.npy`.
6. Persist incremental: tras N páginas o al final, `store.save()`.
7. Imágenes PNG van a `visual/images/` para render posterior; opcionalmente convertidas a WebP para ahorrar disco.

### Equivalentes para EPUB y PDF

- `ingest_epub_visual(path, store, ...)`: spine → render cada XHTML con Playwright headless a viewport fijo (768×1024 default).
- `ingest_pdf_visual(path, store, ...)`: `pdf2image.convert_from_path` a 200dpi.

Los tres comparten 90% de la implementación; las diferencias están en el rasterizer.

## Hardware strategy

```python
# jw_rag/visual/colpali.py
class ColPaliEmbedder:
    name = "colpali-v1.2"
    target: Literal["nvidia", "mlx"]

    @classmethod
    def is_available(cls, target: str = "nvidia") -> bool:
        if target == "nvidia":
            try:
                import torch
                return torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory > 12_000_000_000
            except ImportError:
                return False
        if target == "mlx":
            try:
                import mlx.core as mx
                return mx.metal.is_available()
            except ImportError:
                return False
        return False

    def embed_image(self, image: PIL.Image.Image) -> np.ndarray:
        """(N_patches, dim) float16. Lazy-load del modelo en primera llamada."""
```

`factory.get_default_visual_embedder()` ordena `[nvidia, mlx]` (no `[api, ...]` como otros providers — aquí NO hay API path):

```python
PROVIDER_ORDER = ["nvidia", "mlx"]   # CPU deliberadamente ausente

def get_default_visual_embedder() -> ColPaliEmbedder | ColQwen2Embedder:
    for target in PROVIDER_ORDER:
        for cls in (ColQwen2Embedder, ColPaliEmbedder):
            if cls.is_available(target=target):
                return cls(target=target)
    raise ConfigError(
        "No GPU disponible para ColPali. Opciones:\n"
        "  1. Instalar en máquina con NVIDIA GPU ≥12GB VRAM: uv sync --extra visual\n"
        "  2. Instalar en Apple Silicon ≥M2: uv sync --extra visual-mlx\n"
        "  3. Desactivar el módulo visual: dejar JW_VISUAL_ENABLED=0\n"
        "Para tests usar FakeColPaliEmbedder.\n"
    )
```

Razón del orden NVIDIA-primero (rompe la convención de las otras fases que ponen `api` primero): ColQwen2 con `colpali-engine` está optimizado para CUDA. La ruta MLX vía `mlx-vlm` es experimental y los pesos no están portados al 100%. La elección del autor de tener una 5090 (32GB) hace que NVIDIA sea el camino feliz real.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | `colpali-engine` cambia API breakings entre minor releases | Pin estricto en `[visual]` extra + smoke test semanal en CI nightly con GPU runner self-hosted (opt-in, no bloqueante en CI público) |
| 2 | Modelos descargan ~5GB de HuggingFace en primera llamada | Documentar en `docs/guias/visual-rag.md`; precarga manual con `huggingface-cli download` antes del primer ingest |
| 3 | Storage explota: 10k páginas × 1030 patches × 128 dims × 2B (fp16) ≈ 2.5GB | float16 obligatorio + flag `max_patches` que recorta resoluciones extremas (mapas gigantes) |
| 4 | Rasterización inconsistente entre OS (WeasyPrint vs Playwright vs pdf2image) | Pipeline único por formato; documentar resolución target = 200dpi y viewport 768×1024 para EPUB; tests con golden hashes de imágenes pequeñas |
| 5 | MaxSim O(N×patches×dim×q_tokens) escala mal sobre >100k páginas | v1 limitado a ~10k páginas/store; documentar split por store y unión vía RRF para corpora mayores. v2 puede añadir ANN multi-vector (PLAID) |
| 6 | Playwright requiere Chromium descargado (~150MB) | Documentado en `[visual]` extra; CI público nunca corre ingesta visual real |
| 7 | Tests con imágenes reales son lentos | `FakeColPaliEmbedder` devuelve vectores deterministas por `sha256(image_bytes)`; rasterizer fake devuelve PIL en blanco |
| 8 | Usuarios sin GPU intentan usar el módulo y se confunden | `ConfigError` con mensaje accionable + check temprano en MCP tool `visual_search` que retorna `{"error": "...", "hint": "..."}` |
| 9 | Inconsistencia entre store textual y visual (mismo source_id apunta a chunks distintos) | `VisualChunk.source_id` usa la **misma** convención que textual: `sha256(file_bytes)`. Permite cross-reference exacto para citas |
| 10 | Cita visual ¿qué URL emite el agente? | Visual hit produce metadata con `page_number` + `source_path`; el `apologetics` agent ya sabe construir URL wol.jw.org desde JWPUB metadata. Para EPUB/PDF arbitrario emite ruta local + página |

## Métricas de éxito de la fase

- **Recall@10 sobre 5 golden queries figura-pesadas mejora ≥40%** vs Fase 33 texto-only. Casos en `packages/jw-eval/fixtures/golden_qa/l1/visual_*.yaml`. Queries sugeridas:
  - "viajes misioneros de Pablo" → debe traer página con el mapa
  - "tabernáculo: medidas y materiales" → debe traer la ilustración
  - "los siete tiempos de Daniel" → debe traer la línea de tiempo
  - "estructura organizativa de los testigos de Jehová" → debe traer el organigrama
  - "comparativa de las cuatro bestias de Daniel 7" → debe traer la tabla
- `uv sync --extra visual` instala todo sin errores en máquina NVIDIA (Linux).
- `uv sync --extra visual-mlx` instala todo sin errores en Apple Silicon (no garantiza recall, sí garantiza que no rompe).
- `uv run pytest packages/jw-rag/tests/visual/` pasa en CI público con 0 GPU (usa fakes).
- `jw rag ingest-visual --path X.jwpub` produce store visual funcional en <60s para JWPUB de ~50 páginas en GPU.
- `VisualStoreMismatchError` se lanza claramente cuando se carga con embedder distinto.
- Documentado en `docs/guias/visual-rag.md` con flujo end-to-end + diagrama.

## Cómo verificar al cerrar

```bash
# 1. CI público (sin GPU)
uv sync --all-packages
uv run pytest packages/jw-rag/tests/visual/   # usa FakeColPaliEmbedder

# 2. Linux con NVIDIA (manual)
uv sync --all-packages --extra visual
JW_VISUAL_ENABLED=1 uv run jw rag ingest-visual --path examples/sample.jwpub
JW_VISUAL_ENABLED=1 uv run jw rag search "viajes de Pablo" --visual

# 3. Apple Silicon (manual, experimental)
uv sync --all-packages --extra visual-mlx
JW_VISUAL_ENABLED=1 JW_VISUAL_TARGET=mlx uv run jw rag ingest-visual --path examples/sample.epub

# 4. Eval golden cases visuales (requiere GPU)
JW_VISUAL_ENABLED=1 uv run jw eval --layer 1 --filter agent=research_topic,visual=true
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-37-colpali-visual-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold `packages/jw-rag/src/jw_rag/visual/` + extras `[visual]` y `[visual-mlx]` en `pyproject.toml`.
2. `models.py` (VisualChunk, MultiVectorHit, IngestResult, VisualStoreMismatchError, ConfigError) con tests.
3. `fakes.py` (FakeColPaliEmbedder determinista + FakeRasterizer) con tests — base para todo lo demás.
4. `visual_store.py` (add/search/save/load + MaxSim) con tests usando fakes.
5. `page_rasterizer.py` (PDF vía pdf2image; EPUB vía Playwright; JWPUB vía render XHTML decrypted) con fixtures sintéticos.
6. `colpali.py` (ColPaliEmbedder, ColQwen2Embedder, factory) — imports perezosos, `is_available()` con `pytest.skip` si no hay GPU en CI.
7. `ingest.py` (ingest_jwpub_visual, ingest_epub_visual, ingest_pdf_visual) con tests usando fakes.
8. `hybrid.py` (hybrid_search_with_visual = RRF de bm25+text+visual) con tests.
9. CLI: `jw rag ingest-visual` y `jw rag search --visual` en `jw-cli`.
10. MCP: `visual_search(query, top_k, language)` y `ingest_publication_visual(path)` en `jw-mcp` con check temprano de `is_available()`.
11. 5 golden cases L1 figura-pesados en `jw-eval/fixtures/golden_qa/l1/visual_*.yaml` + integración con el suite (Fase 22).
12. Guía `docs/guias/visual-rag.md` con diagrama de pipeline + benchmarks + troubleshooting GPU + ejemplos de queries que se benefician del visual.
13. Audit 1:1 en `docs/VISION_AUDIT.md` describiendo trade-off espacio/calidad/hardware.

Cada paso con su PR + tests + sin regresiones en los 1649 tests existentes ni en los stores textuales de Fase 33.
