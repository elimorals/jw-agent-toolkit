# Hoja de ruta

> Roadmap **operacional**: cubre las fases ya entregadas (0-10). Para visión de producto a largo plazo (Fases 11+: reunión semanal, ministerio, TTS, multimodalidad, etc.) ver [VISION.md](VISION.md).

Leyenda de estado: ✅ hecho · 🚧 en progreso · ⬜ planeado

## Fase 0 — Configuración ✅

- ✅ Monorepo con `uv workspace`
- ✅ Andamiaje de paquetes (`jw-core`, `jw-cli`, `jw-mcp`, `jw-rag`, `jw-agents`)
- ✅ Tooling: ruff, mypy, pytest
- ✅ Workflow de CI (`.github/workflows/ci.yml`) — añadido en Fase 10

## Fase 1 — Núcleo + MVP del MCP ✅

- ✅ `jw-core.models.BibleRef`
- ✅ `jw-core.data.books` — 66 libros × 3 idiomas
- ✅ `jw-core.parsers.reference` — parser multiidioma de citas bíblicas
- ✅ `jw-core.clients.cdn` — cliente CDN con autenticación JWT + búsqueda
- ✅ `jw-core.clients.wol` — cliente WOL (capítulo, página de hoy, fetch arbitrario)
- ✅ `jw-core.parsers.article` — wol HTML → `Article` estructurado
- ✅ `jw-core.parsers.daily_text` — texto diario desde la homepage de WOL
- ✅ Servidor `jw-mcp` con 5 herramientas (resolve_reference, get_chapter,
  get_daily_text, search_content, get_article)
- ✅ Suite de pruebas (44 passing)

## Fase 2 — CLI + media + pub-media ✅

- ✅ `jw-cli` con Typer: `jw verse`, `jw search`, `jw daily`, `jw download`,
  `jw languages`, `jw chapter`
- ✅ `jw-core.clients.pub_media` — `GETPUBMEDIALINKS` para descargas y streaming
- ✅ `jw-core.clients.mediator` — listado de idiomas + finder de contenido
- ✅ Herramientas MCP: `download_publication`, `list_languages`, `list_publication_files`
- ✅ El registro de idiomas ahora rastrea por idioma `wol_resource` (`r1` para en,
  `r4` para es, `r5` para pt) y `default_bible` (`nwtsty` para en, `nwt` para
  es/pt). Esta es una corrección específica de español/portugués descubierta
  durante la fase 2 — el MVP anterior solo producía URLs correctas en inglés.

## Fase 3 — Referencias cruzadas y notas de estudio ✅

- ✅ `jw-core.parsers.verse` — extracción limpia de versículos (elimina marcas
  de pronunciación `· ʹ`, números de versículo iniciales, marcadores `+`
  inline, asteriscos `*` de notas al pie)
- ✅ `jw-core.parsers.study_notes` — notas de estudio + marcadores de
  referencias cruzadas desde el HTML de nwtsty, con emparejamiento
  normalizado entre el `headword` (palabra clave de la nota) y el versículo
- ✅ Modelos: `Verse`, `StudyNote`, `CrossReference` (Pydantic)
- ✅ `WOLClient.get_cross_reference_panel(href)` para fetching lazy del panel
- ✅ Herramientas MCP: `get_verse`, `get_study_notes`, `get_cross_references`
  (con `resolve_panel=True` opcional), `compare_translations`
- ✅ Agente `verse_explainer` reescrito: emite findings de versículo objetivo +
  notas de estudio mapeadas al versículo + marcadores de referencias cruzadas
  (en lugar de volcar los primeros N párrafos)
- ✅ Agente `apologetics` enriquecido: cada referencia bíblica en la pregunta
  ahora arrastra el texto del versículo + notas de estudio nwtsty hacia los findings
- ✅ Fixture de pruebas `nwtsty_john3.html` (195KB) + 17 pruebas del parser
  cubriendo normalización de pronunciación, matching headword → versículo,
  y extracción de cross-refs

## Fase 3.5 — Mapeo 100% nota de estudio → versículo ✅

- ✅ Investigación de la hipótesis `data-pid` (descartada: los pids de las
  notas de estudio no coinciden con los pids del cuerpo del capítulo; son
  esquemas de numeración independientes)
- ✅ Mejorado `_tokenize_headword`: divide por cualquier carácter no-word
  (maneja "wind … spirit", "he … was baptizing", em-dashes, etc.)
- ✅ Restricción monotónica en `_find_verse_for_headword`: cada match debe ser
  >= al versículo coincidente anterior (previene desviación por colisión de
  headwords)
- ✅ Fallback relajado cuando min_verse bloquea un match real (red de seguridad)
- ✅ Interpolación posicional para headwords genuinamente sin match, con campo
  `confidence` en `StudyNote` para señalar la calidad del estimado
- ✅ Resultado John 3: 18 de 18 notas matched por headword (100%, antes 83%)
- ✅ 5 nuevas pruebas cubriendo monotonicidad, ellipsis y fallback posicional

## Fase 4 — Índice de Publicaciones (Topic Index / Guía de Investigación) ✅

- ✅ Modelos: `TopicSubject`, `TopicSubheading`, `TopicCitation` (Pydantic)
- ✅ `jw-core.parsers.topic_index` — parsea la estructura `<p class="st|sa|su|sv">`
  de una página de tema; separa referencias bíblicas (anchors `<a class="b">`
  enlazados) de códigos de publicación (texto plano)
- ✅ `jw-core.clients.topic_index.TopicIndexClient`:
  - `search_subjects(query)` — búsqueda en CDN con `filter='indexes'`,
    extrae docid tanto de URLs estilo path como estilo query
  - `get_subject_page(docid_or_url)` — fetch y parseo de página de tema
- ✅ Herramientas MCP: `search_topic_index`, `get_topic_articles`
- ✅ El agente `apologetics` ahora consulta el índice temático PRIMERO
  (fuente autoritativa JW), luego refs explícitas, luego búsqueda CDN,
  luego RAG
- ✅ Fixtures `wt_pub_index_trinity.html` (73KB), `wt_pub_index_home.html`,
  `wt_research_guide.html` + 11 pruebas del parser
- ✅ Verificación en vivo: el tema "Trinity" devuelve 185 subtítulos, 563 citas
- ⬜ Resolución código de publicación → URL (p.ej. "g05 4/22 7" → URL real del
  artículo). Requiere la API `GETPUBMEDIALINKS` de la fase 2 + un mapeo
  código → pub-code. Hoy el LLM recibe solo el texto abreviado.
- ⬜ Páginas de temas con entradas estilo "título de artículo" (p.ej.
  "Religions, Customs, and Beliefs") parsean con `citations=0`; el formato
  difiere de las páginas estilo Trinity. Caso límite para v0.4.

## Fase 4.5 / 4.6 / 4.7 — Mejoras del índice temático ✅

- ✅ **4.5 Códigos de publicación con URL**: los `<a>` sin clase dentro de
  páginas de tema apuntan al panel `/pc/`. Todas las citas (Biblia + publicaciones)
  ahora salen del parser con URL absoluta, no solo las refs bíblicas.
- ✅ **4.6 Páginas estilo "título de artículo"**: nuevo formato detectado en
  subjects como "Religions, Customs, and Beliefs" — una entrada por párrafo,
  sin `:`. El parser lo identifica vía heurística (>60% de subheadings con un
  único `<a>` y sin `;`) y separa título/publicación con marcadores conocidos
  ("The Watchtower", "Awake!", "Good News", etc.). `TopicSubject.style` ahora
  reporta `"trinity"` o `"article_title"`.
- ✅ **4.7 Ranking de búsqueda por título**: post-procesado de
  `search_subjects` con score 0-100 (100 match exacto, 80 startswith-word, 60
  whole-word, 40 substring, 20 token). En la query "Trinity" el subject TRINITY
  ahora sube de rank #3 a rank #1.

## Fase 5 — Texto offline (EPUB + metadata JWPUB) ✅

Pivote pragmático: el `Content` del JWPUB está cifrado AES-CBC con derivación
de clave no documentada públicamente (ver "Limitación documentada" abajo). En
vez de bloquearnos, abrimos el mismo outcome (indexación offline) vía **EPUB**,
el formato hermano abierto que JW publica para casi todas sus publicaciones
recientes.

- ✅ `jw-core.parsers.epub` — parser EPUB 3 estándar (container.xml → OPF →
  spine → XHTML). Extrae título, creador, idioma, identifier y por cada
  documento del spine: título, href, párrafos. Usa `lxml-xml` para evitar el
  warning XMLParsedAsHTMLWarning.
- ✅ `jw-core.parsers.jwpub` — extractor de metadata JWPUB. Lee `manifest.json`
  + tabla `Document` (sin `Content` cifrado). Expone: title, symbol,
  publication_type, year, manifest_hash, schema_version, document_count, y por
  documento: id, MEPS id, title, toc_title, chapter_number, section_number,
  paragraph_count, page range, content_length. `decrypted_text_available=False`
  siempre — declara explícitamente que el texto no está disponible.
- ✅ Modelos: `Epub`, `EpubDocument`, `JwpubMetadata`, `JwpubDocument` (Pydantic)
- ✅ `jw-rag.ingest.ingest_epub(store, epub_path, ...)` — pipeline completo:
  parse → chunk → embed → store. Verificado en vivo con `bh_E.epub` (Bible
  Teach, 79 documentos, 1774 párrafos) → 1087 chunks indexados. Búsqueda
  semántica "love" devuelve hits relevantes de capítulos sobre familia,
  esperanza y vida eterna.
- ✅ Herramientas MCP: `extract_epub_text(epub_path)`,
  `inspect_jwpub_metadata(jwpub_path)`, `ingest_epub(epub_path, publication_code, language)`
- ✅ 16 tests nuevos (7 EPUB parser con EPUB sintético en memoria, 4 JWPUB
  metadata con JWPUB sintético en memoria, 5 más en topic_index para 4.5/4.6/4.7)

## Fase 5.5 — Desencriptación JWPUB ✅

El bloqueo inicial se resolvió encontrando el algoritmo en
`gokusander/jwpub-toolkit` (MIT). El derivado de clave usa la
**identidad de la publicación** (no `manifest.hash` ni `MepsDocumentId`,
que era donde habíamos buscado):

```
pub_string = f"{language_index}_{symbol}_{year}"        # ej. "0_ti_1989"
             (+ "_{issue_tag_number}" si distinto de 0)
digest     = SHA-256(pub_string)
material   = digest XOR 11cbb5587e32846d4c26790c633da289f66fe5842a3a585ce1bc3a294af5ada7
key        = material[:16]    # AES-128 key
iv         = material[16:32]  # CBC IV
plaintext  = zlib_inflate(AES-128-CBC-decrypt(content_blob))
```

