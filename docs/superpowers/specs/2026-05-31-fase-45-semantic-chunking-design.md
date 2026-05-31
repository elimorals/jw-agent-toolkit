# Fase 45 — `semantic-chunking`: chunking por unidad de pensamiento

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (frontera técnica)
> **Depende de**: ninguna fase. Reusa Fase 22 (`jw-eval` L3) para medir.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

`jw_rag.chunker.chunk_paragraphs` —el chunker actual— ya hace lo correcto en el 80 % de los casos: respeta la unidad mínima de párrafo (`<p data-pid="N">`), fusiona párrafos cortos hasta llegar a un mínimo de caracteres y corta los muy largos por límite de oración. Esto evita el peor pecado del chunking ingenuo: trocear a `N` tokens fijos sin atender la estructura.

El 20 % restante, sin embargo, es exactamente el caso doctrinal donde más nos duele:

1. **Argumentos que abarcan dos o tres párrafos consecutivos**. En las Atalayas y libros doctrinales es muy común el patrón "Premisa. (¶17) Sin embargo, … (¶18) Por lo tanto, … (¶19)". El recuperador devuelve uno solo de los tres y se pierde la cadena lógica.
2. **Párrafos largos** (> `max_chars`) hoy se cortan en frontera de oración. Eso parte el argumento por la mitad cuando la oración no es el límite semántico.
3. **Párrafos cortos sueltos** (titulares, preguntas retóricas) se fusionan ciegamente con el siguiente, mezclando dos temas.

Las consecuencias son medibles en Fase 22 L3: queries doctrinales donde el `golden_answer` requiere la cadena completa "premisa + matiz + conclusión" caen al filtro de embeddings (`cosine ≥ 0.78`) porque el `agent_answer` cita un fragmento aislado.

Fase 45 cierra ese hueco con una mejora **opt-in** sin tocar el path por defecto.

## Objetivos (en orden de prioridad)

1. **Mejorar recall doctrinal** ≥ 10 % NDCG@10 sobre el subset de 10 queries doctrinales del corpus de Fase 22 (ver § Métrica de éxito).
2. **Mantener backward-compat absoluto**: `chunk_paragraphs` sigue siendo la API pública estable de `jw_rag.chunker`. Nada del código actual cambia su comportamiento si no se opt-in.
3. **Cero red en tests** y cero LLM en el path crítico. La capa LLM es build-time only y cacheada.

## No-objetivos (boundaries vinculantes)

- **No** re-chunkear lo ya indexado automáticamente. Cualquier mejora se aplica a `ingest_*` futuros; el dueño de un índice existente decide cuándo re-ingestar.
- **No** entrenar nuestro propio modelo de segmentación. El `LLMChunker` usa los providers ya integrados (Claude, OpenAI, Ollama).
- **No** tocar el chunker de Biblia. Para versículos la unidad sigue siendo el versículo. Fase 5/M11 ya cubre eso.
- **No** producir contenido nuevo distribuible. Política #6 (jw-gen) sigue vigente — el `LLMChunker` solo segmenta, nunca reescribe.

## Arquitectura

Nuevo subpaquete `packages/jw-rag/src/jw_rag/chunkers/`. El módulo legacy `jw_rag.chunker` queda como façade re-exportando `Chunk` y `chunk_paragraphs` para no romper imports existentes.

```
packages/jw-rag/src/jw_rag/
├── chunker.py                       # façade — re-export desde chunkers/
└── chunkers/
    ├── __init__.py                  # public API: get_chunker(name), Chunk
    ├── protocol.py                  # Chunker Protocol
    ├── paragraph_chunker.py         # chunk_paragraphs() — sin cambios funcionales
    ├── semantic_chunker.py          # heurística-first con marcadores
    ├── llm_chunker.py               # opt-in deep mode con cache
    ├── markers.py                   # carga de continuation_markers.json
    └── fakes.py                     # FakeSemanticChunker para tests
```

Y los datos multilingües:

```
packages/jw-core/src/jw_core/data/continuation_markers.json
```

### `Chunker` Protocol

```python
# chunkers/protocol.py
from typing import Protocol, Any
from jw_rag.chunker import Chunk

class Chunker(Protocol):
    name: str  # "paragraph" | "semantic" | "llm"

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]: ...
```

`paragraph_chunker.chunk_paragraphs` ya satisface ese contrato vía wrapper trivial.

### `SemanticChunker` — la capa heurística (default opt-in)

Pipeline en dos pasos sobre la lista de párrafos:

1. **Continuation merge** — si el párrafo `N` empieza con un marcador del set `continuation_markers[lang]`, se anexa al chunk del párrafo `N-1`, no abre uno nuevo, aun cuando el chunk previo ya superó `max_chars` (con tolerancia configurable, default +30 %).
2. **Closure split** — si el párrafo `N` contiene un marcador de cierre argumentativo (`Por lo tanto`, `En conclusión`, `Así que`, `Therefore`, `In conclusion`, `Portanto`, `Em conclusão`), el chunk se cierra **inmediatamente después** de ese párrafo aunque queden caracteres por debajo del mínimo.

Ambos pasos consultan `markers.py`, que detecta el idioma por hint del `metadata["language"]` o por heurística rápida (palabras-funcionales). Si no se reconoce el idioma → fallback a paragraph_chunker (degrada con gracia).

```json
// jw_core/data/continuation_markers.json
{
  "es": {
    "continuation": ["Sin embargo", "Por otro lado", "Además", "Pero",
                     "No obstante", "Asimismo", "Es más", "También"],
    "closure":      ["Por lo tanto", "En conclusión", "Así que",
                     "En resumen", "De manera que"]
  },
  "en": {
    "continuation": ["However", "On the other hand", "Moreover",
                     "But", "Nevertheless", "Furthermore", "Also"],
    "closure":      ["Therefore", "In conclusion", "So",
                     "In summary", "Hence", "Thus"]
  },
  "pt": {
    "continuation": ["No entanto", "Por outro lado", "Além disso",
                     "Mas", "Contudo", "Ademais", "Também"],
    "closure":      ["Portanto", "Em conclusão", "Assim",
                     "Em resumo", "Logo"]
  }
}
```

Los marcadores se matchean *case-sensitive en el inicio de párrafo* (acento incluido). Esto evita falsos positivos dentro de la prosa.

### `LLMChunker` — la capa profunda (opt-in build-time)

Cuando `JW_CHUNKER=llm`, después del heurístico se aplica una pasada LLM que recibe los chunks ya formados y devuelve recomendaciones de "splittear este chunk aquí" o "mergear estos dos". Nunca reescribe el texto; solo emite índices.

**Prompt**: el output es JSON estricto:
```json
{"actions": [
  {"op": "split", "chunk_index": 4, "after_paragraph": 2},
  {"op": "merge", "chunk_indices": [7, 8]}
]}
```

**Provider**: usa el `GenerationProvider` resuelto vía `jw_gen.providers.resolve()` (Claude / OpenAI / Ollama / MLX). Default seguro: Ollama local con `llama3.1:8b`.

**Cache**: cada llamada al LLM se cachea por `sha256(source_id + paragraphs_joined + provider_id + prompt_version)` en:
```
~/.jw-agent-toolkit/chunk-cache/{hash[:2]}/{hash}.json
```

Esto convierte la re-ingesta determinista mientras la cache exista, y vuelve el chunker LLM apto para CI offline si se le pre-calienta la cache (commiteada como fixture cuando sea necesario para tests).

### Selección del chunker

Tres canales, en orden de precedencia:

1. **Constructor arg** de `VectorStore.ingest_*` (cuando lo añadamos en F40 follow-up) o directamente `get_chunker("semantic")`.
2. **Env var** `JW_CHUNKER` con valores `paragraph` (default) / `semantic` / `llm`.
3. **Default** = `paragraph` (estado actual, sin cambios).

```python
# chunkers/__init__.py
def get_chunker(name: str | None = None, **kwargs) -> Chunker:
    name = name or os.environ.get("JW_CHUNKER", "paragraph")
    match name:
        case "paragraph": return ParagraphChunker(**kwargs)
        case "semantic":  return SemanticChunker(**kwargs)
        case "llm":       return LLMChunker(**kwargs)
        case _: raise ValueError(f"Unknown chunker: {name}")
```

`ingest_article` / `ingest_bible_chapter` / `ingest_epub` / `ingest_jwpub` mantienen su firma; internamente se reescriben para llamar a `get_chunker()` en vez de `chunk_paragraphs` directo. El comportamiento por defecto es **idéntico**.

## Modelos y tipos

`Chunk` se extiende sin romper compat:

```python
@dataclass
class Chunk:
    id: str
    text: str
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata adicional que los nuevos chunkers pueblan:
    #   - "chunker": "paragraph" | "semantic" | "llm"
    #   - "merge_reason": "continuation_marker" | "short_paragraph" | None
    #   - "closure_marker": str | None
    #   - "para_ids": list[str]  # los data-pid originales que componen el chunk
```

El campo `para_ids` es clave: permite a Fase 40 (`content-provenance`) recuperar el rango `data-pid` exacto y a Fase 39 (`nli-runtime`) usar el texto exacto del passage.

## Integración con `jw-eval` (Fase 22)

