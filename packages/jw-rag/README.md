# jw-rag

Recuperación híbrida (BM25 + vector + RRF) sobre el corpus JW.

## Capacidades

- **Chunking** por párrafos con merge de párrafos cortos y split de párrafos largos en límites de oración.
- **Embedder protocol**: pluggable. Incluye `FakeEmbedder` determinista para tests; OpenAI y sentence-transformers son extras opcionales.
- **VectorStore híbrido** en memoria + persistencia JSON en disco:
  - Búsqueda vectorial por cosenos (numpy, vectores L2-normalizados).
  - Búsqueda BM25 (`rank-bm25`).
  - Fusión híbrida vía Reciprocal Rank Fusion (RRF).
- **Pipeline de ingest** con helpers de alto nivel: `ingest_bible_chapter`, `ingest_article`, `ingest_search_topk`.

## Instalación

Por defecto solo `numpy` + `rank-bm25`:

```bash
uv add jw-rag
```

Con un embedder real:

```bash
uv add "jw-rag[openai]"        # OpenAI embeddings
uv add "jw-rag[local]"         # sentence-transformers
```

## Uso rápido

```python
from pathlib import Path
from jw_rag import VectorStore, FakeEmbedder
from jw_rag.ingest import ingest_bible_chapter

store = VectorStore(Path("~/.jw-rag").expanduser(), FakeEmbedder(dim=64))
await ingest_bible_chapter(store, book_num=43, chapter=3, language="es")
store.save()

hits = store.hybrid_search("amor", top_k=5)
for h in hits:
    print(h.rank, h.score, h.chunk.text[:100])
```

## Referencia detallada

Ver [`docs/referencia/jw-rag.md`](../../docs/referencia/jw-rag.md) para la documentación de cada clase, función y formato de persistencia.
