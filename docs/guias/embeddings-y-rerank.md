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

# Desactivar rerank desde el MCP semantic_search tool (rerank=False)
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