- ✅ `jw_core.parsers.jwpub.parse_jwpub(path)` — decrypta todos los
  documentos. Devuelve `text` (XHTML) + `paragraphs` (texto plano) por doc.
- ✅ `jw_core.parsers.jwpub._compute_key_iv()` — implementación del
  derivado de clave, con crédito a la fuente.
- ✅ `jw_rag.ingest.ingest_jwpub()` — pipeline: decrypt → chunks → embed → store.
- ✅ Herramientas MCP: `extract_jwpub_text(jwpub_path)`,
  `ingest_jwpub(jwpub_path, language)`. `inspect_jwpub_metadata` queda
  para metadata barata sin decrypt.
- ✅ Live verificado con `ti_E.jwpub` (Trinity brochure, 402 KB):
  14 documentos decryptados, 235 chunks ingestados. Hybrid search por
  "trinity doctrine" devuelve "How Did the Trinity Doctrine Develop?".
- ✅ 3 tests nuevos: key/iv conocido para Trinity brochure (verificación
  exacta de hex), variación por issue_tag_number, fixture live con check
  de "people" en el Foreword.

## Fase 8 — Bundle de skills ✅

- ✅ `skills/jw-verse-lookup/SKILL.md` (fase 1)
- ✅ `skills/jw-research/SKILL.md` (fase 1)
- ✅ `skills/jw-daily-text/SKILL.md` (fase 1)
- ✅ `skills/jw-meeting-prep/SKILL.md` — guía para preparar comentarios y
  estudio semanal a partir de un URL o referencia bíblica.
- ✅ `skills/jw-apologetics/SKILL.md` — guía para responder preguntas
  doctrinales con prioridad de fuentes (topic_index >
  verse_text > study_note > cdn_search > rag) y reglas de citación.

## Fase 9 — Pulido ✅

- ✅ `jw_core.cache.DiskCache` — TTL cache backed por SQLite con WAL,
  lazy eviction, `cleanup_expired()` y `stats()`. Tests de roundtrip,
  expiración, cleanup, stats, clear.
- ✅ `jw_core.throttle.TokenBucket` + `Throttler` — token bucket async
  por host con burst configurable, defaults conservadores para jw.org
  (2 req/s, capacity 5). Tests de burst inmediato, throttling, set_limit.
- ✅ `jw_core.throttle.backoff_delay` — exponential backoff con full
  jitter (estilo AWS). Tests de bounding por cap y crecimiento estadístico.
- ✅ `jw_core.telemetry.Telemetry` — drift detector opt-in (`JW_TELEMETRY_ENABLED`).
  Hashea la SHAPE estructural de respuestas (keys + types + depth), no
  el contenido. Persiste baseline a JSON local; emite warning cuando una
  respuesta no coincide con su baseline (canario para "JW cambió su API").
  Tests de baseline, drift, persistencia entre instancias.
- ⬜ Publicar `jw-core` a PyPI (queda como siguiente paso operacional, no
  bloquea uso interno).

## Fase 10 — Cierre del 100% del plan original ✅

Auditoría detectó 14 gaps respecto al plan original. Todos cerrados.

### Funcionales

- ✅ **`auth.py` separado** (`jw_core/auth.py`): `JWTManager` con `asyncio.Lock`,
  `get_token`, `authorized_headers`, `invalidate`. `CDNClient` lo usa via
  composición.
- ✅ **`jw_core/clients/_polite.py`**: helper compartido `politely_get()`
  que cablea Throttler + DiskCache + Telemetry en cada GET.
- ✅ **Phase 9 integrado en los 5 clientes HTTP** (CDN, WOL, Mediator,
  PubMedia, TopicIndex): todos aceptan `throttler`, `cache`, `telemetry`
  opcionales en el constructor. Default None → comportamiento previo
  intacto. Cada cliente tiene `cache_stats()`.
- ✅ **`jw_core/clients/factory.py`**: `build_clients()` arma una
  `ClientSuite` con los 6 clientes (incluye Weblang) compartiendo
  Throttler+Cache+Telemetry. Listo para producción.
- ✅ **`jw_core/clients/weblang.py`**: nuevo cliente para
  `www.jw.org/{iso}/languages` con `WeblangLanguage` (incluye
  `vernacularName`, `script`, `direction`, `isSignLanguage`,
  `altSpellings` que el mediator no devuelve).
- ✅ **`WOLClient.get_daily_text_by_date(date, language)`**: patrón
  `/dt/{r}/{lp_tag}/{YYYY}/{M}/{D}` para fechas pasadas.
- ✅ **`WOLClient.get_document_by_id(doc_id, language)`**: patrón
  `/d/{r}/{lp_tag}/{docId}` para documentos arbitrarios.
- ✅ **`WOLClient.get_publication_page(pub_code, number, language)`**:
  patrón `/publication/{r}/{lp_tag}/{pub}[/{number}]` para TOC.

### MCP — 3 tools nuevos + 2 parámetros nuevos (total **29** vs 26)

- ✅ `get_cache_stats()` — snapshot del DiskCache (path, total, live, expired).
- ✅ `get_publication_toc(pub_code, language, number)` — TOC genérico.
- ✅ `list_weblang_languages(in_language_iso)` — endpoint `www.jw.org/...`.
- ✅ `get_chapter(..., with_footnotes=True)` — devuelve `study_notes[]` +
  `cross_refs[]` además del texto.
- ✅ `get_daily_text(language, date="YYYY-MM-DD")` — `date` opcional usa
  la ruta `/dt/...`; vacío usa la homepage `/h/`.

### CLI — 2 commands nuevos (total **8** vs 6)

- ✅ `jw jwpub <path> [--extract] [--max N]` — inspecciona JWPUB (TOC) o
  con `--extract` decrypta y muestra los párrafos.
- ✅ `jw topic <query> [--lang E] [--limit 5] [--max-sub 12]` — busca
  topic index, muestra ranking + fetcha el top subject por default.
- ✅ `apps/cli/` y `apps/mcp/` removidos (eran directorios vacíos).

### Infraestructura

- ✅ `.github/workflows/ci.yml`: GitHub Actions con uv + ruff (check +
  format) + mypy (continue-on-error) + pytest + wheel-build smoke +
  bandit security scan. Cache de uv habilitado.
- ✅ `test_polite_get.py` (10 tests): cache key determinístico, cache
  hit/miss, throttler consume token, telemetry shape recording + drift
  detection, smoke check de cada cliente con Phase 9 deps, factory build smoke.
- ✅ `test_cassettes.py` + `conftest.py` + `scripts/record_cassettes.sh`:
  4 endpoints críticos (mediator, weblang, CDN search, pub-media) con
  cassettes pytest-recording. Skip-if-missing por defecto;
  `--record-mode=rewrite` re-graba.
- ✅ **166 tests passing + 4 skipped** (vs 156 al cerrar Fase 9).

---

## Fase 6 — RAG ✅

- ✅ `jw-rag.embed` — protocolo `Embedder` + `FakeEmbedder` determinista
  (los embedders reales son dependencias opcionales: `[openai]`, `[local]`)
- ✅ `jw-rag.chunker` — chunking por párrafos con división de párrafos largos
- ✅ `jw-rag.store.VectorStore` — en memoria + persistencia JSON en disco,
  similitud por cosenos (numpy), BM25 (`rank-bm25`), recuperación híbrida
  vía RRF (Reciprocal Rank Fusion)
- ✅ `jw-rag.ingest` — `ingest_bible_chapter`, `ingest_article`,
  `ingest_search_topk`
- ✅ `jw-rag.retrieve` — `dedup_by_source`, `filter_by_metadata`
- ✅ Herramientas MCP: `semantic_search`, `ingest_bible_chapter`, `ingest_search_topk`
- ⬜ Providers de embedders reales (OpenAI / sentence-transformers) — la
  interfaz está lista; los usuarios cablean el suyo.

## Fase 7 — Agentes ✅

Orquestadores procedurales (no LLM-driven). Cada agente devuelve un
`AgentResult` con `Finding`s estructurados + `Citation`s; el LLM
llamante sintetiza la prosa.

- ✅ `jw-agents.base` — dataclasses `AgentResult`, `Finding`, `Citation`
- ✅ `jw-agents.verse_explainer` — resuelve ref → fetch capítulo → emite
  versículos objetivo + notas de estudio + cross-refs
- ✅ `jw-agents.research_topic` — búsqueda CDN → fetch top K → cosecha extractos
- ✅ `jw-agents.meeting_helper` — URL o ref bíblica → artículo + prompts de prep
- ✅ `jw-agents.apologetics` — combina refs de la pregunta + búsqueda CDN +
  RAG opcional, con índice temático como ancla autoritativa
- ✅ Herramientas MCP: `verse_explainer`, `research_topic`, `meeting_helper`,
  `apologetics`

---

> **Nota sobre orden**: las fases 6 y 7 se completaron antes que 4.5-4.7,
> 5, 5.5 y 9, por eso aparecen al final del documento. El orden lógico de
> los paquetes sigue siendo: 0 → 1 → 2 → 3 → 3.5 → 4 → 4.5-4.7 → 6 → 7 → 5
> → 5.5 → 8 → 9 → 10.

---

## Fase 19 — Integración con la app oficial JW Library ✅

> Objetivo: que el toolkit pueda **operar con la app instalada del usuario** (abrir versículos en ella, leer sus notas, mantener el RAG al día con backups incrementales) sin violar ToS ni la sandbox de la app. Conceptos en [`conceptos/integracion-jw-library.md`](conceptos/integracion-jw-library.md), referencia en [`referencia/integraciones.md`](referencia/integraciones.md).

### Capa 1 — Deep linking (`jwlibrary://`)

- ✅ `jw_core.integrations.jw_library.build_bible_url` — Biblia, ranges, multi-chapter, multi-book.
- ✅ `build_bible_urls` — versos disjuntos → lista de URLs.
- ✅ `build_publication_url` — `?docid=N&par=P&wtlocale=LL`.
- ✅ `build_url_for_ref` — atajo desde `BibleRef`.
- ✅ `open_jw_library` — dispatcher cross-plataforma con `dry_run`, defensa contra URLs no-`jwlibrary://`.
- ✅ Tool MCP `open_in_jw_library`.

### Capa 2 — Backup `.jwlibrary` + sync incremental + catálogo MEPS

