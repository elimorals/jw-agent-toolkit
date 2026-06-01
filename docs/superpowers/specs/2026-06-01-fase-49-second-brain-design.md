# Fase 49 — `second-brain`: Karpathy-style compiler + GraphRAG + plugin-genericized domain runtime

> **Fecha**: 2026-06-01
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (nueva superficie / paradigma)
> **Tamaño**: XL — ~8-10 semanas
> **Depende de**: Fase 39 (`nli-runtime`), Fase 40 (`content-provenance`), Fase 41 (`plugin-sdk`), Fase 45 (`semantic-chunking`).
> **Habilita**: la transición del toolkit de "librería técnica completa" a **runtime agéntico de second-brains sobre dominios relationship-dense**, con TJ como reference implementation y un primer dominio alternativo (finanzas personales) como prueba de generalidad.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md) (este spec lo extiende — añade F49 fuera del plan maestro original)

## Motivación

Las Fases 39-48 cierran el techo técnico del **toolkit como librería procedural** sobre `jw.org` / `wol.jw.org`. El proyecto puede recuperar, verificar fidelidad, citar verificablemente, generar de forma controlada, y servirse via CLI/MCP/REST.

Pero hay un techo arquitectónico que ninguna de esas fases ataca: **la información se sigue recuperando "de cero" en cada query**. El topic_index existe, las cross-references existen, las study notes existen — pero como datos transitorios que se computan cada vez. Nada se **integra** en una estructura persistente que represente "lo que el sistema sabe".

