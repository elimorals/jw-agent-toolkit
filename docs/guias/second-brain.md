# Second Brain (Fase 49)

> Karpathy-style compiler + GraphRAG sobre el toolkit. **Foco exclusivo del proyecto: publicaciones de los testigos de Jehová.** TJ es el único dominio que el toolkit empaqueta y mantiene.

## Foco del proyecto (lectura obligatoria)

**`jw-agent-toolkit` es 100% para publicaciones JW** (wol.jw.org, JWPUB, EPUBs de la organización, Watchtower, Despertad, libros de estudio, etc.). Eso no cambia con Fase 49.

Lo que Fase 49 sí hace es **separar dos cosas que antes estaban mezcladas**:

1. **El runtime** (compiler, grafo, wiki, lint) — lógica que en sí misma no contiene NodeType ni EdgeType específicos de TJ.
2. **El dominio TJ** — las 6 NodeTypes (`Verse`, `Topic`, `Publication`, `Concept`, `Person`, `Place`) y 6 EdgeTypes (`CITED_IN`, `MENTIONS`, `EXPANDS`, `CROSS_REFERENCES`, `CONTRADICTS`, `ABOUT`) que sí codifican la estructura de la literatura JW.

Esa separación es **una decisión de ingeniería**, no un cambio de scope.

## TL;DR

```bash
# Inicializar (TJ por defecto). Crea raw/, vault/, graph/ + config.toml + CLAUDE.md.
jw brain init --domain tj --brain ~/jw-second-brain

# Tirar archivos en raw/inbox/ (md, txt, html, epub, jwpub, pdf-future...)
cp ~/Downloads/notas-*.md ~/jw-second-brain/raw/inbox/

# Dry-run primero (recomendado en el primer compile)
jw brain compile --brain ~/jw-second-brain --dry-run

# Compile real
jw brain compile --brain ~/jw-second-brain

# Query (Karpathy-first → graph → vector)
jw brain query "Qué versículos se conectan a través de Eclesiastés 9:5?" --brain ~/jw-second-brain

# Lint
jw brain lint --brain ~/jw-second-brain

# Snapshot
jw brain snapshot --brain ~/jw-second-brain --label pre-experiment

# Multi-tenant
jw brain list                                    # registry global
jw brain status --brain my-tj-brain              # alias del registry
JW_BRAIN_HOME=~/jw-second-brain jw brain status  # env var
```

## El patrón

Tres capas, una operación recurrente:

```
raw/ (usuario tira datos)  →  Compiler agéntico  →  graph + wiki
                              "sale a pasear"
```

- **`raw/inbox/`**: cualquier formato cae aquí. El parser_router enruta por mime-type. Tras procesar, el archivo se mueve a `raw/processed/` (audit trail).
- **`vault/Second-Brain/`**: el agente es dueño absoluto. Páginas Markdown autogeneradas con frontmatter YAML; cualquier página con `human_edited: true` queda inmune a futuras compilaciones.
- **`graph/backend.duckdb`**: la capa GraphRAG persistente. Nodos: `Verse`, `Topic`, `Publication`, `Concept`, `Person`, `Place`. Aristas: `CITED_IN`, `MENTIONS`, `EXPANDS`, `CROSS_REFERENCES`, `CONTRADICTS`, `ABOUT`.

## Por qué grafo además de RAG vectorial

Para queries de multi-hop ("versículos en publicaciones que también citan X"), el grafo es estrictamente superior al vector. Benchmark canónico (Microsoft GraphRAG 2024 → 2026): queries con 3+ saltos pasan de **~16.7% accuracy** en vector solo a **56-80%** en grafo + vector híbrido.

## Backends

| Backend | Cuándo | Pros | Contras |
|---|---|---|---|
| `duckdb` (default) | siempre | embedded, cero deps externos, snapshot por tarball | SQL recursivo limitado vs Cypher |
| `neo4j` (opt-in) | corpus grande, queries Cypher complejas | traversal pleno, ecosystem maduro | proceso externo, opt-in via `[neo4j]` extra |

Mismo `GraphBackend` Protocol — el código de aplicación no cambia entre uno y otro.

## El fixture `financial_brain_plugin` — qué es y qué NO es

En `packages/jw-brain/tests/fixtures/financial_brain_plugin/` hay un paquete Python pequeño que registra un `FinanceBrainDomain` con NodeTypes `Transaction`/`Vendor`/`Category`/`TaxYear`.

