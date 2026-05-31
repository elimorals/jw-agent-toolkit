# Fase 33 — `embed-rerank`: núcleo RAG al SOTA

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (núcleo)
> **Depende de**: Fases 6 (RAG), 9 (throttle/cache), 22 (eval — para medir el delta)
> **Documento padre**: [`2026-05-31-fases-33-38-overview.md`](2026-05-31-fases-33-38-overview.md)

## Motivación

El núcleo de recuperación del toolkit corre hoy con un atajo: `FakeEmbedder` (hash determinístico, 64 dim, semánticamente vacío) cargando los embeddings y BM25 cargando todo el peso real de la relevancia. La hibridación con RRF (`hybrid_search` en `packages/jw-rag/src/jw_rag/store.py`) reduce el daño pero no compensa: una pregunta como *"¿Es la Trinidad bíblica?"* no encuentra documentos cuyo único matching sea **doctrinal** (no léxico).

Además, no hay paso de **reranking** después del fusion. RRF deja arriba 10 candidatos por solapamiento de listas; lo que el usuario quiere es que **el más doctrinalmente relevante** quede primero. Un cross-encoder reranker resuelve esto en ~150 ms por consulta sobre 50 candidatos.

Esta fase reemplaza el placeholder por una **familia real de providers** de embeddings y reranking, manteniendo `FakeEmbedder` solo para tests y garantizando que:

1. Default funciona local en Apple Silicon (MLX) y en Linux GPU (NVIDIA).
2. APIs son opt-in vía env (cuando el usuario las prefiere).
3. CI público sigue sin red.
4. Los 1649 tests existentes no se rompen.

## Objetivos (en orden de prioridad)

1. **Embeddings reales multilingües (en/es/pt)** disponibles por defecto cuando hay hardware, con auto-detect inteligente.
2. **Cross-encoder reranker** activo en `hybrid_search` cuando hay hardware o API key.
3. **Patrón Provider Protocol con triple-target** (`api | mlx | nvidia | cpu`) reutilizable por las Fases 34-38.
4. **Sin breaking changes** al contrato externo de `VectorStore.hybrid_search` (parámetros nuevos son opt-in con defaults compatibles).
5. **NDCG@10 ≥ +30%** sobre baseline `FakeEmbedder + BM25` en las 5 golden queries de Fase 22 L3.

## No-objetivos (boundaries vinculantes)

- **No** se sustituye BM25. Sigue siendo parte del RRF — es ortogonal y barato.
- **No** se rediseña `Chunk` ni el formato on-disk de `VectorStore`. Vectors siguen siendo `(N, dim) float32` en `vectors.npy`. La migración entre dims se hace re-ingestando, no convirtiendo en sitio.
- **No** se añade cuantización ni binarización de embeddings en esta fase. Se trackea para una Fase de optimización futura.
- **No** se exponen los embeddings sparse/colbert de BGE-M3 (solo dense). Multi-vector visual va en Fase 37 (`colpali-visual`).
- **No** se mete telemetría nueva. La existente (`jw_core.telemetry`) basta para registrar latencia.

## Arquitectura

Reorganización mínima dentro de `packages/jw-rag/src/jw_rag/`:

```
packages/jw-rag/src/jw_rag/
├── embed.py                        # Embedder Protocol + FakeEmbedder (sin cambios)
├── embed_providers/                # NUEVO
│   ├── __init__.py                 # re-exports + EmbedProvider Protocol
│   ├── factory.py                  # get_default_embedder()
│   ├── bge_m3.py                   # local mlx|nvidia, sentence-transformers
│   ├── multilingual_e5.py          # local mlx|nvidia, ligero
│   ├── jina.py                     # API httpx contra Jina v3
│   ├── cohere.py                   # API cohere SDK lazy
│   ├── voyage.py                   # API voyageai SDK lazy
│   ├── ollama.py                   # local httpx → /api/embeddings
│   └── fakes.py                    # FakeBGEM3 / FakeCohere / FakeJina / ...
├── rerank.py                       # NUEVO — Reranker Protocol + factory
├── rerank_providers/               # NUEVO
│   ├── __init__.py
│   ├── bge_v2_m3.py                # local CrossEncoder
│   ├── cohere_rerank.py            # API
│   ├── jina_rerank.py              # API
│   └── fakes.py                    # FakeBGEReranker / FakeCohereReranker
└── store.py                        # extendido — hybrid_search(rerank=True, candidate_pool=50)
```

### Reglas duras de diseño

