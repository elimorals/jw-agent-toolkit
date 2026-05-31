# Fase 23 — `jw_core.citations`: validador de integridad de citas / link-rot

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (infraestructura de confianza)
> **Depende de**: ninguna fase. Idealmente Fase 22 ya merged (reutilizan snapshots), pero **no es bloqueante**.
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)
> **Hermana**: [`2026-05-30-fase-22-eval-doctrinal-design.md`](2026-05-30-fase-22-eval-doctrinal-design.md)

## Motivación

Cada `Finding` que producen los 12 agentes carga una URL canónica de wol.jw.org. El toolkit confía en que **esa URL resuelve** y que el **docId que lleva sigue apuntando** a la publicación correcta. Hoy esa promesa no se valida en ningún sitio:

- Los tests son offline y usan fixtures HTML congeladas — no pueden detectar link-rot real.
- La Fase 22 (L2 live) **detecta** drift una vez por semana, pero **no diagnostica**: solo dice "el snapshot ya no contiene la frase esperada". No te dice si el problema es 404, redirect a otra publicación, o un cambio menor de wording.
- Telemetría (Fase 9) solo monitoriza forma de respuestas JSON de los endpoints de API, no la integridad de URLs HTML que entregan los agentes.

Fase 23 cierra el hueco con un módulo **inyectable y composable** que verifica tres dimensiones por URL:

1. **Resuelve**: HTTP 200 directo o 3xx que termina en 200 (cadena de redirecciones registrada).
2. **El docId↔pub_code está sano**: si la URL contiene `/d/{r}/{lp_tag}/{docId}`, el catálogo MEPS local (Fase 19) confirma que existe una publicación con ese `meps_document_id`.
3. **Drift estructural** (opcional, cuando hay snapshot previo): el `shape_hash` del HTML descargado coincide con el de referencia.

El **modo por defecto es estructural y offline**: solo (2) — no toca la red. Modo `--live` activa (1) y (3). Esto lo hace seguro de integrar en cualquier test, smoke o pipeline.

## Objetivos (en orden de prioridad)

1. **Validar batch de URLs offline (modo estructural)**: comprobar docId↔pub_code contra `MepsCatalog` sin red. Útil en CI público y en el smoke test de cada agente.
2. **Validar batch de URLs en vivo (modo live)**: HEAD/GET contra wol.jw.org con redirecciones, concurrencia limitada y drift opcional. Sólo opt-in (`--live` o env).
3. **Aceptar tres formas de entrada**: lista de URLs, un `AgentResult` serializado (JSON o YAML), o un objeto in-memory `AgentResult`-like (cualquier cosa con `.findings` y `metadata['citation_url']` o `citation.url`).
4. **Devolver siempre un `CitationReport` (Pydantic)** con per-URL `CitationCheck` — verdict + diagnóstico estructurado para enriquecer issues de Fase 22.
5. **Composable con Fase 22**: cuando L2-live abre un issue de drift, `scripts/eval_open_drift_issues.py` (Fase 22) puede llamar a este validador y adjuntar el reporte detallado.

## No-objetivos (boundaries vinculantes)

- **No** descarga ni almacena snapshots completos por sí mismo. Los snapshots los maneja Fase 22 (`packages/jw-eval/fixtures/wol_snapshots/`). Fase 23 los **lee** si existen para el modo drift; cross-package lectura está OK, **no se importa nada de `jw-eval`**.
- **No** reescribe URLs ni intenta "arreglar" link-rot. Solo diagnostica.
- **No** modifica los agentes ni el contrato `Finding`. Es un validador de salida.
- **No** abre issues por sí mismo. Eso lo hace el script de Fase 22 consumiendo el `CitationReport`.
- **No** distribuye en CI público una API key. El modo live no requiere autenticación — wol.jw.org es público.

## Arquitectura

Nuevo subpaquete `packages/jw-core/src/jw_core/citations/`. Vive **dentro de `jw-core`** porque (a) usa `MepsCatalog` y `WOLClient`, (b) los consumidores naturales son `jw-agents` (smoke test) y `jw-mcp` (tool), no requiere un paquete propio. Dependencias hacia abajo idénticas al resto de `jw-core`: nada del workspace lo importa hacia atrás.

```
packages/jw-core/src/jw_core/citations/
├── __init__.py          # public API re-exports
├── models.py            # CitationCheck, CitationReport, ResolveStatus
└── validator.py         # CitationValidator + helpers (extract URLs, classify)

packages/jw-core/tests/
└── test_citation_validator.py

packages/jw-mcp/src/jw_mcp/
└── server.py            # MODIFICA: tool validate_citations

packages/jw-cli/src/jw_cli/commands/
└── citations.py         # NUEVO: jw citations check ...
                          # MODIFICA: main.py registra el comando
```