Andrej Karpathy formalizó en abril 2026 (cf. su [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) un patrón que invierte el paradigma RAG: en vez de un LLM que **consulta** documentos, un LLM que **compila** documentos a un wiki persistente que se vuelve la base de conocimiento. Su frase clave:

> "Ask a subtle question that requires synthesizing five documents, and the LLM has to find and piece together the relevant fragments every time. Nothing is built up."

Microsoft GraphRAG (2024) y los benchmarks comparativos de 2026 demuestran cuantitativamente la diferencia: queries que requieren 3+ saltos lógicos pasan de ~16.7% accuracy en vector RAG a 56-80% en grafo + vector híbrido. Para dominios **relationship-dense** —compliance, legal, científico, **religioso**— el grafo es estrictamente superior.

**La literatura JW es un grafo ya construido por la organización** que el toolkit ignora estructuralmente:
- La Biblia contiene 63,779 cross-references explícitas (Chris Harrison, BibleViz).
- El Índice Temático (`rsg/wt-pubidx`) es literalmente un grafo bipartito tema↔publicación.
- Las study notes de la NWT son anotaciones por versículo que enlazan publicaciones, otros versículos y conceptos.
- WOL ya marca cada xref con `<a class="xref">` y URLs canónicas.

Fase 49 hace tres cosas a la vez:

1. **Materializa la estructura latente** en un grafo persistente (`GraphBackend`: DuckDB embebido por default, Neo4j externo opt-in).
2. **Aplica el patrón Karpathy literal**: agente LLM-driven que compila `raw/` → `wiki/` Markdown sobre Obsidian, con `CLAUDE.md` como schema operacional.
3. **Generaliza la arquitectura via Fase 41 plugin-sdk**: el dominio (TJ, finanzas, legal, médico) se conecta como plugin. El toolkit deja de ser "para TJ" y se vuelve "runtime para construir second-brains sobre cualquier dominio relationship-dense, con TJ como implementación de referencia".

## El paradigma en una frase

> El usuario tira **cualquier dato crudo** en una carpeta. Un agente LLM "sale a pasear" cada cierto tiempo, **da orden al caos**, materializa entidades + relaciones en un grafo navegable y un wiki Markdown explorable en Obsidian. La aplicación final **no consume documentos** — consume el modelo de conocimiento que el agente mantiene vivo.

## Decisiones tomadas (del usuario, 2026-06-01)

| # | Decisión | Implicación arquitectónica |
|---|---|---|
| 1 | **Dual backend**: DuckDB (default, embebido, local-first) + Neo4j (opt-in, externo, Cypher completo) | `GraphBackend` Protocol con dos implementaciones intercambiables; ambas pasan los mismos tests de contrato |
| 2 | **Wiki sobre Obsidian** (extensión de Fase 20) | El wiki vive en una carpeta de la vault del usuario; markdown puro con wikilinks; Obsidian graph view es free visualization |
| 3 | **LLM-driven compiler** (Karpathy literal, no procedural) | Rompe la regla histórica del toolkit ("agentes procedurales no LLM"). Reconocido y mitigado: provider local por default (Ollama llama3.1), cache por content_hash, dry-run obligatorio, snapshot/rollback |
| 4 | **F49 después de F41** | F49 es la **implementación de referencia** del plugin SDK. Cada dominio se conecta como plugin (`jw_agent_toolkit.brain_domains`) — TJ es uno, "financial-brain" es otro |
| 5 | **Scope abierto desde día 1**: cualquier formato cae en `raw/inbox/` | El compiler enruta por mime-type a parsers (los 9 existentes + plugins via F41) sin asumir el tipo |

## Distinción de capas (ortogonalidad con fases previas)

| Capa | Pregunta que responde | Fase | Modo |
|---|---|---|---|
| L0 — URL resolve | "¿Existe?" | 23 | live HTTP |
| L1 — catalog | "¿Está en MepsCatalog?" | 23 | offline |
| L2 — content fidelity | "¿El texto sigue siendo el mismo?" | 40 | hash + re-fetch |
| L3 — entailment | "¿Se desprende lógicamente?" | 39 | NLI semántico |
| **L4 — knowledge graph** | "¿Cómo conecta esto con el resto de lo que sé?" | **49** | grafo materializado + wiki sintetizado |
| L5 — proactive synthesis | "¿Qué falta? ¿Qué contradice?" | **49 (lint)** | agente "sale a pasear" sobre L4 |

Las seis son ortogonales. L4/L5 son donde Fase 49 vive — la primera capa que ataca **la estructura entre los textos**, no los textos en sí. F39, F40 y F45 alimentan la calidad de L4 (cada arista lleva provenance, cada chunk LLM tiene cache, cada claim puede re-validarse por NLI).

## Objetivos (en orden de prioridad)

1. **Materializar el grafo TJ** completo desde el corpus disponible: versículos ↔ temas ↔ publicaciones ↔ cross-refs ↔ personas/lugares bíblicos. Sobre `wol.jw.org` + JWPUB descifrados + EPUBs + index temático.
2. **Operar el patrón Karpathy** completo (raw/ + wiki/ + CLAUDE.md + agente compiler/query/lint) sobre una vault Obsidian gestionada.
3. **Cumplir el "dual backend"**: mismos tests de contrato pasan en DuckDB y Neo4j; la elección es env var o flag, **el código de aplicación no cambia**.
4. **Demostrar genericidad** via un segundo brain de **finanzas personales** entregado como plugin externo (`jw-brain-finance-plugin`) que reusa 100% el runtime de F49 con un `CLAUDE.md` distinto y NodeType/EdgeType propios.
5. **Lint cross-publication** sobre el grafo aprovechando F39 NLI: descubrir contradicciones latentes entre publicaciones TJ de distintas épocas — el caso que ninguna otra capa puede atacar.
6. **Multi-tenant**: soportar varios brains simultáneos (`~/jw-second-brain/`, `~/financial-brain/`) sin colisión.
7. **Backup / snapshot / dry-run** como ciudadanos de primera clase — un LLM-driven compiler sin rollback es ingeniería irresponsable.

## No-objetivos (boundaries vinculantes)

- **No** reemplazar el RAG vectorial existente (Fase 6/33). El grafo es complemento; los chunks vectoriales siguen siendo el fallback para queries que no enganchan estructura.
- **No** distribuir el wiki generado de TJ. Política #6 (Fase 38) sigue vigente — el wiki es **personal**, vive en la vault del usuario, nunca se publica como contenido derivado.
- **No** sandboxing del compiler agent. Misma postura que Fase 41: el plugin/compilador corre en proceso. Documentado en `security.md`.
- **No** UI nueva. El front-end es Obsidian + jw-cli + jw-mcp. Cualquier viewer web es post-F49.
- **No** hot-reload del grafo. Cambios al schema requieren `compile --rebuild`. Snapshots cubren la transición.
- **No** ML/training sobre el wiki. El wiki alimenta queries y lint; entrenamiento custom es F22+ scope (jw-finetune).
- **No** modificar las notas del usuario en Obsidian. El agente escribe **solo** en `<vault>/Second-Brain/wiki/...`. Idéntico contrato write-safe que F20.

## Arquitectura

### Nuevo paquete del workspace

```
packages/jw-brain/
├── pyproject.toml                       # [project.optional-dependencies]: duckdb, neo4j
├── src/jw_brain/
│   ├── __init__.py                      # API pública mínima
│   ├── backends/                        # GraphBackend Protocol + 2 implementaciones
│   │   ├── protocol.py                  # GraphBackend ABC
│   │   ├── duckdb_backend.py            # default, embedded
│   │   ├── neo4j_backend.py             # opt-in, external
│   │   └── factory.py                   # get_backend(name|env)
│   ├── schema/                          # schema-on-read (descubrible)
│   │   ├── nodes.py                     # NodeType registry
│   │   ├── edges.py                     # EdgeType registry
│   │   ├── provenance.py                # Aristas con source_chunk + run_id + confidence
│   │   └── builtins.py                  # TJ domain: Verse, Topic, Publication, Concept, Person, Place
│   ├── wiki/                            # Wiki layer sobre Obsidian
│   │   ├── obsidian_writer.py           # extiende jw_core.integrations.obsidian_vault
│   │   ├── pages/                       # templates Markdown por NodeType
│   │   └── index.py                     # genera index.md + log.md
│   ├── compiler/                        # El "agente que sale a pasear"
│   │   ├── orchestrator.py              # compile() main loop
│   │   ├── llm_extractor.py             # LLM-driven entity/relation extraction
│   │   ├── parser_router.py             # raw file → parser apropiado (jw-core + plugins F41)
│   │   ├── cache.py                     # cache por sha256(content + prompt_version + provider_id)
│   │   ├── dry_run.py                   # reporte sin tocar grafo/wiki
│   │   └── snapshot.py                  # tarball del grafo + wiki para rollback
│   ├── query/                           # Karpathy-first + graph + vector
│   │   ├── router.py                    # decide: wiki-first / graph-traversal / vector-fallback
│   │   ├── wiki_searcher.py             # busca en synthesis pre-compilada
│   │   ├── graph_traverser.py           # Cypher (Neo4j) o SQL recursivo (DuckDB)
│   │   └── hybrid_reranker.py           # vector recall + graph rerank
│   ├── lint/                            # "el agente sale a pasear" sin disparador
│   │   ├── orphan_pages.py              # detecta wiki pages sin edges
│   │   ├── stale_chunks.py              # detecta provenance_drift (reusa F40)
│   │   ├── contradiction_finder.py      # corre F39 NLI cross-publication
│   │   ├── missing_xrefs.py             # detecta gaps respecto al índice temático
│   │   └── reporter.py                  # genera lint-report.md
│   ├── domain/                          # extensión via F41 plugin SDK
│   │   ├── contract.py                  # BrainDomain Protocol (NodeType[], EdgeType[], CompilerHook[], LintHook[])
│   │   ├── registry.py                  # descubre plugins via jw_agent_toolkit.brain_domains
│   │   └── builtin_tj.py                # TJ domain como referencia (Verse, Topic, Pub, ...)
│   ├── cli.py                           # jw brain {init, compile, query, lint, snapshot, status}
│   └── server.py                        # MCP tools: second_brain_*
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── raw_samples/                 # mini corpus: 1 jwpub, 1 epub, 5 md notes
│   │   ├── golden_graph.json            # estado esperado tras compile()
│   │   └── financial_brain_plugin/      # ejemplo de plugin alternativo
│   ├── test_backends_contract.py        # corre los MISMOS tests sobre DuckDB y Neo4j
│   ├── test_schema_registry.py
│   ├── test_wiki_writer.py
│   ├── test_compiler_dry_run.py
│   ├── test_compiler_cache.py
│   ├── test_compiler_snapshot.py
│   ├── test_query_router.py
│   ├── test_lint_contradictions.py      # mock NLI provider; verifica detection
│   ├── test_lint_orphans.py
│   ├── test_domain_plugin_tj.py
│   ├── test_domain_plugin_finance.py    # fixture plugin financiero
│   ├── test_cli_smoke.py
│   └── test_multi_tenant.py
```

### El layout que el usuario ve

```
~/jw-second-brain/                       ← una "brain instance"
├── raw/
│   ├── inbox/                           ← user tira aquí (mime-types arbitrarios)
│   │   ├── nwt-genesis.jwpub
│   │   ├── Reasoning.epub
│   │   ├── notas-personales-2024.md
│   │   ├── transcripcion-broadcast-2024-12.txt
│   │   └── screenshot-wp22-pp.png
│   └── processed/                       ← post-ingest, audit trail
│       └── {original_path_preserved}/
│
├── vault/                               ← Obsidian vault gestionada por F49
│   └── Second-Brain/                    ← namespace EXCLUSIVO del agente
│       ├── CLAUDE.md                    ← schema/rules del LLM compiler
│       ├── wiki/
│       │   ├── verses/Juan_3_16.md
│       │   ├── topics/Trinidad.md
│       │   ├── publications/wt22-pp.md
│       │   ├── concepts/Identidad_de_Cristo.md
│       │   ├── people/David.md
│       │   ├── places/Egipto.md
│       │   ├── timeline/586-aec.md
│       │   ├── index.md                 ← catálogo navegable autogenerado
│       │   └── log.md                   ← append-only audit
│       └── _snapshots/                  ← tarballs de rollback
│           └── 2026-06-01T10-30-00Z.tar.zst
│
├── graph/                               ← capa GraphRAG persistente
│   ├── backend.duckdb                   ← default
│   ├── communities.json                 ← clusters Leiden (opt-in, batch)
│   └── embeddings/                      ← vector fallback para hybrid query
│       └── chunks.faiss
│
├── config.toml                          ← per-brain config (backend, vault path, LLM provider, ...)
└── .jw-brain-state.json                 ← state interno (last_compile, last_lint, cache_keys)
```

Y el usuario puede tener varios:

```
~/jw-second-brain/        ← brain TJ (este spec)
~/financial-brain/        ← brain financiero (plugin externo F41)
~/legal-brain/            ← brain legal (plugin externo F41)
```

### `GraphBackend` Protocol

```python
# jw_brain/backends/protocol.py
from typing import Protocol, runtime_checkable, Iterator, Any
from contextlib import contextmanager

@runtime_checkable
class GraphBackend(Protocol):
    """Backend-agnostic graph store.

    Both DuckDB (embedded, default) and Neo4j (external, opt-in) implement
    this. Tests run the same contract against both via parametrize.
    """

    name: str  # "duckdb" | "neo4j"

    # ── Mutations ───────────────────────────────────────────────────────
    def upsert_node(
        self,
        *,
        node_type: str,
        canonical_id: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str:
        """MERGE node. Returns internal id. canonical_id is the dedup key."""

    def upsert_edge(
        self,
        *,
        edge_type: str,
        from_node: str,
        to_node: str,
        properties: dict[str, Any],
        provenance: dict[str, Any],
    ) -> str:
        """MERGE edge. Returns internal id. (from, to, edge_type) is the dedup key."""

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All-or-nothing. Rolls back on exception."""

    # ── Reads ───────────────────────────────────────────────────────────
    def get_node(self, canonical_id: str) -> dict[str, Any] | None: ...
    def neighbors(
        self,
        canonical_id: str,
        *,
        edge_type: str | None = None,
        hops: int = 1,
        direction: str = "both",
    ) -> list[dict[str, Any]]: ...

    def query(self, expr: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """DuckDB: SQL with recursive CTE. Neo4j: Cypher. Backend-specific syntax —
        callers should prefer neighbors()/get_node() unless they need traversal."""

    # ── Operacionales ───────────────────────────────────────────────────
    def snapshot(self, path: Path) -> None: ...
    def restore(self, path: Path) -> None: ...
    def stats(self) -> dict[str, int]: ...  # {n_nodes, n_edges, by_type, ...}
```

### Wiki layer sobre Obsidian (extiende F20)

`packages/jw-brain/src/jw_brain/wiki/obsidian_writer.py` reusa `jw_core.integrations.obsidian_vault` (ya existe y soporta vault detection + `.obsidian/` marker + path-traversal defense del Fase 48). Añade:

- **Write contract estricto**: el agente NUNCA escribe fuera de `<vault>/Second-Brain/`. La validación pasa por `_resolve_safe_path()` con check de `vault.resolve()`.
- **Page templates** por NodeType (verse, topic, publication, etc.). Cada template tiene secciones obligatorias (`## Citations`, `## Cross-references`, `## See also`) y secciones LLM-generated (`## Synthesis`, `## Open questions`).
- **Wikilinks bidireccionales** materializados como Obsidian `[[link]]`. Cuando el grafo añade arista `Juan_3_16 -[CITED_IN]-> wt22-pp`, ambas páginas se actualizan.
- **Frontmatter YAML estricto** con `node_type`, `canonical_id`, `last_compiled_at`, `provenance.run_id`, `confidence_score` para Dataview queries del usuario.
- **`log.md` append-only**: cada `compile()` agrega un entry con timestamp, archivos procesados, nodos/aristas creados, contradicciones flagged.
- **`index.md` regenerable**: cada N compiles se regenera del state del grafo. Idempotente.

### Compiler agente (LLM-driven)

**El paso más sensible.** Rompe explícitamente la regla histórica "agentes procedurales no LLM" del toolkit. Mitigaciones de robustez (puntos añadidos a la propuesta original):

1. **Cache por content_hash**: re-compilar la misma raw file (mismo `sha256(content) + prompt_version + provider_id`) salta la llamada LLM. Patrón idéntico a Fase 45 LLMChunker.
2. **Dry-run mode obligatorio**: `compile --dry-run` emite el reporte de qué nodos/aristas/wiki pages crearía sin tocar nada. El usuario lo revisa antes del primer run real.
3. **Provider default local**: Ollama `llama3.1:8b`. API providers (Claude, OpenAI) son opt-in vía env var. Cero red por default.
4. **Snapshot pre-compile**: cada `compile()` exitoso crea tarball `_snapshots/{timestamp}.tar.zst` del grafo + wiki **antes** de aplicar cambios. Rollback con `jw brain rollback <ts>`.
5. **Confidence score por edge**: cada arista lleva `confidence: float ∈ [0,1]` del extractor LLM. Lint reporta aristas low-confidence; usuario puede confirmar/eliminar manualmente.
6. **Run_id propagado**: cada operación de compile tiene `run_id = uuid4()`. Toda página wiki y arista creada lleva `provenance.run_id`. Rollback selectivo de "el último run" es trivial.
7. **Temperature 0**: el LLM extractor corre con temperature=0 + seed fijo para determinismo dentro del mismo provider/prompt_version.
8. **Schema-on-read estricto en NodeType**: el LLM emite `{"node_type": "Verse", "canonical_id": "...", ...}`. Si `node_type` no está registrado, el extractor lo **flagea** en log pero NO inventa schema. El usuario decide registrarlo.
9. **Audit forensics**: cada llamada LLM se loguea con prompt sha256, tokens in/out, latency, model_id. Permite reconstruir qué pasó si el grafo se ensucia.
10. **Conflict resolution** configurable (por dominio en `CLAUDE.md`):
    - `merge`: union de propiedades; provenance lista
    - `override`: la última arista escrita gana
    - `flag`: deja ambas con `flag: contradicts_existing` y emite warning en lint

### Schema-on-read

Crítico para genericidad. NodeType/EdgeType son **datos registrados** (Python o JSON), no clases hardcoded:

```python
# jw_brain/schema/nodes.py
@dataclass(frozen=True)
class NodeTypeSpec:
    name: str                          # "Verse", "Transaction", "Vendor"
    canonical_id_pattern: str          # regex o template: "verse:{book}:{ch}:{v}"
    properties: dict[str, type]        # campos esperados; valida en upsert
    wiki_page_template: str            # ruta a .md template
    obsidian_subdir: str               # "verses/", "vendors/"
    confidence_threshold: float = 0.5  # debajo de esto, marca low_confidence

class NodeRegistry:
    """Singleton process-wide. Populated by:
      1. jw_brain.schema.builtins (TJ domain)
      2. Domain plugins via F41 (`jw_agent_toolkit.brain_domains`)
    """

    def register(self, spec: NodeTypeSpec) -> None: ...
    def get(self, name: str) -> NodeTypeSpec | None: ...
    def all(self) -> list[NodeTypeSpec]: ...
```

EdgeType análogo. La clave: el toolkit no asume `Verse` o `Transaction` — descubre lo que está registrado. **Eso es lo que hace que el mismo runtime sirva para TJ y para finanzas.**

## Las 5 operaciones del agente (expandidas de 3 a 5)

### 1. `compile(raw_path) -> CompileReport`

Loop principal:

```
1. Snapshot pre-compile (skippable con --no-snapshot, no recomendado)
2. for file in raw/inbox/:
     2.1 hash = sha256(file)
     2.2 if cache.has(hash): continue
     2.3 mime = detect_mime(file)
     2.4 parser = parser_router.resolve(mime)   ← F41 plugins entran aquí
     2.5 chunks = parser.parse(file)            ← F45 chunkers
     2.6 stamps = stamp_provenance(chunks)      ← F40
     2.7 extracted = llm_extractor.run(chunks, schema=NodeRegistry.all())
         → returns list[NodeUpsert | EdgeUpsert]
     2.8 with backend.transaction():
            for upsert in extracted:
                backend.upsert_*(upsert)
            for page_to_touch in wiki_pages_affected(extracted):
                obsidian_writer.update(page_to_touch)
     2.9 if dry_run: print plan, exit
     2.10 move file → raw/processed/
     2.11 append entry to log.md
3. Regenerate index.md if N % regen_interval == 0
4. Return CompileReport: {n_files, n_nodes_new, n_edges_new, contradictions_flagged, ...}
```

### 2. `query(question, *, mode="auto") -> QueryResult`

Karpathy-first, graph-second, vector-third. Modos:

- `auto` (default): el router decide
- `wiki`: forzar wiki-only
- `graph`: forzar graph traversal
- `vector`: forzar fallback vectorial

Router heuristics (en `query/router.py`):

```python
def route(question: str) -> QueryStrategy:
    # Multi-hop detection: "que conecte", "a través de", "que también", "cross"
    if has_multi_hop_signal(question):
        return QueryStrategy.GRAPH_FIRST
    # Entity-specific: contains canonical_id-like (Juan 3:16, wt22-pp)
    if has_canonical_entity(question):
        return QueryStrategy.WIKI_FIRST
    # Default: wiki-first per Karpathy
    return QueryStrategy.WIKI_FIRST
```

El benefit concreto del grafo: queries como "qué versículos sobre la condición humana se citan en publicaciones que también citan Eclesiastés 9:5" se resuelven con 2-hop traversal en milisegundos.

### 3. `lint() -> LintReport`

El agente "sale a pasear" sin user trigger (manual o cron). Detecta:

| Check | Cómo | Aprovecha |
|---|---|---|
| Páginas wiki huérfanas | sin aristas in/out en grafo | — |
| Aristas low-confidence | `confidence < threshold` por NodeType | — |
| Contradicciones cross-publication | NLI sobre cada par `(claim_a, claim_b)` que comparten verse_node o topic_node | **F39 NLI** |
| Provenance drift | content_hash de citation viva vs almacenado | **F40 provenance_check** |
| Chunks LLM stale | cache age > N días en F45 LLMChunker | F45 |
| Missing xrefs | nodo Verse sin edge a publicaciones que lo citan según índice temático | — |
| Schema-on-read failures | nodos creados con NodeType desconocido (LLM hallucinó) | schema registry |

Output: `lint-report.md` en la vault + entradas en `log.md`. Telemetría opt-in (F9): cada drift se loguea.

### 4. `snapshot(label?) -> SnapshotInfo`

Tarball `_snapshots/{ts}-{label?}.tar.zst` con:
- `graph/` completo (backend-agnostic export)
- `vault/Second-Brain/wiki/` completo
- `.jw-brain-state.json`

`restore <ts>` revierte ambos atómicamente.

### 5. `sync_obsidian() -> SyncReport`

Cuando el **usuario** edita una wiki page (¡tiene derecho!) detectamos el cambio y:
- Markamos la page como `human_edited: true` en frontmatter
- Excluimos esa page de re-write automático por el LLM (próximo `compile()`)
- El usuario puede "release back to LLM" via frontmatter flag

Esto resuelve el conflicto humano/agente fundamental: el usuario quiere editar; el LLM quiere "compilar". Política: humano gana por default.

## Genericidad via F41 plugin SDK

El segundo brain de finanzas vive como paquete externo:

```toml
# jw-brain-finance-plugin/pyproject.toml
[project]
name = "jw-brain-finance-plugin"
dependencies = ["jw-agent-toolkit>=1.0,<2.0"]

[project.entry-points."jw_agent_toolkit.brain_domains"]
finance = "jw_brain_finance.domain:FinanceBrainDomain"
```

```python
# jw_brain_finance/domain.py
from jw_brain.domain.contract import BrainDomain, NodeTypeSpec, EdgeTypeSpec

class FinanceBrainDomain:
    name = "finance"

    nodes = [
        NodeTypeSpec(name="Transaction", canonical_id_pattern="tx:{date}:{amount}:{hash}", ...),
        NodeTypeSpec(name="Vendor", canonical_id_pattern="vendor:{slug}", ...),
        NodeTypeSpec(name="Category", canonical_id_pattern="cat:{slug}", ...),
        NodeTypeSpec(name="TaxYear", canonical_id_pattern="tax:{year}", ...),
        NodeTypeSpec(name="Account", canonical_id_pattern="acct:{slug}", ...),
    ]
    edges = [
        EdgeTypeSpec(name="PAID_TO", source=("Transaction",), target=("Vendor",), ...),
        EdgeTypeSpec(name="CATEGORIZED_AS", source=("Transaction",), target=("Category",), ...),
        EdgeTypeSpec(name="AFFECTS_TAX", source=("Transaction",), target=("TaxYear",), ...),
    ]
    parser_hooks = [...]  # parsers para extractos bancarios, facturas pdf
    compiler_hooks = [...]  # prompts custom para LLM extraction
    lint_hooks = [...]     # lint específico: TaxYear sin Cierre, Vendor duplicado, etc.
```

`jw brain init --domain finance --vault ~/financial-brain/` instala el plugin, lee su `CLAUDE.md`, levanta el runtime con NodeType/EdgeType financieros, escribe a Obsidian vault financiera. **Cero código nuevo del toolkit por dominio adicional.**

## Multi-tenant / multi-brain

Cada "brain instance" tiene su `config.toml`:

```toml
# ~/jw-second-brain/config.toml
[brain]
name = "jw-tj"
domain = "tj"                            # plugin name
vault = "~/Documents/Obsidian/jw-vault"
vault_namespace = "Second-Brain"
graph_backend = "duckdb"                 # | "neo4j"
graph_path = "graph/backend.duckdb"

[compiler]
llm_provider = "ollama"
llm_model = "llama3.1:8b"
prompt_version = "v1"
cache_dir = "~/.jw-brain/cache/jw-tj"
snapshot_on_compile = true
dry_run_required_first_time = true

[lint]
nli_provider = "deberta"                 # F39
nli_threshold = 0.7
schedule = "weekly"                      # cron / on_demand / weekly / daily

[vector_fallback]
enabled = true
embedder = "bge-m3"                      # F33
index_path = "graph/embeddings/chunks.faiss"
```

El CLI selecciona brain por flag o env:

```bash
jw brain --brain ~/jw-second-brain/ compile
jw brain --brain ~/financial-brain/ compile
JW_BRAIN_HOME=~/jw-second-brain jw brain compile
```

`jw brain list` enumera brains conocidos (descubiertos en `~/.jw-brain/registry.toml`).

## CLAUDE.md como contrato operacional

Template generado por `jw brain init`:

```markdown
# Second Brain — operational schema for the LLM compiler

> This file tells the agent how to operate the wiki, the graph, and the rules.

## Ownership

- `raw/` is the user's. The agent reads, never writes.
- `vault/Second-Brain/` is the agent's. User edits are honored (see "Human edits").
- `graph/` is the agent's. User reads via queries; never edits directly.

## NodeTypes (per active domain)

{auto-generated from NodeRegistry}

## EdgeTypes

{auto-generated from EdgeRegistry}

## Compile loop

When the user runs `jw brain compile`:
1. For each new file in `raw/inbox/`:
   - Extract entities + relations matching NodeTypes/EdgeTypes above
   - Emit JSON: `{"nodes": [...], "edges": [...], "confidence": ...}`
   - NEVER invent new NodeType. If unclear, flag in log.
   - For each entity, ensure a wiki page exists; update synthesis section
2. Append to `log.md`
3. Move file to `raw/processed/`

## Conflict policy

When an upsert conflicts with existing data:
- For Verse properties: merge (union of provenance lists)
- For Topic synthesis: override last-wins
- For contradictory claims (NLI = contradicts): FLAG, do not overwrite

## Human edits

If a wiki page has `human_edited: true` in frontmatter:
- DO NOT regenerate the synthesis section
- DO update the references/citations section
- DO update the graph based on links you find

## Citations

EVERY claim in the wiki MUST point to a passage in the graph with content_hash.
No claim, no cite. (Fase 40 invariant.)

## Lint

Once a week (configurable), run `jw brain lint`:
- Check NLI cross-publication for contradictions
- Check provenance_check for drift
- Flag low-confidence edges
- Output: `Second-Brain/lint-{date}.md` + log entry
```

## Integraciones con fases existentes

| Fase | Cómo F49 la usa |
|---|---|
| **F20 Obsidian bridge** | Wiki vive en Obsidian vault. F49 extiende el writer write-safe. |
| **F22 eval doctrinal** | Golden cases L4 nuevos: queries multi-hop que solo grafo resuelve correctamente. |
| **F23 citation validator** | El compiler valida cada citation antes de materializarla como arista. |
| **F33 embed/rerank** | El vector fallback del query router usa el embedder configurado. |
| **F38 jw-gen** | El LLM compiler usa GenerationProvider. Default Ollama local. |
| **F39 NLI runtime** | `lint.contradiction_finder` corre NLI sobre pares de claims. **Es donde F39 brilla**. |
| **F40 content-provenance** | Cada arista lleva `content_hash + accessed_at`. `lint.stale_chunks` usa `provenance_check()`. |
| **F41 plugin SDK** | `BrainDomain` es un nuevo extension point (`jw_agent_toolkit.brain_domains`). |
| **F45 semantic-chunking** | El compiler usa chunkers configurables (default semantic) para preparar texto al extractor LLM. |
| **F48 wol-browser-ext** | Future: botón "Guardar al second brain" además de Obsidian. |

## Reglas duras de diseño

1. **El runtime no asume dominio**. NodeType/EdgeType vienen del registry. Mover TJ a un plugin separado es opcional pero posible.
2. **El backend es elegible en cualquier momento**. DuckDB ↔ Neo4j vía export/import. No hay lock-in.
3. **Sin red en tests**. LLM mockeable. Backends en `:memory:` o tmpfs. Snapshot a tmp_path.
4. **Schema-on-read estricto**. El compiler NUNCA registra NodeType nuevos en runtime. Solo el plugin domain puede.
5. **Provenance es non-negotiable**. Toda arista creada por LLM tiene `run_id`, `model_id`, `confidence`. F40 keys propagadas a citations.
6. **Wiki = output puro derivable**. Borrar la vault y reconstruir desde grafo + raw debe ser idempotente.
7. **Dry-run primero**. Primer `compile()` sobre un brain nuevo requiere `--dry-run` previo. Hard-fail si no se hizo.
8. **Snapshots automáticos**. Cada `compile()` snapshot. Eviction policy: keep last N (default 10).
9. **Conflict resolution explícita**. Política por dominio en `CLAUDE.md`. Silent merge prohibido para edge_types marcados sensitive.
10. **Multi-language wiki**. Páginas en es/en/pt con secciones nativas. El LLM compiler escribe en el idioma del raw input; el wiki tiene `## Cross-translation` que apunta a páginas hermanas.

## Tests (sin red, sin LLM real)

Toda la suite corre sobre:
- DuckDB `:memory:` y Neo4j vía testcontainers (opt-in con `--neo4j-tests`).
- FakeGenerationProvider con outputs canned (cf. F38/F45 pattern).
- FakeNLIProvider para lint (cf. F39 pattern).
- Mini fixtures de raw: 1 jwpub stub, 1 markdown nota, 1 transcripción.

**Tests críticos**:
- `test_backends_contract.py` parametrizado sobre `["duckdb", "neo4j"]` — los mismos asserts pasan en ambos.
- `test_compiler_cache.py` — re-run sobre mismo raw no llama al LLM.
- `test_compiler_snapshot.py` — restore desde snapshot deja grafo + wiki bit-identical.
- `test_lint_contradictions.py` — fake NLI dice "contradicts" → arista marcada y reportada.
- `test_domain_plugin_finance.py` — instala plugin fixture, verifica NodeType registrados, compila 1 fixture financiero.
- `test_multi_tenant.py` — dos brains paralelos sobre tmp_paths distintos no se contaminan.

CI público corre todo offline. `--neo4j-tests` opcional.

## Métricas de éxito de la fase

- ✅ `jw brain init --domain tj --vault tmp/` crea estructura completa + CLAUDE.md.
- ✅ `jw brain compile` sobre fixture mini-corpus crea ≥10 nodes, ≥15 edges, ≥5 wiki pages.
- ✅ Multi-hop query "versículos citados en publicaciones que también citan Eclesiastés 9:5" devuelve resultado en <1s con DuckDB.
- ✅ Mismo query devuelve mismo resultado en Neo4j backend.
- ✅ `jw brain lint` corre NLI cross-publication y emite reporte con ≥1 contradicción detectada en fixture.
- ✅ Dry-run reporta plan sin tocar grafo ni wiki.
- ✅ Snapshot + restore es idempotente (golden hash).
- ✅ `jw brain --brain ~/financial-brain/ compile` con plugin fixture financiero crea Transaction/Vendor/Category sin tocar código del toolkit.
- ✅ Edit manual de un wiki page → `human_edited: true` → próximo compile preserva la edición.
- ✅ Suite completa en <60s offline.
- ✅ Cero regresiones en los 2030+ tests existentes.

## Riesgos y mitigaciones (los honestos)

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | **LLM compiler no determinista**: dos runs producen grafos distintos | Cache por content_hash + temperature=0 + seed fijo. Tests sobre FakeProvider deterministas. Real-LLM en E2E sólo nightly. |
| 2 | **Grafo se ensucia con tiempo** | Lint semanal + snapshots automáticos + confidence threshold para auto-purge de low-confidence edges no confirmadas en N runs. |
| 3 | **LLM inventa entities/edges fuera del schema** | Schema-on-read estricto: NodeType desconocido → flagear, no auto-create. Confidence score per edge. |
| 4 | **Cost de tokens** (raw grandes → muchas llamadas) | Default Ollama local. Cache content_hash. Chunking (F45) reduce contexto. Streaming compile para archivos > N MB. |
| 5 | **Wiki crece sin control** | Karpathy comprobó empíricamente que ~100 articles / 400k words es manejable. Lint detecta orphans y stale. |
| 6 | **Doble fuente de verdad** (grafo vs wiki) | Wiki es derivado del grafo (rebuild from graph es idempotente). Grafo es source of truth. |
| 7 | **Política #6 (no contenido distribuible)** | Wiki es **personal** en vault del usuario. NUNCA se publica. Cada claim apunta a passage canónico via F40. Idéntico contrato a F20. |
| 8 | **Backend lock-in** | Protocol contract idéntico. Export DuckDB → import Neo4j vía Parquet intermedio. Test de migración bidireccional en suite. |
| 9 | **Plugin malicioso** (F41 boundary) | Mismas mitigaciones que F41: ALLOW_LIST + DISABLED + documentado. F49 hereda. |
| 10 | **El usuario edita el grafo manualmente y rompe la consistencia** | Backend tiene `read_only_after_lint` flag opt-in. Mejor: no exponer el grafo binario; el usuario interactúa via CLI/MCP/wiki. |
| 11 | **Conflict resolution silencioso entre runs** | `CLAUDE.md` declara política explícita por EdgeType. Flag mode default para cualquier edge_type marcado `sensitive`. |
| 12 | **Cold start: primer compile lleva horas sobre corpus grande** | Streaming compile + paralelización via asyncio + per-file checkpointing en `.jw-brain-state.json`. Interrumpible y reanudable. |
| 13 | **Obsidian sync conflicts** (mobile / multi-device) | El agente respeta `human_edited: true`. Recommended: usuario corre `compile` en una sola máquina; sync Obsidian para read. |
| 14 | **Neo4j operativo (proceso externo)** | Doc clara: "Neo4j es opt-in. DuckDB cubre 90% de casos. Solo si necesitas Cypher avanzado o > 10M edges." Testcontainers opcional. |
| 15 | **El lint NLI cross-publication produce muchos falsos positivos** | Threshold configurable. Lint emite ranking por NLI score. Usuario marca true_positive / false_positive en frontmatter; el lint aprende a ignorarlos. |

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages --extra brain

# 2. Init brain TJ
mkdir /tmp/jw-test-brain
uv run jw brain init --domain tj --vault /tmp/jw-test-brain/vault

# 3. Llenar inbox con fixture
cp packages/jw-brain/tests/fixtures/raw_samples/* /tmp/jw-test-brain/raw/inbox/

# 4. Dry-run primero (obligatorio)
uv run jw brain --brain /tmp/jw-test-brain/ compile --dry-run

# 5. Compile real
uv run jw brain --brain /tmp/jw-test-brain/ compile

# 6. Query multi-hop
uv run jw brain --brain /tmp/jw-test-brain/ query \
  "Qué versículos sobre la condición humana se citan junto a Eclesiastés 9:5?"

# 7. Lint con NLI
JW_NLI_PROVIDER=fake uv run jw brain --brain /tmp/jw-test-brain/ lint

# 8. Snapshot + restore
uv run jw brain --brain /tmp/jw-test-brain/ snapshot --label pre-experiment
# ... modifica algo ...
uv run jw brain --brain /tmp/jw-test-brain/ rollback --to pre-experiment

# 9. Backend swap
uv run jw brain --brain /tmp/jw-test-brain/ migrate --to neo4j
# verificación: misma query devuelve mismos resultados

# 10. Plugin domain (finance)
uv pip install -e packages/jw-brain/tests/fixtures/financial_brain_plugin
mkdir /tmp/fin-test-brain
uv run jw brain init --domain finance --vault /tmp/fin-test-brain/vault
uv run jw brain --brain /tmp/fin-test-brain/ compile

# 11. Tests suite
.venv/bin/python -m pytest packages/jw-brain/ -v
```

## Pendientes explícitos (post-F49)

- Web UI para visualizar el grafo (Obsidian graph view ya da el 80% del valor — UI dedicada queda como post).
- Mobile compile (compile remoto desde el móvil del usuario vía REST API de jw-mcp).
- Distributed brains (federación entre máquinas). No urgente; F11 (sync) ya cubre el caso simple.
- Auto-ML: el lint aprende a auto-rechazar contradicciones que el usuario marcó falsas N veces.
- Marketplace de domains (en PyPI con prefijo `jw-brain-*-plugin`). No es responsabilidad del toolkit.

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-06-01-fase-49-second-brain-plan.md`.

Pasos cronológicos:

1. Scaffold `packages/jw-brain/` workspace member + Protocols vacíos.
2. `GraphBackend` Protocol + DuckDB backend + contract tests parametrizados.
3. `GraphBackend` Neo4j backend (mismos tests pasan).
4. Schema-on-read: NodeRegistry + EdgeRegistry + builtins TJ.
5. `ObsidianWikiWriter` extendiendo F20 con write-safe contract.
6. `parser_router` + integración con jw-core parsers existentes.
7. `LLMExtractor` con FakeGenerationProvider tests + cache content_hash.
8. `Compiler` orchestrator + dry-run + snapshot pre-compile.
9. `query/router` Karpathy-first → graph → vector fallback.
10. `lint` con F39 NLI mock; detecta contradictions/orphans/stale.
11. CLI `jw brain {init, compile, query, lint, snapshot, rollback, status, migrate}`.
12. MCP tools `second_brain_*`.
13. `BrainDomain` Protocol + F41 plugin SDK integration + builtin TJ + fixture financial plugin.
14. Multi-tenant: `--brain` flag + `JW_BRAIN_HOME` env + `~/.jw-brain/registry.toml`.
15. `CLAUDE.md` template + auto-gen por dominio activo.
16. Documentación: `docs/guias/second-brain.md` + `docs/plugin-sdk/brain-domains.md` + actualizar ROADMAP/VISION_AUDIT.

Cada paso con PR + tests + sin regresiones en los ~2030 tests existentes.

## Auto-revisión del spec

Verifico contra las 5 decisiones del usuario:

- ✅ **Dual backend (DuckDB + Neo4j)**: GraphBackend Protocol con contract tests parametrizados; export/import vía Parquet.
- ✅ **Wiki sobre Obsidian (F20 extension)**: ObsidianWikiWriter reusa write-safe contract + `.obsidian/` marker check + namespace exclusivo `Second-Brain/`.
- ✅ **LLM-driven compiler**: GenerationProvider (F38), default Ollama local, cache content_hash, dry-run obligatorio, snapshot pre-compile, temperature=0.
- ✅ **F49 después de F41**: BrainDomain como nuevo entry-point group F41; TJ es plugin builtin, finance es plugin fixture, cualquier dominio es plugin externo.
- ✅ **Scope abierto día 1**: parser_router por mime-type + F41 parser plugins; raw/inbox acepta cualquier formato detectable.

Adicionales de robustez incluidos (vs. propuesta inicial):

- Cache por content_hash (de F45)
- Snapshot/rollback automáticos
- Dry-run mode obligatorio
- Confidence score per edge
- Run_id propagado
- Schema-on-read estricto
- Conflict resolution explícita
- Audit forensics LLM
- Multi-tenant / multi-brain
- `human_edited` flag para edits del usuario
- `sync_obsidian` como 5ta operación core
- `migrate` entre backends
- Streaming compile para archivos grandes
- Telemetría drift (F9)
- Multi-language wiki pages (es/en/pt)

`★ Insight ─────────────────────────────────────`
Fase 49 es la primera fase del proyecto cuya arquitectura **no depende del dominio TJ**. Es deliberado: el spec invierte la jerarquía. Hasta F48, "jw-agent-toolkit" era un toolkit para TJ. Desde F49, "jw-agent-toolkit" es un runtime de second-brains con TJ como **implementación de referencia**. Esta inversión es la que permite que tu app financiera (y cualquier dominio futuro: legal, médico, scientific lit) reuse 100% del runtime. La regla de no-LLM en path crítico del toolkit se preserva: el LLM solo vive en el compiler, que es opt-in y cacheado. El resto del toolkit sigue siendo procedural y determinista.
`─────────────────────────────────────────────────`
