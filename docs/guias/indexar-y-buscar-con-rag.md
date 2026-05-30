# Guía: indexar y buscar con RAG

> Cómo poblar el `VectorStore`, configurar embedders, hacer búsquedas (vector / BM25 / híbrida) y persistir en disco.

## Conceptos

- **Chunk**: unidad mínima de texto indexado. Cada chunk tiene `id`, `text`, `source_id` y `metadata`.
- **Embedder**: convierte chunks en vectores. Protocolo simple: una clase con `dim: int` y `embed(texts) -> ndarray (N, dim)`.
- **VectorStore**: indexa chunks. Mantiene un `numpy.ndarray (N, dim)` de vectores + un `BM25Okapi`. Persiste a disco como `chunks.jsonl + vectors.npy + meta.json`.
- **SearchHit**: resultado de búsqueda. Lleva `chunk`, `score`, `rank` y `source` (`"vector"`, `"bm25"` o `"hybrid"`).

## Setup mínimo

```python
from pathlib import Path
from jw_rag import VectorStore, FakeEmbedder

store = VectorStore(
    Path("~/.jw-rag").expanduser(),
    FakeEmbedder(dim=64),
)
```

`FakeEmbedder` es determinista y hash-based — **no es semánticamente útil**, pero permite que el RAG funcione offline para tests y sanity-checks.

Para producción, cablea un embedder real (siguiente sección).

## Embedders reales

### OpenAI

```bash
uv add "jw-rag[openai]"
```

```python
from openai import OpenAI

class OpenAIEmbedder:
    dim = 1536  # ada-002

    def __init__(self):
        self.client = OpenAI()

    def embed(self, texts: list[str]) -> np.ndarray:
        resp = self.client.embeddings.create(
            input=texts, model="text-embedding-ada-002"
        )
        return np.array([d.embedding for d in resp.data], dtype=np.float32)

store = VectorStore(Path("~/.jw-rag"), OpenAIEmbedder())
```

### sentence-transformers (local, sin API key)

```bash
uv add "jw-rag[local]"
```

```python
from sentence_transformers import SentenceTransformer

class LocalEmbedder:
    def __init__(self, model="paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, convert_to_numpy=True).astype(np.float32)

store = VectorStore(Path("~/.jw-rag"), LocalEmbedder())
```

El modelo `paraphrase-multilingual-MiniLM-L12-v2` funciona bien para mezcla inglés/español/portugués.

## Pipeline de ingest

### Capítulo bíblico

```python
from jw_rag.ingest import ingest_bible_chapter
from jw_core.clients.wol import WOLClient

wol = WOLClient()
try:
    count = await ingest_bible_chapter(
        store, book_num=43, chapter=3,
        language="es", publication="nwt",
        wol=wol,
    )
    print(f"Añadidos {count} chunks")
finally:
    await wol.aclose()

store.save()
```

### Artículo arbitrario

```python
from jw_rag.ingest import ingest_article

count = await ingest_article(
    store,
    "https://wol.jw.org/en/wol/d/r1/lp-e/2024365",
    metadata={"campaign": "weekly_research"},  # opcional
)
```

### Búsqueda + ingest de los top-N

```python
from jw_rag.ingest import ingest_search_topk

total = await ingest_search_topk(
    store,
    query="el día de Jehová",
    filter_type="all",
    language="S",       # JW code
    top_n=5,
)
print(f"Indexados {total} chunks de 5 artículos")
```

### EPUB completo (Fase 5)

```python
from jw_rag.ingest import ingest_epub

total = ingest_epub(
    store,
    epub_path="./descargas/bh_E.epub",
    publication_code="bh",
    language="en",
    skip_short_docs=1,   # ignora cover/divider con <1 párrafo
)
print(f"Indexado libro completo: {total} chunks")
```

`ingest_epub` es **síncrono** (a diferencia de los demás `ingest_*`): no hace I/O de red, solo desempaqueta el ZIP y parsea XHTML.

## Búsquedas

### Vectorial (cosenos)

```python
hits = store.vector_search("amor incondicional", top_k=5)
for h in hits:
    print(f"[{h.rank}] score={h.score:.3f}")
    print(f"  source: {h.chunk.source_id}")
    print(f"  text: {h.chunk.text[:100]}")
```

Similitud cos = producto punto (porque vectores son L2-normalizados en `add()`).

### BM25 (keyword)

```python
hits = store.bm25_search("Jehová", top_k=5)
```

Útil cuando el query es muy específico (nombre propio, frase exacta) o cuando el embedder es flojo (como FakeEmbedder).

### Híbrida (default recomendado)

