# jw-mcp

Servidor [Model Context Protocol](https://modelcontextprotocol.io) que expone las capacidades de `jw-agent-toolkit` a cualquier cliente MCP (Claude Desktop, Claude Code, etc.).

## Herramientas disponibles

### Núcleo (Fase 1)

- `resolve_reference(text, language="en")` — Parsea una cita bíblica como "Juan 3:16" → estructura + URL canónica
- `get_chapter(book_num, chapter, language="en", publication="nwtsty")` — Descarga un capítulo bíblico desde wol.jw.org
- `get_daily_text(language="en")` — Texto diario de hoy
- `search_content(query, filter_type="all", language="en", limit=10)` — Búsqueda en jw.org
- `get_article(url)` — Descarga y parsea cualquier artículo de wol.jw.org

### Media (Fase 2)

- `list_languages(in_language="E", only_with_web_content=True)` — Lista de idiomas con códigos JW + ISO
- `list_publication_files(pub_code, language="E", file_format=None, bible_book=None, issue=None)` — Inventario de archivos descargables
- `download_publication(pub_code, out_dir, language="E", file_format="EPUB", bible_book=None, issue=None)` — Descarga publicación a disco

### Versículos y notas de estudio (Fase 3)

- `get_verse(book_num, chapter, verse, language="en")` — Texto limpio de un versículo
- `get_study_notes(book_num, chapter, verse=None, language="en")` — Comentario nwtsty
- `get_cross_references(book_num, chapter, verse=None, language="en", resolve_panel=False)` — Marcadores de referencias cruzadas
- `compare_translations(book_num, chapter, verse, languages=None)` — Mismo versículo en varios idiomas

### Índice temático (Fase 4)

- `search_topic_index(query, language="E", limit=10)` — Busca temas en el Índice de Publicaciones Watch Tower
- `get_topic_articles(docid_or_url, language="en")` — Parsea una página de tema completa

### Texto offline EPUB + metadata JWPUB (Fase 5)

- `extract_epub_text(epub_path, max_docs=0)` — Parsea un .epub descargado y devuelve su texto completo
- `inspect_jwpub_metadata(jwpub_path)` — Metadata + TOC de un .jwpub (el contenido cifrado no se decodifica)
- `ingest_epub(epub_path, publication_code="", language="en")` — Indexa el EPUB en el RAG local

### RAG (Fase 6)

- `semantic_search(query, top_k=5, mode="hybrid")` — Búsqueda híbrida (BM25 + cosenos + RRF) sobre el store local
- `ingest_bible_chapter(book_num, chapter, language="en")` — Indexa un capítulo
- `ingest_search_topk(query, top_n=5, filter_type="all", language="E")` — Indexa los top N resultados de búsqueda

### Agentes de alto nivel (Fase 7)

- `verse_explainer(reference, language="en", max_paragraphs=5)` — Explica un versículo con contexto + cross-refs
- `research_topic(topic, language="E", top_n=5, fetch_top_k=3)` — Investigación multipaso de un tema
- `meeting_helper(input_text, language="en", max_paragraphs=8)` — Prep de reuniones desde URL o ref bíblica
- `apologetics(question, language="E", web_top_k=3, use_rag=True, rag_top_k=5)` — Respuesta doctrinal con citas de jw.org

## Ejecutar

```bash
uv run jw-mcp
```

El servidor habla MCP sobre stdio (transporte por defecto).

## Configuración de Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "jw": {
      "command": "uv",
      "args": ["--directory", "/ruta/absoluta/a/jw-agent-toolkit", "run", "jw-mcp"]
    }
  }
}
```

## Variables de entorno

- `JW_RAG_STORE_PATH` — Ruta del directorio donde persiste el store RAG.
  Por defecto: `~/.jw-agent-toolkit/rag/`.

## Referencia detallada

Ver [`docs/referencia/jw-mcp.md`](../../docs/referencia/jw-mcp.md) para los contratos completos de cada herramienta (parámetros, formato de retorno, manejo de errores).
