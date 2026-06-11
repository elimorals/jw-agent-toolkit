---
title: "Meta-orquestador (Fase 65)"
description: "Planner LLM + executor topológico + crítica NLI sobre los 12 agentes existentes con replan opt-in, plan/replay determinista y export Mermaid del DAG."
date: "2026-06-11"
---

# Meta-orquestador (Fase 65)

> Orquesta los 12 agentes existentes en un solo comando con plan auditable,
> critique con NLI F39 y replan opt-in. Sin nuevos modelos LLM en el camino
> crítico de los sub-agentes — solo el meta paso usa LLM para planificar,
> criticar y re-planificar.

## Quick start

```bash
# Lista tools disponibles (12 builtin + plugins F41)
jw meta tools

# Inspecciona el plan sin ejecutar
jw meta plan "Prepara mi domingo" --language es

# Ejecuta plan + critique + replan
jw meta run "Prepara apologética sobre la Trinidad" --language es --max-replans 2

# Alias preconfigurado para reunión del domingo
jw plan-sunday --language es
jw plan-sunday --congregation norte
```

## CLI

| Comando            | Descripción                          |
|--------------------|--------------------------------------|
| `jw meta tools`    | Lista tools registradas              |
| `jw meta plan`     | Solo plan, sin ejecutar              |
| `jw meta run`      | Plan + execute + critique            |
| `jw plan-sunday`   | Alias preconfigurado para reunión    |

### Flags principales de `jw meta run`

| Flag                      | Default | Efecto                                         |
|---------------------------|---------|------------------------------------------------|
| `--language` / `-l`       | `es`    | Idioma de salida (`es` / `en` / `pt`)          |
| `--congregation` / `-c`   | —       | Resuelve contra `congregations.toml` F57.16    |
| `--max-steps`             | `8`     | Cap de pasos por plan                          |
| `--max-replans`           | `2`     | Cap de iteraciones critique → replan           |
| `--timeout-s`             | `120`   | Wall-clock cap                                 |
| `--dry-run`               | `False` | Imprime el plan sin ejecutarlo                 |

## MCP

| Tool              | Descripción                          |
|-------------------|--------------------------------------|
| `meta_list_tools` | Tools disponibles                    |
| `meta_plan_goal`  | Devuelve `OrchestrationPlan`         |
| `meta_run_plan`   | Devuelve `OrchestrationResult`       |

## Variables de entorno

| Env                    | Default                  | Efecto                                |
|------------------------|--------------------------|---------------------------------------|
| `JW_META_LLM`          | `fake`                   | `anthropic`/`claude` · `ollama` · `fake` |
| `JW_META_MODEL`        | per-backend default      | Override model id                     |
| `JW_META_OLLAMA_HOST`  | `http://localhost:11434` | Endpoint Ollama                       |
| `JW_META_NLI`          | `off`                    | `auto` activa F39 (`get_default_nli_provider`) |
| `JW_META_MAX_STEPS`    | `8`                      | Cap steps por plan                    |
| `JW_META_MAX_REPLANS`  | `2`                      | Cap iteraciones critique → replan     |
| `JW_META_TIMEOUT_S`    | `120`                    | Wall-clock cap                        |

### LLM provider factory

`jw_agents.meta.llm_factory.build_llm_from_env()` resuelve el provider
desde `JW_META_LLM`:

- `fake` → `_FakeAcompletionLLM` determinista (planes vacíos, ideal tests).
- `anthropic`/`claude` → `AnthropicProvider` envuelto en
  `_SyncProviderAcompletionAdapter` (`generate` sync → `acomplete` async vía
  `asyncio.to_thread`).
- `ollama` → `OllamaProvider` con el mismo adapter; usa `JW_META_MODEL`
  (default `llama3.1:8b`) y `JW_META_OLLAMA_HOST`.

Si falla la dependencia (paquete no instalado, API key ausente), degrada a
`fake` con un warning. Nunca crashea en boot.

### NLI provider factory

`jw_agents.meta.nli_factory.build_nli_from_env(language=...)` resuelve el
NLI de Fase 39:

- `JW_META_NLI=off` (default) → `None` (critique sin NLI).
- `JW_META_NLI=auto` → `get_default_nli_provider()` envuelto en
  `_NLIAdapter` que normaliza la firma a `evaluate_entailment(claim=,
  premise=)` y forwarda `language`.

Si `is_available()` falla o el provider no se puede resolver, devuelve
`None` con un warning informativo.

## Arquitectura

