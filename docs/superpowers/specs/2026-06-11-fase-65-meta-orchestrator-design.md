# Fase 65 — `meta-orchestrator`: orquestador agéntico sobre agentes existentes

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (kernel agéntico)
> **Capa**: A — Agéntica
> **Depende de**: todos los agentes F11-F64 (especialmente F11 workbook, F11 public_talk_outline, F7 multimodalidad slides, F3 TTS), F35 (constrained), F39 (NLI), F43 (tracing), F57.16 (multi-congregación), F61 (memoria)
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: ningún agente actual orquesta a otros

## Motivación

El toolkit tiene 12 agentes procedurales (`verse_explainer`,
`research_topic`, `meeting_helper`, `apologetics`, `workbook_helper`,
`public_talk_outline`, `conversation_assistant`, `presentation_builder`,
`revisit_tracker`, `reverse_citation_lookup`, `fact_checker`,
`apocrypha_detector`, `life_topics`, `study_conductor`,
`student_part_helper`). Cada uno hace una cosa bien.

Pero el caso de uso real "**prepara mi domingo**" requiere una secuencia
multi-paso: descubre el programa del Workbook semanal → arma outline
del discurso público asignado → genera slides → produce audio TTS de
los puntos clave → exporta hoja de estudio PDF. Hoy el publicador
ejecuta 4-6 comandos CLI/MCP separados y compone los outputs
mentalmente.

Esa fricción rompe el loop de uso. Un orquestador meta colapsa el
flujo a un solo comando con plan auditable.

## Objetivos

1. Un único punto de entrada (`jw plan-sunday`, MCP `meta_run_plan`)
   que dado un objetivo de alto nivel produce un `OrchestrationResult`
   con todas las salidas de los sub-agentes encadenadas.
2. **Plan/replan/critique** explícitos. Antes de ejecutar, el
   orquestador imprime el plan (lista de sub-tools con sus args).
   Tras ejecutar, evalúa el resultado con NLI F39 y puede re-planear.
3. **Pluggable**. Terceros añaden nuevos sub-agentes via Plugin SDK
   F41 sin modificar el orquestador.
4. **Determinista bajo `JW_META_LLM=fake`** para testing offline.
5. **Tracing F43 obligatorio**: cada step emite evento JSONL con
   inputs, outputs, tokens.

## No-objetivos (boundaries vinculantes)

- **No** reemplaza los 12 agentes existentes. Es una capa sobre ellos.
- **No** introduce un framework externo (no LangGraph, no CrewAI, no
  AutoGen). Se construye con stdlib + Pydantic + el patrón ya usado
  por `apologetics` (chains procedurales).
- **No** llama LLMs en producción de los sub-agentes (los sub-agentes
  siguen siendo procedurales). El LLM solo aparece en el meta-paso
  de planning, critique y replanning.
- **No** persiste el plan en disco salvo opt-in (`--save-plan path/`).
  La memoria F61 se usa para continuidad de sesión, no para snapshot.

## Decisión clave: ¿stateful framework vs in-house state machine?

### Opción A — LangGraph / CrewAI / AutoGen

**Pros**:
- API conocida.
- Visualización de grafo gratis.

**Contras**:
- Cada framework trae 50+ MB de dependencias transitorias.
- Acopla el ciclo de release del toolkit al del framework.
- El patrón procedural del toolkit (agentes async puros + `AgentResult`)
  ya tiene la mitad de lo que LangGraph ofrece.
- Ninguno respeta el patrón de "local-first + sin telemetría" que
  define el toolkit.

### Opción B — In-house FSM sobre Pydantic + stdlib

Construir `OrchestrationPlan` (Pydantic), `Step` (Pydantic), `Executor`
(async loop con tool dispatch via dict de callables), `Critique`
(NLI F39 over the final `OrchestrationResult`).

**Pros**:
- Cero dependencias nuevas.
- Reusa `AgentResult`, `Finding`, `Citation` ya existentes.
- Integra trivialmente con F43 tracing y F35 constrained decoding.
- El "grafo" se imprime como JSON/Markdown — visualización suficiente.

**Contras**:
- Hay que escribir el dispatcher de tools. ~150 LOC.