La métrica oficial usa el harness de Fase 22 L3 con dos extensiones, no un nuevo sistema:

1. **Marcador `metric=ndcg10`** en los Golden Cases L3. Cuando una case lo trae, el reporte calcula NDCG@10 además del cosine. El cálculo es Hit/MRR/NDCG estándar sobre el ranking devuelto por `VectorStore.search(query, k=10)` comparado contra `expected_citations`.
2. **Variantes de chunker en el suite**: se introduce un parámetro `chunker_variant` en `Suite.run()` que re-ingesta el corpus de fixtures con cada chunker antes de evaluar. El reporte queda agrupado:

```
suite_ndcg_doctrinal.json
{
  "paragraph": {"ndcg10_mean": 0.61, "per_case": {...}},
  "semantic":  {"ndcg10_mean": 0.69, "per_case": {...}},
  "llm":       {"ndcg10_mean": 0.71, "per_case": {...}},
  "delta_semantic_vs_paragraph": +13.1 %,
  "delta_llm_vs_paragraph":      +16.4 %
}
```

### ¿Nuevos golden cases o suite benchmark separada?

**Decisión: ambas, separadas**:

- Los **10 cases L3 doctrinales** que ya viven en `packages/jw-eval/fixtures/golden_qa/l3/` (Trinidad, alma, infierno, identidad de Cristo, nombre de Dios, esperanza terrestre, + 4 que se añadirán como semilla F45) se etiquetan `metric: ndcg10` y se reutilizan. No duplicamos casos.
- Para evitar contaminar el reporte L3 *de calidad de respuesta* con métricas de *recall de chunker*, las corridas de chunker viven en un nuevo subcomando:

```bash
jw eval chunker-bench \
  --variants paragraph,semantic,llm \
  --queries packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml \
  --report md --out bench.md
```

`doctrinal_queries.yaml` declara 10 queries con sus `expected_citations` (las URLs son las mismas de los cases L3, deduplicadas). Cada query expande al ranking esperado top-K que se usa para NDCG.

`jw eval chunker-bench` es un subcomando bajo `jw eval` para reusar todo el plumbing (loader, reporter, embeddings) pero **no** corre en CI bloqueante. Es nightly + on-demand.

### Reuso del judge de embeddings

`SemanticChunker` no necesita embeddings en su path. El bench usa el mismo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` que la Fase 22 ya carga (extra `[local-embeddings]`). Cero dependencias nuevas.

## Reglas duras de diseño

1. `jw_rag.chunkers` **no** importa nada que haga red en import time. `LLMChunker` lazy-importa providers.
2. La cache es del usuario (no del repo) excepto fixtures explícitas. No commiteamos cache real al repo.
3. Los marcadores son **datos** (JSON), no código. Comunidad puede contribuir traducciones (sign langs y otras Romance) sin tocar Python.
4. `Chunker` Protocol no es abstracto — cualquier dataclass con `chunk(...)` lo satisface (PEP 544 structural typing).
5. Cada chunker tiene su `FakeXxxChunker` hermano en `fakes.py` con verdict determinista.

## Tests (sin red, en/es/pt)

```
packages/jw-rag/tests/chunkers/
├── test_paragraph_chunker_backcompat.py  # mismo output que chunk_paragraphs() pre-F45
├── test_semantic_chunker_continuation_es.py
├── test_semantic_chunker_continuation_en.py
├── test_semantic_chunker_continuation_pt.py
├── test_semantic_chunker_closure.py
├── test_llm_chunker_with_fake_provider.py
├── test_llm_chunker_cache.py             # cache hit no llama al provider
├── test_get_chunker_env_var.py
└── fixtures/
    ├── article_with_continuation_es.txt
    ├── article_with_continuation_en.txt
    ├── article_with_continuation_pt.txt
    └── chunk_cache_sample/               # cache pre-calentada para CI
```

CI público corre todos. El bench NDCG corre nightly o on-demand:

```yaml
chunker-bench-nightly:
  if: github.event_name == 'schedule'
  schedule: "0 5 * * *"
  steps:
    - run: uv run jw eval chunker-bench --variants paragraph,semantic --report md
    - uses: actions/upload-artifact@v4
