# Fase 43 — `agent-tracing`: debuggability local de agentes

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (comunidad / DX)
> **Depende de**: ninguna fase. Independiente; opcionalmente se enriquece con Fase 39 (NLI) cuando esté disponible.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

Hoy un agente procedural (`apologetics`, `research_topic`, `verse_explainer`, …) toma decisiones internas opacas: ¿qué hits del Topic Index conservó? ¿por qué descartó un finding del RAG? ¿qué peso le dio al ranking? Cuando un usuario reporta "esta respuesta omitió tal cita", la única herramienta de debugging es **leer logs sueltos o re-ejecutar mentalmente la pipeline**. Para Fases 40-44 (community + content-provenance) necesitamos **un canal estructurado que explique el proceso**.

Fase 43 introduce **trazas estructuradas por run**: cada agente emite un JSON Lines de eventos describiendo paso a paso qué consideró, qué conservó, qué descartó y por qué.

### Cómo se distingue de lo existente y vecino

| Fase | Qué mide | Cuándo |
|---|---|---|
| **22 (eval doctrinal)** | OUTPUTS: ¿la respuesta es correcta? | Pre-merge sobre golden cases |
| **39 (NLI runtime)** | OUTPUTS: ¿el claim se desprende del passage? | En vivo, post-finding |
| **9 (telemetry/logging)** | Eventos sueltos del request HTTP | Continuo, no agrupable por run |
| **43 (agent-tracing)** ← nuevo | **PROCESO**: qué decisiones internas tomó el agente y por qué | Por run, opt-in via flag |

Las trazas **no** son métricas — son un microscopio sobre la ejecución.

## Objetivos (orden de prioridad)

1. **Debuggability local**: un dev pueda re-ejecutar `jw apologetics --question "X" --trace` y leer un JSON estructurado que explique los pasos.
2. **Overhead ≤5%** cuando el tracer está activo; **0%** cuando está NO-OP (default).
3. **Schema estable y documentado** que herramientas terceras (UIs, dashboards, IDE plugins) puedan parsear sin tocar internals.
4. **Integración natural** con CLI, MCP y plugins (Fase 41) sin modificar la firma pública de los agentes.
5. **No introducir red ni dependencias pesadas**: stdlib + Pydantic.

## No-objetivos (boundaries vinculantes)

- **No** dashboard web — solo schema + writer + CLI viewer. Una web UI sobre los JSON Lines es fase futura.
- **No** distributed tracing entre máquinas — local-only por diseño (ver discusión OpenTelemetry abajo).
- **No** auto-traceo: el tracer es **opt-in** via flag CLI / parámetro MCP / context manager Python. Sin opt-in → NO-OP.
- **No** modifica los outputs de los agentes — el `AgentResult` mantiene su shape; el `trace_id` viaja en `metadata`.
- **No** persiste PII más allá de lo que ya ingresó como `input` al agente (querys del usuario).

## Decisión clave: OpenTelemetry vs JSON local

Esta es la decisión arquitectónica central de la fase. Tradeoffs:

### Opción A — OpenTelemetry (OTel SDK estándar)

**Pro**:
- Estándar industrial; ecosistema enorme (Jaeger, Tempo, Honeycomb, Datadog, …).
- Spans nesteables nativamente, propagación de contexto automática (`context.attach`).
- Métricas + logs + traces en un solo SDK.
- Si el toolkit se despliega en prod (REST API M11), encajar con Grafana/Jaeger es trivial.

**Contra**:
- **`opentelemetry-sdk` + `opentelemetry-exporter-otlp` agregan ~80MB** de deps transitivas (gRPC, protobuf, jaeger-client, …).
- Forza pensar en términos de spans/attrs/events — más ergonomía para SREs que para dev local.
- El default suele ser **fire-and-forget a un collector**: sin collector configurado, los traces se pierden silenciosamente.
- Schema OTel es genérico (`name`, `attributes`, `events`); las semantic conventions doctrinales (`finding_kept`, `finding_dropped`, `reason`) hay que mapearlas a `event.attributes` y se pierde **legibilidad** al inspeccionar el JSON crudo.
- Tests determinísticos requieren un `InMemorySpanExporter` ad-hoc.