### Decisión: **Opción B** (FSM in-house)

Justificación:
1. El proyecto rechazó frameworks LLM externos desde Fase 1 (ver
   [`decisiones-de-diseno.md#2`](../../conceptos/decisiones-de-diseno.md)).
2. Los 12 agentes existentes ya son async callables que devuelven
   `AgentResult`. Son tools nativos del meta-orchestrator sin adapter.
3. F35 constrained decoding garantiza JSON estricto para el plan
   producido por el LLM planner.
4. Si en el futuro emerge necesidad de visualización gráfica, se
   exporta el plan a Mermaid (1 función).

## Arquitectura

```
                  ┌───────────────────────────────────┐
                  │   CLI:  jw plan-sunday            │
                  │   MCP:  meta_run_plan             │
                  └──────────────┬────────────────────┘
                                 │ goal + context + langua
                                 ▼
                  ┌───────────────────────────────────┐
                  │   1. Planner                      │
                  │      LLM (constrained F35)        │
                  │      → OrchestrationPlan          │
                  │        (lista de Steps + deps)    │
                  └──────────────┬────────────────────┘
                                 │ plan
                                 ▼
                  ┌───────────────────────────────────┐
                  │   2. Executor                     │
                  │      topological sort de Steps    │
                  │      dispatch a tools registradas │
                  │      cada step emite trace F43    │
                  └──────────────┬────────────────────┘
                                 │ raw results
                                 ▼
                  ┌───────────────────────────────────┐
                  │   3. Critique                     │
                  │      NLI F39 sobre cada output    │
                  │      detecta findings vacíos      │
                  │      decide replan vs commit      │
                  └──────────────┬────────────────────┘
                                 │
                  ┌──────────────┴──────────┐
                  │ replan?                 │ commit
                  ▼                         ▼
        loop con step extra        OrchestrationResult
        (max 3 iteraciones)        consolidado
```

## Contratos de tipos

```python
# packages/jw-agents/src/jw_agents/meta/models.py

from pydantic import BaseModel, Field
from typing import Literal, Any

StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]

class Step(BaseModel):
    id: str                       # "step-1", "step-2"
    tool: str                     # nombre de agente registrado
    args: dict[str, Any]          # kwargs para el agente
    depends_on: list[str] = []    # ids de pasos previos
    status: StepStatus = "pending"
    rationale: str = ""           # por qué el planner eligió este step

class OrchestrationPlan(BaseModel):
    goal: str
    language: Literal["en", "es", "pt"] = "es"
    steps: list[Step]
    congregation: str | None = None
    plan_revision: int = 0        # incrementa con cada replan

class StepResult(BaseModel):
    step_id: str
    agent_result: dict[str, Any]  # AgentResult.model_dump()
    error: str | None = None
    elapsed_ms: int
    tokens_used: int = 0

class CritiqueVerdict(BaseModel):
    overall_ok: bool
    findings_per_step: dict[str, int]   # step_id -> count
    nli_warnings: list[str]
    suggested_replan: Step | None = None
    reason: str = ""

class OrchestrationResult(BaseModel):
    plan: OrchestrationPlan
    step_results: list[StepResult]
    critique: CritiqueVerdict
    consolidated_findings: list[dict[str, Any]]   # AgentResult-like
    total_elapsed_ms: int
    total_tokens: int
    trace_path: str | None = None
```

## API pública

```python
# packages/jw-agents/src/jw_agents/meta/__init__.py

from jw_agents.meta.orchestrator import MetaOrchestrator
from jw_agents.meta.models import (
    OrchestrationPlan,
    OrchestrationResult,
    Step,
    StepResult,
    CritiqueVerdict,
)
from jw_agents.meta.registry import (
    register_tool,
    list_tools,
    get_tool,
    ToolNotFound,
)

__all__ = [
    "MetaOrchestrator",
    "OrchestrationPlan",
    "OrchestrationResult",
    "Step",
    "StepResult",
    "CritiqueVerdict",
    "register_tool",
    "list_tools",
    "get_tool",
    "ToolNotFound",
]
```

## CLI