1. **Cero red en import time**. Cada provider hace `is_available()` antes de tocar el modelo o la API.
2. **Lazy SDK loading**. Los SDKs externos (`cohere`, `voyageai`, `sentence-transformers`) viven detrás de extras opcionales y se importan dentro de la primera llamada, nunca en el módulo top-level.
3. **Cada provider real tiene fake hermano** en `fakes.py`. Los tests usan los fakes; los fakes son determinísticos.
4. **Cosine simil queda well-defined**: todos los providers devuelven vectores **L2-normalizados**. El `Embedder` Protocol existente ya lo exige.
5. **dim variable**: la `dim` la decide cada provider (BGE-M3 = 1024, E5-large = 1024, Jina-v3 = 1024, Cohere-v3 = 1024, Voyage-multilingual = 1024, Ollama nomic-embed-text = 768). El `VectorStore.load()` ya valida dim mismatch y refuse cross-loading — usuarios reingestan al cambiar provider.

### Provider Protocol (canonical)

Tanto embeddings como reranker siguen el mismo shape:

```python
from typing import Literal, Protocol, runtime_checkable

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class EmbedProvider(Protocol):
    name: str           # "bge-m3" | "cohere" | ...
    target: Target
    dim: int            # output dim de cada vector

    def is_available(self) -> bool: ...
    def embed(self, texts: list[str]) -> np.ndarray: ...  # (N, dim) float32 L2-normalized


@runtime_checkable
class Reranker(Protocol):
    name: str
    target: Target

    def is_available(self) -> bool: ...
    def rerank(self, query: str, candidates: list[str]) -> list[float]: ...
    # returns one score per candidate, higher = more relevant; not necessarily probabilities
```

**Por qué `runtime_checkable`**: permite `isinstance(obj, EmbedProvider)` en factory tests sin metaclasses.

**Por qué `is_available()` y no excepciones lazy**: la factory necesita preguntar sin pagar el coste de importar SDK pesados. La convención es:

- `is_available()` retorna `True` solo si:
  - Para `target=api`: la API key del provider está en env (`COHERE_API_KEY`, `VOYAGE_API_KEY`, `JINA_API_KEY`).
  - Para `target=mlx`: corriendo en Apple Silicon (`platform.processor() == "arm"`) y el SDK está instalado.
  - Para `target=nvidia`: `torch.cuda.is_available()` True y el SDK está instalado.
  - Para `target=cpu`: el SDK está instalado.

### Inventario de providers

#### Embeddings

| Provider | Modelo | Target | Auth | dim | Notas |
|---|---|---|---|---|---|
| `BGEM3Provider` | BAAI/bge-m3 | mlx, nvidia, cpu | — | 1024 | Apache 2.0. Dense+sparse+colbert; aquí solo dense. ~2.3 GB. |
| `MultilingualE5Provider` | intfloat/multilingual-e5-large | mlx, nvidia, cpu | — | 1024 | MIT. ~2.2 GB. Más rápido que BGE-M3, ligeramente menor calidad. |
| `JinaEmbeddingsV3Provider` | jina-embeddings-v3 | api | `JINA_API_KEY` | 1024 | Fuerte multilingüe. https://api.jina.ai/v1/embeddings. |
| `CohereEmbedV3Provider` | embed-multilingual-v3.0 | api | `COHERE_API_KEY` | 1024 | SDK `cohere>=5.5`. |
| `VoyageMultilingualProvider` | voyage-multilingual-2 | api | `VOYAGE_API_KEY` | 1024 | SDK `voyageai>=0.2`. |
| `OllamaEmbedProvider` | nomic-embed-text | local (Ollama HTTP) | — | 768 | Requiere `ollama serve` corriendo + `ollama pull nomic-embed-text`. Httpx puro, sin SDK. |
| `FakeEmbedder` | — | cpu | — | 64 | Existente. Sigue siendo el default cuando `JW_EMBED_PROVIDER=fake` o nada matchea. |

#### Rerankers

| Provider | Modelo | Target | Auth | Notas |
|---|---|---|---|---|
| `BGERerankerV2M3Provider` | BAAI/bge-reranker-v2-m3 | mlx, nvidia, cpu | — | Apache 2.0. CrossEncoder. ~568 MB. ~150 ms / 32 candidatos en M-series. |
| `CohereRerankV35Provider` | rerank-multilingual-v3.5 | api | `COHERE_API_KEY` | SDK `cohere`. Súper rápido y barato. |
| `JinaRerankerV2Provider` | jina-reranker-v2-base-multilingual | api | `JINA_API_KEY` | Httpx puro. |
| `NoOpReranker` | passthrough | cpu | — | Devuelve scores `[1.0, 1.0, ...]` — opt-out elegante cuando nada disponible. |

### Factory + auto-detect

