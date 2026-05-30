# jw-agent-toolkit

Toolkit agéntico para contenido de jw.org / wol.jw.org. Monorepo Python multi-paquete: librería principal, CLI, servidor MCP, indexador RAG, agentes de alto nivel y skills para Claude.

## Paquetes

| Paquete | Propósito |
|---|---|
| `jw-core` | Librería principal: 6 clientes HTTP (CDN, mediator, WOL, pub-media, topic-index, weblang), 9 parsers (citas, artículos, texto diario, versículos, notas de estudio, índice temático, EPUB, JWPUB), modelos Pydantic, registro de idiomas, e infraestructura Fase 9 (cache SQLite, throttle, telemetría opt-in, JWT auth). |
| `jw-cli` | CLI de terminal con 8 comandos (`jw verse`, `jw search`, `jw daily`, `jw download`, `jw languages`, `jw chapter`, `jw jwpub`, `jw topic`) construida con Typer + Rich. |
| `jw-mcp` | Servidor [Model Context Protocol](https://modelcontextprotocol.io) — expone **29 herramientas** a Claude Desktop, Claude Code o cualquier cliente MCP. |
| `jw-rag` | Indexación vectorial + recuperación híbrida (BM25 + cosenos + Reciprocal Rank Fusion) sobre el corpus de Biblia + publicaciones + EPUBs + JWPUBs descifrados. |
| `jw-agents` | Agentes procedurales multipaso: `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`. |
| `jw-finetune` | Plataforma local de fine-tuning estilo Unsloth Studio: extrae JWPUB/EPUB → genera Q&A sintéticos → entrena LoRA → exporta GGUF/MLX. Cada usuario entrena su propio modelo con sus publicaciones; los pesos nunca se distribuyen. Ver [guía](docs/guias/fine-tuning-local.md). |

Además: `skills/` (5 skills Markdown para Claude: jw-verse-lookup, jw-daily-text, jw-research, jw-meeting-prep, jw-apologetics) y `scripts/` (scripts de exploración + reverse engineering JWPUB).

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

> **macOS bajo `~/Documents` o `~/Desktop`:** sigue la receta de [`docs/guias/setup-macos.md`](docs/guias/setup-macos.md) *antes* del `uv sync`. macOS marca los `.venv/` como `UF_HIDDEN` automáticamente en esas rutas, lo que rompe los imports editables con `ModuleNotFoundError` silencioso. La guía explica el porqué y deja un fix permanente con `venv/` + symlink.

## Licencia

GPL-3.0-only. Incorpora código derivado de [`jwlib`](https://github.com/allejok96/jwlib) (allejok96, GPL-3.0).

## Estado

Ver [docs/ROADMAP.md](docs/ROADMAP.md). **Fases 0-10 completadas**, incluyendo:

- Fase 5.5: descifrado completo de JWPUB (AES-128-CBC con derivación de clave de [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit)).
- Fase 9: infraestructura de producción — cache SQLite con TTL, throttle por host (token bucket), telemetría opt-in para detectar drift de la API, JWT auth aislado, factory unificado de clientes.
- Fase 10: cierre del 100% del plan original (CI con GitHub Actions, cassettes pytest-recording, weblang client, 3 URL patterns nuevos en WOLClient, 6 tools MCP adicionales).

**166 tests passing + 4 skipped** (corren sin red gracias a cassettes).

## Documentación

Toda la documentación detallada vive en [`docs/`](docs/):

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Manual de arquitectura: objetivos, capas, inventario de endpoints, decisiones clave.
- [docs/ROADMAP.md](docs/ROADMAP.md) — Hoja de ruta operacional por fases (0-10, completadas).
- [docs/VISION.md](docs/VISION.md) — Roadmap de visión a largo plazo: qué falta para un ecosistema LLM/IA completo para TJ.
- [docs/conceptos/](docs/conceptos/) — Glosario JW.org, decisiones de diseño, estrategia multi-idioma, inventario de endpoints, flujos end-to-end, CI y testing.
- [docs/guias/](docs/guias/) — Guías prácticas (resolver citas, usar clientes HTTP, construir agentes, RAG, extender parser, conectar MCP, infraestructura Fase 9, scripts de exploración).
- [docs/referencia/](docs/referencia/) — Referencia exhaustiva módulo por módulo, clase por clase, función por función.
