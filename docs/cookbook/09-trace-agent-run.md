# Trace de la ejecución de un agente

> **Tiempo estimado**: 5 minutos
> **Requisitos**: Fase 43 (agent-tracing) — pendiente.
> **Slug URL**: `/cookbook/09-trace-agent-run`

## ¿Qué construyes?

Capturar un trace JSON de cada paso del agente: qué findings consideró, cuáles descartó, por qué, con qué rank.

## Código (copy-pasteable)

```python
# test skip-until-fase=43
# Esta receta requiere Fase 43 (AgentTracer). Se actualizará al cerrar F43.
from jw_agents.tracing import AgentTracer

async def example():
    tracer = AgentTracer(agent="apologetics")
    with tracer.span("topic_index_lookup") as span:
        span.record_input("Trinity")
        span.record_kept(3, dropped_reasons={"low_score": 9})
    trace = tracer.finalize()
    assert trace["agent"] == "apologetics"
    assert "steps" in trace
```

## Por qué funciona

Cuando F43 cierre: cada agente tendrá un `AgentTracer` context manager que serializa pasos a `~/.jw-agent-toolkit/traces/{agent}-{run_id}.json` (JSON Lines). Distinto de F22 eval (mide outputs) — este explica el **proceso**.

## Variaciones

- `jw apologetics --trace /tmp/x.json` para output a path custom.
- Tool MCP devuelve trace_id en metadata.
- Combinar con F39 NLI para registrar por qué un finding se rechazó.

## Próximo paso

→ [10 — Calibrar un golden case](10-calibrate-golden-case.md)
