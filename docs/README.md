# Documentación de jw-agent-toolkit

> Toda la documentación está en español. Los archivos en inglés del repositorio original han sido traducidos in situ.

## Mapa rápido

### Comienza aquí

- **[README principal](../README.md)** — Visión general del proyecto, paquetes y comandos.
- **[QUICKSTART](../QUICKSTART.md)** — Instalación, primer comando, conexión a Claude Desktop.
- **[ARCHITECTURE](ARCHITECTURE.md)** — Manual de arquitectura: capas, endpoints, decisiones clave.
- **[ROADMAP](ROADMAP.md)** — Hoja de ruta operacional por fases (0-10, completadas).
- **[VISION](VISION.md)** — Roadmap de visión a largo plazo: qué falta para un ecosistema LLM/IA completo para TJ (reunión semanal, ministerio, audio, multilenguaje, multimodalidad, etc.).
- **[VISION_AUDIT](VISION_AUDIT.md)** — Verificación 1:1 de cada ítem de VISION contra los 12 módulos entregados en Fases 11-18.

### Manual conceptual — entender el porqué

Para colaboradores nuevos y para tomar decisiones de diseño con criterio.

- [Glosario JW.org](conceptos/glosario.md) — Términos del ecosistema JW: WOL, nwtsty, JWPUB (descifrado), pub-media, lp-tag, docid, infraestructura Fase 9.
- [Decisiones de diseño](conceptos/decisiones-de-diseno.md) — Las 17 decisiones que dan forma al proyecto: por qué monorepo, agentes procedurales, FakeEmbedder, JWPUB con crédito, telemetría opt-in, etc.
- [Estrategia multi-idioma](conceptos/estrategia-multi-idioma.md) — Niveles de soporte, registro `Language`, colisiones ortográficas.
- [Inventario de endpoints](conceptos/inventario-endpoints.md) — Cada endpoint externo (incluyendo weblang y los 3 patrones WOL nuevos): método, auth, payload, TTL de cache, ejemplos.
- [Flujos end-to-end](conceptos/flujos-end-to-end.md) — Diagramas de secuencia de los flujos más comunes (incluyendo politely_get y JWPUB decryption).
- [Integración con JW Library](conceptos/integracion-jw-library.md) — Fase 19: cómo y por qué conectamos con la app oficial (deep links, backups, sync incremental, catálogo MEPS, Full Disk Access en macOS).
- [Integración con Obsidian](conceptos/integracion-obsidian.md) — Fase 20: portar utilidades del plugin `obsidian-library-linker`, sync bidireccional vault ↔ toolkit, plugin Obsidian propio, 17 locales de nombres de libros.
- [CI y testing](conceptos/ci-y-testing.md) — GitHub Actions workflow, suite de pruebas, sistema de cassettes pytest-recording.

### Guías por tema — hacer algo concreto

Orientadas a casos de uso. Cada una es autocontenida con código de ejemplo.

