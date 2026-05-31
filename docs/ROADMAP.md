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