- ✅ `jw_core.parsers.jw_library_backup` — parser ZIP defensivo (schema v16 al cierre, soporta v9-v16+).
- ✅ Modelos Pydantic: `BackupContents`, `BackupManifest`, `Location`, `UserNote`, `UserHighlight`, `Bookmark`, `Tag`, `InputField`.
- ✅ `parse_user_data_db` — para leer un `userData.db` standalone (caso macOS FDA).
- ✅ `jw_core.integrations.jw_library_sync` — `SyncState` + `SyncStateStore` + `compute_sync_plan` + `sync_backup_to_rag` con diff por `content_hash` + `last_modified`. Detecta new / updated / deleted. Cleanup de chunks viejos vía nuevo `VectorStore.delete_by_source_ids`.
- ✅ `jw_core.integrations.meps_catalog` — SQLite con `publication` + `document`, `MepsCatalog.resolve_docid` con preferencia de inglés cuando no se especifica idioma.
- ✅ Tools MCP: `import_jw_library_backup`, `list_user_notes`, `ingest_user_notes`, `sync_jw_library_backup`, `register_jwpub_in_catalog`, `find_publication_in_catalog`, `open_publication_by_symbol`.

### Capa 3 — Inspector local

- ✅ `jw_core.integrations.jw_library_local` — opt-in con `JW_LIBRARY_LOCAL_READ=1`.
- ✅ Windows: lectura de `publications.db` en `%LOCALAPPDATA%\Packages\WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_*\LocalState\` con PRAGMA-projected select.
- ✅ macOS Full Disk Access: `check_macos_full_disk_access` (probe con `os.scandir`), `read_macos_userdata` (copia `userData.db` a tempfile y parsea como backup), instrucciones paso a paso cuando TCC bloquea.
- ✅ Tools MCP: `inspect_local_jw_library_tool`, `check_jw_library_full_disk_access`, `read_jw_library_live_userdata`.

### Capa 4 — Coexistencia documentada con otros MCPs

- ✅ Doc en `guias/integracion-jw-library.md` con `claude_desktop_config.json` ejemplo apuntando a `jw-agent-toolkit` + `advenimus/jw-mcp` simultáneamente.

### Tests y cobertura

- ✅ 87 tests nuevos en `packages/jw-core/tests/test_jw_library_{integration,backup,local,sync}.py` y `test_meps_catalog.py`.
- ✅ Suite global: **488 passed, 4 skipped, 0 failed** post-Fase 19.
- ✅ Validación end-to-end real: `open_in_jw_library(reference="Juan 3:16")` despachado contra `/Applications/JW Library.app` con `returncode=0`.

### Próximos pasos posibles (no scopados a esta fase)

- ⬜ UI Automation Windows para casos no cubiertos por el deep link.
- ⬜ AXUIElement macOS para igualar la cobertura de Windows.
- ⬜ Sync inverso (toolkit → app): escribir notas mientras la app no corre. Implica invalidar el sync con cuenta JW.
- ⬜ Parser de `PlaylistItem*` (medios anclados a notas).
- ⬜ Catálogo MEPS pre-poblado: shipping un seed con los pub_codes más comunes para no exigir indexing manual de `.jwpub`.

---

## Fase 20 — Integración con Obsidian (second brain) ✅

> Objetivo: portar las utilidades de manipulación de markdown del plugin `msakowski/obsidian-library-linker` (MIT) como funciones Python puras + REST + plugin Obsidian propio, cerrando el ciclo agente ↔ vault. Conceptos en [`conceptos/integracion-obsidian.md`](conceptos/integracion-obsidian.md), guía paso a paso en [`guias/usar-con-obsidian.md`](guias/usar-con-obsidian.md).

### Capa 1 — Utilidades markdown (linkify + convert + render)

- ✅ `jw_core.integrations.markdown.parse_jwlibrary_url` — URL → `BibleRef` (inverso de `build_bible_url`).
- ✅ `convert_jwpub_bible_url`, `convert_jwpub_publication_url` — `jwpub://b/...` y `jwpub://p/...` → `jwlibrary://`.
- ✅ `convert_jw_links_in_text` — rewrite de markdown completo con counters.
- ✅ `render_markdown_link` — `BibleRef` → `[label](jwlibrary://…)`.
- ✅ `linkify_markdown` con offset-map para preservar acentos, skip de `[…](…)` existentes, fenced code y inline code.
- ✅ `render_verse_block` — 5 templates: `plain`, `link`, `blockquote`, `callout`, `callout-collapsed`.
- ✅ Tools MCP: `linkify_markdown_text`, `convert_jw_links_in_markdown`, `get_verse_as_markdown`.

### Capa 2 — Sign language → spoken base

- ✅ `data.book_locales.SIGN_LANGUAGE_BASE_MAP` (47 lenguas de signos).
- ✅ `languages.get_book_language` resuelve LSM → S, ASL → E, DGS → X, etc.
- ✅ Integrado en el render de labels y en la resolución de URLs.

### Capa 3 — 17 locales de nombres de libros

- ✅ Portados desde `obsidian-library-linker/locale/bibleBooks/` (yamls → JSON).
- ✅ `data/bible_books/{E,S,TPO,F,X,I,U,J,KO,B,C,D,O,FI,TG,VT,CW}.json` — 1122 entries.
- ✅ `data.book_locales.merge_into_books` con prioridad por idioma y `_alias_key` espejo del parser para detectar colisiones (ej. "Ap" → es:Apocalipsis vs vi:Áp-đia).
- ✅ El parser de referencias reconoce ahora 17 idiomas con short/medium/long + aliases comunidad.

### Capa 4 — Sync bidireccional vault ↔ toolkit

- ✅ `jw_core.integrations.obsidian_vault.index_vault_to_rag` — incremental, con sidecar `vault_sync.json`, frontmatter parser mínimo (sin PyYAML), filtros por tag, evict de notas borradas.
- ✅ `export_backup_to_vault` — escribe `.md` por cada `UserNote`, organizados por libro/capítulo o publicación, con frontmatter y deep-link callouts.
- ✅ `VectorStore.delete_by_source_ids` ya disponible (Fase 19).
- ✅ Tools MCP: `index_obsidian_vault`, `export_jw_library_backup_to_vault`.

### Capa 5 — REST API expansion

- ✅ `jw_mcp.rest_api` con 5 endpoints nuevos: `POST /api/v1/linkify`, `/convert_links`, `/verse_markdown`, `/vault/index`, `/vault/export`.
- ✅ CORS permisivo (ya estaba) — preparado para el plugin Obsidian que llama desde Electron/localhost.

### Capa 6 — Plugin Obsidian nativo

- ✅ `apps/obsidian-jw-bridge/` con manifest, package.json, esbuild config, tsconfig, README.
- ✅ `src/main.ts` con 8 comandos (linkify selection/note/vault, convert jwpub, insert verse modal, export backup modal, index vault, health check), settings tab completo, soporte mobile (`requestUrl`).
- ✅ `src/toolkitClient.ts` — thin wrapper REST sin lógica de negocio.

### Tests y cobertura

- ✅ 57 tests nuevos: `test_markdown_utils.py` (40) + `test_obsidian_vault.py` (17).
- ✅ Suite global: **551 passed, 4 skipped, 0 failed** post-Fase 20.

### Próximos pasos posibles (no scopados a esta fase)

- ⬜ Auto-completion in-editor en el plugin (suggester de Obsidian completo).
- ⬜ Templates custom configurables por el usuario.
- ⬜ Modo offline en `get_verse_as_markdown` usando JWPUB local (ya descifrado) en lugar de WOL.
- ⬜ Publicar el plugin al Obsidian Community Plugins registry.
- ⬜ Versión del plugin para Logseq / Foam / otros sistemas markdown.

---

## Fase 23 — Citation integrity / link-rot validator ✅

> Tier 1 infraestructura de confianza. Spec: `docs/superpowers/specs/2026-05-30-fase-23-citation-validator-design.md`.

- ✅ Subpaquete `packages/jw-core/src/jw_core/citations/`.
- ✅ Modelos Pydantic: `CitationCheck`, `CitationReport`, status enums.
- ✅ `CitationValidator` con tres modos: structural (default offline), live (HTTP opt-in), live+drift (compara HTML shape contra snapshots).
- ✅ Reutiliza `MepsCatalog` (Fase 19) para docId↔pub_code y `_shape_hash` (Fase 9) para drift.
- ✅ Fetcher inyectable; adapter `httpx_fetcher` para producción.
- ✅ Concurrencia bounded (`asyncio.Semaphore(4)` por defecto).
- ✅ CLI `jw citations check --urls / --agent-output / --live / --drift / --report / --out`.
- ✅ Tool MCP `validate_citations` con guard `JW_CITATIONS_LIVE=1`.
- ✅ Smoke integration en `verse_explainer` (modo estructural).
- ✅ Lee snapshots de `packages/jw-eval/fixtures/wol_snapshots/` (cross-package read, sin import dependency).
- ✅ Guía `docs/guias/citation-validator.md`.

### Cobertura de tests

- ✅ 25+ tests nuevos en `packages/jw-core/tests/test_citation_validator.py`.
- ✅ 5 tests en `packages/jw-mcp/tests/test_citations_tool.py`.
- ✅ 2 tests en `packages/jw-cli/tests/test_citations_cli.py`.
- ✅ Smoke en `packages/jw-agents/tests/test_agents_e2e.py`.
- ✅ Suite global sin regresiones.

---

## Fase 24 — `study_conductor` + `StudentProgress` (Tier 2) ✅

**Entregado**: agente procedural `study_conductor.prepare_lesson` (no LLM),
store local cifrable `StudentProgressStore`, comandos `jw study {lesson,
log, progress, lessons, goals, directory}`, 4 tools MCP, golden cases L1+L3
en `jw-eval`, guía `docs/guias/conductor-de-estudio.md`.

**Cubre**: VISION.md item #1 («Conductor de Disfruta de la vida para
siempre»).

**No cubre** (post-fase): recordatorios temporales (Fase 25-adjacent),
gráficas (export JSON ya lo habilita externamente), modo familia.

---

## Fase 25 — Monitor de novedades jw.org ✅

> Tier 2 alto valor recurrente. Spec: `docs/superpowers/specs/2026-05-30-fase-25-news-monitor-design.md`.

- ✅ Módulo nuevo `jw_core.news` (`models`, `store`, `sources`, `digest`, `seeds`).
- ✅ Tres `NewsSource`:
  - `PublicationsSource` — seed list × idiomas, periodical/non-periodical.
  - `BroadcastingSource` — `discover_all_videos` sobre `VideoOnDemand`.
  - `ProgramsSource` — `mwb`/`w` para [mes_actual, mes_actual+2).