```
                   Goal de alto nivel
                          │
                          ▼
        ┌───────────────────────────────────┐
        │ Planner (LLM + Jinja2 + GBNF F35) │
        └────────────────┬──────────────────┘
                         │ OrchestrationPlan
                         ▼
        ┌───────────────────────────────────┐
        │ Executor (topological sort async) │
        └────────────────┬──────────────────┘
                         │ list[StepResult]
                         ▼
        ┌───────────────────────────────────┐
        │ Critique (NLI F39 sobre findings) │
        └────────────────┬──────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼ overall_ok          ▼ replan?
        OrchestrationResult     loop con suggested_replan
                                 (max `max_replans` veces)
```

## Builtin tools registradas

12 wrappers placeholder sobre los agentes existentes. Cada uno será
sustituido por el callable real en PRs subsiguientes:

| Tool                       | Agente backing                |
|----------------------------|-------------------------------|
| `verse.explain`            | `verse_explainer`             |
| `research.topic`           | `research_topic`              |
| `apologetics.research`     | `apologetics`                 |
| `meeting.workbook`         | `workbook_helper`             |
| `meeting.public_talk_outline` | `public_talk_outline`      |
| `meeting.student_part`     | `student_part_helper`         |
| `ministry.conversation`    | `conversation_assistant`      |
| `ministry.presentation`    | `presentation_builder`        |
| `ministry.revisit`         | `revisit_tracker`             |
| `apologetics.fact_check`   | `fact_checker`                |
| `apologetics.apocrypha`    | `apocrypha_detector`          |
| `study.life_topics`        | `life_topics`                 |

## Extensión via Plugin SDK F41

Cualquier paquete con entry-point `jw_agent_toolkit.agents` se descubre al
startup y aparece en `jw meta tools` con prefijo `plugin.<name>`.

Ver [`docs/plugin-sdk/overview.md`](../plugin-sdk/overview.md).

## Tracing (planeado)

El plan original prevé emitir un evento JSONL F43 por cada step. En la
entrega MVP el hook `on_step_done` del `Executor` existe pero no se cablea
todavía; se conectará en seguimiento.

## Política de citas y replan

- Si el primer plan NO produce findings, el critique sugiere un step de
  `research.topic` automático (revisión `plan_revision += 1`).
- Si los findings que SÍ existen no pasan NLI F39 (>50% no-`entails`), el
  critique sugiere un step `apologetics.research`.
- `--max-replans 0` desactiva la iteración de replan.

## Estado actual

- Models: `Step`, `OrchestrationPlan`, `StepResult`, `CritiqueVerdict`,
  `OrchestrationResult`.
- Registry con Plugin SDK F41 discovery.
- Executor con topological sort, timeout, skip de upstream-failed steps y
  hook `on_step_done` cableado.
- Planner con Jinja2 (es/en/pt) y GBNF para constrained F35.
- Critique con NLI F39 importado vía factory.
- **12 builtin tools wireados a sus agentes reales** (adapters normalizan
  firmas: `verse_explainer(text=...)`, `workbook_helper(target_date=...)`,
  `student_part_helper(kind, topic_or_ref)`, etc.).
- **LLM provider factory** env-driven con Anthropic + Ollama + Fake +
  degradación grácil.
- **NLI provider factory** env-driven que envuelve `get_default_nli_provider()`
  de F39.
- **Tracing F43** opt-in: `--trace path/` o `--trace -` emite eventos
  `meta_plan` / `meta_step` / `meta_critique` como `CustomEvent`.
- **Persistencia opt-in**: `--save-plan` + `--save-result` escriben JSON a
  disco.
- CLI `jw meta {tools,plan,run}` + alias `jw plan-sunday`.
- MCP: 3 tools nuevas (`meta_list_tools`, `meta_plan_goal`, `meta_run_plan`).
- Suite de tests: **55 passing** (MVP 38 + post-MVP 17).

## Ejemplos de uso completos

```bash
# Plan determinista offline + persistencia
jw meta plan "Trinity" -l en --save-plan plans/trinity.json

# Run con tracing JSONL + persistencia del result
jw meta run "Prepara mi domingo" -l es \
  --trace ~/.jw-traces/ \
  --save-result results/sunday.json

# Activar NLI real (requiere F39 provider disponible)
JW_META_NLI=auto JW_META_LLM=ollama JW_META_MODEL=llama3.1:8b \
  jw meta run "Reino de Dios" -l es

# Anthropic
JW_META_LLM=anthropic JW_META_MODEL=claude-opus-4-20250805 \
  jw meta run "Trinity" -l en --max-replans 2
```

## Pendiente (futuro)

- Export Mermaid del DAG.
- Persistencia de planes versionados con índice consultable.
- Streaming progresivo del result mientras se ejecutan los steps.
