# Hoja de ruta

Leyenda de estado: ✅ hecho · 🚧 en progreso · ⬜ planeado

## Fase 0 — Configuración ✅

- ✅ Monorepo con `uv workspace`
- ✅ Andamiaje de paquetes (`jw-core`, `jw-cli`, `jw-mcp`, `jw-rag`, `jw-agents`)
- ✅ Tooling: ruff, mypy, pytest
- ⬜ Workflow de CI (`.github/workflows/ci.yml`)

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

## Fase 8 — Bundle de skills ⬜

- ✅ `skills/jw-verse-lookup/SKILL.md` (existe — base)
- ✅ `skills/jw-research/SKILL.md` (existe — base)
- ✅ `skills/jw-daily-text/SKILL.md` (existe — base)
- ⬜ `skills/jw-meeting-prep/SKILL.md`
- ⬜ `skills/jw-apologetics/SKILL.md`

## Fase 9 — Pulido ⬜

- ⬜ Cache persistente en disco (SQLite) con TTL
- ⬜ Rate limiting + backoff exponencial
- ⬜ Logging estructurado
- ⬜ Telemetría (opt-in) para detectar drift de la API
- ⬜ Publicar jw-core en PyPI
