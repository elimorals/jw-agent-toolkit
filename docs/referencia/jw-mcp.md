# Referencia: jw-mcp

> Contratos completos de las **29 herramientas MCP**. Cada herramienta documenta entrada, salida y errores.

## Arranque del servidor

Entry point: `jw_mcp.server:main`. Equivalente CLI: `uv run jw-mcp`.

El servidor crea un `FastMCP("jw-agent-toolkit")` y registra las herramientas con `@mcp.tool`. Habla stdio.

### Clientes compartidos (lazy)

Para evitar abrir múltiples connection pools:

| Variable global | Tipo | Creado por |
|---|---|---|
| `_wol` | `WOLClient` | `_get_wol()` |
| `_cdn` | `CDNClient` | `_get_cdn()` |
| `_pub` | `PubMediaClient` | `_get_pub()` |
| `_med` | `MediatorClient` | `_get_med()` |
| `_topic` | `TopicIndexClient(cdn=_get_cdn(), wol=_get_wol())` | `_get_topic()` |
| `_rag_store` | `VectorStore` | `_get_rag_store()` |

### Variables de entorno

| Var | Default | Descripción |
|---|---|---|
| `JW_RAG_STORE_PATH` | `~/.jw-agent-toolkit/rag` | Path del store RAG |
| `JW_CACHE_PATH` | `~/.jw-agent-toolkit/cache.db` | Path del DiskCache SQLite leído por `get_cache_stats` |
| `JW_TELEMETRY_ENABLED` | (no) | `1`/`true`/`yes` activa el detector de drift de la API |
| `JW_TELEMETRY_PATH` | `~/.jw-agent-toolkit/telemetry.json` | Path del JSON con baselines y eventos de drift |

---

## Núcleo (Fase 1)

### `resolve_reference(text, language="en")`

Parsea una referencia bíblica y devuelve estructura + URL canónica.

**Args**: `text: str`, `language: str = "en"`.

**Returns**: dict con `book_num`, `book_canonical`, `chapter`, `verse_start`, `verse_end`, `detected_language`, `display`, `raw_match`, `wol_url`. Si no se detecta cita: `{"error": "..."}`.

### `get_chapter(book_num, chapter, language="en", publication="nwtsty")`

Descarga y parsea un capítulo bíblico.

**Returns**: `title`, `paragraphs[]`, `references[]`, `source_url`, `language`, `publication`. Si `book_num` ∉ `1..66`: `{"error": "..."}`.

### `get_daily_text(language="en", date="")`

Texto diario. Sin `date`, lee de la homepage `/h/`; con `date="YYYY-MM-DD"`, navega a `/dt/{r}/{lp_tag}/{YYYY}/{M}/{D}` (funciona para cualquier fecha publicada).

**Returns**: `date`, `scripture`, `commentary`, `source_url`, `language`, `requested_date` (la fecha pedida o `"today"`). Si falla el parseo: `{"error": "...", "source_url": "...", "html_length": int}`. Si falla el fetch por fecha específica: `{"error": "Could not fetch daily text for {date}: {e}"}`.

### `search_content(query, filter_type="all", language="en", limit=10)`

Búsqueda CDN.

**Args**: `filter_type` ∈ `{"all", "publications", "videos", "audio", "bible", "indexes"}`.

**Returns**: `query`, `filter_type`, `language`, `results` (JSON crudo de la CDN). Si idioma desconocido: `{"error": "..."}`.

### `get_article(url)`

Fetch + parse de cualquier URL de wol.jw.org.

**Returns**: `title`, `paragraphs[]`, `references[]`, `source_url`.

---

## Media (Fase 2)

### `list_languages(in_language="E", only_with_web_content=True)`

Lista de idiomas con JW + ISO codes.

**Returns**: `in_language`, `count`, `languages: [{code, locale, name, vernacular, rtl, is_sign_language, has_web_content}]`.

### `list_publication_files(pub_code, language="E", file_format=None, bible_book=None, issue=None)`

Inventario de archivos descargables.

**Returns**: `pub_code`, `pub_name`, `file_count`, `files: [{url, filename, title, language, file_format, size_bytes, checksum, ...}]`. Si error: `{"error": "..."}`.

### `download_publication(pub_code, out_dir, language="E", file_format="EPUB", bible_book=None, issue=None)`

Descarga a `out_dir`.

