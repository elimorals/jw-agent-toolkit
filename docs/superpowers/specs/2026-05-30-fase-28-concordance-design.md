# Fase 28 — Concordancia exacta NWT + publicaciones

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (especializado pero único)
> **Tamaño**: S (~2-3 días)
> **Depende de**: Fase 5 (parsers EPUB), Fase 5.5 (parsers JWPUB descifrado), Fase 19 (`meps_catalog` para URLs canónicas — opcional). No bloquea ninguna fase posterior.
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

El RAG actual (`jw_rag` con BM25 + vector + RRF) es **probabilístico**: encuentra los chunks más similares a una consulta, pero no garantiza listar *todas* las ocurrencias literales de una expresión. Para un publicador haciendo una asignación o un anciano preparando un discurso público, la pregunta práctica suele ser:

> "Muéstrame **cada vez** que aparece la frase `«conocimiento exacto»` en la NWT y en mis publicaciones descargadas."

Eso es **concordancia exacta**, no semántica. Hoy no existe ese flujo determinístico en el toolkit. Cualquier reemplazo con RAG falla en dos modos:

1. **Falsos negativos** — el vector puede saltarse ocurrencias literales si el chunking dispersó la frase.
2. **Costo de embeddings** — innecesario cuando la pregunta es puramente léxica.

Fase 28 cierra ese hueco con un índice **SQLite FTS5** sobre el corpus que el usuario ya descifró localmente: capítulos NWT (vía `WOLClient`), JWPUB descifrados (Fase 5.5) y EPUB (Fase 5). Cero red en lectura, cero LLM, citas verificables.

## Objetivos (en orden de prioridad)

1. **Búsqueda literal exhaustiva** sobre corpus offline ya descifrado, con snippet + URL canónica por hit.
2. **Indexación incremental** (re-correr el comando salta archivos cuyo sha256 no cambió) — el usuario añade publicaciones con el tiempo.
3. **Multilenguaje desde el día 1** — `en` / `es` / `pt` mínimo, sin re-ranking por idioma.
4. **Complementa, no reemplaza, el RAG semántico** — esta es la herramienta para "literal", el RAG sigue siendo la herramienta para "conceptos".

## No-objetivos (boundaries vinculantes)

- **No** indexa contenido remoto bajo demanda. Solo lo que el usuario ya descifró localmente.
- **No** hace stemming ni reformulación de consulta. Es búsqueda **literal** (con normalización de diacríticos, decisión documentada abajo).
- **No** sustituye al chunker del RAG. Aquí los "chunks" son **párrafos individuales** ya extraídos por el parser correspondiente — la unidad natural de cita es el párrafo o el versículo.
- **No** persiste en `~/.jw-agent-toolkit/notes.db`. Tiene su propia DB `concordance.db` para no acoplar el ciclo de vida del usuario con el del corpus.
- **No** soporta búsqueda regex. FTS5 phrase + AND/OR + NEAR es el contrato.

## Arquitectura

Módulo nuevo `packages/jw-core/src/jw_core/concordance/`. No es un paquete del workspace — vive dentro de `jw-core` porque depende directamente de los parsers `epub` y `jwpub` y porque el patrón SQLite/FTS5 ya está en uso (ver `study/personal_notes.py`).

```
packages/jw-core/src/jw_core/concordance/
├── __init__.py              # Re-exports: build_index, concordance_search, ConcordanceHit
├── models.py                # ConcordanceHit, IndexEntry (Pydantic)
├── store.py                 # SQLite FTS5 — schema + add/iter/sources/clear
├── indexer.py               # Ingestion adapters: NWT chapter / JWPUB / EPUB
└── search.py                # Query API + snippet rendering + URL resolution
```

Superficies:

- `packages/jw-cli/src/jw_cli/commands/grep.py` → `jw grep "<query>" [--build-index PATH...] [--language es]`.
- `packages/jw-mcp` → herramientas `concordance_build_index` y `concordance_search`.

### Reglas duras de diseño

