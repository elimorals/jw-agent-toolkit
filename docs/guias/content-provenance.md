# Content provenance (Fase 40)

> **Estado:** Estable desde Fase 40 (2026-05-31). Complementa Fase 23 (validación de URL) y Fase 39 (NLI runtime).

## Qué resuelve

`wol.jw.org` cambia. Artículos se reescriben, NWT publica revisiones, párrafos se reordenan. Una `Citation` que apuntaba a un texto concreto el martes puede quedar **huérfana** el viernes — la URL sigue resolviendo (Fase 23 ✓, L0), el `doc_id` sigue en el catálogo (Fase 23 ✓, L1), pero el **texto** ya no es el que el agente usó. Sin Fase 40, esto ocurre en silencio.

Fase 40 añade cuatro datos pequeños a cada `Citation.metadata`:

| Clave            | Tipo          | Significado                                                    |
|------------------|---------------|----------------------------------------------------------------|
| `published_date` | `str \| None` | Fecha original de publicación del artículo (ISO 8601).         |
| `accessed_at`    | `str`         | Cuándo descargó el texto el toolkit (ISO 8601 UTC).            |
| `content_hash`   | `str`         | sha256 hex del texto **canonicalizado** (NFC + whitespace).    |
| `revision`       | `str \| None` | Etiqueta de revisión, ej. `"rev. 2023"` para NWT.              |

En cualquier momento posterior, `ProvenanceValidator.check(citation)` puede:
1. Re-fetchar la URL.
2. Re-canonicalizar el texto.
3. Comparar con el `content_hash` original.
4. Si está integrado con Fase 39, re-correr NLI sobre el texto nuevo.

## La taxonomía de capas

Fase 40 ocupa una capa concreta — **L2: fidelidad de contenido** — dentro de un esquema de cuatro:

| Capa | Pregunta                                                                | Fase  | Modo            |
|------|-------------------------------------------------------------------------|-------|-----------------|
| L0   | ¿La URL existe y responde 200?                                          | 23    | live HTTP       |
| L1   | ¿El `doc_id`/`pub_code` está en MepsCatalog?                            | 23    | offline catalog |
| L2   | ¿El **contenido** sigue siendo el mismo que el agente usó?              | **40**| hash + re-fetch |
| L3   | ¿La afirmación se desprende del passage actual?                         | 39    | NLI semántico   |

Las cuatro capas son **ortogonales**: una URL puede resolver (L0 ✓), estar en catálogo (L1 ✓), tener fidelidad rota (L2 ✗), y por ende entailment incierto (L3 ?). Fase 40 es la primera capa que ataca el texto en sí, no su envoltorio.

## Uso desde CLI

```bash
# Re-chequear todas las citas de un resultado de agente:
jw provenance check --agent-output result.json

# Solo lo que se accedió antes del 2026-01-01 (típico cron mensual):
jw provenance check --agent-output result.json --since 2026-01-01

# Reporte legible en Markdown:
jw provenance check --agent-output result.json --report md --out drift.md

# Con re-validación NLI cuando Fase 39 está configurado:
JW_NLI_PROVIDER=deberta jw provenance check --agent-output result.json --with-nli
```

Códigos de salida:
- `0` — todo `match` (o `no_record`).
- `2` — hubo al menos un `changed`. Investigar.
- `3` — hubo al menos un `unreachable`. Red caída o URL muerta.

## Uso desde MCP

```python
@mcp.tool
async def verify_provenance(
    agent_output: dict,
    since: str | None = None,
    with_nli: bool = False,
) -> dict:
    """Re-check that each citation's content_hash still matches the live page."""
```

Devuelve un `ProvenanceReport` serializado. La invocación es network-bound (respeta el throttle del `WOLClient`).

## Uso programático

```python
from jw_core.provenance import ProvenanceValidator
from jw_agents.verse_explainer import verse_explainer

result = await verse_explainer("Juan 3:16", language="es")

validator = ProvenanceValidator(fetcher=my_fetcher)
report = await validator.check_agent_output(result)

if report.summary.get("changed", 0):
    print("Drift detectado:")
    for v in report.verdicts:
        if v.status == "changed":
            print(f"  {v.url} — {v.delta_chars} chars de delta")
```

## Backwards compatibility

Los `AgentResult` emitidos antes de Fase 40 no llevan las claves de provenance. `ProvenanceValidator` los detecta y devuelve verdict `no_record` sin llamar al fetcher — cero coste, cero falsos positivos.

## Telemetría opt-in

Cuando `JW_TELEMETRY_ENABLED=1`, cada `changed` se registra como un evento `provenance_drift` en `~/.jw-agent-toolkit/telemetry.json`. Nada sale de tu máquina. Inspeccionable con `Telemetry.report()`.

## Tests

```bash
.venv/bin/python -m pytest packages/jw-core/tests/test_provenance -v
.venv/bin/python -m pytest packages/jw-cli/tests/test_cli_provenance.py -v
.venv/bin/python -m pytest packages/jw-mcp/tests/test_provenance_tool.py -v
```