**Returns**: `pub_code`, `language`, `file_format`, `saved: [{path, size_bytes}]`, `total_bytes`.

### `get_publication_toc(pub_code, language="en", number=None)`

Fetcha la página landing/TOC de una publicación. URL pattern: `/{iso}/wol/publication/{r}/{lp_tag}/{pub}[/{number}]`. Para Bibles (`pub="nwtsty"`), `number` selecciona book TOC. Para revistas, `number` es issue. Para libros, capítulo.

**Returns**: `pub_code`, `language`, `number`, `title`, `paragraphs[]`, `references[]`, `source_url`. Si falla: `{"error": str(e)}`.

### `list_weblang_languages(in_language_iso="en")`

Lista alterna desde `www.jw.org/{iso}/languages/`. Complementa `list_languages` (mediator): trae más campos por idioma (vernacular, script, altSpellings).

**Returns**: `in_language_iso`, `count`, `languages: [WeblangLanguage.model_dump()]` (campos: code, iso, name, vernacular, alt_names, rtl, script, is_sign_language).

---

## Versículos y notas de estudio (Fase 3)

### `get_verse(book_num, chapter, verse, language="en")`

Texto limpio de un versículo.

**Returns**: `book_num`, `chapter`, `verse`, `text`, `language`, `wol_url`, `source_url`. Si no encontrado: `{"error": "...", "source_url": "..."}`.

### `get_study_notes(book_num, chapter, verse=None, language="en")`

Notas nwtsty. Si `verse` se especifica, filtra a notas de ese versículo.

**Returns**: `book_num`, `chapter`, `verse`, `language`, `source_url`, `count`, `notes: [StudyNote.model_dump(), ...]`.

### `get_cross_references(book_num, chapter, verse=None, language="en", resolve_panel=False)`

Marcadores cross-ref. Con `resolve_panel=True` descarga el HTML del panel (+1 request por marcador).

**Returns**: `cross_references: [{book_num, chapter, verse, href, marker, language, full_url, panel_url?, panel_text?}]`.

### `compare_translations(book_num, chapter, verse, languages=None)`

Mismo versículo en varios idiomas. Default `["en", "es", "pt"]`.

**Returns**: `book_num`, `chapter`, `verse`, `translations: {lang: {text, wol_url, found}}`.

---

## Índice temático (Fase 4)

### `search_topic_index(query, language="E", limit=10)`

Busca temas en el Índice de Publicaciones.

**Returns**: `query`, `language`, `count`, `results: [{title, snippet, wol_url, docid, subtype, original_rank, score}]`.

### `get_topic_articles(docid_or_url, language="en")`

Página de tema completa.

**Returns**: `docid`, `title`, `see_also`, `source_url`, `language`, `total_citations`, `subheadings: [{heading, is_top_level, citations: [{text, kind, url}]}]`.

---

## EPUB (Fase 5)

### `extract_epub_text(epub_path, max_docs=0)`

Parsea un .epub descargado.

**Returns**: `title`, `creator`, `language`, `identifier`, `publisher`, `document_count`, `paragraph_count`, `source_path`, `documents: [EpubDocument.model_dump()]`.

### `ingest_epub(epub_path, publication_code="", language="en")`

Indexa el EPUB en el store RAG.

**Returns**: `epub_path`, `publication_code`, `language`, `chunks_added`, `store_total`.

---

## JWPUB (Fase 5 + 5.5 — descifrado AES-128-CBC)

### `inspect_jwpub_metadata(jwpub_path)`

Metadata + TOC sin desencriptar (barato). El campo `text` de cada documento se excluye explícitamente del response.

**Returns**: `JwpubMetadata.model_dump(exclude={"documents": {"__all__": {"text"}}})` con title, symbol, year, publication_type, manifest_hash, schema_version, document_count, documents[] con chapter_number, paragraph_count, page range, content_length.

### `extract_jwpub_text(jwpub_path, max_docs=0)`

Decrypta y devuelve el texto completo. Usa la derivación de clave `SHA256(f"{lang}_{symbol}_{year}") XOR magic_constant` (crédito `gokusander/jwpub-toolkit`, MIT).

**Returns**: `title`, `symbol`, `year`, `publication_type`, `language_index`, `document_count`, `decrypted_text_available` (True salvo en variantes raras), `source_path`, `documents: [JwpubDocument.model_dump()]` con `text` (XHTML) y `paragraphs` (texto plano).

