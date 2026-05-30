# Referencia: jw-rag

> Documentación exhaustiva del paquete RAG: chunker, embedders, store híbrido, pipeline de ingest y helpers de retrieval.

## Estructura del paquete

```
jw_rag/
├── __init__.py            # Re-exporta Chunk, Embedder, FakeEmbedder, SearchHit, VectorStore, chunk_paragraphs
├── chunker.py             # Chunk + chunk_paragraphs
├── embed.py               # Embedder protocol + FakeEmbedder + l2_normalize
├── store.py               # SearchHit + VectorStore
├── ingest.py              # ingest_bible_chapter, ingest_article, ingest_search_topk, ingest_epub
└── retrieve.py            # dedup_by_source, filter_by_metadata
```

---

## Módulo `jw_rag.chunker`

### `class Chunk` (dataclass)

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `id` | `str` | — | `{source_id}#{index}` |
| `text` | `str` | — | Texto del chunk |
| `source_id` | `str` | `""` | Identificador del origen (URL, `bible:43:3:es`, ...) |
| `metadata` | `dict[str, Any]` | `{}` | Metadata libre |

### `chunk_paragraphs(paragraphs, source_id, *, max_chars=1500, min_chars=80, metadata=None) -> list[Chunk]`

Convierte párrafos en chunks aplicando:

- Párrafos `> max_chars` → split en límites de oración (helper `_split_long`).
- Párrafos `< min_chars` → mergan con el siguiente hasta superar `min_chars`.
- Flush al alcanzar `max_chars` acumulado o terminar en `.`/`!`/`?` con `≥ min_chars`.

Cada chunk lleva el `metadata` base + `{"para_count": N}` o `{"split": True}` según corresponda.

---

## Módulo `jw_rag.embed`

### `Protocol Embedder`

```python
@runtime_checkable
class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> np.ndarray:
        """(len(texts), self.dim) float32 array, L2-normalized."""
```

Cualquier objeto con `dim: int` y `embed(texts) -> ndarray (N, dim)` satisface el protocolo.

### `class FakeEmbedder`

Embedder hash-based determinista para tests y offline.

**`__init__(dim: int = 64)`**.

**`embed(texts) -> np.ndarray (N, dim) float32`** — vectores L2-normalizados. Mismo texto → mismo vector. Textos distintos → vectores no correlacionados.

### `l2_normalize(matrix: np.ndarray) -> np.ndarray`

Normaliza cada fila a longitud unidad. Filas con norma 0 se devuelven inalteradas.

---

## Módulo `jw_rag.store`

### `class SearchHit` (dataclass)

| Campo | Tipo | Descripción |
|---|---|---|
| `chunk` | `Chunk` | |
| `score` | `float` | Score de similitud (escala depende de `source`) |
| `rank` | `int` | 1-indexed ranking |
| `source` | `str` | `"vector"` / `"bm25"` / `"hybrid"` |

### `class VectorStore`

Store híbrido en memoria con persistencia JSON en disco.

**`__init__(path: Path | str, embedder: Embedder)`** — `path` es el directorio raíz.

#### Estado

- `count: int` — número total de chunks indexados.
- `is_empty: bool` — `count == 0`.

#### Indexación

**`add(chunks: list[Chunk]) -> None`** — embeddea, normaliza, vstack a `_vectors`. Reconstruye BM25 entero (rank_bm25 no soporta updates incrementales).

#### Búsqueda

**`vector_search(query: str, top_k: int = 10) -> list[SearchHit]`** — similitud cos = producto punto. Usa `argpartition` + `argsort` para top-k.

**`bm25_search(query: str, top_k: int = 10) -> list[SearchHit]`** — `BM25Okapi.get_scores(_tokenize(query))`.

**`hybrid_search(query: str, top_k: int = 10, *, candidate_pool: int = 50, rrf_k: int = 60) -> list[SearchHit]`** — RRF entre vector y BM25.

```
contribution = 1 / (rrf_k + hit.rank)
fused[chunk.id] = sum de contributions de ambos métodos
ordered = sort(fused, key=-score)
return top_k de ordered con source="hybrid"
```

#### Persistencia

**`save() -> None`** — escribe en `self.path`:

| Archivo | Contenido |
|---|---|
| `chunks.jsonl` | Una línea JSON por chunk |
| `vectors.npy` | `numpy.save` de la matriz `(N, dim) float32` |
| `meta.json` | `{"dim": int, "count": int}` |

**`load() -> None`** — restaura desde disco. **Lanza `ValueError` si el `dim` del embedder no coincide con el guardado.** Si `meta.json` no existe, retorna silenciosamente (store vacío).

### `_tokenize(text)` (interno)

Lowercase + `re.findall(r"\w+")` + filtra tokens de longitud 1. Usado por BM25 tanto en indexación como en query.

---

## Módulo `jw_rag.ingest`

Todos los helpers excepto `ingest_epub` son `async`. Cada uno acepta clientes opcionales y los gestiona ("propietario").

### `async ingest_bible_chapter(store, book_num, chapter, *, language="en", publication="nwtsty", wol=None) -> int`

Pipeline: `WOLClient.get_bible_chapter()` → `parse_article()` → `chunk_paragraphs()` → `store.add()`.

`source_id = f"bible:{book_num}:{chapter}:{language}"`.

Metadata por chunk: `{kind, book_num, chapter, language, publication, title, source_url}`.

### `async ingest_article(store, url, *, wol=None, metadata=None) -> int`

Pipeline: `WOLClient.fetch(url)` → `parse_article()` → `chunk_paragraphs()` → `store.add()`.

`source_id = f"article:{url}"`.

Metadata: `{kind: "article", title, source_url, **metadata}` (el extra del caller se mergea encima).

### `async ingest_search_topk(store, query, *, filter_type="all", language="E", top_n=5, cdn=None, wol=None) -> int`

Pipeline: `CDNClient.search()` → `_extract_article_urls()` → para cada URL, `ingest_article()`.

Devuelve el **total** de chunks añadidos a través de todos los artículos.

Errores por artículo individual se loggean y continúan (no abortan).

### `ingest_epub(store, epub_path, *, publication_code="", language="en", skip_short_docs=1) -> int`

Pipeline síncrono (no hace red): `parse_epub()` → para cada `EpubDocument` con `len(paragraphs) >= skip_short_docs`, chunk + add.

`source_id = f"epub:{publication_code or epub.title}:{doc.id}"`.

Metadata por chunk: `{kind: "epub_document", publication, publication_code, language, title, spine_index, epub_href, source_path}`.

### Helpers internos

- `_extract_article_urls(data, *, limit)` — aplana grupos vs items y extrae `links.wol` o `links.jw.org`.
- `_wol_url_from(entry)` — `entry.links.wol or entry.links.jw.org or None`.

---

## Módulo `jw_rag.retrieve`

Helpers para post-procesar resultados de búsqueda.

### `dedup_by_source(hits) -> list[SearchHit]`

Mantiene solo el primer (top-ranked) hit por `chunk.source_id`.

### `filter_by_metadata(hits, **eq_filters) -> list[SearchHit]`

Filtra hits cuyo `chunk.metadata` matchea todos los kwargs por igualdad exacta.

```python
filter_by_metadata(hits, kind="article", language="es")
```

---

## Patrones canónicos

### Reset del store

```python
import shutil
shutil.rmtree(store.path, ignore_errors=True)
store = VectorStore(store.path, store.embedder)  # nuevo, vacío
```

### Cambiar de embedder (requiere re-indexar)

```python
# Guardar lista de chunks como CSV/JSONL antes
chunks_backup = list(store._chunks)

# Crear store con nuevo embedder
new_store = VectorStore(new_path, new_embedder)
new_store.add(chunks_backup)
new_store.save()
```

### Búsqueda con score mínimo

```python
hits = store.hybrid_search(query, top_k=50)
hits = [h for h in hits if h.score > 0.01]   # umbral según RRF
```

### Indexar Biblia entera (66 libros)

```python
from jw_core.data.books import BOOKS

for book in BOOKS:
    book_num = book["num"]
    # Aquí necesitas la cantidad de capítulos; usa una tabla aparte o
    # confía en que get_bible_chapter() falle limpiamente
    for chapter in range(1, 51):  # placeholder
        try:
            await ingest_bible_chapter(store, book_num, chapter, language="es")
        except WOLError:
            break  # capítulo no existe → fin del libro
    store.save()
    print(f"{book['canonical']} indexado")
```