### Opción B — JSON Lines local-only (camino elegido)

**Pro**:
- **Cero deps extra** (solo Pydantic, ya transitiva en el monorepo).
- Schema explícito y doctrinal (`type: "finding_kept"`) — legible con `cat trace.jsonl | jq`.
- Local-first coherente con principio #3 del proyecto; el archivo vive en `~/.jw-agent-toolkit/traces/`.
- Tests determinísticos triviales: el writer es un `Path`-target; en test → `tmp_path`.
- **Cero red por default** (principio #4 de tests).
- Overhead ~1-3% en benchmarks preliminares (un `json.dumps` por evento, append-only).

**Contra**:
- No interopera con Jaeger out-of-the-box.
- Si el día de mañana queremos federar trazas a un collector central, hay que escribir un adapter.

### Decisión y mitigación

**Elegimos Opción B (JSON Lines local-only) como capa principal**, con **adapter OTel opt-in** vía extra `[otel]` que envuelve los `TraceEvent` como spans OTel cuando el usuario lo activa. Así:

- **Default**: zero-dep, local-first, JSON Lines legible.
- **Power users** (devs en prod, integración Grafana): `pip install jw-agent-toolkit[otel]` + `JW_TRACE_OTEL_EXPORTER=otlp://collector:4317` activa el bridge.
- El `AgentTracer` es la API estable; los exporters son intercambiables.

Esto sigue el patrón `triple-target provider abstraction` (principio #7): default ergonómico + opt-in industrial.

## Arquitectura

Nuevo módulo `packages/jw-agents/src/jw_agents/tracing/`. Dependencias hacia abajo: solo `jw_core.observability.logging_setup` (para reusar `_JsonFormatter` style) y `pydantic`.

```
packages/jw-agents/src/jw_agents/tracing/
├── __init__.py            # re-exporta AgentTracer, TraceEvent, get_active_tracer
├── schema.py              # Pydantic models (TraceEvent variants, Trace)
├── tracer.py              # AgentTracer context manager + step/finding helpers
├── store.py               # JsonlTraceStore (default) + NullTraceStore (NO-OP)
├── context.py             # contextvars.ContextVar para tracer activo
├── exporters/
│   ├── __init__.py
│   ├── otel.py            # opt-in OTel bridge (extra [otel])
│   └── inmemory.py        # útil en tests
├── viewer.py              # CLI pretty-printer: jw trace view <run_id>
└── _flag.py               # helper compartido --trace para Typer/argparse
```

### Reglas duras de diseño

1. `jw_agents.tracing` **nunca** importa en hot path al inicializarse (deps lazy).
2. `AgentTracer` **siempre** es no-op si no hay store configurado (zero overhead pasivo).
3. El `TraceEvent` shape es **estable y semverable**: cualquier cambio incompatible incrementa `TRACE_SCHEMA_VERSION`.
4. Eventos se escriben **append-only** a JSONL; el `Trace` envelope se escribe al final como ÚLTIMA línea con tipo `trace_complete`.
5. **Cero red por default**. El exporter OTel solo se activa si el extra `[otel]` está instalado **y** `JW_TRACE_OTEL_EXPORTER` está set.
6. `trace_id` es UUID v4. `run_id` (alias) viaja en `AgentResult.metadata['trace_id']`.

## Schema de eventos (Pydantic)

`packages/jw-agents/src/jw_agents/tracing/schema.py`:

```python
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field

TRACE_SCHEMA_VERSION = "1.0"

class _BaseEvent(BaseModel):
    ts: datetime
    seq: int  # monotonic per-trace counter

class StepStartEvent(_BaseEvent):
    type: Literal["step_start"] = "step_start"
    name: str                    # "topic_index_lookup", "cdn_search", ...
    input_digest: dict[str, Any] | None = None  # NOT raw input — small fingerprint

class StepEndEvent(_BaseEvent):
    type: Literal["step_end"] = "step_end"
    name: str
    duration_ms: int
    hits: int | None = None      # raw hit count before filtering
    kept: int | None = None
    dropped: int | None = None
    error: str | None = None

class FindingKeptEvent(_BaseEvent):
    type: Literal["finding_kept"] = "finding_kept"
    source: str                  # "topic_index", "verse_text", "rag", ...
    citation_url: str            # canonical jw.org URL
    score: float | None = None
    rank: int | None = None
    reason: str = ""             # "primary match", "highest cosine", ...

class FindingDroppedEvent(_BaseEvent):
    type: Literal["finding_dropped"] = "finding_dropped"
    source: str
    citation_url: str | None = None
    reason: str                  # "duplicate", "low_score", "nli_neutral", ...
    score: float | None = None

class WarningEvent(_BaseEvent):
    type: Literal["warning"] = "warning"
    message: str
    step: str | None = None

class CustomEvent(_BaseEvent):
    """Escape hatch for plugin authors (Fase 41)."""
    type: Literal["custom"] = "custom"
    name: str
    payload: dict[str, Any]

TraceEvent = (
    StepStartEvent | StepEndEvent | FindingKeptEvent
    | FindingDroppedEvent | WarningEvent | CustomEvent
)

class Trace(BaseModel):
    """Envelope. Written as the FINAL line of the JSONL file."""
    schema_version: str = TRACE_SCHEMA_VERSION
    trace_id: UUID
    agent: str
    language: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    input: dict[str, Any]        # the public agent kwargs (no clients)
    findings_in: int             # total considered across steps
    findings_out: int            # in AgentResult.findings
    warnings_count: int
    events_path: str             # relative path to the JSONL (self-reference)
```

## API pública

### `AgentTracer` context manager

```python
from jw_agents.tracing import AgentTracer, get_active_tracer

async def apologetics(question: str, *, trace: AgentTracer | None = None, ...) -> AgentResult:
    tr = trace or get_active_tracer()  # may be NO-OP

    async with tr.step("topic_index_lookup", input_digest={"q_len": len(question)}) as step:
        subjects = await topic.search_subjects(question, ...)
        step.note_hits(len(subjects))
        for s in subjects[:topic_top_k]:
            if not s.get("docid"):
                tr.dropped(source="topic_index", reason="no docid", citation_url=s.get("wol_url"))
                continue
            tr.kept(source="topic_index", citation_url=s["wol_url"], score=s.get("score"), reason="primary match")
            ...
```

Si `tr` es el `NullTracer` (default cuando no hay `--trace`), todos los métodos son **no-op inlineables** (≤1ns).

### CLI

Cada CLI de agente gana un flag compartido vía `jw_agents.tracing._flag.add_trace_flag(parser)`:

```bash
jw apologetics --question "¿Trinidad?" --trace                       # ~/.jw-agent-toolkit/traces/apologetics-<uuid>.jsonl
jw apologetics --question "¿Trinidad?" --trace /tmp/trace.jsonl       # path explícito
jw apologetics --question "¿Trinidad?" --trace -                      # stdout
jw trace view <run_id>                                                # pretty printer
jw trace list --agent apologetics --last 10
```

El flag `--trace` solo activa el `JsonlTraceStore`. Sin flag → `NullTraceStore`.

### MCP

Cada herramienta MCP existente (`jw_apologetics`, `jw_research_topic`, …) acepta un parámetro extra implícito `trace: bool = False`. Cuando es `True`:

- `AgentResult.metadata['trace_id']` lleva el UUID.
- `AgentResult.metadata['trace_events_path']` lleva la ruta absoluta al JSONL.

Nueva herramienta MCP:

```python
async def get_trace(trace_id: str) -> dict:
    """Return parsed trace events + envelope for an existing run."""
```

Esto permite al cliente MCP (Claude Desktop, etc.) pedir el trace **después** de ver la respuesta y razonar sobre ella ("¿por qué no incluiste la cita X?").

## Integración con Fase 39 (NLI runtime)

Cuando Fase 39 esté implementada, el wrapper `fidelity_wrap` emite `FindingDroppedEvent(reason="nli_below_threshold", score=0.42)` automáticamente, sin que el agente lo sepa. El tracer es el canal natural de visibilidad para por qué NLI tumbó algo.

## Integración con Fase 41 (Plugin SDK)

Plugins terceros que implementen agentes vía entry-point `jw_agent_toolkit.agents` pueden:
- Recibir el tracer activo vía `get_active_tracer()`.
- Emitir `CustomEvent(name="my_step", payload={...})` para sus pasos propios.
- El schema versionado garantiza que un viewer futuro puede pretty-printear eventos custom sin caer.

## Almacenamiento

### Default

`~/.jw-agent-toolkit/traces/{agent}-{YYYY-MM-DD}-{trace_id}.jsonl`

Estructura del archivo (cada línea es un JSON object):

```
{"type":"step_start","ts":"...","seq":0,"name":"topic_index_lookup","input_digest":{"q_len":18}}
{"type":"finding_kept","ts":"...","seq":1,"source":"topic_index","citation_url":"https://wol.jw.org/...","score":0.91,"reason":"primary match"}
{"type":"finding_dropped","ts":"...","seq":2,"source":"rag","reason":"duplicate of seq=1"}
{"type":"step_end","ts":"...","seq":3,"name":"topic_index_lookup","duration_ms":142,"hits":12,"kept":1,"dropped":11}
{"type":"trace_complete","schema_version":"1.0","trace_id":"...","agent":"apologetics","duration_ms":1234,"findings_in":25,"findings_out":10,...}
```

### Rotación / GC

- `jw trace gc --older-than 30d` borra trazas viejas.
- Nada se borra automáticamente; el dev decide.
- El path raíz respeta `JW_TRACE_DIR` env override.

### Tamaño

Benchmark preliminar (agente `apologetics` con corpus medio): ~8KB por trace promedio. 1000 runs ≈ 8MB. Trivial.

## Overhead

Compromiso: **≤5% perf hit con tracer activo**, **0% con NO-OP**.

Estrategias:
1. `NullTracer` es la implementación default — todos los métodos son `pass`. JIT/branch predictor los elimina.
2. `JsonlTraceStore` usa **write-buffered append** (`io.BufferedWriter`); flush al cerrar el context manager raíz.
3. `datetime.now(UTC)` cacheado por evento (no por field).
4. `Pydantic` se usa para validación de **input** (eventos construidos por nosotros) pero la serialización es `model_dump_json()` directo — no roundtrip.
5. No se hace `deepcopy` del input — solo `input_digest` (proyecciones controladas).

Benchmark target en CI: `tests/perf/test_tracer_overhead.py` mide `apologetics` con y sin trace sobre fixtures fakes; falla si overhead > 7% (margen sobre el 5% nominal).

## Tests

`packages/jw-agents/tests/tracing/`:

- `test_schema.py` — round-trip Pydantic, schema_version.
- `test_tracer_noop.py` — `NullTracer` no escribe nada; perf ≤1µs por evento.
- `test_tracer_jsonl.py` — append correcto, ordering por `seq`, envelope al final.
- `test_context.py` — `contextvars` aísla tracers en concurrencia.
- `test_cli_flag.py` — `--trace` y `--trace /path` y `--trace -`.
- `test_viewer.py` — pretty-print de un fixture.
- `test_otel_bridge.py` — bajo `pytest.importorskip("opentelemetry")`.
- `test_overhead.py` — guard de regresión perf.
- `test_integration_apologetics.py` — corre el agente con stubs + verifica eventos esperados.

**Cero red. Cero LLM**. Stubs de WOLClient/CDNClient ya existentes en el monorepo se reusan.

## Integración con `jw-eval` (Fase 22)

Fase 22 puede correr la suite con `--trace` para que cada caso L1/L2/L3 deje su traza adyacente al reporte. Esto convierte "este L2 falló" en "este L2 falló, y aquí el trace que muestra cuál finding faltó". **Mutualmente útil**, opt-in.

## Variables de entorno

| Var | Default | Efecto |
|---|---|---|
| `JW_TRACE_DIR` | `~/.jw-agent-toolkit/traces` | Raíz de archivos |
| `JW_TRACE_AUTO` | `0` | Si `1`, todo CLI activa tracer aunque no haya `--trace` |
| `JW_TRACE_OTEL_EXPORTER` | unset | Si set, activa bridge OTel (requiere extra `[otel]`) |
| `JW_TRACE_BUFFER_SIZE` | `64` | Eventos antes de flush |

## Métricas de éxito de la fase

- ✅ `jw apologetics --trace` produce un JSONL parseable que valida contra el schema Pydantic v1.0.
- ✅ Overhead medido en CI ≤7%.
- ✅ Los 12 agentes existentes están instrumentados (mínimo `step_start`/`step_end` por etapa + `finding_kept`/`finding_dropped` por decisión clave).
- ✅ MCP tool `get_trace(trace_id)` devuelve eventos parseables.
- ✅ CLI `jw trace view` y `jw trace list` funcionan.
- ✅ Tests offline pasan (cero red).
- ✅ Documentación en `docs/guias/agent-tracing.md` con un ejemplo end-to-end.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Overhead crece con el corpus | Buffer de escritura + benchmark guard en CI |
| 2 | Trazas exponen PII (preguntas usuario) | Vivienda local-only; doc explícito; `JW_TRACE_DIR` configurable |
| 3 | Schema cambia y rompe viewers terceros | `TRACE_SCHEMA_VERSION` semverado; viewer maneja N-1 |
| 4 | Devs olvidan instrumentar nuevos agentes | Lint check en CI: `grep -L "tracer.step\|get_active_tracer" packages/jw-agents/src/jw_agents/*.py` listará agentes sin instrumentar |
| 5 | OTel bridge se queda desactualizado | Solo se testea cuando el extra está instalado; integration test opcional |
| 6 | Concurrencia (varios agentes en paralelo) confunde el contexto | `contextvars.ContextVar` aísla por task; tests cubren `asyncio.gather` |
| 7 | Archivos JSONL se acumulan | `jw trace gc` + doc; nunca auto-borramos |

## Cómo verificar al cerrar

```bash
# 1. Run con trace
uv run jw apologetics --question "¿Es la Trinidad bíblica?" --trace /tmp/t.jsonl

# 2. Inspeccionar
cat /tmp/t.jsonl | jq -c 'select(.type == "finding_kept" or .type == "finding_dropped")'

# 3. Pretty print
uv run jw trace view /tmp/t.jsonl

# 4. MCP roundtrip
uv run jw mcp call jw_apologetics --question "Test" --trace true
uv run jw mcp call get_trace --trace_id <uuid>

# 5. Tests
.venv/bin/python -m pytest packages/jw-agents/tests/tracing

# 6. Overhead guard
.venv/bin/python -m pytest packages/jw-agents/tests/tracing/test_overhead.py -v
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-43-agent-tracing-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold `packages/jw-agents/src/jw_agents/tracing/` + `schema.py` con tests.
2. `NullTracer` + `JsonlTraceStore` + `AgentTracer` core, sin instrumentar agentes aún.
3. `contextvars` + `get_active_tracer()` + tests de concurrencia.
4. Flag CLI compartido `--trace` + Typer integration.
5. Instrumentar `apologetics` (agente pilot) + integration test.
6. Instrumentar los 11 agentes restantes (un commit por agente, con golden test del trace shape).
7. MCP wiring: `trace` param + `get_trace` tool.
8. `jw trace view` + `jw trace list` + `jw trace gc`.
9. OTel bridge bajo extra `[otel]` + integration test opcional.
10. Doc `docs/guias/agent-tracing.md` + audit 1:1 en `docs/VISION_AUDIT.md`.
11. Benchmark `test_overhead.py` + threshold CI.

Cada paso con su PR + tests + cero regresiones en los 1984 tests existentes.

## Pendientes explícitos (post-Fase 43)

- **Web UI sobre trazas**: lectura visual con timeline + drill-down. Fase futura.
- **Cross-agent tracing**: cuando un agente llama a otro (composición Fase 14), encadenar `parent_trace_id`. No urgente para v1.
- **Sampling**: hoy trace es todo-o-nada por run. Sampling porcentual queda para cuando haya volumen prod real.
- **Anonimización automática** de queries en trace: opt-in vía `JW_TRACE_ANON=1` + reglas sencillas; queda para Fase futura si surge necesidad.