- ✅ `SeenStore` SQLite en `~/.jw-agent-toolkit/news_seen.db` (`JW_NEWS_SEEN_DB`).
- ✅ Cache TTL: 6h (publications), 24h (broadcasting), 7d (programs).
- ✅ Diff `(new, retired)` + render markdown determinista byte-estable.
- ✅ Agente `news_monitor` (envuelve sources + store en AgentResult).
- ✅ CLI `jw news digest --since {last_run|epoch|ISO} --languages --channels --out --no-update --json`.
- ✅ Tool MCP `news_digest`.
- ✅ Guía `docs/guias/monitor-de-novedades.md` (incluye cron + systemd timers de ejemplo).
- ✅ 1 case L1 nuevo en `jw-eval` (`news_monitor_digest_en`).

### Cobertura de tests

- ✅ ~29 tests nuevos (`test_news_models.py`, `test_news_store.py`, `test_news_sources.py`, `test_news_digest.py`, `test_news_monitor.py`, `test_news_cli.py`).
- ✅ Suite global sin regresiones.

---

## Fase 26 — Asistente de partes del estudiante V&M ✅

> Tier 2 alto valor recurrente. Spec: `docs/superpowers/specs/2026-05-30-fase-26-student-parts-design.md`.

- ✅ 4 tipos de asignación: `bible_reading`, `starting_conversation`, `return_visit`, `bible_study`.
- ✅ 4 audiencias (`default` / `new` / `religious` / `atheist`) × 3 idiomas (`en` / `es` / `pt`) → **48 plantillas** en `jw_core.data.student_parts_templates`.
- ✅ Registro de **50 puntos de oratoria** del folleto *Mejore su predicación* (`th`) en `jw_core.data.oratory_points` (paráfrasis ≤300 chars, `applies_to` por kind, mapping mes→punto).
- ✅ Agente procedural `jw_agents.student_part_helper` — sin LLM, sin red salvo modo `"this week"` (delegado al workbook scraper, Fase 11).
- ✅ Salida AgentResult con exactamente 4 findings (`opening` / `body` / `transition` / `close`), `time_target_seconds`, `oratory_point_applied`, citation por sección (`verse` o `topic_anchor`).
- ✅ CLI `jw student <kind> <topic_or_ref> --lang --audience --point --json` con aliases (`reading`/`conversation`/`revisit`/`study`).
- ✅ Tool MCP `student_part_help`.
- ✅ 4 golden cases L1 (uno por kind): `student_part_bible_reading_es`, `student_part_conversation_en`, `student_part_return_visit_pt`, `student_part_bible_study_es`.
- ✅ Guía `docs/guias/partes-del-estudiante.md`.

### Cobertura de tests

- ✅ **34 tests nuevos** (`test_oratory_points.py` 11 · `test_student_parts_templates.py` 9 · `test_student_part_helper.py` 14).
- ✅ Suite global sin regresiones.

**Cubre**: VISION.md item #2 («Ministerio / predicación») — pieza recurrente de Vida y Ministerio.

## Fase 27 — Informe mensual de precursor

- ✅ `jw_core.data.field_service_tags` con vocabulario controlado + override JSON.
- ✅ `jw_core.ministry.field_report.FieldReportStore` SQLite con cifrado columnar (`note`, `student_id`).
- ✅ `HoursEntry` + `StudyEntry` + `MonthlyReport` Pydantic models.
- ✅ `aggregate_monthly_report` con regla MAX para estudios activos y redondeo de display a 5 min.
- ✅ `RevisitProvider` Protocol inyectable; CLI/MCP usan adapter read-only sobre `RevisitStore` (Fase 12).
- ✅ Exporters: `render_markdown`, `render_csv`, `render_pdf` (PDF detrás de `[pdf]` extra).
- ✅ CLI `jw report` con sub-sub `log-hours`, `log-study`, `met-today`, `show`.
- ✅ MCP tools: `field_log_hours`, `field_log_study`, `field_monthly_report`.
- ✅ Tests: 100% paths, `test_field_report.py` con fakes para revisitas y test de encriptación raw-row.
- ✅ Guía `docs/guias/informe-precursor.md`.

### Fase 28 — Concordancia exacta NWT + publicaciones ✅

- `jw_core.concordance` con SQLite FTS5 y dedupe por sha256.
- Indexer adapters: NWT chapters (HTML), JWPUB descifrado, EPUB.
- CLI `jw grep "<phrase>"` con `--build-index`, `--build-nwt`, `--stats`, `--kind`, `--language`.
- MCP tools `concordance_build_index` y `concordance_search`.
- Guía: [`docs/guias/concordancia-exacta.md`](guias/concordancia-exacta.md).

### Fase 29 — Compositor de carta / teléfono / carrito (Tier 4) ✅

- Agente `letter_composer` con 3 modalidades × 7 audiencias × 8 familias temáticas.
- Salida estructurada (`opener · bridge · scripture · closing`), copyright-safe.
- CLI `jw letter`, tool MCP `compose_witnessing`, 3 golden cases L1.
- Guía: [`docs/guias/compositor-de-predicacion.md`](guias/compositor-de-predicacion.md).
- Spec / plan: `docs/superpowers/specs/2026-05-30-fase-29-letter-composer-design.md`.

---

## Fase 30 — Compañero de cánticos del Reino ✅

> Objetivo: registro local de metadatos de Cánticos del Reino (`sjj`) — número, títulos en/es/pt, tema en una línea, referencias bíblicas citadas, URL canónica en jw.org. Sin letra (copyright). Integración opt-in con `workbook_helper`. Spec en [`superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md`](superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md).

- ✅ `jw_core.data.kingdom_songs/{E,S,T}.json` — seed de 12 cánticos paralelos en los 3 idiomas.
- ✅ `jw_core.songs.models.KingdomSong` (Pydantic, máximo 200 chars en `theme`, scriptures parseables).
- ✅ `jw_core.songs.registry.SongRegistry` con `importlib.resources` + `lru_cache` por idioma.
- ✅ `jw_core.songs.integration.enrich_with_songs` — adapter idempotente para `workbook_helper`.
- ✅ Test de integridad anti-letra (`test_seed_integrity`).
- ✅ CLI `jw song <N>` y `jw song week`.
- ✅ Tools MCP `lookup_song`, `songs_for_week`.
- ✅ Guía `docs/guias/canticos-del-reino.md` con sección legal al frente.

---

## Fase 31 — Exportador hoja de estudio (PDF / DOCX / Anki) ✅

> Objetivo: convertir cualquier `AgentResult` en un entregable imprimible (PDF / DOCX / Markdown) o un mazo Anki para repaso espaciado. IR única (`StudySheet`) consumida por cuatro exporters. Dependencias pesadas opt-in vía extras (`[pdf]`, `[docx]`, `[anki]`). Spec en [`superpowers/specs/2026-05-30-fase-31-exporter-design.md`](superpowers/specs/2026-05-30-fase-31-exporter-design.md).

- ✅ `jw_core.exporters.ir.StudySheet` IR Pydantic v2 + `from_agent_result()` conversor único.
- ✅ Markdown exporter con 3 estilos de cita (`inline-paren`, `footnote`, `bibliography`).
- ✅ Jinja2 template resolver con override en `~/.jw-agent-toolkit/templates/` y 2 temas built-in (`plain`, `study-sheet`).
- ✅ PDF exporter vía WeasyPrint (opt-in `[pdf]`).
- ✅ DOCX exporter vía python-docx con hyperlinks reales (opt-in `[docx]`).
- ✅ Anki exporter vía genanki con GUIDs sha256 estables → re-export actualiza, no duplica (opt-in `[anki]`).
- ✅ CLI `jw export <source.json> --format {markdown|pdf|docx|apkg}` con soporte stdin (`-`).
- ✅ Tool MCP `export_study_sheet`.
- ✅ Tests: 45 nuevos (IR · markdown · templates · pdf · docx · anki · CLI · MCP).
- ✅ Guía `docs/guias/exportador-hoja-de-estudio.md`.

---

## Fase 32 — Asistente informativo de temas de vida ✅

> Tier 4 capa UX / nicho. Spec: `docs/superpowers/specs/2026-05-30-fase-32-life-topics-design.md`.

- ✅ Registry de 9 temas (anxiety, grief, marriage_conflict, depression_signs, addictions, doubts_in_faith, parenting, loneliness, conflict_with_brother) con aliases en `en/es/pt`.
- ✅ Disclaimer bilingüe + elders_redirect (sin mencionar profesionales médicos por nombre — boundary deliberada).
- ✅ Agente `life_topics` con disclaimer obligatorio + redirect en temas sensibles.
- ✅ Pipeline: Topic Index → CDN `filter='publications'` → parse_article → previews.
- ✅ Comando CLI `jw life "<query>" --lang en|es|pt`.
- ✅ Tool MCP `life_topic_info`.
- ✅ Golden cases en `jw-eval`: 2 L1 (anxiety_es, parenting_en) + 2 L3 (grief_en, doubts_es).
- ✅ Guía `docs/guias/temas-de-vida.md`.

### Boundary explícita

- El agente nunca fabrica citas bíblicas; solo enlaza versículos presentes en el material matched.
- El agente nunca sustituye consejería pastoral.
- Sin persistencia: stateless por diseño.
- Lista de temas sensibles cerrada — añadir temas requiere PR independiente con justificación.

### Cobertura de tests

- ✅ 11 tests en `packages/jw-core/tests/test_life_topics_data.py`.
- ✅ 8 tests en `packages/jw-core/tests/test_life_disclaimers.py`.
- ✅ 9 tests en `packages/jw-agents/tests/test_life_topics.py`.
- ✅ 2 tests en `packages/jw-cli/tests/test_life_cmd.py`.
- ✅ 2 tests en `packages/jw-mcp/tests/test_life_topic_tool.py`.
- ✅ Suite global sin regresiones.

---

## Fase 22 — Eval doctrinal regresión ✅