```bash
# Caso de uso primario
jw plan-sunday --congregation norte --language es

# Goal arbitrario
jw meta run "Prepara apologética para Trinity con slides"

# Inspeccionar plan sin ejecutar
jw meta run "..." --dry-run

# Limitar replanes
jw meta run "..." --max-replans 0

# Trace explícito
jw meta run "..." --trace ~/.jw-traces/sunday.jsonl

# Listar tools disponibles (12 + plugins F41)
jw meta tools
```

## MCP tools

- `meta_plan_goal(goal: str, language="es", congregation=None) → OrchestrationPlan`
- `meta_run_plan(plan_or_goal, **kwargs) → OrchestrationResult`
- `meta_list_tools() → list[str]`

## Provider abstraction (planner LLM)

Reusa `jw_finetune.synth.provider.LLMProvider` (mismo abstraction que
F44 synth-judge). Factories env-driven:

| Env                  | Default | Efecto                                       |
|----------------------|---------|----------------------------------------------|
| `JW_META_LLM`        | `fake`  | `claude`/`openai`/`ollama`/`fake`            |
| `JW_META_MODEL`      | —       | Override model id per provider               |
| `JW_META_MAX_STEPS`  | `8`     | Cap de steps por plan                        |
| `JW_META_MAX_REPLANS`| `2`     | Cap de iteraciones de critique → replan      |
| `JW_META_TIMEOUT_S`  | `120`   | Wall-clock cap                               |

`FakeLLMProvider` devuelve un plan determinista (hardcoded patterns
por goal) — suficiente para tests offline.

## Tools registradas por defecto

| Tool name                      | Wraps agente                       |
|--------------------------------|------------------------------------|
| `verse.explain`                | `verse_explainer`                  |
| `verse.cross_refs`             | `verse_explainer` con flag         |
| `research.topic`               | `research_topic`                   |
| `meeting.workbook`             | `workbook_helper`                  |
| `meeting.public_talk_outline`  | `public_talk_outline`              |
| `meeting.student_part`         | `student_part_helper`              |
| `apologetics.research`         | `apologetics`                      |
| `apologetics.fact_check`       | `fact_checker`                     |
| `apologetics.apocrypha`        | `apocrypha_detector`               |
| `ministry.conversation`        | `conversation_assistant`           |
| `ministry.presentation`        | `presentation_builder`             |
| `ministry.revisit`             | `revisit_tracker`                  |
| `study.conductor`              | `study_conductor`                  |
| `study.life_topics`            | `life_topics`                      |
| `media.discover_week`          | `meeting_media.discover`           |
| `media.download_week`          | `meeting_media.download`           |
| `export.study_sheet`           | `exporters.study_sheet`            |
| `audio.say`                    | `audio.tts.synthesize`             |
| `slides.generate`              | `vision.slides`                    |

Plugins F41 con entry-point `jw_agent_toolkit.agents` se descubren al
startup y aparecen en `meta_list_tools()`.

## Prompt del planner (es/en/pt)

Template Jinja2 minimalista:

```jinja
{# packages/jw-agents/src/jw_agents/meta/prompts/planner_es.j2 #}
Eres un planificador de tareas para Testigos de Jehová. Recibes un
objetivo y eliges entre las siguientes herramientas (tools) en cuál
orden ejecutarlas para satisfacer el objetivo con citas verificables
de wol.jw.org.

Objetivo: {{ goal }}
Idioma: {{ language }}
{% if congregation %}Congregación: {{ congregation }}{% endif %}

Herramientas disponibles:
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
  Args: {{ tool.args_schema }}
{% endfor %}

Devuelve un JSON con esta forma exacta:
{
  "goal": "...",
  "language": "{{ language }}",
  "steps": [
    {"id": "step-1", "tool": "...", "args": {...}, "depends_on": [], "rationale": "..."},
    ...
  ]
}

Máximo {{ max_steps }} steps. NO inventes herramientas. Si el objetivo
no se cubre, devuelve {"goal":"...","steps":[]} con rationale en lugar
de inventar.
```

Constrained con gramática GBNF F35 para garantizar JSON parseable.

## Critique stage (NLI F39)

Tras ejecutar todos los steps:

1. Recolecta `consolidated_findings = [f for s in step_results for f in s.agent_result.findings]`.
2. Por cada finding con `kind in ("verse", "study_note", "topic_subject", "cdn_search")`,
   ejecuta `evaluate_entailment(claim=finding.excerpt, premise=finding.citation.url)`.
3. Cuenta `nli_warnings = [w for verdict in ... if verdict.verdict != "entails"]`.
4. Si `len(consolidated_findings) == 0` o `len(nli_warnings) > 0.5 * len(consolidated_findings)`,
   propone `suggested_replan = Step(tool="research.topic", args={"query": goal})` como
   step extra.

Replan máximo 2 veces (env `JW_META_MAX_REPLANS`).

## Plan de pruebas

| Caso                                                       | Tipo        | Provider |
|------------------------------------------------------------|-------------|----------|
| `Step` Pydantic acepta args dict arbitrario                | Unit        | —        |
| `OrchestrationPlan` rechaza step con `depends_on` ciclo    | Unit        | —        |
| Topological sort produce orden correcto                    | Unit        | —        |
| Tool registry lookup falla con `ToolNotFound`              | Unit        | —        |
| Plugin SDK F41 entry-points son descubiertos               | Integration | fake     |
| FakeLLMProvider devuelve plan para "prepara domingo"       | Unit        | fake     |
| Plan vacío → `OrchestrationResult` con `overall_ok=False`  | Unit        | fake     |
| Execute con step que falla propaga `error` no crashea      | Unit        | fake     |
| Critique con 0 findings sugiere replan                     | Unit        | fake     |
| Critique con NLI=entails 100% → `overall_ok=True`          | Unit        | fake NLI |
| Max-replans=0 nunca replanea                               | Unit        | fake     |
| CLI `jw plan-sunday` produce exit code 0 con golden goal   | E2E         | fake     |
| MCP `meta_run_plan` devuelve dict serializable             | Integration | fake     |
| Trace F43 contiene un evento por step                      | Integration | fake     |
| Multi-congregación: pasa `congregation` a sub-tools        | Integration | fake     |

**Golden goals** para tests E2E:

1. "Prepara mi reunión del domingo" (es) → workbook + outline + slides.
2. "Research Trinity for apologetics" (en) → research + apologetics + export.
3. "Prepara para revisitar a Juan" (es) → revisit + presentation + tts.

## Riesgos / mitigaciones

| Riesgo                                                | Mitigación                                       |
|-------------------------------------------------------|--------------------------------------------------|
| LLM planner alucina tool name inexistente             | Validación contra registry; replan con error msg |
| Plan con ciclo en `depends_on`                        | Pydantic validator + topological sort failure    |
| Tool individual cuelga / tarda mucho                  | `JW_META_TIMEOUT_S` wall-clock + cancellation    |
| Costo LLM se dispara con replans                      | Cap `JW_META_MAX_REPLANS=2` + report tokens      |
| Plan genera 50 findings ruido                         | Critique consolida + dedup por `citation.url`    |
| Multi-congregación: programa de otra fecha            | Pasar `current_date` siempre desde caller        |

## Métricas de éxito

- **Adopción**: uso de `jw plan-sunday` ≥ semanal en >50% sábados de
  usuarios activos (tracking opt-in con `JW_META_USAGE=1`).
- **Calidad**: critique reporta `overall_ok=True` en >80% de runs
  sobre golden goals.
- **Costo**: <500 input tokens + <500 output tokens promedio por
  plan con Claude/OpenAI; <2s con Ollama local.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/meta.py` — `jw meta {plan,run,tools}` + alias `jw plan-sunday`.
- MCP: `packages/jw-mcp/src/jw_mcp/server.py` — 3 tools nuevas.
- Plugin SDK F41: registry descubre `jw_agent_toolkit.agents` entry-points en `MetaOrchestrator.__init__`.
- Tracing F43: cada `executor.run_step()` emite `Event(kind="meta_step", step_id=..., elapsed_ms=...)`.

## Guía resultante

`docs/guias/meta-orchestrator.md` — quick start, CLI flags, MCP tools,
ejemplos de extensión via plugin.