### Reglas duras de diseño

1. `jw_core.citations` **no** importa nada que haga red en import time. El fetcher live se construye lazy.
2. El fetcher es **inyectable**: tests usan un fake síncrono; CLI usa httpx async; producción puede usar `WOLClient` si quiere reutilizar throttler/cache de Fase 9.
3. **El modo por defecto NO usa red**. Lograr modo live requiere flag explícito (`--live`) o env (`JW_CITATIONS_LIVE=1`).
4. Concurrencia limitada a 4 conexiones en modo live (`asyncio.Semaphore(4)`), configurable.
5. Redirect handling: sigue hasta **3** redirecciones; treat final 200 como success con `redirect_chain` poblado (>=1 redirect lo marca como `ok_redirect`, no `ok`).
6. Si `MepsCatalog` no está poblado (DB vacía / inexistente), el chequeo de docId↔pub_code se reporta como `unknown` (no como `fail`). Es la situación esperada en CI público sin `.jwpub` indexados.

## Modelos (Pydantic)

```python
# src/jw_core/citations/models.py

from typing import Literal
from pydantic import BaseModel, Field

ResolveStatus = Literal[
    "ok",            # HTTP 200 sin redirección
    "ok_redirect",   # HTTP 3xx → … → 200 (final OK, hay redirect_chain)
    "not_found",     # HTTP 404
    "gone",          # HTTP 410
    "server_error",  # HTTP 5xx
    "redirect_loop", # >3 redirecciones
    "network_error", # timeout, DNS, TLS
    "skipped",       # modo offline / fetcher None
]

CatalogStatus = Literal[
    "ok",            # docId encontrado en MepsCatalog, pub_code coincide
    "mismatch",      # docId existe pero pub_code de la URL ≠ catálogo
    "missing",       # docId NO existe en catálogo
    "unknown",       # catálogo vacío o no aplicable (URL sin docId)
    "skipped",       # catálogo no configurado
]

DriftStatus = Literal[
    "ok",            # shape_hash del live == snapshot
    "drift",         # difieren
    "no_snapshot",   # no hay snapshot para comparar
    "skipped",       # modo offline
]


class CitationCheck(BaseModel):
    """Per-URL diagnostic."""

    url: str
    resolved_url: str | None = None             # final URL after redirects
    redirect_chain: list[str] = Field(default_factory=list)
    http_status: int | None = None
    resolve: ResolveStatus = "skipped"

    # MEPS catalog cross-check
    doc_id: int | None = None                   # parsed from URL
    pub_code: str | None = None                 # parsed from URL
    catalog: CatalogStatus = "unknown"

    # Snapshot drift (optional)
    drift: DriftStatus = "skipped"
    snapshot_path: str | None = None

    notes: list[str] = Field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return (
            self.resolve in {"ok", "ok_redirect", "skipped"}
            and self.catalog in {"ok", "unknown", "skipped"}
            and self.drift in {"ok", "no_snapshot", "skipped"}
        )


class CitationReport(BaseModel):
    """Aggregate result of validating a batch of URLs."""

    mode: Literal["structural", "live", "live+drift"]
    checks: list[CitationCheck]
    summary: dict[str, int] = Field(default_factory=dict)

    @staticmethod
    def summarize(checks: list[CitationCheck]) -> dict[str, int]:
        agg = {"total": len(checks), "ok": 0, "failed": 0, "warning": 0}
        for c in checks:
            if c.is_ok and c.resolve != "ok_redirect" and c.drift != "no_snapshot":
                agg["ok"] += 1
            elif c.is_ok:
                agg["warning"] += 1
            else:
                agg["failed"] += 1
        return agg
```

## Validador

```python
# src/jw_core/citations/validator.py

class CitationValidator:
    def __init__(
        self,
        *,
        catalog: MepsCatalog | None = None,
        fetcher: AsyncFetcher | None = None,
        snapshots_root: Path | None = None,
        max_redirects: int = 3,
        concurrency: int = 4,
    ) -> None: ...

    async def validate_urls(
        self,
        urls: list[str],
        *,
        mode: Literal["structural", "live", "live+drift"] = "structural",
    ) -> CitationReport: ...

    async def validate_agent_output(
        self,
        agent_output: dict | AgentResultLike,
        *,
        mode: Literal["structural", "live", "live+drift"] = "structural",
    ) -> CitationReport: ...
```