> Tier 1 infraestructura de confianza. Spec: `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.

- ✅ Paquete nuevo `packages/jw-eval/`.
- ✅ Modelos Pydantic: `GoldenCase`, `LayerResult`, `SuiteReport`.
- ✅ YAML loader recursivo con filtro por capa.
- ✅ Layer 1 (structural): contract regression sobre agentes.
- ✅ Layer 2 (citations): snapshot (offline, bloqueante CI) + live (weekly, abre issues).
- ✅ Layer 3 (semantic): embeddings (sentence-transformers opcional, FakeEmbedder default) + escalada LLM (Ollama default, Claude/OpenAI opt-in).
- ✅ 12 cases L1 + 12 cases L2 + 6 cases L3 = 30 cases iniciales (más fixtures parqueadas de fases 24-32: ~22 extra).
- ✅ Reporter markdown + JSON.
- ✅ CLI `jw eval --layer 1,2,3 --live --report md --out file`.
- ✅ Tool MCP `run_eval_suite`.
- ✅ CI jobs: `eval-fast` (bloqueante), `eval-l2-live` (weekly), `eval-nightly` (no-block).
- ✅ Script `build_eval_snapshots.py` + `eval_open_drift_issues.py`.
- ✅ Guía `docs/guias/eval-doctrinal.md`.

### Cobertura de tests

- ✅ 26 tests nuevos en `packages/jw-eval/tests/`.
- ✅ 1 test MCP en `packages/jw-mcp/tests/test_eval_tool.py`.
- ✅ Suite global sin regresiones.

---

## Fase 33 — embed-rerank: núcleo RAG al SOTA ✅

> Tier 1 núcleo. Spec: `docs/superpowers/specs/2026-05-31-fase-33-embed-rerank-design.md`.

- ✅ `EmbedProvider` Protocol + `Target` literal (api/mlx/nvidia/cpu).
- ✅ 6 embed providers: BGE-M3, Multilingual-E5, Jina-v3, Cohere-v3, Voyage-multilingual-2, Ollama (nomic-embed-text).
- ✅ Fake sibling por cada provider — deterministic, used by tests.
- ✅ `Reranker` Protocol + `NoOpReranker` fallback.
- ✅ 3 rerank providers reales: BGE-reranker-v2-m3, Cohere-rerank-v3.5, Jina-reranker-v2.
- ✅ Factory con auto-detect + env override (`JW_EMBED_PROVIDER`, `JW_RERANK_PROVIDER`, `JW_PROVIDER_ORDER`).
- ✅ `VectorStore.hybrid_search(rerank=True, reranker=None, candidate_pool=50)` — backwards-compatible.
- ✅ Param MCP `semantic_search(rerank: bool = True)`.
- ✅ Lazy SDK loading; cero red en import time; safe_repr para API keys.
- ✅ Extras pyproject: `[embeddings-local]`, `[embeddings-api]`, `[rerank-local]`, `[rerank-api]`.
- ✅ Guía `docs/guias/embeddings-y-rerank.md`.

### Cobertura de tests

- ✅ ~50 tests nuevos en `packages/jw-rag/tests/`.
- ✅ 1649 tests previos sin regresión.
- ✅ Markers `@pytest.mark.embeddings_local` y `@pytest.mark.rerank_local` para tests con descargas reales.

---

## Fase 34 — `audio-premium` ✅

> Audio upgrade. Spec: `docs/superpowers/specs/2026-05-31-fase-34-audio-premium-design.md`.

- ✅ Kokoro-82M (local, multilingüe) como TTS default
- ✅ ElevenLabs TTS opt-in (env key)
- ✅ XTTSv2 voice-cloning con doble opt-in + consent.txt (Política #6)
- ✅ F5-TTS experimental (nvidia primary)
- ✅ Whisper Turbo + auto-select por VRAM (`hardware.recommend_model_size()`)
- ✅ Deepgram ASR opt-in (env key, SDK + httpx fallback)
- ✅ Providers originales `system`/`edge`/`piper` intactos
- ✅ Nuevos comandos `jw say` y `jw transcribe`
- ✅ Nuevas tools MCP `synthesize_speech` y `transcribe_audio`
- ✅ Guía `docs/guias/audio-premium.md`
- ✅ Extras opt-in: `tts-kokoro`, `tts-xtts`, `tts-f5`, `tts-elevenlabs`,
  `asr-deepgram`, `asr-turbo`, `tts-premium`, `asr-premium`, `audio-premium`

### Cobertura de tests

- ✅ 6 tests `test_audio_hardware.py` (target detection + recommend).
- ✅ 5 tests `test_tts_kokoro.py` + 5 `test_tts_xtts.py` + 5 `test_tts_f5.py` + 5 `test_tts_elevenlabs.py`.
- ✅ 5 tests `test_asr_whisper_turbo.py` (4 + 1 skipped sin faster-whisper) + 5 `test_asr_deepgram.py`.
- ✅ 6 tests `test_audio_factory.py` (chain + JW_TTS_PROVIDER).
- ✅ Suite global sin regresiones.

---

## Fase 35 — Constrained decoding ✅

> Tier 2 habilitador transversal. Spec: `docs/superpowers/specs/2026-05-31-fase-35-constrained-decoding-design.md`.

- ✅ `jw_core.grammar`: builders GBNF, Pydantic → GBNF, regex anclada a `wol.jw.org`.
- ✅ Pydantic mirror `AgentResultModel` con conversión bidireccional al dataclass.
- ✅ Factory `get_default_constrained_caller(provider="auto"|...)` con fallback seguro a `FakeConstrainedCaller`.
- ✅ `OllamaAdapter` extendido con `grammar=` y `json_schema=` (back-compat).
- ✅ `AnthropicAdapter` (tool-use) — extra `[grammar-claude]`.
- ✅ `OpenAIAdapter` (response_format json_schema strict) — extra `[grammar-openai]`.
- ✅ `LlamaCppAdapter` (in-process GBNF nativo) — extra `[grammar-local]`.
- ✅ Helper `run_with_citations()` con reconciliación contra forja.
- ✅ Property test Hypothesis: 100 prompts adversarios → 0 violaciones.
- ✅ CLI `jw constrained ask` + tool MCP `run_constrained`.
- ✅ Guía `docs/guias/constrained-decoding.md`.

### Cobertura de tests

- ✅ ~30 tests nuevos en `packages/jw-core/tests/` + `packages/jw-agents/tests/` + `packages/jw-cli/tests/` + `packages/jw-mcp/tests/`.
- ✅ Property test cubre el contrato schema↔grammar↔sampler↔schema.
- ✅ Suite global sin regresiones.

---

## Fase 36 — `vlm-ocr` ✅

> Tier 1 visual upgrade. Spec: `docs/superpowers/specs/2026-05-31-fase-36-vlm-ocr-design.md`.
> Plan: `docs/superpowers/plans/2026-05-31-fase-36-vlm-ocr-plan.md`.

- ✅ `StructuredBlock` + `StructuredPage` Pydantic models (`jw_core.vision.vlm`).
- ✅ `VLMProvider` Protocol con triple-target taxonomy (`api` / `mlx` / `nvidia` / `cpu`).
- ✅ 6 providers concretos:
  - `FakeVLMProvider` (deterministic, used by tests).
  - `ClaudeVisionProvider` (adapter sobre `anthropic` SDK — Claude 4.5/4.6/4.7 son nativamente multimodales).
  - `OpenAIVisionProvider` (adapter sobre `openai` SDK).
  - `Qwen3VLAPIProvider` (httpx contra DashScope / Replicate).
  - `Qwen3VLProvider` local con backends `_MLXBackend`, `_VLLMBackend`, `_GGUFBackend`.
  - `TesseractFallbackProvider` que emite `DeprecationWarning` y envuelve el legacy `ocr_image()`.
- ✅ Factory `get_default_provider()` + `JW_VLM_PROVIDER` env override.
- ✅ `extract_bible_reference_from_image_v2()` — replacement v2 con `StructuredPage`.
- ✅ `jw_rag.ingest_image()` — one chunk per StructuredBlock; `bible_ref` blocks carry `parsed_reference`.
- ✅ CLI `jw image extract|ingest`.
- ✅ MCP tools `extract_structured_page` + `ingest_image_to_rag`.
- ✅ `migrate_to_vlm()` helper devuelve un callable drop-in con la misma firma que `ocr_image()`.
- ✅ Extras opt-in: `vlm-anthropic`, `vlm-openai`, `vlm-api-qwen`, `vlm-mlx`, `vlm-nvidia`, `vlm-cpu`, `vlm-tesseract`.
- ✅ Guía `docs/guias/vlm-ocr.md`.

### Cobertura de tests

- ✅ 8 `test_vlm_models.py` + 6 `test_vlm_provider_fake.py` + 5 `test_vlm_provider_claude.py`.
- ✅ 3 `test_vlm_provider_openai.py` + 3 `test_vlm_provider_qwen_api.py` + 4 `test_vlm_provider_qwen_local.py`.
- ✅ 4 `test_vlm_provider_tesseract_fallback.py` + 5 `test_vlm_factory.py` + 3 `test_vlm_extract_v2.py`.
- ✅ 4 `test_ingest_image.py` (jw-rag) + 2 `test_command_image.py` (jw-cli) + 2 `test_mcp_vlm_tools.py` (jw-mcp).
- ✅ 4 `test_vlm_real.py` opt-in con `@pytest.mark.vlm_real` (skipped sin env keys / hardware).


## Fase 37 — colpali-visual

Multi-vector store con ColPali/ColQwen2 sobre páginas rasterizadas, fusionado
vía RRF con el RAG textual. Opt-in `[visual]` / `[visual-mlx]`. Spec:
`docs/superpowers/specs/2026-05-31-fase-37-colpali-visual-design.md`. Plan:
`docs/superpowers/plans/2026-05-31-fase-37-colpali-visual-plan.md`.
Guía: `docs/guias/visual-rag.md`.


## Fase 38 — jw-gen (séptimo paquete)

Generación ilustrativa para uso personal con tres safety filters y policy
fail-closed. Spec: `docs/superpowers/specs/2026-05-31-fase-38-jw-gen-design.md`.
Plan: `docs/superpowers/plans/2026-05-31-fase-38-jw-gen-plan.md`.
Guía: `docs/guias/generacion-ilustrativa.md`.


## Fase 48 — wol-browser-extension (nueva superficie web) ✅

> Tier 4 nueva superficie. Spec: `docs/superpowers/specs/2026-05-31-fase-48-wol-browser-ext-design.md`. Guía: `docs/guias/wol-browser-ext.md`.

Extensión MV3 para Chrome/Edge/Firefox que añade 3 botones inline a cada
versículo en `wol.jw.org`:

- ✅ **📖 Explicar** → `POST /api/v1/verse_markdown`
- ✅ **🔗 Referencias cruzadas** → `POST /api/v1/cross_references` *(endpoint nuevo)*
- ✅ **📝 Guardar en Obsidian** → `POST /api/v1/vault/append` *(endpoint nuevo, con `.obsidian/` marker check + path-traversal defense)*

Privacidad por construcción — 3 capas:
1. Manifest v3 `host_permissions=["http://localhost:8765/*"]`.
2. Runtime `JwApiClient.assertLocal()` guard.
3. CI `tests/playwright/privacy.spec.ts` (BLOCKING) — rompe la build si aparece cualquier URL externa.

Backend hardening incluido en la misma fase:
- ✅ CORS tightening: de `allow_origins=["*"]` a `["https://wol.jw.org"]` + regex `(chrome|moz)-extension://` only.
- ✅ Nuevo `POST /api/v1/cross_references` con tolerancia de red (vacío + error string en lugar de 5xx).
- ✅ Nuevo `POST /api/v1/vault/append` con guard `.obsidian/` marker check, `subdir.resolve().relative_to(vault)` para bloquear `..`, rechaza `/` y `~` literal.

