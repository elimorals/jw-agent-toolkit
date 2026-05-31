# Plan maestro Fases 39-48 — Confianza en runtime + comunidad + frontera JS

> **Fecha**: 2026-05-31
> **Estado**: Índice de planificación. Cada fase tiene su propio spec hijo.
> **Owner**: Elias
> **Documentos hijos**: `2026-05-31-fase-39-*.md` … `2026-05-31-fase-48-*.md`
> **Predecesores**: Fases 0-38 (1984 tests verdes en CI), live-smoke diario, eval doctrinal (87% L1).

## Contexto

Las Fases 33-38 cerraron el techo técnico del **núcleo de recuperación + síntesis multimodal + generación**. Lo que sigue ataca tres frentes ortogonales que aparecen como límites del proyecto en su estado actual:

1. **Confianza en runtime** (Fases 39-40): hoy "citas siempre verificables" es un principio cultural y un set de tests offline. La pieza que falta es **verificación semántica en vivo** (NLI/entailment) sobre cada output de agente, con **trazabilidad de provenance** del passage exacto que sustentó la afirmación.

2. **Comunidad y descubribilidad** (Fases 41-44): el proyecto es "lo de Elias". Para que sea "lo de la comunidad" necesita **Plugin SDK** (extension points sin forkear el monorepo), **scaffolding** (`create-jw-agent` + cookbook), **tracing local de agentes** (debuggability) y **LLM-as-judge** para que las contribuciones a `jw-finetune` se filtren antes de entrenar.

3. **Frontera técnica + nuevas superficies** (Fases 45-48): **chunking semántico** que sube todas las métricas RAG, **versification canónica** para apologética avanzada (nicho), **port TS de jw-core mínimo** para abrir la puerta móvil/web (Capacitor/Expo), y **extensión de navegador** que encuentra a la gente donde ya lee (wol.jw.org).

Esta serie convierte el toolkit de "librería técnica completa" en "**plataforma adoptable por terceros con garantías de fidelidad en vivo**".

## Principios duros que TODAS las fases respetan

Heredados y no negociables:

1. **Sin LLM en el camino crítico** del toolkit (los providers son opt-in cuando son LLM-backed).
2. **Citas verificables siempre** — toda salida de agente lleva URL canónica de wol.jw.org.
3. **Local-first** — providers locales son default cuando hay hardware; APIs son opt-in.
4. **No red en tests** — cada provider real ship un fake/stub hermano determinista.
5. **Multilenguaje desde día 1** — en/es/pt mínimo.
6. **No sustituir consejería de ancianos** — los agentes orientan, no aconsejan.
7. **Triple-target provider abstraction** — APIs default + GPU NVIDIA opt-in + MLX/Apple Silicon opt-in con auto-detección.
8. **Política #6 (jw-gen)** sigue vigente para Fases 39-48: nada de las nuevas fases genera contenido nuevo distribuíble.

## Tabla maestra de fases

| Fase | Slug | Propuesta original | Tier | Tamaño | Bloqueantes |
|---|---|---|---|---|---|
| **39** | `nli-runtime` | #3 NLI entailment | T1 confianza | L ~3-4 sem | — |
| **40** | `content-provenance` | #4 Provenance | T1 confianza | S ~1 sem | Fase 39 (Finding metadata channel) |
| **41** | `plugin-sdk` | #9 Plugin SDK | T2 comunidad | L ~3-4 sem | — |
| **42** | `scaffolding` | #10 create-jw-agent + cookbook | T2 comunidad | M ~1-2 sem | Fase 41 |
| **43** | `agent-tracing` | #8 Tracing local | T2 comunidad | M ~1-2 sem | — |
| **44** | `synth-judge` | #7 LLM-as-judge Q&A | T2 comunidad | S ~1 sem | Fase 39 (reusa NLI) |
| **45** | `semantic-chunking` | #5 Chunking unidad de pensamiento | T3 frontera | M ~1-2 sem | — |
| **46** | `canonical-versification` | #6 Versification mapping | T3 frontera | M ~1-2 sem | — |
| **47** | `jw-core-js-minimal` | #1 Port TS mínimo | T4 superficie | XL ~6-8 sem | — |
| **48** | `wol-browser-ext` | #2 Browser extension | T4 superficie | M ~1-2 sem | — (usa REST existente; Fase 47 ideal pero no requerido) |