### `ingest_jwpub(jwpub_path, language="en")`

Decrypta + chunkea + indexa todo el JWPUB en el store RAG local. Si la decryption falla (variante de formato no soportada), devuelve `chunks_added=0` con warning.

**Returns**: `jwpub_path`, `language`, `chunks_added`, `store_total`.

---

## RAG (Fase 6)

### `semantic_search(query, top_k=5, mode="hybrid")`

Búsqueda en el RAG local.

**Args**: `mode` ∈ `{"hybrid", "vector", "bm25"}`.

**Returns**: `query`, `mode`, `count`, `results: [{rank, score, source, chunk_id, text, metadata}]`. Si vacío: `{"warning": "...", "results": []}`.

### `ingest_bible_chapter(book_num, chapter, language="en")`

Descarga + indexa un capítulo.

**Returns**: `book_num`, `chapter`, `language`, `chunks_added`, `store_total`.

### `ingest_search_topk(query, top_n=5, filter_type="all", language="E")`

Búsqueda + indexa los top N artículos.

**Returns**: `query`, `ingested_articles`, `chunks_added`, `store_total`.

---

## Agentes de alto nivel (Fase 7)

Todas devuelven `AgentResult.to_dict()`. Estructura común:

```json
{
  "query": "...",
  "agent_name": "...",
  "warnings": [],
  "metadata": {...},
  "findings": [
    {
      "summary": "...",
      "excerpt": "...",
      "metadata": {...},
      "citation": {
        "url": "...",
        "title": "...",
        "kind": "...",
        "metadata": {...}
      }
    }
  ]
}
```

### `verse_explainer(reference, language="en", max_paragraphs=5)`

Resuelve referencia → fetch capítulo → versículos objetivo + study notes + cross-refs.

`findings` contienen: target verses (`kind="verse"`), study notes (`kind="study_note"`), cross-ref markers (`kind="cross_ref"`).

### `research_topic(topic, language="E", top_n=5, fetch_top_k=3)`

Búsqueda CDN → fetch top K → extractos.

`findings` contienen: hasta `max_excerpts_per_article` por artículo, con `citation.url` = URL del artículo.

### `meeting_helper(input_text, language="en", max_paragraphs=8)`

Entrada: URL o referencia bíblica.

`metadata.prep_prompts` incluye preguntas heurísticas de preparación.

`findings` contienen: cada párrafo con un sugerencia de comentario en `metadata.suggest_comment`.

### `apologetics(question, language="E", web_top_k=3, use_rag=True, rag_top_k=5)`

Pipeline completo:

1. Topic Index (`source="topic_index"` / `"topic_index_entry"`).
2. Bible refs explícitas (`source="question_refs"` + `"verse_text"` + `"study_note"`).
3. Búsqueda CDN (`source="cdn_search"`).
4. RAG opcional (`source="rag"`).

Cada `Finding.metadata.source` permite al LLM rankear por autoridad.

---

## Infraestructura (Fase 9)

### `get_cache_stats()`

Snapshot del `DiskCache` en disco. Lee `JW_CACHE_PATH` (default `~/.jw-agent-toolkit/cache.db`).

**Returns**:
- Si no existe el archivo: `{"enabled": False, "path": "...", "reason": "no cache file"}`.
- Si existe: `{"enabled": True, "path": "...", "total": int, "live": int, "expired": int}`.

Útil para que un operador inspeccione o limpie el cache que comparten los clientes wired vía `factory.build_clients()`. El servidor MCP por defecto NO arranca con cache wired (los clientes lazy se crean sin throttler/cache/telemetry); el `get_cache_stats` solo refleja el cache standalone que pudo dejar otro proceso.

---

## Política de errores

| Tipo de fallo | Respuesta |
|---|---|
| `book_num` fuera de rango | `{"error": "book_num must be 1..66, got X"}` |
| Idioma desconocido | `{"error": "Unknown language: ..."}` |
| Filtro inválido | `{"error": "filter_type must be one of {...}"}` |
| `CDNError` / `WOLError` / `MediatorError` / `PubMediaError` / `TopicIndexError` / `JwpubError` | `{"error": str(e)}` (capturado dentro del handler) |

El servidor **nunca** levanta excepciones por encima de la capa MCP; eso mantendría la sesión viva ante fallos transitorios.