1. `jw_core.concordance` **no** hace red. La ingestión de capítulos NWT recibe el HTML/texto ya descargado por `WOLClient` (inyectado por el llamante). El indexer no llama al cliente HTTP.
2. SQLite en modo **WAL**: single-writer, multi-reader concurrente. Los tests usan rutas temporales.
3. **Determinista**: misma query + mismo índice ⇒ mismos hits en el mismo orden.
4. El esquema de la tabla FTS5 vive **en código**, no en migraciones. La función `_init_schema` es idempotente.
5. Cada `IndexEntry` lleva `source_sha256` (sha del archivo fuente cuando aplica) para soporte incremental.

## Modelo de datos

### SQL schema

```sql
-- Tabla "real" con metadatos por chunk
CREATE TABLE IF NOT EXISTS concordance_entries (
    entry_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_kind TEXT NOT NULL,          -- 'nwt' | 'jwpub' | 'epub'
    source_id   TEXT NOT NULL,          -- p.ej. 'nwt:es:43:3' o sha256(file) o pub_symbol
    ref         TEXT NOT NULL,          -- p.ej. 'Juan 3:16' o 'doc#42 p7' o 'item-23:p5'
    chunk_text  TEXT NOT NULL,
    language    TEXT NOT NULL,
    url         TEXT,                   -- URL canónica resuelta (puede ser NULL al insertar)
    source_path TEXT,                   -- ruta al .jwpub/.epub o '' para NWT
    source_sha256 TEXT NOT NULL DEFAULT '',
    indexed_at_unix REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source ON concordance_entries (source_kind, source_id);
CREATE INDEX IF NOT EXISTS idx_sha    ON concordance_entries (source_sha256);

-- Tabla FTS5 — el contenido del rowid mapea a entry_id
CREATE VIRTUAL TABLE IF NOT EXISTS concordance_fts USING fts5(
    chunk_text,
    content='concordance_entries',
    content_rowid='entry_id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers de sincronización
CREATE TRIGGER IF NOT EXISTS conc_ai AFTER INSERT ON concordance_entries BEGIN
    INSERT INTO concordance_fts(rowid, chunk_text) VALUES (new.entry_id, new.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS conc_ad AFTER DELETE ON concordance_entries BEGIN
    INSERT INTO concordance_fts(concordance_fts, rowid, chunk_text)
    VALUES('delete', old.entry_id, old.chunk_text);
END;

-- Cache de archivos ya indexados (soporte incremental)
CREATE TABLE IF NOT EXISTS concordance_sources (
    source_kind TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    language TEXT NOT NULL,
    n_entries INTEGER NOT NULL,
    indexed_at_unix REAL NOT NULL,
    PRIMARY KEY (source_kind, source_path)
);
```

### Pydantic

```python
class IndexEntry(BaseModel):
    source_kind: Literal["nwt", "jwpub", "epub"]
    source_id: str
    ref: str
    chunk_text: str
    language: str
    url: str | None = None
    source_path: str | None = None
    source_sha256: str = ""

class ConcordanceHit(BaseModel):
    entry_id: int
    source_kind: Literal["nwt", "jwpub", "epub"]
    source_id: str
    ref: str
    snippet: str          # con marcadores `‹…›` alrededor del término encontrado
    language: str
    url: str | None
```

## Decisiones clave (cada una explícita por su trade-off)

### 1. `tokenize='unicode61 remove_diacritics 2'` — sí o no

**Elegido**: **sí**, con `remove_diacritics 2`.

- **Pro**: el usuario hispanohablante busca "espiritu" o "Espíritu" indistintamente y encuentra ambos. Idem `"Mãe"` ↔ `"Mae"` en portugués.
- **Contra**: dos palabras que solo difieren por acento se vuelven equivalentes (raro en este corpus — no hay pares como `solo`/`sólo` que cambien sentido en contextos doctrinales).
- **Mitigación**: documentado en la guía. Si en el futuro alguien quiere case+accent sensible, se puede crear una vista alternativa con `tokenize='unicode61 case_sensitive 1 remove_diacritics 0'` sin migrar datos.

### 2. Stemming **OFF** (no `porter`)

**Elegido**: stemming desactivado.