**Total estimado**: ~24-32 semanas secuencial; ~15-20 semanas con paralelización tier-interna.

## Diagrama de dependencias

```
                Tier 1 — Confianza en runtime (build first)
                ┌────────────────────────────────────────────┐
                │  Fase 39 (nli-runtime)                     │
                │  ↓ provee metadata channel                 │
                │  Fase 40 (content-provenance)              │
                └────────────────────────┬───────────────────┘
                                         │
                                         ▼
                Tier 2 — Comunidad (paralelizable)
                ┌────────────────────────────────────────────┐
                │  Fase 41 (plugin-sdk) ───── prerequisite ┐ │
                │  Fase 42 (scaffolding)  ◄─────────────── ┘ │
                │  Fase 43 (agent-tracing)  — independent    │
                │  Fase 44 (synth-judge)  ◄── usa Fase 39    │
                └────────────────────────┬───────────────────┘
                                         │
                                         ▼
                Tier 3 — Frontera técnica
                ┌────────────────────────────────────────────┐
                │  Fase 45 (semantic-chunking)  — independent│
                │  Fase 46 (canonical-versification) — indep │
                └────────────────────────┬───────────────────┘
                                         │
                                         ▼
                Tier 4 — Nueva superficie JS
                ┌────────────────────────────────────────────┐
                │  Fase 47 (jw-core-js-minimal)              │
                │  Fase 48 (wol-browser-ext) ◄─ usa REST API │
                └────────────────────────────────────────────┘
```

## Fase 39 — `nli-runtime`: el guardián en vivo

**Objetivo**: aplicar **entailment semántico en runtime** sobre cada output de agente. Para cada `Finding`, verificar que el `summary`/`excerpt` se desprende lógicamente del passage citado. Es la contraparte ONLINE de Fase 22 (eval doctrinal, OFFLINE).

**Cómo se distingue de lo existente**:
- **Fase 22 (eval)**: pre-merge, sobre golden cases, mide regresión.
- **Fase 35 (constrained decoding)**: bloquea sintácticamente (URL obligatoria, JSON schema).
- **Fase 9 (fact_checker)**: verifica que el claim **existe** en una publicación JW.
- **Fase 39 (NLI runtime)** ← nuevo: verifica que el claim **se desprende lógicamente** del passage exacto citado.

**Arquitectura**:
- Nuevo módulo `packages/jw-core/src/jw_core/fidelity/`:
  - `nli.py` — `NLIProvider` Protocol + `evaluate_entailment(claim: str, premise: str) -> NLIVerdict`
  - `verdicts.py` — `Literal["entails", "neutral", "contradicts"]` con score 0-1
  - `nli_providers/` — proveedores: `DeBERTaV3MNLI` (local CPU/MPS/CUDA, 440MB, Apache 2.0), `ClaudeNLI` (anthropic SDK, NLI prompt), `OpenAINLI`, `OllamaNLI` (llama3-based)
- Nuevo wrapper `jw_agents.fidelity_wrap` que envuelve cualquier agente:
  ```python
  @fidelity_wrap(min_score=0.7, on_fail="warn")
  async def apologetics(...): ...
  ```
- Cada `Finding` post-NLI gana `metadata['nli_verdict']` + `metadata['nli_score']`.

**Triple-target**: api (Claude/OpenAI) / mlx (DeBERTa via mlx-transformers) / nvidia (DeBERTa via transformers) / cpu (DeBERTa via transformers).

**Spec hijo**: `2026-05-31-fase-39-nli-runtime-design.md`

## Fase 40 — `content-provenance`: trazabilidad del passage

**Objetivo**: cada citation lleva información reproducible de **qué versión exacta del texto** se usó. Permite re-validar cuando jw.org cambia un artículo o cuando WOL publica una revisión de la NWT.

**Estado actual**: `JwpubMetadata.schema_version`/`year`/`manifest_hash` existen como **strings sueltos**. NO se propagan al AgentResult.

**Cambios**:
- Extender `Citation.metadata` con campos obligatorios:
  - `published_date: str (ISO 8601)` — cuándo se publicó el artículo
  - `accessed_at: str (ISO 8601)` — cuándo lo descargamos
  - `content_hash: str` — sha256 del texto exacto usado
  - `revision: str | None` — identificador opcional para revisiones (ej. "rev. 2023")