```python
hits = store.hybrid_search("el día de Jehová", top_k=5)
for h in hits:
    print(h.score, h.chunk.text[:80])
```

Implementación: Reciprocal Rank Fusion (RRF).

```python
candidate_pool = 50    # de cuántos candidatos por método extraer
rrf_k = 60             # constante estándar de RRF

# Para cada hit en (vec_hits + bm25_hits):
#   contribución = 1 / (rrf_k + hit.rank)
#   fused[chunk.id] += contribución
# ordenar por score descendiente, devolver top_k
```

RRF es robusto: no asume nada sobre las escalas de los scores. Solo usa los rankings.

## Filtrar resultados por metadata

```python
from jw_rag.retrieve import filter_by_metadata, dedup_by_source

hits = store.hybrid_search("amor", top_k=20)

# Solo capítulos bíblicos
bible_hits = filter_by_metadata(hits, kind="bible_chapter")

# Solo en español
es_hits = filter_by_metadata(hits, language="es")

# Quedarse con el mejor hit por fuente
unique = dedup_by_source(hits)
```

`filter_by_metadata` exige igualdad exacta en cada filtro pasado por kwargs.

## Persistencia

```python
store.save()   # escribe chunks.jsonl + vectors.npy + meta.json en path

# En otra sesión:
store_2 = VectorStore(Path("~/.jw-rag"), embedder)  # mismo path, mismo embedder
store_2.load()                                        # restaura todo desde disco
```

⚠️ El embedder debe tener el **mismo `dim`** que cuando se guardó. Si no, `load()` lanza `ValueError`. Esto es deliberado: cambiar de embedder requiere re-indexar.

Estructura en disco:

```
~/.jw-rag/
├── chunks.jsonl    # una línea JSON por chunk (id, text, source_id, metadata)
├── vectors.npy     # matriz (N, dim) float32 — vectores L2-normalizados
└── meta.json       # {"dim": 64, "count": 412}
```

`chunks.jsonl` es human-readable y útil para inspeccionar. `vectors.npy` es binario numpy.

## Tuning del chunker

```python
from jw_rag.chunker import chunk_paragraphs

chunks = chunk_paragraphs(
    paragraphs,
    source_id="article:url",
    max_chars=1500,        # chunks más grandes que esto se dividen en oraciones
    min_chars=80,          # párrafos más cortos se mergan con el siguiente
    metadata={"kind": "article"},
)
```

Defaults son razonables para artículos JW (un párrafo bien formado = un chunk; párrafos cortos se acumulan; párrafos extra largos se splittean en límites de oración).

## Patrones de búsqueda

### Multi-modo con fallback

```python
def find(query, top_k=5):
    hits = store.hybrid_search(query, top_k=top_k)
    if not hits:
        # Fallback: vector solo (por si BM25 no encontró tokens válidos)
        hits = store.vector_search(query, top_k=top_k)
    return hits
```

### Filtrar por origen antes de mostrar

```python
hits = store.hybrid_search("Trinidad")
# Quitar duplicados por artículo
hits = dedup_by_source(hits)
# Quedarse con artículos (no capítulos bíblicos)
hits = filter_by_metadata(hits, kind="article")
# Top 3
for h in hits[:3]:
    print(h.chunk.metadata.get("title"), h.score)
```

## Anti-patrones

### No re-indexes en caliente sin guardar

```python
# MAL
await ingest_bible_chapter(store, 43, 3)
await ingest_bible_chapter(store, 43, 4)
# si el proceso muere aquí, pierdes todo

# BIEN
await ingest_bible_chapter(store, 43, 3)
await ingest_bible_chapter(store, 43, 4)
store.save()
```

El MCP server hace `store.save()` después de cada `ingest_*` por defecto.

### No mezcles embedders

Cada `VectorStore` está atado a su embedder en runtime. Si cambias el embedder, debes re-indexar (los vectores antiguos no son comparables con los nuevos).

### No esperes alta calidad con `FakeEmbedder`

`FakeEmbedder` es para pruebas. Si vas a hacer recuperación real, conecta un embedder propio. Mientras tanto, **BM25 lleva el peso** y `hybrid_search` sigue dando resultados útiles porque RRF se beneficia de BM25 aunque vector sea ruido.

## Ver también

- [`docs/referencia/jw-rag.md`](../referencia/jw-rag.md) — referencia exhaustiva de `VectorStore`, `Embedder`, `chunker`, `ingest`, `retrieve`
- [`docs/conceptos/flujos-end-to-end.md`](../conceptos/flujos-end-to-end.md) — diagramas de ingest + búsqueda