```

`llm` variant no se corre en CI público (necesitaría Ollama o API key) — solo en local del owner para el reporte semanal.

## Integración con el resto del toolkit

### `jw-rag` (productor)

`ingest_article`, `ingest_bible_chapter`, `ingest_epub`, `ingest_jwpub`, `ingest_jw_library_backup` todos enrutados vía `get_chunker()`. Firma estable.

### `jw-cli`

Nuevo flag global `--chunker` y comando dedicado:

```bash
jw rag ingest article <url> --chunker semantic
jw eval chunker-bench --variants paragraph,semantic
```

### `jw-mcp`

Nueva tool `set_chunker(name: str) -> dict` que persiste la elección en la sesión MCP. Tools de ingesta existentes reciben `chunker: str | None = None` opcional.

### `jw-eval`

Subcomando `chunker-bench` + reusa `judges.embeddings`.

## Métricas de éxito de la fase

- ✅ `JW_CHUNKER=paragraph` produce **bit-for-bit el mismo output** que el chunker pre-F45 (asegurado por `test_paragraph_chunker_backcompat.py`).
- ✅ `JW_CHUNKER=semantic` mejora NDCG@10 ≥ **10 %** sobre las 10 doctrinal queries del bench, con embedder local, sin red.
- ✅ `JW_CHUNKER=llm` mejora NDCG@10 ≥ **15 %** (techo aspirational; aceptamos ≥ 12 % si el delta vs `semantic` es < 3 % consistente).
- ✅ `jw eval chunker-bench` corre en < 90 s offline para `paragraph` + `semantic`.
- ✅ Cache del LLMChunker hit > 95 % en re-runs (test con FakeProvider + clock).
- ✅ Soporte verificado en/es/pt vía fixtures dedicadas.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Marcadores de continuación causan chunks gigantes en artículos con muchos `Sin embargo` consecutivos | Tolerancia +30 % sobre `max_chars`; tras 2 merges consecutivos se fuerza flush |
| 2 | LLMChunker no determinista entre runs rompe el bench | Temperature 0 + seed fijo + cache de outputs commiteada en fixtures |
| 3 | Sólo 10 queries → varianza alta en NDCG | Reportamos también CI95 vía bootstrap; el ≥ 10 % debe sostenerse en el LB del intervalo |
| 4 | Detección de idioma falla en mixed-language paragraphs | Fallback a paragraph_chunker; loguea `mixed_language=true` en metadata |
| 5 | Re-ingesta selectiva confunde a usuarios con índices viejos | `chunker_version` se persiste en metadata del chunk; `VectorStore.stats()` lo reporta |
| 6 | Embedder multilingüe tiene sesgo hacia EN — falso positivo de mejora en ES | Bench segrega NDCG por idioma; el ≥ 10 % se exige en cada idioma por separado |
| 7 | `closure_marker` cierra chunks demasiado pronto si el párrafo siguiente es la conclusión real | Closure detecta solo si está en posición sentencial inicial y el chunk ya superó `min_chars` |
| 8 | Cache crece sin límite | Política LRU por mtime; cap 500 MB con eviction en `__init__` |

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages --extra local-embeddings

# 2. Backwards-compat (debe pasar igual que antes)
.venv/bin/python -m pytest packages/jw-rag/tests/

# 3. Nuevos tests de chunkers
.venv/bin/python -m pytest packages/jw-rag/tests/chunkers/

# 4. Bench NDCG paragraph vs semantic (sin red)
JW_EVAL_LLM=none uv run jw eval chunker-bench \
  --variants paragraph,semantic --report md --out bench.md

# 5. Bench con LLM (requiere Ollama corriendo local)
JW_CHUNKER=llm JW_GEN_PROVIDER=ollama uv run jw eval chunker-bench \
  --variants paragraph,semantic,llm --report md
```

## Pendientes explícitos (post-Fase 45)

- Auto-re-ingest de índices existentes con `jw rag rechunk --from paragraph --to semantic` → fase futura cuando haya señal de adopción.
- Chunker específico para versículos bíblicos (chunk = perícopa) → ROADMAP Bible-aware chunking, no F45.
- LLMChunker que también reescriba texto (resumir, expandir) → **explícitamente prohibido** por política #6.
- Web UI para inspeccionar diff de chunkers sobre un artículo dado → fase futura, fuera del scope F45.

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-45-semantic-chunking-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Mover `chunk_paragraphs` a `chunkers/paragraph_chunker.py`; dejar façade en `chunker.py`. Tests de backcompat verdes.
2. Añadir `continuation_markers.json` en `jw-core/data/` + loader `markers.py`. Tests por idioma.
3. Implementar `SemanticChunker` con continuation merge + closure split. Fixtures en/es/pt.
4. Implementar `LLMChunker` + cache + `FakeLLMProvider` para tests deterministas.
5. Router `get_chunker()` + env var + flag CLI.
6. Subcomando `jw eval chunker-bench` reusando harness L3.
7. Etiquetar las 10 cases doctrinales con `metric: ndcg10`; añadir `doctrinal_queries.yaml`.
8. Workflow CI nightly + guía en `docs/guias/semantic-chunking.md` + audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones en los ~1984 tests existentes.