- Nuevo `provenance_check(citation) -> bool` que re-fetcha la URL y compara `content_hash`.
- Integración con telemetría drift (Fase 9): si content_hash difiere, se loguea automáticamente.

**Combinación con Fase 39**: cuando una citation falla `provenance_check`, automáticamente re-corre NLI sobre el nuevo texto y notifica si el verdict cambió.

**Esfuerzo**: pequeño porque el channel `Citation.metadata` ya existe; es propagación + validación.

**Spec hijo**: `2026-05-31-fase-40-content-provenance-design.md`

## Fase 41 — `plugin-sdk`: extension points sin forkear

**Objetivo**: terceros pueden publicar paquetes Python en PyPI que extienden el toolkit sin tocar el monorepo. La pieza más alta de palanca para que el proyecto sea "lo de la comunidad".

**Patrón técnico**: Python entry points (PEP 621):

```toml
# myproject/pyproject.toml
[project.entry-points."jw_agent_toolkit.agents"]
my_agent = "my_pkg:my_agent_callable"

[project.entry-points."jw_agent_toolkit.parsers"]
my_parser = "my_pkg.parsers:parse_my_format"
```

**5 tipos de plugin** (5 entry-point groups):
1. `jw_agent_toolkit.agents` — agentes (signature: `async (**kwargs) -> AgentResult`)
2. `jw_agent_toolkit.parsers` — parsers de nuevos formatos (signature: `(bytes) -> ParsedDocument`)
3. `jw_agent_toolkit.embedders` — embedders custom (extends `jw_rag.embed.Embedder`)
4. `jw_agent_toolkit.vlm_providers` — VLMs custom (extends `jw_core.vision.vlm.VLMProvider`)
5. `jw_agent_toolkit.gen_providers` — generative providers (extends `jw_gen.providers.GenerationProvider`)

**Nuevo módulo** `packages/jw-core/src/jw_core/plugins/`:
- `registry.py` — descubre plugins via `importlib.metadata.entry_points`
- `contracts.py` — define los 5 Protocols con docstrings explícitos de la API
- `verify.py` — `verify_plugin(name)` que valida shape, dependencies, signature compatibility
- `errors.py` — `PluginError`, `PluginConflictError`, `PluginVersionMismatch`

**MCP/CLI surfaces actualizados**: `default_agent_registry` ahora incluye plugins descubiertos.

**Tests**: paquete fake en `packages/jw-core/tests/fixtures/plugin_sample/` que se "instala" durante el test y verifica discoverability.

**Spec hijo**: `2026-05-31-fase-41-plugin-sdk-design.md`

## Fase 42 — `scaffolding`: create-jw-agent + cookbook

**Objetivo**: bajar la curva de "primer agente custom" a 10 minutos.

**Componentes**:
1. **CLI generator** `create-jw-agent`:
   ```bash
   npx create-jw-agent my-translation-agent --type=agent --lang=es
   # genera: pyproject.toml (con entry point F41), src/, tests/, README, Makefile
   ```
   Implementado en Python via `cookiecutter` o template propio + Typer.
2. **Cookbook** `docs/cookbook/`:
   - 12-15 recipes copy-pasteable (Markdown con código testeable):
     - "Resolve a Bible reference in 4 lines"
     - "Search topic index and synthesize prose with Claude"
     - "Build a Telegram bot over the MCP"
     - "Fine-tune Llama 3 on your JWPUB library"
     - "Add a parser for a new publication format"
     - "Wrap a custom embedder behind the Embedder Protocol"
     - "Add NLI to your existing agent"
     - "Publish your agent to PyPI"
     - + 4 más
3. **Quickstart deeplinkable**: `https://jw-agent-toolkit.vercel.app/cookbook/{recipe-slug}` con Pagefind indexado.

**Spec hijo**: `2026-05-31-fase-42-scaffolding-design.md`

## Fase 43 — `agent-tracing`: debuggability

**Objetivo**: cada agente puede emitir un trace JSON con qué findings consideró, cuáles descartó, por qué, con qué rank. Distinto de Fase 22 (mide outputs) — esto explica el **proceso**.

