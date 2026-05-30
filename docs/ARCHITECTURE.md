# Arquitectura

> Manual de arquitectura del proyecto. Cubre objetivos, organización en capas, inventario de endpoints externos, decisiones de diseño clave y políticas que se mantienen vigentes a través de todas las fases.

## Objetivos

1. **Fuente única de verdad** para el acceso a contenido de jw.org / wol.jw.org en Python.
2. **Desacoplar** el acceso a datos (`jw-core`) de las superficies de exposición (`jw-cli`, `jw-mcp`) y de los comportamientos de alto nivel (`jw-rag`, `jw-agents`).
3. **Citas siempre verificables**: cada respuesta de cualquier agente debe poder enlazarse a una URL de wol.jw.org.
4. **Sin LLM en el camino crítico**: los parsers, clientes y agentes son determinísticos. La síntesis con LLM ocurre fuera del toolkit (Claude Desktop, Claude Code, tu propio cliente).

## Organización en capas

```
┌──────────────────────────────────────────────────────────────────────┐
│   Skills (Markdown)             Agentes (orquestación multi-paso)    │
│   skills/jw-*/SKILL.md          packages/jw-agents/                  │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│        Superficies                                                   │
│        • CLI            packages/jw-cli/   (Typer + Rich)            │
│        • Servidor MCP   packages/jw-mcp/   (FastMCP)                 │
│        • RAG            packages/jw-rag/   (vector + BM25 + RRF)     │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│        jw-core (librería)                                            │
│        ├─ clients/    cdn.py · mediator.py · wol.py                  │
│        │              pub_media.py · topic_index.py                  │
│        ├─ parsers/    reference.py · article.py · daily_text.py      │
│        │              verse.py · study_notes.py · topic_index.py     │
│        │              jwpub.py (Fase 5, pendiente)                   │
│        ├─ data/       books.py (66 libros × 3 idiomas)               │
│        ├─ models.py   BibleRef · Verse · StudyNote · CrossReference  │
│        │              TopicSubject · TopicSubheading · TopicCitation │
│        └─ languages.py                                               │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                          jw.org / wol.jw.org / b.jw-cdn.org
                          data.jw-api.org/mediator
```

**Las dependencias fluyen hacia abajo únicamente**. Cada paquete depende de `jw-core` (y `jw-rag` también es usado por `jw-agents` y por `jw-mcp`).

Reglas duras:

- `jw-core` no importa nada del resto del workspace.
- `jw-rag` puede importar `jw-core` (clientes para el ingest).
- `jw-agents` puede importar `jw-core` y `jw-rag`.
- `jw-cli` puede importar `jw-core` (no agentes — los agentes viven detrás del MCP por ahora).
- `jw-mcp` puede importar todos los anteriores y es el único que liga el RAG global.

## Inventario de endpoints JW.org

| Endpoint | Método | Auth | Envuelto por |
|---|---|---|---|
| `b.jw-cdn.org/tokens/jworg.jwt` | GET | — | `clients.cdn.CDNClient._get_token` |
| `b.jw-cdn.org/apis/search/results/{lang}/{filter}?q=` | GET | JWT | `clients.cdn.CDNClient.search` |
| `b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS` | GET | — | `clients.pub_media.PubMediaClient.get_publication` |
| `data.jw-api.org/mediator/v1/languages/{lang}/web` | GET | — | `clients.mediator.MediatorClient.list_languages` |
| `data.jw-api.org/mediator/finder?lang=&item=` | GET | — | `clients.mediator.MediatorClient.find_item` |
| `wol.jw.org/{iso}/wol/b/{resource}/{lp_tag}/{pub}/{book}/{ch}` | GET | — | `clients.wol.WOLClient.get_bible_chapter` |
| `wol.jw.org/{iso}/wol/d/{resource}/{lp_tag}/{docId}` | GET | — | `clients.wol.WOLClient.fetch` y `TopicIndexClient.get_subject_page` |
| `wol.jw.org/{iso}/wol/h/{resource}/{lp_tag}` | GET | — | `clients.wol.WOLClient.get_today_homepage` |
| `wol.jw.org/{iso}/wol/bc/{resource}/{lp_tag}/{doc}/{group}/{index}` | GET | — | `clients.wol.WOLClient.get_cross_reference_panel` |

**Formato JWPUB (offline)**: ZIP → `manifest.json` + ZIP interno → imágenes + SQLite `.db` con columna `Document.Content` comprimida. Decodificarlo es la Fase 5.

Para el detalle de cada endpoint (parámetros, respuestas, ejemplos), ver [`docs/conceptos/inventario-endpoints.md`](conceptos/inventario-endpoints.md).

## Por qué monorepo

- **Tipos compartidos** (`BibleRef`, `Article`, `StudyNote`, etc.) cambian con frecuencia al inicio; el overhead de PRs cross-repo sería caro.
- **Commits atómicos** a través de core + MCP + tests.
- Un único `uv.lock` hace los instalables reproducibles para CI y contribuidores.
- Cada `packages/*` sigue siendo **publicable independientemente** a PyPI cuando esté estable.