### Cobertura de tests

- ✅ **15 tests Python nuevos** (6 CORS + 3 cross_references + 6 vault/append).
- ✅ **34 tests vitest verde** sobre la extensión: manifest contract (5) + JwApiClient con fetch mock (7) + verse_detector (6) + button_injector (5) + i18n (6) + content_script (2) + popup (2) + no-external-URL static guard (1).
- ✅ ESLint flat config v9 con `no-restricted-syntax` que prohíbe `fetch()` fuera de `src/api.ts` y URL literales no-localhost.
- ✅ Playwright E2E + privacy.spec.ts listos (requieren `pnpm exec playwright install chromium` en CI; el workflow `.github/workflows/wol-extension.yml` lo hace).

### Métricas de bundle

- ✅ dist/ raw: ~20 KB, gzip: ~8 KB.
- ✅ zip de release: 13 KB *(ceiling pactado: 800 KB; 98% headroom).*

## Fase 49 — second-brain

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-06-01-fase-49-second-brain-design.md`.
- **Plan**: `docs/superpowers/plans/2026-06-01-fase-49-second-brain-plan.md`.
- **Guía**: `docs/guias/second-brain.md`.

Nuevo paquete del workspace `packages/jw-brain/` con runtime
Karpathy-style + GraphRAG. Dual backend (DuckDB embebido + Neo4j
opt-in) detrás del mismo Protocol con contract tests parametrizables.
Compiler LLM-driven con dry-run obligatorio + cache content_hash +
provenance per edge. Wiki sobre Obsidian con write-safe contract
extendido de F20 (incluye fix de seguridad sobre el parseo de
frontmatter `human_edited`). CLI `jw brain {init,compile,query,lint,
status,snapshot,list}`. MCP tools `second_brain_*` (5 nuevas).
Multi-tenant via `--brain` flag + `JW_BRAIN_HOME` env + registry
global. `BrainDomain` se conecta via Fase 41 plugin SDK
(`jw_agent_toolkit.brain_domains`) — TJ builtin + financial fixture
prueba la generalidad. CLAUDE.md autogenerado per dominio activo.

### Cobertura de tests

- ✅ **+81 tests** sobre jw-brain (8 backend contract + 7 schema + 6 wiki + 4 parser + 8 extractor/cache + 3 compiler + 7 query + 4 lint + 8 CLI + 6 MCP + 4 domain registry + 7 multi-tenant + 7 CLAUDE.md + 1 smoke).
- ✅ Cero regresiones en suite existente.
- ✅ Cero red en tests: FakeGenProvider + FakeNLIProvider + monkey-patched plugin SDK.
- ✅ Cero LLM real en CI: `JW_GEN_PROVIDER=fake` por default; production wiring opt-in.
- ✅ Security fix de F40 wiki_writer: parseo YAML estricto fail-closed (vs substring match bypaseable).

## Fase 42 — scaffolding

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-06-01-fase-42-scaffolding-design.md`.
- **Plan**: `docs/superpowers/plans/2026-06-01-fase-42-scaffolding-plan.md`.
- **Guía**: `docs/guias/scaffolding.md`.