- "Concordancia exacta" implica que `caminó` no matchea `caminar`. Stemming porter en FTS5 ni soporta español/portugués bien — añadirlo daría matches espurios.
- El usuario que quiere variantes morfológicas usa el RAG semántico, no esta herramienta.

### 3. Unidad de chunk = párrafo, no oración ni verso

**Elegido**: **párrafo**. Para NWT el parser ya devuelve `verses[]` — usamos el verso completo. Para JWPUB/EPUB usamos cada `<p data-pid>` extraído.

- Una oración suelta es muy poco contexto para el snippet. Un capítulo entero es demasiado para resaltar.
- Coherente con el chunker del RAG (`chunk_paragraphs`) — el usuario recibe la **misma** unidad de cita en ambos sistemas.

### 4. URL canónica al **indexar**, no al consultar

- Para `nwt`: el llamante (CLI/MCP) ya conoce la URL antes de inyectar el texto (la construye `WOLClient.get_bible_chapter`). Se persiste.
- Para `jwpub`: si `meps_catalog` (Fase 19) tiene el pub registrado, resolvemos `pub_code → URL pattern`. Si no, `url=NULL` y el snippet vive sin URL canónica (el usuario puede registrar después y re-indexar).
- Para `epub`: `file://{absolute_path}` como fallback. Coherente con la guía de "citas siempre referenciables".

### 5. Snippet con marcadores `‹…›` (no HTML)

FTS5 `snippet(<table>, <col>, <start>, <end>, <ellipsis>, <tokens>)` con marcadores Unicode `‹` y `›` y elipsis `…`. Razones:

- Markdown-safe (no choca con asteriscos, backticks, ni HTML del callsite).
- Distinguible visualmente en CLI y en respuesta MCP.
- Documentado: si el cliente necesita HTML, sustituye `‹` por `<mark>` con `replace`.

### 6. Incremental por `sha256` de archivo

Re-correr `build_index` con el mismo `.jwpub` salta la re-ingestión si `source_sha256` ya existe en `concordance_sources`. Para capítulos NWT, el `source_id` ya es `nwt:{lang}:{book}:{chapter}` y se reemplaza in-place (DELETE + INSERT atómico en una transacción).

## API pública

```python
# jw_core.concordance — re-exports

from jw_core.concordance.indexer import build_index
from jw_core.concordance.search import concordance_search
from jw_core.concordance.models import ConcordanceHit, IndexEntry
from jw_core.concordance.store import ConcordanceStore, default_db_path

__all__ = [
    "build_index",
    "concordance_search",
    "ConcordanceHit",
    "IndexEntry",
    "ConcordanceStore",
    "default_db_path",
]
```

### `build_index`

```python
def build_index(
    paths: list[Path] | None = None,
    *,
    language: str,
    source_tag: str = "",                  # opcional, etiqueta libre para agrupar
    db_path: Path | None = None,
    force: bool = False,                   # ignorar sha256 cache
    nwt_chapters: list[NWTChapter] | None = None,
) -> int:
    """Index a list of paths and/or pre-resolved NWT chapters.

    `paths` puede mezclar .jwpub y .epub — el detector de extensión enruta a
    cada adapter. `nwt_chapters` son objetos ya descargados por el caller
    (el indexer no hace red). Retorna el número de entries insertadas.
    """
```

### `concordance_search`

```python
def concordance_search(
    query: str,
    *,
    language: str | None = None,
    source_kind: str | None = None,
    max_results: int = 100,
    db_path: Path | None = None,
) -> list[ConcordanceHit]:
    """Phrase / AND / OR via FTS5 syntax.

    Ejemplos:
        concordance_search('"conocimiento exacto"')              # phrase
        concordance_search('Jehová AND amor')                    # AND
        concordance_search('"reino de Dios" OR "reino del cielo"') # OR
        concordance_search('Jehová NEAR/3 amor', max_results=20)  # proximity
    """
```

## Superficies

### CLI

Nuevo comando `jw grep`:

```
jw grep "conocimiento exacto"
jw grep "conocimiento exacto" --language es
jw grep "Jehová NEAR/3 amor" --max 20
jw grep --build-index ~/jw-publications/*.jwpub --language es
jw grep --build-index ~/Biblioteca --language es --recursive
jw grep --stats
```