- [Fidelidad NLI en runtime](guias/fidelity-nli.md) — Fase 39: verificación NLI claim/premise sobre cada `Finding`; 5 providers (Claude / OpenAI / DeBERTa / Ollama / Fake) con `FakeNLI` siempre disponible; CLI/MCP `--fidelity {off,warn,reject}`.
- [Content provenance (Fase 40)](guias/content-provenance.md) — trazabilidad reproducible del texto citado: 4 claves en `Citation.metadata` + `ProvenanceValidator` que re-fetcha y compara hashes + integración opt-in con Fase 39. CLI `jw provenance check` + MCP `verify_provenance`.
- [Plugin SDK (Fase 41)](plugin-sdk/overview.md) — extension points sin forkear el monorepo: 5 entry-point groups (agents/parsers/embedders/vlm_providers/gen_providers) + CLI `jw plugins {list,verify,disable}` + conflict policy `NAMESPACED` por default. Ver también [security](plugin-sdk/security.md), [capabilities](plugin-sdk/capabilities.md), [authoring](plugin-sdk/authoring.md).
- [Scaffolding de un plugin (Fase 42)](guias/scaffolding.md) — `create-jw-agent` (PyPI standalone) genera proyectos plugin con entry-points F41 pre-cableados en <10 min. 5 tipos (agent/parser/embedder/vlm/gen), validación PEP 503, i18n `en/es/pt`. Cookbook ejecutable con 12 recetas verificadas por el plugin `pytest-cookbook` (`docs/cookbook/*.md`).
- [Second Brain (Fase 49)](guias/second-brain.md) — Karpathy-style compiler + GraphRAG sobre el toolkit. Dual backend DuckDB/Neo4j, Wiki sobre Obsidian con `human_edited` honored, CLI `jw brain {init,compile,query,lint,status,snapshot,list}`, MCP `second_brain_*`. Multi-tenant. `BrainDomain` plugins via F41 (TJ builtin + financial fixture).
- [Semantic chunking (Fase 45)](guias/semantic-chunking.md) — chunking por unidad de pensamiento: continuation/closure markers es/en/pt + `LLMChunker` con cache + NDCG@10 bench con per-language lift gate. CLI `jw chunker-bench`, MCP `set_chunker`. Backwards-compat byte-stable.
- [Extensión WOL para el navegador](guias/wol-browser-ext.md) — Fase 48: extensión Chrome/Edge/Firefox que añade botones inline en `wol.jw.org` (📖 Explicar / 🔗 Refs / 📝 Obsidian). 100% local, 3 capas de defensa contra requests externos.
- [Agent tracing (Fase 43)](guias/agent-tracing.md) — trazas JSONL local-first que registran cada decisión interna del agente (kept/dropped/warn/step). CLI `jw apologetics --trace`, viewer `jw trace {view,list,gc}`, MCP `get_trace`. Bridge OpenTelemetry opt-in bajo extra `[otel]`.
- [Synth Judge (Fase 44)](guias/synth-judge.md) — filtro de calidad 3-etapa (heurísticas always-on + LLM pedagógico opt-in + NLI Fase 39 opt-in) sobre Q&A sintético antes de `data/train.jsonl`. CLI `--judge=off/loose/strict`, env `JW_SYNTH_JUDGE_LLM/NLI`, per-recipe overrides, dump de rejected para audit.
- [Canonical versification (Fase 46)](guias/versification.md) — mapeo de referencias bíblicas entre tradiciones de numeración (`nwt`/`masoretic`/`lxx`/`vulgate`) con catálogo curado y explicaciones trilingües. CLI `jw versification {map,explain,list}`. Joel 2:28 ↔ Joel 3:1 (BHS), Malaquías 4 ↔ Malaquías 3:19, superscripciones de Salmos.
- [Resolver citas bíblicas](guias/resolver-citas-biblicas.md) — Usar `parse_reference`, manejar idiomas, construir URLs.
- [Usar los clientes HTTP](guias/usar-clientes-http.md) — CDN, WOL, Mediator, PubMedia, TopicIndex: patrones comunes.
- [Infraestructura Fase 9](guias/infraestructura-fase9.md) — Cache SQLite, throttler per-host, telemetría opt-in, factory unificado.
- [Construir un agente](guias/construir-un-agente.md) — Cómo escribir un nuevo agente procedural sobre `jw-core`.
- [Indexar y buscar con RAG](guias/indexar-y-buscar-con-rag.md) — Ingest (incluyendo JWPUB descifrado), persistencia, búsqueda híbrida, RRF, embedders.
- [Embeddings y reranking](guias/embeddings-y-rerank.md) — Fase 33: providers reales (BGE-M3, Cohere, Jina, Voyage, Ollama, E5) + cross-encoder reranker con auto-detect.
- [Constrained decoding](guias/constrained-decoding.md) — Fase 35: gramáticas GBNF + Pydantic para forzar citas verificables en cualquier LLM consumidor de `AgentResult`.
- [Extender el parser de referencias](guias/extender-el-parser.md) — Añadir un idioma, añadir abreviaturas, manejar casos especiales.
- [Conectar el MCP a Claude Desktop](guias/conectar-mcp-a-claude-desktop.md) — Configuración paso a paso, troubleshooting.
- [Integración con JW Library](guias/integracion-jw-library.md) — Deep links `jwlibrary://`, parser de backups `.jwlibrary`, sync incremental, catálogo MEPS docid↔pub_code, inspector local (Windows publications.db + macOS userData.db con Full Disk Access).
- [Usar con Obsidian (second brain)](guias/usar-con-obsidian.md) — Setup paso a paso del plugin Obsidian: linkify, insertar versos con quote callouts, importar notas de JW Library al vault, indexar al RAG, agente LLM con vista total.
- [Scripts de exploración](guias/scripts-de-exploracion.md) — Los 20 scripts en `scripts/`: discovery de fixtures, exploración de HTML, reverse engineering JWPUB, live tests end-to-end.
- [Eval doctrinal](guias/eval-doctrinal.md) — Suite de regresión doctrinal `jw-eval`: 3 capas (estructural, citas, semántico), CI bloqueante + nightly.
- [Fine-tuning local](guias/fine-tuning-local.md) — Entrena tu propio modelo JW personal con `jw-finetune` (Unsloth + JWPUB/EPUB locales).