```python
# packages/jw-rag/src/jw_rag/embed_providers/factory.py

PROVIDER_ORDER: list[Target] = ["api", "mlx", "nvidia", "cpu"]
# Configurable vía env JW_PROVIDER_ORDER="mlx,nvidia,api,cpu"

ENV_EMBED = "JW_EMBED_PROVIDER"     # "bge-m3" | "cohere" | "jina" | ...
ENV_RERANK = "JW_RERANK_PROVIDER"


def get_default_embedder() -> EmbedProvider:
    """Resolution order:
      1. If JW_EMBED_PROVIDER is set, instantiate exactly that one.
         Raise ValueError if unknown name.
      2. Otherwise scan PROVIDER_ORDER × PROVIDERS in priority order;
         pick first that .is_available().
      3. Fall back to FakeEmbedder with a logged warning.
    """
```

Análoga para `get_default_reranker()` en `jw_rag.rerank`.

**Por qué APIs primero por defecto**: cuando el usuario ha configurado una key, es porque quiere usarla — es más predecible que un local que puede no estar cargado/calentado. MLX antes que NVIDIA porque el creador del proyecto está en Apple Silicon. CPU último.

### Integración con `VectorStore`

Cambio en `store.py` — `hybrid_search` gana dos parámetros (defaults compatibles):

```python
def hybrid_search(
    self,
    query: str,
    top_k: int = 10,
    *,
    candidate_pool: int = 50,
    rrf_k: int = 60,
    rerank: bool = True,
    reranker: Reranker | None = None,  # None → factory.get_default_reranker()
) -> list[SearchHit]:
```

**Flujo nuevo**:

1. `vector_search(query, top_k=candidate_pool)` → 50 candidatos vector.
2. `bm25_search(query, top_k=candidate_pool)` → 50 candidatos BM25.
3. RRF como hoy → top `candidate_pool` fused.
4. Si `rerank=True` y `(reranker o factory).is_available()`:
   - `scores = reranker.rerank(query, [hit.chunk.text for hit in fused])`
   - Re-ordena por `scores` desc.
   - `source = "hybrid+rerank"` en el SearchHit.
5. Devuelve top `top_k`.

**Backwards compatibility**: si llamas `hybrid_search(query)` igual que antes, el comportamiento solo cambia si hay reranker disponible. En CI offline sin API keys y sin GPU, `factory.get_default_reranker()` retorna `NoOpReranker` y el output es **bit-idéntico** al de hoy.

**Test crítico**: `test_hybrid_search_backwards_compat` con `FakeEmbedder + NoOpReranker` debe producir el mismo top-10 que antes.

### Integración con CLI / MCP

- **CLI** (`jw rag search`): se añade flag `--no-rerank` y `--provider <name>`. Defaults idénticos al actual.
- **MCP** (`semantic_search` tool): añade param opcional `rerank: bool = True`.

No es necesario modificar agentes — todos pasan por `hybrid_search`, así que se benefician transparentemente.

### Integración con CI

- `.github/workflows/ci.yml`:
  - El job actual `test` sigue funcionando: `FakeEmbedder + NoOpReranker` (sin extras instalados, sin env keys).
  - Nuevo job opcional `test-rag-embeddings` con `pip install -e packages/jw-rag[embeddings-local]` que corre tests bajo `pytest -m embeddings_local` (marker nuevo). NO bloqueante en PRs comunes.

### Integración con `jw-eval` (Fase 22)

`jw-eval` ya usa `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` para L3 — eso queda intacto. Pero **se añade un benchmark dedicado en `packages/jw-eval/fixtures/golden_qa/l3_retrieval/`**: 5 golden queries con `expected_doc_id` esperado. Se mide NDCG@10 con FakeEmbedder/BM25 baseline vs cada provider real. Reporte sale en `eval_nightly` (no bloqueante).

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Cambiar dim rompe stores existentes en disco | `VectorStore.load()` ya rechaza dim mismatch. Guía `docs/guias/embeddings-y-rerank.md` documenta el flujo de re-ingest. CLI da error claro: "rebuild: jw rag rebuild --provider <new>". |
| 2 | API keys filtradas en logs | `safe_repr` en cada provider truncates keys a `cohere-***`. Probado en tests. |
| 3 | Costes de API sin control | `cost_estimate(texts)` en el Protocol opcional; CLI imprime estimación antes de ingest >1k docs. |
| 4 | sentence-transformers tarda 5-15s al importar | Lazy import dentro de `is_available()` solo cuando el provider gana el round; NUNCA en factory probing pasivo. Probe = `importlib.util.find_spec`. |
| 5 | Reranker se cuelga la query | Wrapping con `asyncio.wait_for(..., timeout=10)` en el tool MCP. Fallback a no-rerank con warning. |
| 6 | MLX backend cambia API entre versiones | Pin `mlx>=0.18` y test smoke en CI Apple si runner disponible (otherwise opt-in marker). |
| 7 | Ollama no instalado pero env apunta a él | Probe HTTP `GET http://localhost:11434/api/tags` con timeout 0.5s en `is_available()`. |
| 8 | Tests vuelven flakey por descargas | Tests reales contra modelos viven en `tests/test_embed_providers_local.py` con `@pytest.mark.embeddings_local`, no se ejecutan por default. |