**Implementación**:
- `jw_agents.tracing.AgentTracer` context manager
- `~/.jw-agent-toolkit/traces/{agent}-{run_id}.json` (JSON Lines)
- CLI: `jw apologetics --question "..." --trace /tmp/trace.json`
- MCP: tool returns trace under `metadata['trace_id']`
- Web UI eventual sobre los JSON (no en esta fase — solo schema + writer)

**Schema del trace**:
```json
{
  "trace_id": "uuid",
  "agent": "apologetics",
  "input": {...},
  "started_at": "...",
  "duration_ms": 1234,
  "steps": [
    {"name": "topic_index_lookup", "duration_ms": 142,
     "input": "Trinity", "hits": 12, "kept": 3, "dropped_reasons": {...}}
  ],
  "findings_in": 25,
  "findings_out": 10,
  "discarded": [...]
}
```

**Combinación con Fase 39**: si NLI rechaza un finding, el trace registra la razón.

**Spec hijo**: `2026-05-31-fase-43-agent-tracing-design.md`

## Fase 44 — `synth-judge`: filtro de calidad para Q&A sintético

**Objetivo**: filtrar pares Q&A sintéticos antes de fine-tuning. Reusa Fase 39 (NLI).

**Estado actual**: `jw_finetune.synth.validators` tiene validators heurísticos (longitud, no-empty, etc.). **Falta**: scoring de calidad doctrinal.

**Nuevo módulo** `packages/jw-finetune/src/jw_finetune/synth/judge.py`:
- `score_qa_pair(q: str, a: str) -> QAScore` con campos:
  - `cites_jw_publication: bool` (heurística URL + content check)
  - `nli_score: float` (Fase 39 sobre claim ↔ premise)
  - `pedagogical_quality: 0-3` (LLM judge: ¿es enseñanza útil?)
  - `overall: 0-10`
- Pipeline default: descarta `overall < 6`.
- Threshold configurable por receta.

**Spec hijo**: `2026-05-31-fase-44-synth-judge-design.md`

## Fase 45 — `semantic-chunking`: chunking por unidad de pensamiento

**Objetivo**: el chunker actual ya es paragraph-based, pero algunos párrafos largos cortan argumentos doctrinales. Mejora chunking con análisis estructural.

**Estrategia**:
- Heurística primero: detectar "este párrafo continúa el argumento del anterior" via marcadores (`Sin embargo`, `Por otro lado`, `Además`).
- LLM opt-in (build-time, no runtime): `LLMChunker` que segmenta por unidad argumentativa cuando el heuristic falla.
- Métrica de éxito: NDCG@10 mejora ≥10% en queries doctrinales.

**Spec hijo**: `2026-05-31-fase-45-semantic-chunking-design.md`

## Fase 46 — `canonical-versification`: mapping de tradiciones

**Objetivo**: mapeo entre numeraciones de versículos (cristiana vs hebrea masorética; Salmos con/sin superscripción).

**Catálogo**: ~150 discrepancias documentadas en `packages/jw-core/src/jw_core/data/versification_map.json`.

**API**: `to_canonical(ref: BibleRef, tradition: Literal["nwt", "masoretic", "lxx"]) -> BibleRef`.

**Justificación de incluirla a pesar de ROI medio-bajo**: el plan completo es las 10 propuestas. La fase queda documentada y la pospone se hace en el ROADMAP, no como omisión.

**Spec hijo**: `2026-05-31-fase-46-canonical-versification-design.md`

## Fase 47 — `jw-core-js-minimal`: port TS de los 3 módulos críticos

**Objetivo**: port TypeScript de los 3 módulos que el 80% de casos JS necesita:
1. `parse_reference` — el corazón. Resuelve "Juan 3:16" → BibleRef.
2. `WOLClient.get_bible_chapter` — fetcher de la NWT.
3. `parsers.article` — HTML → Article structured.

**Estructura**:
- Nuevo paquete `packages/jw-core-js/` (workspace member npm, no Python).
- Pruebas cross-language: un golden JSON fixture en `packages/jw-core/tests/fixtures/cross_lang/` que ambos TS y Python deben producir idénticamente. CI corre comparator.
- Distribución: publicar a npm como `@jw-agent-toolkit/core`.

**Tamaño realista**: 6-8 semanas. Es el spec más grande de Fases 39-48.

