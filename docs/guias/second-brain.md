# Second Brain (Fase 49)

> Karpathy-style compiler + GraphRAG sobre el toolkit. Dominio TJ como referencia; cualquier otro dominio (finanzas, legal, médico) se conecta como plugin via Fase 41.

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

## Otros dominios (financial brain)

El runtime de F49 **no asume el dominio TJ**. Un plugin externo declara su propio NodeType/EdgeType y se conecta vía Fase 41:

```toml
# jw-brain-finance-plugin/pyproject.toml
[project.entry-points."jw_agent_toolkit.brain_domains"]
finance = "jw_brain_finance.domain:FinanceBrainDomain"
```

```python
class FinanceBrainDomain:
    name = "finance"
    nodes = [NodeSpec("Transaction", ...), NodeSpec("Vendor", ...), ...]
    edges = [EdgeSpec("PAID_TO", ...), EdgeSpec("CATEGORIZED_AS", ...)]
```

Luego: `jw brain init --domain finance --brain ~/financial-brain`. El runtime carga el plugin, escribe `CLAUDE.md` con tu dominio, y arranca. **Cero código del toolkit modificado.**

## Multi-tenant

Cada brain es independiente. El registry global en `~/.jw-brain/registry.toml` mantiene el mapa alias → ruta absoluta. Auto-registro en cada `jw brain init`.

```bash
jw brain init --brain ~/jw-second-brain      # alias = "jw-second-brain"
jw brain init --brain ~/financial-brain      # alias = "financial-brain"
jw brain list                                # lista ambos
jw brain status --brain jw-second-brain      # alias resuelve a path
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
