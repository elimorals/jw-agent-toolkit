# Documentación de jw-agent-toolkit

> Toda la documentación está en español. Los archivos en inglés del repositorio original han sido traducidos in situ.

## Mapa rápido

### Comienza aquí

- **[README principal](../README.md)** — Visión general del proyecto, paquetes y comandos.
- **[QUICKSTART](../QUICKSTART.md)** — Instalación, primer comando, conexión a Claude Desktop.
- **[ARCHITECTURE](ARCHITECTURE.md)** — Manual de arquitectura: capas, endpoints, decisiones clave.
- **[ROADMAP](ROADMAP.md)** — Hoja de ruta por fases (fase actual: 7 completa, 5 y 8 pendientes).

### Manual conceptual — entender el porqué

Para colaboradores nuevos y para tomar decisiones de diseño con criterio.

- [Glosario JW.org](conceptos/glosario.md) — Términos del ecosistema JW: WOL, nwtsty, JWPUB, pub-media, lp-tag, docid, etc.
- [Decisiones de diseño](conceptos/decisiones-de-diseno.md) — Por qué monorepo, por qué agentes procedurales, por qué FakeEmbedder por defecto, etc.
- [Estrategia multi-idioma](conceptos/estrategia-multi-idioma.md) — Niveles de soporte, registro `Language`, colisiones ortográficas.
- [Inventario de endpoints](conceptos/inventario-endpoints.md) — Cada endpoint externo: método, auth, payload, ejemplos.
- [Flujos end-to-end](conceptos/flujos-end-to-end.md) — Diagramas de secuencia de los flujos más comunes.

### Guías por tema — hacer algo concreto

Orientadas a casos de uso. Cada una es autocontenida con código de ejemplo.

- [Resolver citas bíblicas](guias/resolver-citas-biblicas.md) — Usar `parse_reference`, manejar idiomas, construir URLs.
- [Usar los clientes HTTP](guias/usar-clientes-http.md) — CDN, WOL, Mediator, PubMedia, TopicIndex: patrones comunes.
- [Construir un agente](guias/construir-un-agente.md) — Cómo escribir un nuevo agente procedural sobre `jw-core`.
- [Indexar y buscar con RAG](guias/indexar-y-buscar-con-rag.md) — Ingest, persistencia, búsqueda híbrida, RRF, embedders.
- [Extender el parser de referencias](guias/extender-el-parser.md) — Añadir un idioma, añadir abreviaturas, manejar casos especiales.
- [Conectar el MCP a Claude Desktop](guias/conectar-mcp-a-claude-desktop.md) — Configuración paso a paso, troubleshooting.

### Referencia exhaustiva — cada función documentada

Documentación módulo a módulo, clase a clase, función a función. Incluye firmas, parámetros, retornos, excepciones y ejemplos.

- [jw-core](referencia/jw-core.md) — Modelos, parsers, clientes, languages, data/books.
- [jw-cli](referencia/jw-cli.md) — Cada comando con sus opciones y códigos de salida.
- [jw-mcp](referencia/jw-mcp.md) — Las 21 herramientas MCP con contratos completos.
- [jw-rag](referencia/jw-rag.md) — `VectorStore`, `Embedder`, chunker, ingest, retrieve.
- [jw-agents](referencia/jw-agents.md) — `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`.

## Convenciones

- **Idioma**: todo en español. Términos técnicos del código (nombres de clases, funciones, parámetros) se conservan en su forma original.
- **Diagramas**: ASCII art primero; Mermaid solo donde la complejidad lo justifique.
- **Ejemplos**: ejecutables. Los snippets Python asumen el monorepo instalado con `uv sync --all-packages`.
- **Rutas**: relativas a la raíz del repo cuando empiezan por `packages/`, `docs/` o `scripts/`. Absolutas cuando son URLs.
- **Versiones**: la documentación refleja el estado al 2026-05. Los cambios estructurales se reflejan aquí antes que en el código.