**Por qué NO portar todo jw-core**: los otros 30k LOC (cache, throttle, telemetry, JWPUB decrypt, EPUB parser, etc.) **no** los necesita el 80% de casos JS. Quedan Python-only o se portan en una fase futura cuando haya métricas reales de uso.

**Spec hijo**: `2026-05-31-fase-47-jw-core-js-minimal-design.md`

## Fase 48 — `wol-browser-ext`: extensión para Chrome/Firefox

**Objetivo**: extensión que inyecta UI inline en wol.jw.org. Cada versículo gana botones contextuales:
- 📖 "Explicar" → llama a `verse_explainer` via REST API
- 🔗 "Ver cross-refs" → llama a `get_cross_references`
- 📝 "Guardar a Obsidian" → push al vault local del usuario

**Manifest v3** (Chrome/Edge/Firefox unificado).

**Backend**: ataca `localhost:8765/api/v1/*` (REST API existente de Fase 20). Si el usuario no tiene el toolkit corriendo local, fallback a botones disabled con tooltip "Inicia el toolkit local: `jw mcp serve`".

**Opt-in**: la extensión NUNCA envía datos a un servidor remoto. Todo es local-only.

**No depende de Fase 47** (puede atacar REST Python). PERO si Fase 47 ya está, el manifest opt-in puede usar el TS port para validar la URL del versículo **client-side** sin red — UX más rápida.

**Spec hijo**: `2026-05-31-fase-48-wol-browser-ext-design.md`

## Política de ramificación

Cada Fase X tiene:
- Spec en `docs/superpowers/specs/2026-05-31-fase-X-<slug>-design.md`
- Plan en `docs/superpowers/plans/2026-05-31-fase-X-<slug>-plan.md`
- Branch `feature/fase-X-<slug>`
- PR independiente con audit 1:1 + nuevos golden cases en `jw-eval/fixtures/` cuando aplique

## Métricas de éxito por fase

| Fase | Métrica medible |
|---|---|
| 39 | 95%+ de Findings de los 12 agentes pasan NLI con score ≥0.7 sobre golden set |
| 40 | 100% de Citations llevan `content_hash` + `accessed_at`; `provenance_check` detecta cambios reales en jw.org |
| 41 | Test fixture instala un plugin externo y se descubre vía entry_points; conflict detection funciona |
| 42 | `create-jw-agent` genera proyecto que pasa CI en su primer commit; cookbook tiene 12 recipes ejecutables |
| 43 | `jw apologetics --trace` produce JSON parseable con todos los steps + reasons; schema documentado |
| 44 | Filtro descarta ≥30% de Q&A sintético "ruidoso" del baseline jw-finetune; el modelo entrenado mejora en eval |
| 45 | NDCG@10 sobre 10 queries doctrinales mejora ≥10% vs paragraph-only chunker |
| 46 | `to_canonical` produce mapeo correcto para los ~150 casos documentados |
| 47 | `parse_reference("Juan 3:16")` en TS y Python producen idéntico JSON sobre 500 fixtures |
| 48 | Extension carga sobre wol.jw.org, los 3 botones funcionan, sin enviar datos a 3rd parties |

## Lo que NO está en este plan (deliberado)

- **Port completo de jw-core a TS**: solo 3 módulos mínimos en Fase 47. El resto queda Python-only por ahora.
- **Web UI del tracing**: Fase 43 solo escribe JSON; el dashboard web es fase futura.
- **Federación de instalaciones**: no pretendemos hacer sync multi-dispositivo aquí (eso es Fase 11/M11 ya entregado).
- **Modelos custom entrenados por nosotros**: jw-finetune se queda como plataforma; no distribuimos pesos.

## Estado actual del repo (verificado 2026-05-31)

- **CI verde después del fix de lint + audio tests** (último push `3a25772`)
- **1984 tests pasando** offline + 45 skipped (extras opcionales)
- **0 violaciones de ruff lint + 0 de format** (562 archivos)
- **8 paquetes Python** workspace (jw-core, jw-cli, jw-mcp, jw-rag, jw-agents, jw-finetune, jw-eval, jw-gen)
- **Branch `main` ahead 0** (todo pusheado)

## Siguiente paso inmediato

Dispatch 10 sub-agentes paralelos para escribir los specs hijos. Mismo flujo que validó las Fases 22-32 y 33-38. Después implementación tier-por-tier con paralelización interna.