Dos entregables. **(a)** `create-jw-agent`: scaffolder standalone publicable a
PyPI que genera proyectos plugin listos para CI en <10 min, cableando los
entry-points de la Fase 41 desde el primer commit. Soporta 5 tipos (`agent`,
`parser`, `embedder`, `vlm`, `gen`), valida nombres PEP 503 (rechaza prefijo
`jw-*`, reservados core, casing/shape inválido), i18n CLI auto-detectado
(`en`/`es`/`pt` con paridad de claves garantizada por test) y opt-in
`--check-pypi`. **(b)** Cookbook ejecutable: 12 recetas Markdown verificadas
por un plugin nuevo `pytest-cookbook` que detecta bloques ` ```python ` con
markers `# test`, `# test slow`, `# test skip-until-fase=N`. CLI `jw create-agent`
es un thin-wrapper. Defensa en profundidad path-traversal: validación temprana
en `RenderContext.build`, sanitización en `_safe_replace_value` (rechaza `/`,
`\`, `..`, `.`) y verificación final con `Path.resolve()` + `relative_to(root)`.

### Cobertura de tests

- ✅ **create-jw-agent**: validación PEP 503 + i18n parity (3 idiomas) + render security (5 path-traversal regressions) + golden snapshots parametrizados sobre 5 templates + CLI no-network guarantee.
- ✅ **pytest-cookbook plugin**: parsing de fences + marker injection + `__file__` inyectado en `exec()` namespace.
- ✅ **Cookbook**: 12 recetas pasan (01-12). Receta 09 desbloqueada por F43 agent-tracing; receta 12 (validación shape de `package.json` Capacitor) pasa desde el MVP F47 — solo valida metadata, no compila Capacitor.
- ✅ CI: nuevos jobs `cookbook-tests` y `create-jw-agent` (E2E scaffold smoke + assertion de archivos clave).
- ✅ Trusted publishing workflow OIDC (`.github/workflows/publish-create-jw-agent.yml`) on tag `create-jw-agent-v*`, verifica match tag↔pyproject version.
- ✅ Astro site: el glob `**/*.md` en `website/src/content.config.ts` ya indexa `docs/cookbook/*.md` sin cambios.

## Fase 41 — plugin-sdk

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-41-plugin-sdk-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-41-plugin-sdk-plan.md`.
- **Guía**: `docs/plugin-sdk/{overview,security,capabilities,authoring}.md`.

Nuevo subpaquete `jw_core.plugins` con discovery via PEP 621 entry
points sobre 5 extension points: `agents`, `parsers`, `embedders`,
`vlm_providers`, `gen_providers`. `verify_plugin()` chequea contracto +
versión. Conflict policy por default `NAMESPACED` (ambigüedad explota
explícita; configurable via `JW_PLUGINS_CONFLICT_POLICY`). Plugins
descubiertos se integran en `jw-eval.default_agent_registry`,
`jw-rag.embed_providers` y `jw-mcp.register_plugin_tools`. CLI
`jw plugins list/verify/disable`. CI offline con fixture `plugin_sample`.

### Cobertura de tests

- ✅ **59 tests plugin-SDK nuevos**: 5 errors + 9 contracts + 13 policy + 8 registry + 12 verify + 6 factory + 6 e2e (subprocess venv) + integración (3 jw-eval + 2 jw-rag + 2 jw-mcp + 6 jw-cli).
- ✅ Cero regresiones en 2030+ tests existentes.
- ✅ Sin red en tests del registry: `entry_points` y `_distribution_for_entry_point` monkey-patched.
- ✅ Cero deps de runtime (usa `importlib.metadata` y `packaging` del stdlib-adjacent).
- ✅ Fail-soft por default; `JW_PLUGINS_STRICT=1` aborta.
- ✅ Boundary de seguridad documentada (no sandboxing real; mismo modelo de confianza que `pip install`).

## Fase 45 — semantic-chunking

- **Estado**: Estable (2026-05-31).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-45-semantic-chunking-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-45-semantic-chunking-plan.md`.
- **Guía**: `docs/guias/semantic-chunking.md`.

Nuevo subpackage `jw_rag.chunkers` (paragraph/semantic/llm + Chunker
Protocol + fakes), catálogo multilingüe `continuation_markers.json`
(es/en/pt) en `jw-core/data/`, router `get_chunker()` con env var
`JW_CHUNKER`, `LLMChunker` con cache de acciones por content hash. CLI
`jw chunker-bench` con bootstrap CI95 y per-language ≥10% lift gate.
MCP `set_chunker` tool. Backwards-compat byte-stable: `jw_rag.chunker`
sigue siendo façade re-exportando `Chunk` + `chunk_paragraphs`.

### Cobertura de tests

- ✅ **43 tests chunkers nuevos**: 6 backcompat + 21 markers + 7 NDCG + 4 bench + 3 semantic-es + 3 semantic-en + 2 semantic-pt + 8 closure + 5 LLM + 5 LLM cache + 6 env_var.
- ✅ Cero regresiones en suite jw-rag/jw-eval/jw-mcp.
- ✅ Sin nuevas deps de runtime: PyYAML ya estaba (eval).
- ✅ Multilingual: es/en/pt con fixtures dedicadas; fallback gracioso a paragraph cuando detect_language() falla.

## Fase 43 — agent-tracing ✅

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-43-agent-tracing-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-43-agent-tracing-plan.md`.
- **Guía**: `docs/guias/agent-tracing.md`.

Local-first JSONL traces que registran cada decisión interna de un agente
(kept / dropped / warning) con `seq` monotónica y envelope `trace_complete`
al cierre. `AgentTracer` con `step()` context manager + `kept/dropped/warn`
helpers, three stores (`Null`/`InMemory`/`Jsonl`), `contextvars` ambient
tracer (`use_tracer`), shared `--trace` flag installer (resuelve `path`,
`-` para stdout, `DEFAULT` para `$JW_TRACE_DIR`). Viewer Typer
(`jw trace view/list/gc`). Tres agentes piloto instrumentados:
`apologetics`, `verse_explainer`, `research_topic`; resto NO-OP gracias al
fallback. Bridge opt-in OpenTelemetry bajo extra `[otel]`. MCP
`apologetics(trace=true)` + `get_trace(trace_id)` para replay.

### Cobertura de tests

- ✅ **40 tests tracing** (schema 10 + store 6 + context 4 + tracer 6 + flag 7 + viewer 4 + overhead 1 + otel 1 skipped/passing + integration apologetics 2 / verse_explainer 2 / research_topic 2).
- ✅ Cero red; archivos JSONL bajo `tmp_path` en cada test.
- ✅ CLI test (`jw apologetics --trace`) parsea envelope desde stdout/JSONL.
- ✅ MCP test (`get_trace(trace_id)`) reconstruye eventos + envelope.

## Fase 44 — synth-judge ✅

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-44-synth-judge-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-44-synth-judge-plan.md`.
- **Guía**: `docs/guias/synth-judge.md`.

Filtro de calidad de 3 etapas para Q&A sintético antes de que llegue a
`data/train.jsonl`. Etapa 1 heurística always-on (`cites_jw_publication`
sobre regex de pub codes y wol.jw.org + `has_minimum_substance` rechazando
generic stubs ES/EN/PT y question echoes). Etapa 2 LLM pedagógico opt-in
con prompts Jinja2 en/es/pt que retornan 0..3. Etapa 3 NLI bridge opt-in
reusando Fase 39 import-guarded (claim/premise extraction sobre comillas).
Fórmula `overall` transparente con coeficientes nombrados, modos
off/loose/strict con cutoffs 5.0/6.5 y per-recipe overrides. CLI factory
env-driven (`JW_SYNTH_JUDGE_LLM/NLI`). `run_extract_with_judge` integrado
en `data/extract.py` con `dump_rejected_path` para audit.

### Cobertura de tests

- ✅ **85 tests offline**: 8 models + 26 heuristics + 8 thresholds + 9 scoring + 8 nli_bridge + 12 judge + 9 factories + 5 stats + 4 orchestrator integration + 4 extract CLI + 5 golden precision.
- ✅ Cero red; todos los providers fakes/monkeypatched.
- ✅ Golden 50-pair fixture (25 keep + 25 reject) cubre es/en/pt; LOOSE accuracy 0.86 (target 0.85, LLM+NLI pushes to 0.90+), STRICT accuracy 1.00.

## Fase 47 — jw-core-js Minimal 🟡 MVP

- **Estado**: MVP estable (2026-06-01). Roadmap post-MVP pendiente.
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-47-jw-core-js-minimal-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-47-jw-core-js-minimal-plan.md` (123 tasks; MVP cubre ~20).
- **Guía**: `docs/guias/jw-core-js.md`.

Port TypeScript del subset crítico de `jw-core` para superficies que no
pueden ejecutar Python (extensión WOL, futura Capacitor móvil, web
playground). Paquete publicable a npm como `@jw-agent-toolkit/core` con
dual ESM+CJS, tipos `.d.ts`, build via `tsup`, tests via `vitest`.

Surface MVP: `parseReference` + `parseAllReferences` + `BibleRef` (con
`display()`, `wolUrl(lang, pub?)`, `toJSON()`), tabla `BOOKS` 66 × en/es/pt,
`getLanguageConfig`, port de F46 versification (`toCanonical`, `explain`,
`loadCatalog`).

Contrato anti-drift: `shared/data/bible_references_golden.json` consumido
por la suite Python (`test_golden_fixture_parity.py`) y la suite
TypeScript (`tests/parser.test.ts`). Cualquier drift falla CI en uno u
otro lado.

### Cobertura de tests (MVP)

- ✅ **40 tests TypeScript** (Vitest): 25 parser + 6 wol_url + 9 versification.
- ✅ **17 tests Python** (pytest parametrizado sobre el fixture compartido).
- ✅ Build: ESM 52KB + CJS 53KB + DTS 3KB.

### Estado real post-MVP (auditoría F56)

**Integración F48 (WOL ext): completada** en commit `8ed5901`. El paquete se
consume como `dependencies` mandatoria (no `optionalDependencies`),
exportando `displayName` + tipo `Language` desde `verse_detector.ts`.
**No hay fallback** al parser local porque la dep es mandatoria. F48 usa
sólo ~5% de la superficie del MVP; el resto sirve a futuras superficies.

**Cookbook receta 12** (Capacitor): pasa desde el MVP, valida shape de
`package.json` con `@capacitor/core` declarado. No instala ni compila
Capacitor — es un guardián de metadata.

**Buckets B/C/D/E del plan formal: diferidos** hasta que aparezca código
Capacitor real en `apps/` (hoy NO existe; cero `capacitor.config.ts`,
`AndroidManifest.xml`, `Info.plist`). VISION.md no menciona Capacitor;
F49 second-brain explicita que la estrategia móvil del proyecto es
"thin client REST sobre jw-mcp", no app nativa con jw-core-js embebido.
Sin presión real de uso, esos buckets son sobre-engineering.

**Mini-buckets F56 con ROI inmediato para F48** (ejecutados):

- **F56.1** — esta misma corrección del ROADMAP.
- **F56.2** — re-export `Language` desde core, dedup de `normalizeLang`.
- **F56.3** — ampliar `bible_references_golden.json` a ≥100 casos y
  verificar `detectedLanguage`. El "anti-drift" del MVP era ficción con
  17 fixtures sin checkear el campo.
- **F56.4** — workflow `cross-lang.yml` bloqueante en CI + target
  `dump-shared-data` con `git diff --exit-code`.
- **F56.5** — `BibleRef.fromWolUrl(href)` + `langFromWolPath(href)`,
  inverso puro de `wolUrl()`. Permite a F48 ahorrar ~50 LOC de regex
  propias en `verse_detector.ts`. Sin Web Crypto, sin fetch.

### Buckets formalmente diferidos

Sin código Capacitor que los justifique, estos buckets NO se ejecutan:

- **A** — parsers HTML (`parseVerse`, `parseStudyNotes`, `parseArticle`).
  F48 vive in-page con el DOM ya cargado; no los necesita. Sólo serviría
  a un consumidor offline-first móvil.
- **B** — `WOLClient` / `CDNClient` con `fetch` nativo. Misma razón.
- **C** — JWPUB Web Crypto (AES-128-CBC + zlib). Caro y sin usuarios.
- **D** — IndexedDB cache, throttle TokenBucket, telemetría opt-in.
- **E** — Multi-locale extendido (hoy en/es/pt; Python tiene 17). F48
  no usa el resto; aceptado como deuda técnica.

Si en el futuro aparece `apps/capacitor-app/` con `capacitor.config.ts`
y screenshots reales, reabrir A→C en ese orden de prioridad.

## Fase 46 — canonical-versification ✅

- **Estado**: Estable (2026-06-01).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-46-canonical-versification-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-46-canonical-versification-plan.md`.
- **Guía**: `docs/guias/versification.md`.

Mapeo bidireccional de (book, chapter, verse) entre las cuatro tradiciones
de numeración relevantes para el toolkit (`nwt` default, `masoretic`,
`lxx`, `vulgate`). Catálogo curado de 30 entradas seed contra fuentes
académicas (Tov 2012, BHS apparatus, NETS prefaces) con explicaciones
trilingües en/es/pt originales del maintainer (no copia, GPL-3.0 safe).
`to_canonical` idempotente y lossless en round-trip; `explain` retorna
prosa localizada; CLI `jw versification {map,explain,list}`.

### Cobertura de tests

- ✅ **29 tests offline**: 10 models + 4 registry + 8 mapping + 4 explain + 3 CLI.
- ✅ Cero red; catálogo embebido vía importlib.resources con lru_cache(1).
- ✅ Casos famosos cubiertos: Joel 2:28 → 3:1, Malachi 4 → 3:19, Psalm 51 superscript, LXX Psalm 50, round-trip preserving.
- ✅ Sin regresiones en los 1005 tests de jw-core.

## Fase 40 — content-provenance

- **Estado**: Estable (2026-05-31).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-40-content-provenance-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-40-content-provenance-plan.md`.
- **Guía**: `docs/guias/content-provenance.md`.

Añade trazabilidad reproducible al passage citado por cada agente.
Cuatro claves convencionales en `Citation.metadata`
(`published_date`, `accessed_at`, `content_hash`, `revision`) +
`ProvenanceValidator` que re-fetcha y compara hashes. Integra con Fase
39 para re-correr NLI al detectar cambio. CLI `jw provenance check` +
MCP `verify_provenance`. Telemetría opt-in via Fase 9.

Encaja en la taxonomía de cuatro capas L0–L3 — Fase 40 ocupa L2
(fidelidad de contenido), complementando L0/L1 (Fase 23) y L3 (Fase 39).

### Cobertura de tests

- ✅ **42 tests provenance nuevos**: 3 errors + 15 models + 12 hashing + 9 validator + 5 NLI re-run + 9 propagation + 2 drift telemetry + 3 backwards-compat + 5 CLI + 4 MCP tool.
- ✅ Cero regresiones en los 2079+ tests existentes (incluye protocol contract: tool MCP `verify_provenance` registrada).
- ✅ Sin nuevas deps: reusa `httpx` (Fase 23) + Pydantic 2 + stdlib `hashlib`/`unicodedata`.
- ✅ Backwards-compat: `AgentResult`s pre-Fase 40 producen verdict `no_record` sin llamar al fetcher.

## Fase 50 — jwpub-writer ✅

- **Estado**: Estable (2026-06-03).
- **Guía**: `docs/guias/jwpub-writer.md`.

Cierra el ciclo simétrico de Fase 5.5 (descifrado JWPUB). Port del
algoritmo de generación de `darioragusa/html2jwpub` (MIT, Swift) a Python:
`JwpubBuilder` en `jw_core.writers.jwpub` empaqueta HTML+media como
`.jwpub` cifrado consumible por JW Library nativo (SHA-256+XOR para
derivar key/IV, AES-128-CBC encrypt, zlib deflate del Content, SQLite
manifest + ZIP outer).

Crypto compartido extraído de `parsers/jwpub.py` a `jw_core.jwpub_crypto`:
`XOR_KEY`, `compute_key_iv()`, `decrypt_blob()` (existente), `encrypt_blob()`
(nuevo). Una sola fuente de verdad para la constante mágica de JW.

Casos de uso desbloqueados: empaquetar golden fixtures como `.jwpub`,
publicar traducciones custom de publicaciones (compone con Fase 54 NLLB),
exportar datasets de fine-tuning como publicación nativa.

### Cobertura de tests

- ✅ **9 tests round-trip**: builder→parser idéntico, content sizes
  parametrizados (PKCS7 boundary), Watchtower con `issueTagNumber`, media
  bundled en inner ZIP.
- ✅ CLI `jw jwpub build <folder> --symbol --year --lang` añadida en F55.4.
- ✅ Sin regresión: 1031 tests jw-core pre-existentes siguen verdes.

## Fase 51 — organized-app schemas (Pydantic v2) ✅

- **Estado**: Estable (2026-06-03).
- **Guía**: `docs/guias/organized-app-schemas.md`.

Port de los tipos TypeScript de `sws2apps/organized-app` (MIT) — la PWA
React usada por cientos de congregaciones — a Pydantic v2 en
`jw_core.models_organized`. Schemas portados: `PersonType`,
`SchedWeekType`, `WeekType` (con enum `Week`), `AssignmentCode`
(IntEnum 100–300), `MeetingAttendanceType`, `FieldServiceGroupType`,
`UserFieldServiceMonthlyReportType` (layout post-2023 S-21), y la
envolvente CRDT `Timestamped[T]`.

Habilita interoperabilidad con el ecosistema organized-app **sin
depender de su runtime React/Firebase**. La PWA exporta backups JSON;
ahora el toolkit los lee y escribe nativamente (ver F55.5).

### Cobertura de tests

- ✅ **10 tests sanidad**: enum values coinciden verbatim con TS, JSON
  envelopes round-trip via `model_dump(by_alias=True)`, `_deleted` alias
  preservado, weekend skeleton mínimo construible.

## Fase 52 — .jwlibrary writer ✅

- **Estado**: Estable (2026-06-03).
- **Guía**: `docs/guias/jwlibrary-writer.md`.

Cierra el read-write loop con la app oficial JW Library (Fase 19 fue
solo lectura). Port del export pipeline Python de `erykjj/jwlmanager`
(MIT) a `jw_core.writers.jw_library_backup`. Dos funciones:
`write_backup(out, *, user_data_db_path, ...)` empaqueta un userData.db
como `.jwlibrary` (manifest + SHA-256 hash + LastModified stamp + ZIP).
`update_backup(in_path, out_path, modify_fn)` hace el flujo
extract → callback `modify(conn)` → repack.

El **merge** de jwlmanager vive en un blob nativo opaco
(`libjwlCore.{so,dylib,dll}`) — NO se portó; ese sigue requiriendo la
app GUI original. El toolkit cubre el flujo de export/writing puro, que
es el que los agentes necesitan para sintetizar backups con notas.

CLI `jw library {inspect,re-export,from-notes}` añadida en F55.3.

### Cobertura de tests

- ✅ **9 tests round-trip**: write→parse idéntico, hash SHA-256 verificado
  contra bytes DB, LastModified re-stamping, ausencia tolerada cuando
  el DB no tiene esa tabla, callback `modify(conn)` aplicado en
  `update_backup`, errores de archivo no-zip raised.

## Fase 53 — Omnilingual ASR (1672 idiomas) ✅

- **Estado**: Estable (2026-06-03). End-to-end verificado.
- **Guía**: `docs/guias/omnilingual-asr.md`.

Integra `facebookresearch/omnilingual-asr` (Apache 2.0) como proveedor
ASR de primera clase. Cubre **1672 idiomas** — incluyendo cientos de
lenguas low-resource (quechua, kinyarwanda, aymara, guaraní, lenguas
bantúes, lenguas del Pacífico) que ni Deepgram ni Whisper-large-v3
cubren con calidad usable.

### Arquitectura "polyglot Python"

`fairseq2` (dep transitiva de omnilingual-asr) NO publica wheels para
CPython 3.13. El toolkit es 3.13. La solución: `OmnilingualProvider`
instala un **venv dedicado en Python 3.12** (`~/.jw-core/omnilingual/venv`)
y dispara un worker via `subprocess.run(...)` con I/O por JSON.
Patrón "venv-per-feature" — el sobrecosto es un cold-start (~300ms) por
transcripción, despreciable frente al modelo (segundos).

Bootstrap: `jw omnilingual install` (requiere `libsndfile` a nivel OS:
`brew install libsndfile`). El worker script `omnilingual_worker.py`
NO importa `jw_core`, así el venv 3.12 queda mínimo.

### Comandos CLI

`jw omnilingual {install, status, transcribe, supports}`. Por ejemplo:

```bash
jw omnilingual install
jw omnilingual supports kin_Latn  # → yes
jw omnilingual transcribe audio.wav --lang qu
```

### Dependencia knock-on

Para que `fairseq2` coexistiera en el mismo workspace:
- `psutil>=6` en jw-finetune → relajado a `>=5.9.5,<8`.
- `numpy>=2` en jw-rag → relajado a `>=1.26,<3`.

Ambos paquetes solo usan APIs estables disponibles desde 5.9/1.26.

### Cobertura de tests

- ✅ **16 tests** con `subprocess` mockeado: venv detection, lang
  normalization ISO→FLORES, error propagation del worker, env override,
  model card override.
- ✅ End-to-end real verificado: 1672 supported_langs, quechua/kinyarwanda/
  aymara/guaraní confirmados; primera transcripción descarga el modelo.

## Fase 54 — NLLB-200 translation con ref-preservation ✅

- **Estado**: Estable (2026-06-03).
- **Guía**: `docs/guias/nllb-translation.md`.

Proveedor `NLLBProvider` en `jw_core.translation_providers.nllb` envuelve
NLLB-200 de Meta (200 idiomas) con backend CTranslate2 INT8 (~7 GB en
Mac M-series unified memory). Encoder-decoder especializado: no
alucina en low-resource donde GPT/Claude fallan.

### License-as-attribute

NLLB-200 ships bajo **CC-BY-NC-4.0** — no comercial. El proveedor expone
`is_commercial_safe = False`. El router F55.1 lo respeta: con
`get_translation_provider(commercial=True)` el caller excluye NLLB sin
auditar código. La política de licencia se vuelve **chequeable, no
narrativa**.

### Ref preservation

Función pública `translate_preserving_references(text, source, target,
provider)` en `jw_core.translation`:

1. Mask de refs bíblicas: `Juan 3:16` → `<<REF:0>>`.
2. Provider traduce solo texto opaco (sin libro/capítulo/versículo).
3. Restore en el idioma destino con el book naming correcto.

Cero riesgo de alucinación numérica en versículos, que es **donde más
fallan los LLMs generales**. Compone con F55.7 (cross_lingual_research)
para queries multilenguaje.

### Cobertura de tests

- ✅ **10 tests** con `ctranslate2`/`transformers` mockeados — sin
  descarga de pesos en CI: routing FLORES correcto, empty input
  short-circuit, error propagation, env override, license flag, wrapper
  mask/restore verificado con echo-provider.

## Fase 55 — Wire-up multilingüe (integración F50-F54) ✅

- **Estado**: Estable (2026-06-03).
- **Guía**: `docs/guias/multilingual-wire-up.md`.

Convierte F50–F54 de islas portadas en capacidades del toolkit reales.
Ocho sub-fases de wire-up, cada una añade un call site:

| Sub-fase | Punto de conexión |
|---|---|
| F55.1 | Router automático ASR + translation con `get_asr_provider(language=...)` y `get_translation_provider(commercial=...)`. Quechua/Kinyarwanda → Omnilingual sin que el caller los nombre. |
| F55.2 | `jw translate` CLI + MCP `translate_preserving_refs`; refactor de MCP `transcribe_audio` para usar router. |
| F55.3 | `jw library {inspect, re-export, from-notes}` — agentes pueden generar `.jwlibrary` consumible por JW Library nativo. |
| F55.4 | `jw jwpub build` — empaquetar HTML+media como `.jwpub` cifrado nativo. |
| F55.5 | `parse_organized_backup()` / `write_organized_backup()` en `integrations/organized_app.py` — IO del backup JSON de la PWA. |
| F55.6 | `ministry/organized_bridge.py` — converter `MonthlyReport` ↔ `UserFieldServiceMonthlyReportType` con reglas post-2023 S-21. |
| F55.7 | `jw_agents.cross_lingual_research` — query en A → traduce → busca corpus B → traduce excerpts back, refs preservados ambas direcciones. |
| F55.8 | `audio/broadcasting.transcribe_and_index_audio` usa router F55.1 + opcional `translate_to` para indexar transmisiones low-resource en otro idioma. |

### Cobertura de tests

- ✅ **24 tests** de wire-up nuevos.
- ✅ **1887 tests totales pasando** en jw-core/jw-agents/jw-cli (zero
  regresión post-renumeración y refactor `jw jwpub` → sub-app).

### Por qué importan los call sites

Las fases F50-F54 portaron código limpio y testeado, pero **ningún módulo
del toolkit los invocaba**. Auditoría honesta: un `grep -rn "models_organized"`
fuera de `tests/` arrojaba cero coincidencias. F55 cambia eso —
8 puntos de integración con la convención: pequeños (≤50 LOC c/u) pero
multiplicativos. La integración profunda es el efecto de muchos wires,
no de un módulo grande.

## Fase 66 — second brain expuesto vía MCP ✅

- ✅ Tools `@mcp.tool` para `second_brain_status/compile/query/lint/snapshot` en `jw_mcp/server.py` (heredado de F49).
- ✅ Tests E2E sobre temp DuckDB brain (`packages/jw-mcp/tests/test_jw_brain_tools.py`, 5 tests).
- ✅ Fix de drift en `_EXPECTED_TOOLS` (añadidos `get_trace` y `translate_preserving_refs`).
- ✅ Doc en `docs/referencia/jw-mcp.md`.
- ⬜ Tool `second_brain_list` para enumerar brains registrados (futuro).
- ⬜ Resolución por alias en lugar de path absoluto (futuro).

## Fase 58 — Bible Knowledge Graph JW-puro ✅

- ✅ Schema TJ ampliado con `Period`, `Passage` + 5 edges temporales (`LIVED_IN_PERIOD`, `ACTIVE_IN_PERIOD`, `MENTIONED_IN_PASSAGE`, `LOCATED_IN_PASSAGE`, `PASSAGE_BELONGS_TO_PERIOD`).
- ✅ Catálogo curado de 10 periodos bíblicos según cronología JW (607 a.E.C. para destrucción de Jerusalén).
- ✅ `BibleLoader.import_periods()` + `import_insight(jwpub_path)`.
- ✅ Parser procedural de cabezales del Insight (PERSON_HEADWORDS plus PLACE_HEADWORDS).
- ✅ Port a Python de `BibleRef.from_wol_url` (paridad con jw-core-js F56.5).
- ✅ CLI `jw brain import-bible`.
- ✅ Helper `DuckDBBackend.query_persons_in_book(book_num)` con test E2E.
- ✅ Fixture sintético `insight_mini/it_mini.jwpub` (3 entradas) generado por script reusando `jw_core.writers.jwpub.JwpubBuilder`.
- ✅ Guía `docs/guias/bible-knowledge-graph.md`.
- ⬜ Catálogo ampliado a las miles de entradas del Insight (sprint siguiente).
- ⬜ Geocoordenadas de Place (otro catálogo curado).
- ⬜ Import desde NWT cross-references (más Passage).
