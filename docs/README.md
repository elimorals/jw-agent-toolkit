# Documentación de jw-agent-toolkit

> Toda la documentación está en español. Los archivos en inglés del repositorio original han sido traducidos in situ.

## Mapa rápido

### Comienza aquí

- **[README principal](../README.md)** — Visión general del proyecto, paquetes y comandos.
- **[QUICKSTART](../QUICKSTART.md)** — Instalación, primer comando, conexión a Claude Desktop.
- **[ARCHITECTURE](ARCHITECTURE.md)** — Manual de arquitectura: capas, endpoints, decisiones clave.
- **[ROADMAP](ROADMAP.md)** — Hoja de ruta operacional por fases (0-10, completadas).
- **[VISION](VISION.md)** — Roadmap de visión a largo plazo: qué falta para un ecosistema LLM/IA completo para TJ (reunión semanal, ministerio, audio, multilenguaje, multimodalidad, etc.).

### Manual conceptual — entender el porqué

Para colaboradores nuevos y para tomar decisiones de diseño con criterio.

- [Glosario JW.org](conceptos/glosario.md) — Términos del ecosistema JW: WOL, nwtsty, JWPUB (descifrado), pub-media, lp-tag, docid, infraestructura Fase 9.
- [Decisiones de diseño](conceptos/decisiones-de-diseno.md) — Las 17 decisiones que dan forma al proyecto: por qué monorepo, agentes procedurales, FakeEmbedder, JWPUB con crédito, telemetría opt-in, etc.
- [Estrategia multi-idioma](conceptos/estrategia-multi-idioma.md) — Niveles de soporte, registro `Language`, colisiones ortográficas.
- [Inventario de endpoints](conceptos/inventario-endpoints.md) — Cada endpoint externo (incluyendo weblang y los 3 patrones WOL nuevos): método, auth, payload, TTL de cache, ejemplos.
- [Flujos end-to-end](conceptos/flujos-end-to-end.md) — Diagramas de secuencia de los flujos más comunes (incluyendo politely_get y JWPUB decryption).
- [CI y testing](conceptos/ci-y-testing.md) — GitHub Actions workflow, suite de pruebas, sistema de cassettes pytest-recording.

### Guías por tema — hacer algo concreto

Orientadas a casos de uso. Cada una es autocontenida con código de ejemplo.

- [Resolver citas bíblicas](guias/resolver-citas-biblicas.md) — Usar `parse_reference`, manejar idiomas, construir URLs.
- [Usar los clientes HTTP](guias/usar-clientes-http.md) — CDN, WOL, Mediator, PubMedia, TopicIndex: patrones comunes.
- [Infraestructura Fase 9](guias/infraestructura-fase9.md) — Cache SQLite, throttler per-host, telemetría opt-in, factory unificado.
- [Construir un agente](guias/construir-un-agente.md) — Cómo escribir un nuevo agente procedural sobre `jw-core`.
- [Indexar y buscar con RAG](guias/indexar-y-buscar-con-rag.md) — Ingest (incluyendo JWPUB descifrado), persistencia, búsqueda híbrida, RRF, embedders.
- [Extender el parser de referencias](guias/extender-el-parser.md) — Añadir un idioma, añadir abreviaturas, manejar casos especiales.
- [Conectar el MCP a Claude Desktop](guias/conectar-mcp-a-claude-desktop.md) — Configuración paso a paso, troubleshooting.
- [Scripts de exploración](guias/scripts-de-exploracion.md) — Los 20 scripts en `scripts/`: discovery de fixtures, exploración de HTML, reverse engineering JWPUB, live tests end-to-end.

### Referencia exhaustiva — cada función documentada

Documentación módulo a módulo, clase a clase, función a función. Incluye firmas, parámetros, retornos, excepciones y ejemplos.

- [jw-core](referencia/jw-core.md) — Modelos, parsers (incluyendo JWPUB con decryption), 6 clientes HTTP (CDN, WOL, Mediator, PubMedia, TopicIndex, Weblang), infraestructura Fase 9 (auth, cache, throttle, telemetry, _polite, factory), languages, data/books.
- [jw-cli](referencia/jw-cli.md) — Los 8 comandos (`verse`, `chapter`, `daily`, `search`, `languages`, `download`, `jwpub`, `topic`) con sus opciones y códigos de salida.
- [jw-mcp](referencia/jw-mcp.md) — Las **29 herramientas MCP** con contratos completos.
- [jw-rag](referencia/jw-rag.md) — `VectorStore`, `Embedder`, chunker, ingest (incluyendo `ingest_jwpub` y `ingest_epub`), retrieve.
- [jw-agents](referencia/jw-agents.md) — `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`.

## Convenciones

- **Idioma**: todo en español. Términos técnicos del código (nombres de clases, funciones, parámetros) se conservan en su forma original.
- **Diagramas**: ASCII art primero; Mermaid solo donde la complejidad lo justifique.
- **Ejemplos**: ejecutables. Los snippets Python asumen el monorepo instalado con `uv sync --all-packages`.
- **Rutas**: relativas a la raíz del repo cuando empiezan por `packages/`, `docs/` o `scripts/`. Absolutas cuando son URLs.
- **Versiones**: la documentación refleja el estado al 2026-05. Los cambios estructurales se reflejan aquí antes que en el código.