**Aclaración obligatoria** (porque la prosa anterior podía confundir):

- ❌ NO es una funcionalidad del producto.
- ❌ NO es algo que el toolkit ofrece a usuarios finales.
- ❌ NO está en el roadmap.
- ❌ NO se distribuye, no se publica en PyPI, no se instala en producción.
- ✅ Es **únicamente un test fixture** que vive bajo `tests/` y se carga solo durante el test que verifica el descubrimiento de plugins.

**Para qué existe**: probar que el runtime de F49 **no tiene TJ hardcoded en sitios que deberían ser dominio-agnósticos** (graph backend, wiki writer, compiler loop, query router, CLAUDE.md autogen). Sin un dominio distinto a TJ que sirva de "control", esa garantía no se puede demostrar — el test `test_domain_registry.py::test_plugin_domain_discovered_via_f41` falla si alguien introduce ese acoplamiento sin querer.

**El proyecto sigue siendo 100% TJ.** Si en algún momento quisieras usar el runtime para tu propio uso personal en otro dominio, técnicamente podrías porque la arquitectura lo permite — pero eso sería **tu uso personal externo**, no parte del scope del toolkit ni una promesa de soporte de mi parte.

## Multi-tenant

Cada brain es independiente. El registry global en `~/.jw-brain/registry.toml` mantiene el mapa alias → ruta absoluta. Auto-registro en cada `jw brain init`.

El **caso TJ legítimo** del multi-tenant es separar contextos de estudio: por ejemplo un brain para estudio personal y otro para preparación de reuniones, ambos con dominio `tj` pero distinto vault Obsidian y distinto corpus en `raw/`.

```bash
jw brain init --brain ~/jw-study-brain        # estudio personal
jw brain init --brain ~/jw-meeting-brain      # preparación de reuniones
jw brain list                                 # lista ambos
jw brain status --brain jw-study-brain        # alias resuelve a path
```

## Cómo se integra con las fases previas

| Fase | Cómo F49 la usa |
|---|---|
| **F20 Obsidian** | El wiki vive en `<vault>/Second-Brain/` con write-safe contract idéntico (`.obsidian/` marker + path traversal defense). |
| **F39 NLI runtime** | `lint.contradiction_finder` corre NLI sobre pares de claims que comparten un `Topic`. Detecta contradicciones cross-publication. |
| **F40 content-provenance** | Cada arista lleva `content_hash + accessed_at` + `run_id` + `model_id` + `confidence`. |
| **F41 plugin SDK** | `BrainDomain` se descubre via `jw_agent_toolkit.brain_domains` entry-point group. TJ es builtin; cualquier otro es plugin. |
| **F45 semantic-chunking** | El parser_router puede usar chunkers configurables al preparar texto para el extractor LLM. |

## CLI

| Comando | Qué hace |
|---|---|
| `jw brain init` | Crea estructura, config.toml, CLAUDE.md autogenerado per dominio. Auto-registra alias. |
| `jw brain compile` | Loop discover → parse → LLM extract → upsert grafo + escribir wiki + mover a processed/. `--dry-run` no muta. |
| `jw brain query` | Router Karpathy-first: wiki sintetizada → graph traversal → vector fallback. |
| `jw brain lint` | Orphan pages + (TODO) NLI cross-publication contradictions. |
| `jw brain snapshot` | Tarball del backend a `<brain>/snapshots/`. |
| `jw brain status` | Stats del grafo, raw pending/processed. |
| `jw brain list` | Brains del registry global. |

## MCP tools

| Tool | Equivalente CLI |
|---|---|
| `second_brain_status` | `jw brain status` |
| `second_brain_compile` | `jw brain compile` |
| `second_brain_query` | `jw brain query` |
| `second_brain_lint` | `jw brain lint` |
| `second_brain_snapshot` | `jw brain snapshot` |

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_BRAIN_HOME` | unset | Path absoluto a brain por defecto si no se pasa `--brain` |
| `JW_BRAIN_BACKEND` | `duckdb` | Backend default (`duckdb` o `neo4j`) |
| `JW_GEN_PROVIDER` | `fake` | Provider LLM (`fake`, `ollama`, ...). Default fake para mantener CLI sin red |

## Tests

```bash
.venv/bin/python -m pytest packages/jw-brain/tests/ -v
```