## Métricas de éxito

- `uv sync --all-packages && uv run pytest packages/jw-rag/tests -v` sigue **verde sin red**.
- `JW_EMBED_PROVIDER=bge-m3 uv run jw rag rebuild --corpus tests/fixtures/sample_corpus` completa en <2min en M-series.
- `JW_RERANK_PROVIDER=bge-v2-m3 uv run jw rag search "trinidad" --top-k 10` retorna findings con `source="hybrid+rerank"`.
- NDCG@10 sobre 5 queries Fase 22 sube ≥30% vs baseline FakeEmbedder + NoOpReranker (medido en `eval_nightly`).
- Cobertura de tests del nuevo módulo `embed_providers/` y `rerank_providers/` ≥90% líneas, ≥85% branches.
- 0 nuevas violaciones de ruff lint + 0 de format.

## Cómo verificar al cerrar

```bash
# 1. Install completo
uv sync --all-packages

# 2. Tests offline (todos los providers fake)
uv run pytest packages/jw-rag/tests -v

# 3. Tests con extras locales (sentence-transformers)
uv pip install -e packages/jw-rag[embeddings-local]
uv run pytest packages/jw-rag/tests -m embeddings_local -v

# 4. Smoke con BGE-M3 real (Apple Silicon)
JW_EMBED_PROVIDER=bge-m3 JW_RERANK_PROVIDER=bge-v2-m3 \
    uv run jw rag search "¿Es la Trinidad bíblica?" --top-k 5

# 5. Smoke con APIs (requiere keys)
JW_EMBED_PROVIDER=cohere JW_RERANK_PROVIDER=cohere COHERE_API_KEY=... \
    uv run jw rag search "verse on love"

# 6. Eval delta vs baseline
JW_EMBED_PROVIDER=bge-m3 JW_RERANK_PROVIDER=bge-v2-m3 \
    uv run jw eval --layer 3 --filter topic=retrieval --report json --out delta-bge.json
diff baseline.json delta-bge.json
```

## Plan de implementación (alto nivel)

Documento hijo: [`2026-05-31-fase-33-embed-rerank-plan.md`](../plans/2026-05-31-fase-33-embed-rerank-plan.md).

Pasos cronológicos (TDD):

1. Pyproject extras + scaffold `embed_providers/` y `rerank_providers/` con `__init__.py`.
2. `EmbedProvider` Protocol + `Target` Literal.
3. `FakeBGEM3` / `FakeJina` / `FakeCohere` / `FakeVoyage` / `FakeOllama` (fakes hermanos primero — TDD).
4. `factory.get_default_embedder()` con auto-detect y env override.
5. `BGEM3Provider` real (lazy sentence-transformers, MLX detection).
6. `MultilingualE5Provider`.
7. `JinaEmbeddingsV3Provider`.
8. `CohereEmbedV3Provider`.
9. `VoyageMultilingualProvider`.
10. `OllamaEmbedProvider`.
11. `Reranker` Protocol + `NoOpReranker` + `FakeBGEReranker` / `FakeCohereReranker` / `FakeJinaReranker`.
12. `BGERerankerV2M3Provider` real.
13. `CohereRerankV35Provider`.
14. `JinaRerankerV2Provider`.
15. Integración `VectorStore.hybrid_search(rerank=, reranker=)` + backwards-compat test.
16. CLI flag `--no-rerank` y `--provider`; MCP tool param `rerank`.
17. Guía `docs/guias/embeddings-y-rerank.md` + audit 1:1 en `docs/VISION_AUDIT.md` + ROADMAP.

Cada paso con su PR + tests + sin regresiones en los 1649 tests existentes.

## Pendientes explícitos (post-Fase 33)

- **Cuantización binaria** de vectores (BGE-M3 soporta `precision="binary"`) — Fase de optimización futura.
- **Embeddings sparse/colbert** de BGE-M3 — requiere extender `VectorStore` a multi-vector. Va junto con Fase 37 (`colpali-visual`) que comparte ese requisito.
- **Pretrained domain-adaptation** sobre corpus JW — territorio de `jw-finetune`.
- **Tier-2 caches** (memoización de embeddings de query frecuentes) — barato pero ortogonal; espera a tener telemetría de uso real.
- **OpenAI text-embedding-3-large** como provider — fácil de añadir si demand justifica.
