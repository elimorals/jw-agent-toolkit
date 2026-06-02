# Agent tracing (Fase 43)

Local-first, opt-in JSONL traces that record every internal decision of an
agent: which findings were kept, which were dropped, and why.

## Quick start

```bash
uv run jw apologetics "¿Es la Trinidad bíblica?" --trace DEFAULT
# -> ~/.jw-agent-toolkit/traces/apologetics-2026-05-31-abcd1234.jsonl

uv run jw trace view ~/.jw-agent-toolkit/traces/apologetics-2026-05-31-abcd1234.jsonl
uv run jw trace list --agent apologetics --last 5
uv run jw trace gc --older-than 30d
```

The flag also accepts an explicit path or `-` for stdout:

```bash
uv run jw apologetics "..." --trace /tmp/t.jsonl
uv run jw apologetics "..." --trace -
```

Without `--trace` the tracer is a no-op (zero overhead).

## Schema

Each line is one event; the FINAL line is the envelope tagged
`"type": "trace_complete"`. Schema version: `1.0`.

Event types: `step_start`, `step_end`, `finding_kept`, `finding_dropped`,
`warning`, `custom` (plugin escape hatch).

Full Pydantic definitions:
`packages/jw-agents/src/jw_agents/tracing/schema.py`.

## Programmatic use

```python
from pathlib import Path
from jw_agents.apologetics import apologetics
from jw_agents.tracing import AgentTracer, JsonlTraceStore

tracer = AgentTracer(agent="apologetics", store=JsonlTraceStore(Path("/tmp/t.jsonl")))
with tracer.run(input_kwargs={"question": "demo"}, language="en"):
    result = await apologetics("demo", language="E", trace=tracer)
```

The same `AgentTracer` can be bound as the ambient tracer with `use_tracer(...)`
so downstream calls pick it up without changing signatures.

## MCP

The MCP server exposes two new surfaces:

- `apologetics(..., trace=true)` writes a trace under `$JW_TRACE_DIR` and
  returns `metadata.trace_id` + `metadata.trace_events_path`.
- `get_trace(trace_id)` parses that file back into `{envelope, events}`.

## OTel bridge (opt-in)

```bash
uv pip install 'jw-agents[otel]'
export JW_TRACE_OTEL_EXPORTER="otlp://collector:4317"
```

Wraps each `step` as a span, each `kept` / `dropped` / `warn` as a span
event. See `packages/jw-agents/src/jw_agents/tracing/exporters/otel.py`.

## Environment

| Variable                 | Default                        | Effect                       |
|--------------------------|--------------------------------|------------------------------|
| `JW_TRACE_DIR`           | `~/.jw-agent-toolkit/traces`   | Root for auto-named JSONLs   |
| `JW_TRACE_OTEL_EXPORTER` | unset                          | Activates OTel bridge        |
| `OTEL_SERVICE_NAME`      | `jw-agents`                    | OTel service.name attribute  |

## Instrumented agents (v1)

- `apologetics`
- `verse_explainer`
- `research_topic`

Other agents accept `trace=AgentTracer(...)` once they opt in; until then,
they execute unchanged and the tracer remains a NO-OP for them.
