# Citation integrity validator (`jw_core.citations`)

> Fase 23 — validador de integridad de citas / link-rot. Spec en `docs/superpowers/specs/2026-05-30-fase-23-citation-validator-design.md`.

## Para qué sirve

Verifica que cada URL `wol.jw.org` que produce un agente esté sana en tres ejes:

| Eje | Qué chequea | Default |
|---|---|---|
| **Catálogo** | docId↔pub_code contra `MepsCatalog` local (Fase 19) | siempre |
| **Resolve** | HTTP 200 (acepta 3xx terminando en 200) | sólo con `--live` |
| **Drift** | shape del HTML coincide con snapshot de Fase 22 | sólo con `--live --drift` |

Pareja natural de Fase 22 (eval doctrinal). Fase 22 detecta drift una vez por semana; Fase 23 **diagnostica** y enriquece los issues.

## Usar desde CLI

```bash
# Default offline-only (sólo catálogo)
echo "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140" > /tmp/urls.txt
uv run jw citations check --urls /tmp/urls.txt

# Validar un AgentResult serializado
jw mcp call apologetics --question "Trinidad?" --out /tmp/result.json
uv run jw citations check --agent-output /tmp/result.json

# Live: HTTP real con concurrencia limitada
uv run jw citations check --urls /tmp/urls.txt --live

# Live + drift: compara contra snapshots de jw-eval
uv run jw citations check --urls /tmp/urls.txt --live --drift

# JSON output (para pipelines)
uv run jw citations check --urls /tmp/urls.txt --report json --out /tmp/report.json
```

## Usar desde MCP

```python
# tool: validate_citations
out = validate_citations(
    urls=["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
    live=False,
    check_drift=False,
)
# {"mode": "structural", "checks": [...], "summary": {...}}
```

Modo `live` requiere `JW_CITATIONS_LIVE=1` en el entorno del MCP server — diseño explícito para que un cliente LLM no martillee wol.jw.org por accidente.

## Usar desde código (validador de agentes)

```python
from jw_core.citations import CitationValidator

async def smoke(agent_output):
    v = CitationValidator()
    report = await v.validate_agent_output(agent_output, mode="structural")
    assert report.summary["failed"] == 0
```

## Interpretar el reporte

| `resolve` | Qué significa |
|---|---|
| `ok` | HTTP 200 directo |
| `ok_redirect` | 3xx → 200 (warning, no error) |
| `not_found` | 404 |
| `gone` | 410 |
| `server_error` | 5xx |
| `redirect_loop` | >3 redirecciones |
| `network_error` | timeout/DNS/TLS |
| `skipped` | modo estructural |

| `catalog` | Qué significa |
|---|---|
| `ok` | docId en MepsCatalog, pub_code coincide |
| `mismatch` | docId existe pero pub_code de la URL no coincide con catálogo |
| `missing` | docId no está en el catálogo local |
| `unknown` | URL sin docId (Biblia) o catálogo vacío |
| `skipped` | no se pasó catálogo |

| `drift` | Qué significa |
|---|---|
| `ok` | shape HTML == snapshot |
| `drift` | shape difiere; revisar `notes` |
| `no_snapshot` | no hay snapshot para esa URL |
| `skipped` | modo no incluye drift |

## Política

- **CI público corre solo modo estructural**. `--live` es manual o weekly cron de Fase 22.
- **Concurrencia 4 por defecto** en modo live. Aumentar sólo si tu red lo soporta y has hablado con el mantenedor.
- **`missing` en catálogo no es failure**: significa que falta `.jwpub` indexado, no que la URL esté rota.

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Todos `catalog=unknown` | catálogo vacío | `jw library register <archivo.jwpub>` |
| `drift` en una URL conocida | wol cambió el HTML | refrescar snapshot vía `packages/jw-eval/scripts/build_eval_snapshots.py --force` |
| MCP rechaza `live=True` | falta env var | export `JW_CITATIONS_LIVE=1` para esa sesión |