### Guías de los módulos Fase 11-18 (VISION.md)

- [Asistente de ministerio](guias/asistente-de-ministerio.md) — Módulo 2: objeciones, presentaciones, revisitas, búsqueda inversa.
- [Audio y voz](guias/audio-y-voz.md) — Módulo 3: TTS pluggable, transcripción Whisper, índice JW Broadcasting.
- [Estudio personal](guias/estudio-personal.md) — Módulo 4: planes lectura, notas personales, flashcards SM-2, Strong's.
- [Familia y niños](guias/familia-y-ninos.md) — Módulo 5: lecciones, adoración familiar, quiz por edad.
- [Calendario y eventos](guias/calendario-y-eventos.md) — Módulo 6: Memorial, asambleas, visita superintendente.
- [Multimodalidad visual](guias/multimodalidad-visual.md) — Módulo 7: OCR, mapas bíblicos, generador de slides.
- [Idiomas expandidos](guias/idiomas-expandidos.md) — Módulo 8: Tier 1 10 idiomas, sign languages, traducción preservando refs.
- [Apologética avanzada](guias/apologetica-avanzada.md) — Módulo 9: fact_checker, detector de apócrifa.
- [Infraestructura operacional](guias/infraestructura-operacional.md) — Módulo 10: logging estructurado, REST API, bots.
- [Privacidad local-first](guias/privacidad-local-first.md) — Módulo 11: cifrado, Ollama, audit telemetría.
- [Personalización y accesibilidad](guias/personalizacion-y-accesibilidad.md) — Módulo 12: profile, memoria, tono, easy-read.
- [Citation integrity validator](guias/citation-validator.md) — Fase 23. Valida URLs wol.jw.org de agentes (estructural / live / drift). Hermana de Fase 22.
- [Monitor de novedades](guias/monitor-de-novedades.md) — `jw news digest` detecta publicaciones, videos y workbooks nuevos. Local-first, determinista.
- [Partes del estudiante](guias/partes-del-estudiante.md) — guion 4-sección para lectura, conversación, revisita y estudio bíblico (Fase 26).
- [Concordancia exacta](guias/concordancia-exacta.md) — `jw grep` literal con SQLite FTS5 sobre NWT + JWPUB + EPUB (Fase 28).
- [Exportador de hoja de estudio](guias/exportador-hoja-de-estudio.md) — Fase 31: convertir cualquier `AgentResult` en Markdown / PDF / DOCX / Anki con citas verificables y GUIDs Anki estables (re-export idempotente).
- [Temas de vida](guias/temas-de-vida.md) — Fase 32: asistente `life_topics` informativo con citas + redirect a ancianos en temas sensibles. Nunca sustituye consejería pastoral.

### Referencia exhaustiva — cada función documentada

Documentación módulo a módulo, clase a clase, función a función. Incluye firmas, parámetros, retornos, excepciones y ejemplos.

- [jw-core](referencia/jw-core.md) — Modelos, parsers (incluyendo JWPUB con decryption), 6 clientes HTTP (CDN, WOL, Mediator, PubMedia, TopicIndex, Weblang), infraestructura Fase 9 (auth, cache, throttle, telemetry, _polite, factory), languages, data/books.
- [jw-cli](referencia/jw-cli.md) — Los 8 comandos (`verse`, `chapter`, `daily`, `search`, `languages`, `download`, `jwpub`, `topic`) con sus opciones y códigos de salida.
- [jw-mcp](referencia/jw-mcp.md) — Las **29 herramientas MCP** con contratos completos.
- [jw-rag](referencia/jw-rag.md) — `VectorStore`, `Embedder`, chunker, ingest (incluyendo `ingest_jwpub` y `ingest_epub`), retrieve.
- [jw-agents](referencia/jw-agents.md) — `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`.
- [integraciones](referencia/integraciones.md) — Fase 19: capa `jw_core.integrations` (deep links, sync incremental, catálogo MEPS, inspector local + FDA macOS) y parser `.jwlibrary`.

## Convenciones

- **Idioma**: todo en español. Términos técnicos del código (nombres de clases, funciones, parámetros) se conservan en su forma original.
- **Diagramas**: ASCII art primero; Mermaid solo donde la complejidad lo justifique.
- **Ejemplos**: ejecutables. Los snippets Python asumen el monorepo instalado con `uv sync --all-packages`.
- **Rutas**: relativas a la raíz del repo cuando empiezan por `packages/`, `docs/` o `scripts/`. Absolutas cuando son URLs.
- **Versiones**: la documentación refleja el estado al 2026-05. Los cambios estructurales se reflejan aquí antes que en el código.
