# Semantic chunking (Fase 45)

> Selección y benchmark de chunkers en el jw-agent-toolkit.

## TL;DR

```bash
# Usa el chunker heurístico para un ingest puntual.
JW_CHUNKER=semantic uv run jw rag ingest article <url>

# Benchmark NDCG@10 local (paragraph vs semantic).
uv run jw chunker-bench --variants paragraph,semantic --report md --out bench.md
```

## Qué cambió en Fase 45

`jw_rag.chunker.chunk_paragraphs` sigue siendo la API pública por defecto y bit-stable. Nada se rompe si la sigues usando.

Ahora puedes opt-in a:

1. **`semantic`** — fusiona párrafos que empiezan con marcador de continuación (`Sin embargo`, `However`, `No entanto`, ...) con el chunk previo, y corta tras marcadores de cierre (`Por lo tanto`, `Therefore`, `Portanto`, ...). Puramente heurístico — sin LLM, sin red.
2. **`llm`** — corre primero `semantic`, luego pide al provider `jw_gen` configurado **acciones a nivel de índice** (split/merge) — nunca reescritura. Cacheado por content hash; mismos párrafos → mismo output sin llamada.

Selección, en orden de precedencia:

1. kwarg `chunker=` en `ingest_*` o `get_chunker(name=...)`
2. env var `$JW_CHUNKER`
3. default `paragraph`

## Catálogo de marcadores

Los marcadores viven en `packages/jw-core/src/jw_core/data/continuation_markers.json` y vienen para **es / en / pt**. Añadir un idioma es un PR solo de JSON: añade un bloque con `continuation`, `closure`, `fingerprint` (huella de palabras-función para el detector ligero).

## Semántica de re-ingest

Los corpora ya indexados **no** se re-chunkean automáticamente. El chunker que produjo cada chunk queda en `metadata["chunker"]`. Para migrar a semantic, re-ingesta desde la fuente.

## Benchmarking

`jw chunker-bench`:
- lee `packages/jw-eval/fixtures/chunker_bench/doctrinal_queries.yaml`
- ingesta/lee el corpus para cada variante
- corre `VectorStore.search(query, k=10)` y calcula NDCG@10
- reporta media por idioma + CI 95% bootstrap + delta cross-variant
- sale con código no-cero si alguna variante no-baseline cae bajo `--min-lift` (default 10%)

CI nightly corre el bench (paragraph vs semantic). La variante `llm` es local-only — necesita provider.

## Cache

`LLMChunker` cachea acciones en `~/.jw-agent-toolkit/chunk-cache/` (override con `$JW_CHUNK_CACHE_DIR`). Clave = `sha256(source_id | paragraphs | provider_id | prompt_version)`. Cache hit rate >95% sobre inputs idénticos.

## Cuándo usar cada uno

| Caso de uso | Chunker recomendado |
|---|---|
| Ingest default, batch jobs, CI | `paragraph` |
| Q&A doctrinal, artículos largos | `semantic` |
| Build offline con provider disponible, máximo recall | `llm` |
| Capítulos bíblicos | `paragraph` (chunker verse-aware es M11, no F45) |
