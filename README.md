# jw-agent-toolkit

Toolkit agéntico para contenido de jw.org / wol.jw.org. Monorepo Python multi-paquete: librería principal, CLI, servidor MCP, indexador RAG y agentes de alto nivel.

## Paquetes

| Paquete | Propósito |
|---|---|
| `jw-core` | Librería principal: clientes API (CDN, mediator, WOL, pub-media, topic-index), parsers (citas bíblicas, artículos, texto diario, notas de estudio, versículos, índice temático), modelos y registro de idiomas. |
| `jw-cli` | CLI de terminal (`jw verse`, `jw search`, `jw daily`, `jw download`, `jw languages`, `jw chapter`) construida con Typer + Rich. |
| `jw-mcp` | Servidor [Model Context Protocol](https://modelcontextprotocol.io) — expone ~18 herramientas a Claude Desktop, Claude Code o cualquier cliente MCP. |
| `jw-rag` | Indexación vectorial + recuperación híbrida (BM25 + cosenos + Reciprocal Rank Fusion) sobre el corpus de Biblia + publicaciones. |
| `jw-agents` | Agentes procedurales multipaso: `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`. |

Además: `skills/` (skills Markdown para Claude) y `scripts/` (scripts de exploración).

## Inicio rápido

```bash
# Instalar dependencias de desarrollo (monorepo uv workspace)
uv sync --all-packages

# Ejecutar el servidor MCP
uv run jw-mcp

# Usar la CLI
uv run jw verse "Juan 3:16"
uv run jw daily
uv run jw search "amor"
```

Si estás en macOS y tu carpeta `~/Documents` está sincronizada con iCloud, ve la nota sobre `chflags nohidden` en [QUICKSTART.md](QUICKSTART.md).

## Licencia

GPL-3.0-only. Incorpora código derivado de [`jwlib`](https://github.com/allejok96/jwlib) (allejok96, GPL-3.0).

## Estado

Ver [docs/ROADMAP.md](docs/ROADMAP.md). Fases 0 a 4, 6 y 7 completadas. JWPUB (fase 5) y skills bundle (fase 8) pendientes.

## Documentación

Toda la documentación detallada vive en [`docs/`](docs/):

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Manual de arquitectura: objetivos, capas, inventario de endpoints, decisiones clave.
- [docs/ROADMAP.md](docs/ROADMAP.md) — Hoja de ruta por fases.
- [docs/conceptos/](docs/conceptos/) — Glosario JW.org, decisiones de diseño, estrategia multi-idioma, flujos end-to-end.
- [docs/guias/](docs/guias/) — Guías prácticas por caso de uso (resolver citas, construir un agente, indexar con RAG, conectar el MCP a Claude Desktop, etc.).
- [docs/referencia/](docs/referencia/) — Referencia exhaustiva módulo por módulo, clase por clase, función por función.