### MCP

Dos tools nuevas:

- `concordance_build_index(paths: list[str], language: str, force: bool = False) -> {"inserted": int}`
- `concordance_search(query: str, language?: str, source_kind?: str, max_results?: int) -> list[ConcordanceHit]`

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | FTS5 unavailable en sqlite system build | Verificación en `_init_schema` con fallback explícito `RuntimeError` con mensaje accionable. Python 3.13 ships con sqlite ≥ 3.45 → FTS5 garantizado |
| 2 | Frase con caracteres de operador FTS5 (`AND`, `"`, `(`, `*`) confunde al usuario | Documentado: para frase literal usar comillas dobles. Helper `escape_fts_phrase()` para la API CLI por defecto |
| 3 | Indexar todo `~/Biblioteca` consume GB | Documentado en la guía. SQLite WAL crece manejablemente; el índice de las 27 publicaciones de prueba ocupa ~50MB |
| 4 | Re-indexar el mismo archivo duplica entries | Cache `concordance_sources` por `(kind, path, sha256)`. `force=True` para forzar |
| 5 | El usuario espera regex y obtiene FTS5 | Mensaje de error claro cuando la query contiene `\b`, `[`, `+`, `^`, `$`; redirige al manual |
| 6 | URL canónica no disponible para JWPUB sin `meps_catalog` | Insertamos `url=NULL`; la herramienta indica `(sin URL canónica — registra el pub en el catálogo)` |
| 7 | Concurrencia indexer + CLI simultáneos | WAL mode + retry-on-busy con backoff exponencial (5 reintentos a 50–800ms) en `ConcordanceStore._connect` |
| 8 | `remove_diacritics 2` da falso positivo doctrinal | Documentado. Para casos sensibles, el usuario filtra por `language` o usa búsqueda case-sensitive (extensión futura, no en M1) |

## Métricas de éxito

- `jw grep --build-index <fixture.jwpub> --language es` corre en <500ms para un JWPUB de ~50 documentos.
- `jw grep "conocimiento exacto" --language es` devuelve resultados en <50ms sobre un índice de 27 publicaciones.
- 100% determinista en tests (mismo input ⇒ mismo orden de hits).
- Cobertura ≥ 90% del módulo `concordance/` con tests CPU-only y sin red.
- Documentado en `docs/guias/concordancia-exacta.md` con ejemplos por idioma.

## Eval (cobertura Fase 22)

Cada nueva feature **debe** añadir 3 Golden Cases. Para Fase 28:

- L1: `concordance_search` retorna `>= 1` hit para query conocida en fixture sintético.
- L1: snippet contiene marcadores `‹…›` alrededor del término.
- L2: URL retornada matchea el patrón canónico esperado (snapshot) cuando aplica.

Plan de implementación detallado en [`docs/superpowers/plans/2026-05-30-fase-28-concordance-plan.md`](../plans/2026-05-30-fase-28-concordance-plan.md).

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests unitarios del módulo
.venv/bin/python -m pytest packages/jw-core/tests/test_concordance_store.py \
                          packages/jw-core/tests/test_concordance_indexer.py \
                          packages/jw-core/tests/test_concordance_search.py -v

# 3. Smoke CLI con fixture sintético
uv run jw grep --build-index packages/jw-core/tests/fixtures/concordance/demo.epub --language en
uv run jw grep "test phrase" --language en

# 4. MCP tool list muestra las dos nuevas
uv run jw-mcp list-tools | grep concordance

# 5. Suite eval — Fase 22 — no regresa
.venv/bin/python -m pytest packages/jw-eval/tests -v
```

## Pendientes explícitos (post-Fase 28)

- Búsqueda case-sensitive opcional (cambio de tokenize sin migración de schema).
- Highlighting HTML para la futura UI web (`<mark>` en lugar de `‹›`).
- Indexar fuentes Obsidian (Fase 20) — fácil añadir un cuarto `source_kind='obsidian'`.
- Filtros por libro bíblico / pub / fecha en el query — hoy filtramos solo por `language` y `source_kind`.