`AsyncFetcher` es un `Callable[[str], Awaitable[FetcherResponse]]` donde `FetcherResponse` es un dataclass con `final_url, status, redirect_chain, body`. El validador **nunca** instancia un `httpx.AsyncClient` en su `__init__`; eso lo hace el caller (CLI/MCP).

### Extracción de URLs desde un AgentResult-like

Convención del toolkit (Fase 22 spec sec L2): cada `finding.metadata['citation_url']` o `finding.citation.url`. El extractor es tolerante:

1. Si recibe `dict`, busca `findings[i].metadata.citation_url`.
2. Si recibe objeto, intenta `f.metadata.get('citation_url')`, luego `f.citation.url`.
3. URLs duplicadas se deduplican preservando orden.

### Parser de URL → (pub_code, doc_id)

Regex sobre el patrón documentado en `ARCHITECTURE.md`:

```
/{iso}/wol/d/{r}/{lp_tag}/{docId}
/{iso}/wol/b/{r}/{lp_tag}/{pub}/{book_num}/{chapter}
```

- Patrón `/d/.../<digits>$` → `doc_id = int(...)`; `pub_code = None` (se resuelve desde catálogo).
- Patrón `/b/.../<pub>/<n>/<n>` → `pub_code = <pub>`; `doc_id = None`.

Si una URL no calza ninguno → `catalog = "unknown"` (no es error, p.ej. enlaces directos a `b.jw-cdn.org`).

## Integración con el resto del toolkit

### CLI (`jw-cli`)

Nuevo comando `jw citations` con dos subcomandos:

```
jw citations check --urls urls.txt
jw citations check --agent-output result.json
jw citations check --urls urls.txt --live
jw citations check --urls urls.txt --live --drift   # requiere snapshots-root
jw citations check --agent-output result.json --report json --out report.json
jw citations check --urls urls.txt --concurrency 8
```

Defaults:
- `--report md` → markdown a stdout
- `--snapshots-root packages/jw-eval/fixtures/wol_snapshots` (si existe)
- `--live` activa fetcher real (httpx); sin él, modo `structural`

Exit code = número de checks con verdict != ok (capped a 125).

### MCP (`jw-mcp`)

Nueva herramienta:

```python
@mcp.tool()
def validate_citations(
    urls: list[str] | None = None,
    agent_output: dict | None = None,
    live: bool = False,
    check_drift: bool = False,
) -> dict:
    """Validar integridad de citas de un agente. Devuelve CitationReport como dict."""
```

Exactamente una de `urls` o `agent_output` debe estar presente. Modo `live` requiere `JW_CITATIONS_LIVE=1` o el cliente lo concede explícitamente (esto evita que el MCP server pegue a wol sin opt-in).

### Composición con Fase 22

`packages/jw-eval/scripts/eval_open_drift_issues.py` (Fase 22, Task 17) ya recibe `l2-live.json`. Cuando aterrice Fase 23, ese script:

1. Parsea `l2-live.json` y agrupa fails por `case_id`.
2. Extrae `expected_citations` de cada caso L2 fallido (cargando el YAML del caso).
3. Llama `CitationValidator.validate_urls(urls, mode="live+drift")`.
4. Adjunta el `CitationReport.model_dump_json(indent=2)` al body del issue, sección "## Citation diagnostic".

Esto se hace **sin importar `jw-eval` desde `jw-core`**: Fase 22 importa Fase 23 (jw-core), no al revés.

### Smoke test por agente

Cada agente tiene su test de smoke en `packages/jw-agents/tests/test_<agent>.py`. Se añade un patrón opcional `_smoke_citations` que corre `CitationValidator.validate_agent_output(result, mode="structural")` y asserts `report.summary['failed'] == 0`. Esto da regresión gratis si un agente empieza a producir URLs malformadas o con docIds que no existen.

### CI (`.github/workflows/ci.yml`)

No requiere job nuevo en Fase 23. La validación estructural corre dentro de los tests existentes. **Opcionalmente** la Fase 22 puede agregar un step al job `eval-l2-live`:

```yaml
- name: Enrich drift issues with citation diagnostics
  run: uv run python packages/jw-eval/scripts/eval_open_drift_issues.py l2-live.json
  # Internamente ya invoca CitationValidator.
```

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | El validador live abusa wol.jw.org en CI público | Concurrencia 4 por defecto, sólo se activa con flag explícito, **no** corre en PRs |
| 2 | Catálogo vacío en CI público (no hay `.jwpub` indexados) → todos `unknown` ruidosos | Por diseño, `unknown` no es failure. Lo señalamos como warning sólo cuando el modo es live; en structural-only es OK |
| 3 | Redirect loops infinitos | Cap a 3 redirects; >3 marca `redirect_loop` y aborta esa URL |
| 4 | wol.jw.org responde 200 con página de error genérica | Mitigado parcialmente por Fase 22 L2-live (compara support_phrases). Fase 23 sólo garantiza "resuelve"; combinación con Fase 22 da el panorama completo |
| 5 | Fetcher real cambia entre tests y producción | Inyectable, tests usan stub determinístico; CLI usa httpx.AsyncClient con timeout 30s |
| 6 | `MepsCatalog` no thread-safe entre eventos asyncio | Se abre una conexión sqlite por validador, todas las lookups van por un `asyncio.Lock` interno o ejecutan en `asyncio.to_thread` |
| 7 | URL contiene caracteres no-ASCII (idiomas asiáticos) | httpx maneja IRI→URI; tests cubren un caso con `wol.jw.org/jp/wol/...` |
| 8 | Snapshot drift falso positivo por scripts inyectados a posteriori | El `_minify` de Fase 22 ya quita `<script>` y `<style>`; reutilizamos esa convención (importamos `_minify` vía función pública o copiamos 5 líneas) |

## Métricas de éxito de la fase

- ✅ `CitationValidator` con 100% cobertura de ramas en `validate_urls` y `validate_agent_output`.
- ✅ Modo estructural corre en <100ms por 50 URLs (sin red).
- ✅ Modo live respeta concurrencia configurada (verificable con stub que cuenta concurrentes vivos).
- ✅ Tool MCP `validate_citations` accesible y testeada.
- ✅ CLI `jw citations check` funcional con ambos inputs (urls / agent-output) y dos modos.
- ✅ Fase 22 `eval_open_drift_issues.py` se actualiza para invocar este validador (en una sola línea).
- ✅ Smoke test de al menos un agente (`verse_explainer`) corre el validador en modo estructural y pasa.
- ✅ Documentado en `docs/guias/citation-validator.md`.

## Pendientes explícitos (post-Fase 23)

- Adopción del smoke test en los 12 agentes (incremental, agente por agente, en cada PR de fases posteriores).
- Modo "deep drift" que compara texto extraído (no solo shape) → potencial Fase 23.5 si Fase 22 lo demanda.
- Caching del catálogo en memoria entre llamadas para builds CI grandes — bajo prioridad, el overhead actual es <1ms por lookup.

## Cómo verificar al cerrar

```bash
# 1. Instalar (debería ser noop, ya está en jw-core)
uv sync --all-packages

# 2. Tests del validador
.venv/bin/python -m pytest packages/jw-core/tests/test_citation_validator.py -v

# 3. CLI modo estructural con un archivo de URLs
echo "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3" > /tmp/urls.txt
uv run jw citations check --urls /tmp/urls.txt

# 4. CLI modo live (requiere red, opcional)
uv run jw citations check --urls /tmp/urls.txt --live

# 5. MCP tool roundtrip
.venv/bin/python -m pytest packages/jw-mcp/tests/test_citations_tool.py -v

# 6. Suite global sin regresiones
uv run pytest packages/ -q
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-30-fase-23-citation-validator-plan.md`.

Pasos cronológicos:

1. Scaffold subpaquete `citations/` dentro de `jw-core` + `__init__.py` con re-exports vacíos.
2. Modelos Pydantic (`CitationCheck`, `CitationReport`, `ResolveStatus`, `CatalogStatus`, `DriftStatus`).
3. Helpers: `_parse_wol_url`, `_extract_urls_from_agent_output`.
4. `CitationValidator` modo estructural (catálogo only, sin red).
5. Modo live: fetcher injectable, redirect chain, concurrency semaphore.
6. Modo drift: lee snapshots de `packages/jw-eval/fixtures/wol_snapshots/` si existen, compara `_shape_hash` del HTML minificado.
7. Tool MCP `validate_citations`.
8. CLI `jw citations check` (subcomando con --urls / --agent-output / --live / --drift / --report / --out).
9. Smoke test de `verse_explainer` integra el validador.
10. Doc `docs/guias/citation-validator.md`.
11. Actualizar `docs/ROADMAP.md` (Fase 23) y `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests TDD + sin regresiones en los 551+26 tests heredados.