## Estrategia de idiomas

Multi-idioma desde el día 1, pero sin pretender que todos sean iguales:

- **Nivel 1 (parser, URLs, herramientas)**: Inglés (E), Español (S), Portugués (T).
- **Nivel 2 (solo construcción de URLs)**: cualquier idioma registrado en `languages.py`.
- **Nivel 3 (fallback elegante)**: idioma desconocido → inglés.

El parser de referencias tiene una limitación documentada: cuando dos idiomas comparten una ortografía idéntica tras quitar acentos (p.ej. "Corintios" ≈ "Coríntios"), gana el primer idioma registrado para `detected_language`. El número de libro siempre es correcto.

Detalles completos en [`docs/conceptos/estrategia-multi-idioma.md`](conceptos/estrategia-multi-idioma.md).

## Diseño del parser de referencias

Ver `packages/jw-core/src/jw_core/parsers/reference.py`. Decisiones clave:

1. **Regex maestra única** construida desde `BOOKS` en tiempo de import, con alternativas ordenadas de mayor a menor longitud para evitar que "John" gane sobre "1 John".
2. **Matching en dos etapas**: la regex captura el texto del libro normalizado; un lookup por clave despojada obtiene el número de libro e idioma.
3. **Idempotente**: cacheado como singleton a nivel de módulo vía `lru_cache`.
4. **Sin I/O**: puro CPU. Seguro de llamar dentro de handlers MCP.

## Política de citas (Phase 4+)

Cada `Finding` que produce un agente carga `metadata['source']`, que sirve para que el LLM llamante haga ranking por autoridad:

```
topic_index             # Índice de Publicaciones Watch Tower
> topic_index_entry     # Subtítulos del índice
> question_refs         # Citas explícitas en la pregunta del usuario
> verse_text            # Texto del versículo enriquecido
> study_note            # Notas de estudio nwtsty
> cdn_search            # Resultados de búsqueda CDN
> rag                   # Corpus local RAG
```

El agente `apologetics` aplica este ranking implícitamente al orden en que añade findings.

## Superficie de herramientas MCP

| Fase | Herramientas |
|---|---|
| 1 — Núcleo | `resolve_reference`, `get_chapter`, `get_daily_text`, `search_content`, `get_article` |
| 2 — Media | `list_languages`, `list_publication_files`, `download_publication` |
| 3 — Notas | `get_verse`, `get_study_notes`, `get_cross_references`, `compare_translations` |
| 4 — Temas | `search_topic_index`, `get_topic_articles` |
| 5 — EPUB / JWPUB | `extract_epub_text`, `inspect_jwpub_metadata`, `ingest_epub` |
| 6 — RAG | `semantic_search`, `ingest_bible_chapter`, `ingest_search_topk` |
| 7 — Agentes | `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics` |

Total: 24 herramientas. Contratos completos en [`docs/referencia/jw-mcp.md`](referencia/jw-mcp.md).

## Manejo de errores

Cada cliente HTTP tiene su propia excepción base:

- `CDNError` (clients.cdn)
- `WOLError` (clients.wol)
- `MediatorError` (clients.mediator)
- `PubMediaError` (clients.pub_media)
- `TopicIndexError` (clients.topic_index)

Todas heredan de `RuntimeError` y se elevan en lugar de devolver `None` para errores HTTP. Las herramientas MCP capturan estas excepciones y devuelven un dict `{"error": "..."}` en lugar de propagar — esto mantiene la sesión MCP viva ante fallos transitorios.

Los parsers son tolerantes: devuelven listas vacías o `None` ante HTML mal formado, sin levantar excepciones.

## Lo que deliberadamente NO está aquí (todavía)

- **Decodificación del `Content` cifrado del JWPUB** (la metadata sí se extrae; el texto cifrado AES-CBC no es accesible — la derivación de clave no es pública). Workaround: usar EPUB, que cubre el mismo material moderno sin cifrado. Ver ROADMAP — Fase 5.
- **Resolución código de publicación → URL** (p.ej. "g05 4/22 7" → URL real). Requiere `GETPUBMEDIALINKS` + un mapeo código → pub-code.
- **Cache persistente en disco** (Fase 9).
- **Rate limiting** (confiamos en uso educado durante desarrollo).
- **Logging estructurado / telemetría** (Fase 9).
- **Embedders reales** (la interfaz `Embedder` está; los providers OpenAI / sentence-transformers son opcionales y los conecta el usuario).

## Nota de licencia

Parte del código en `jw-core/clients/` está informado por, pero no copia, `jwlib` (allejok96, GPL-3.0). El toolkit completo es GPL-3.0-only, así que la reutilización directa de snippets de `jwlib` sería compatible en licencia si fuera necesaria en fases posteriores.
