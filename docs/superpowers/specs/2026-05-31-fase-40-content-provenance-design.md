# Fase 40 — `content-provenance`: trazabilidad reproducible del passage

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (confianza en runtime)
> **Tamaño**: S — ~1 semana
> **Depende de**: Fase 39 (`nli-runtime`) para el canal `metadata` enriquecido y para re-disparo automático de NLI al detectar cambio.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)
> **Hermanos cercanos**: Fase 22 (eval doctrinal, snapshots), Fase 23 (citation_validator, URL/resolve), Fase 9 (telemetry drift).

## Motivación

Hoy una `Citation` apunta a una URL canónica de `wol.jw.org` y eso basta para "verificable". Pero **wol.jw.org cambia**: artículos se actualizan, párrafos se reescriben, NWT publica revisiones (`rev. 2023`). Una afirmación que el agente respaldó con un párrafo concreto el martes puede quedar **huérfana** el viernes si el texto cambió, **sin que nadie lo note**.

Fase 40 cierra ese hueco con tres datos pequeños que viajan dentro de cada `Citation.metadata` y un validador que puede preguntar, en cualquier momento: *"¿el texto sigue siendo el que mi agente usó?"*. No reemplaza Fase 23 — la complementa en una capa distinta.

## Distinción de capas (clave conceptual)

| Capa | Pregunta que responde | Fase | Modo |
|---|---|---|---|
| **L0 — resolve** | "¿La URL existe y responde 200?" | Fase 23 `citation_validator` | live HTTP |
| **L1 — catalog** | "¿El `doc_id`/`pub_code` está en MepsCatalog?" | Fase 23 (modo structural) | offline |
| **L2 — fidelidad** | "¿El **contenido** sigue siendo el mismo que el agente usó?" | **Fase 40** ← este spec | hash + re-fetch |
| **L3 — entailment** | "¿La afirmación se desprende del passage actual?" | Fase 39 NLI | semántico |

Las cuatro son ortogonales. Una URL puede resolver (L0 ✓), estar en catálogo (L1 ✓), tener fidelidad rota (L2 ✗) y por ende entailment desconocido (L3 ?). Fase 40 es la primera capa que ataca **el texto en sí**, no su envoltorio.

## Objetivos

1. **Reproducibilidad**: dado un `AgentResult` archivado, poder demostrar exactamente qué versión del texto se usó.
2. **Detección automática de cambios**: `provenance_check(citation)` retorna verdict cuando el `content_hash` re-calculado difiere.
3. **Re-validación encadenada**: si Fase 39 está activa, un cambio detectado dispara re-NLI sobre el nuevo texto y se reporta si el verdict cambió de `entails` a otra cosa.
4. **Backwards compatible**: los campos viajan en `Citation.metadata` (`dict[str, Any]` ya existente) — sin breaking change para consumidores actuales.

## No-objetivos

- **No** archivar el texto completo en disco. Solo metadata + hash. Si el usuario quiere el snapshot, usa Fase 22.
- **No** garantizar inmutabilidad — no es un sistema de pruebas legales, es un canario.
- **No** firmar los AgentResults con criptografía pesada (no es blockchain).
- **No** versionar revisiones de NWT por nuestra cuenta — solo registrar la que vimos.

## Extensión de `Citation.metadata` (aditiva)

`packages/jw-agents/src/jw_agents/base.py` mantiene la dataclass `Citation` intacta. La extensión vive en convenciones de claves dentro del dict `metadata`. Cuatro claves nuevas, todas opcionales pero **fuertemente recomendadas** (los parsers de Fase 40 las inyectan al ingesta):

```python
class Citation:
    url: str
    title: str = ""
    kind: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata convencional Fase 40:
    #   "published_date":  str | None  ISO 8601 — fecha original del artículo
    #   "accessed_at":     str         ISO 8601 — cuándo lo descargó el toolkit
    #   "content_hash":    str         sha256 del texto exacto usado
    #   "revision":        str | None  "rev. 2023" para revisiones de NWT, etc.
```

**Por qué dict y no nueva dataclass**: existing tests + serialización JSON (`AgentResult.to_dict`) ya pasan estos campos por `metadata`. Cambiar la dataclass rompería 1984 tests. La validación shape vive en `ProvenanceRecord`.

## Nuevo módulo `packages/jw-core/src/jw_core/provenance/`

```
packages/jw-core/src/jw_core/provenance/
├── __init__.py
├── models.py           # ProvenanceRecord, ProvenanceVerdict, ProvenanceReport (Pydantic)
├── validator.py        # provenance_check(citation, *, fetcher) -> ProvenanceVerdict
├── propagation.py      # helpers de inyección en parsers (WOLClient ingest hook)
├── hashing.py          # canonicalize_text() + sha256 estable
└── errors.py           # ProvenanceError, MissingProvenanceError
```

### `models.py`

```python
class ProvenanceRecord(BaseModel):
    """Vista tipada de los 4 campos en Citation.metadata."""
    published_date: str | None = None       # ISO 8601 date
    accessed_at: str                        # ISO 8601 datetime UTC
    content_hash: str                       # sha256 hex del texto canonicalizado
    revision: str | None = None

    @classmethod
    def from_citation_metadata(cls, meta: dict[str, Any]) -> "ProvenanceRecord | None":
        ...

class ProvenanceVerdict(BaseModel):
    url: str
    status: Literal["match", "changed", "unreachable", "no_record", "skipped"]
    original_hash: str | None
    current_hash: str | None
    delta_chars: int | None                 # |len(new) - len(old)|, heurística
    accessed_at_original: str | None
    accessed_at_recheck: str
    nli_rerun: dict | None = None           # si Fase 39 está activa: nuevo verdict NLI
    notes: list[str] = []

class ProvenanceReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    verdicts: list[ProvenanceVerdict]
    summary: dict[str, int]                 # {"match": 12, "changed": 1, ...}
```

### `validator.py` — el corazón

```python
AsyncFetcher = Callable[[str], Awaitable[FetcherResponse]]  # reusa el de Fase 23

class ProvenanceValidator:
    """Re-fetch a citation URL and compare content_hash. Network is injectable."""

    def __init__(
        self,
        *,
        fetcher: AsyncFetcher,
        extractor: Callable[[str], str] | None = None,  # html → texto plano
        nli_provider: NLIProvider | None = None,        # de Fase 39, opcional
        concurrency: int = 4,
    ) -> None: ...

    async def check(self, citation: Citation) -> ProvenanceVerdict:
        """Re-fetch + compare. Si nli_provider y verdict='changed', re-ejecuta NLI."""

    async def check_agent_output(self, agent_output: Any) -> ProvenanceReport:
        """Itera findings, agrupa por URL única, paraleliza con semáforo."""

    async def check_since(
        self,
        agent_output: Any,
        *,
        since: datetime,
    ) -> ProvenanceReport:
        """Solo re-chequea citations con accessed_at < since (cron-friendly)."""
```

**Reglas duras**:
1. `ProvenanceValidator` NO instancia `httpx`. El fetcher se inyecta — mismo patrón Fase 23. Tests usan un `FakeFetcher` determinista.
2. `extractor` también inyectable — el default usa el `text_extractor` del parser WOL existente. Esto evita acoplamiento a una sola estrategia de canonicalización.
3. Si `nli_provider is None` y un verdict es `changed`, el campo `nli_rerun` queda `None` — no falla, solo no re-valida semánticamente.
4. Concurrency cap idéntico a Fase 23 (4) por respeto a `throttle.py`.

### `hashing.py` — canonicalización

```python
def canonicalize_text(text: str) -> str:
    """Normaliza para que cambios cosméticos no inflen el hash.

    - NFC unicode normalization
    - Collapse whitespace runs to single space
    - Strip leading/trailing whitespace
    - Lowercase NO — preservar mayúsculas doctrinalmente significativas (Jehová)
    - Eliminar zero-width chars
    """

def content_sha256(text: str) -> str:
    """sha256 hex sobre canonicalize_text(text)."""
```

**Decisión NO obvia**: no lowercaseamos. "Dios" vs "dios" puede ser diferencia de revisión doctrinal real (la NWT capitaliza "Mi Padre" en algunos casos). Preservar caja.

### `propagation.py` — inyección en parsers

Helpers para que los puntos donde el toolkit **adquiere texto** dejen rastro:

```python
def stamp_citation(
    citation: Citation,
    *,
    text: str,
    published_date: str | None = None,
    revision: str | None = None,
) -> Citation:
    """Mutates citation.metadata in-place with the 4 provenance keys.

    Idempotent: re-stamping con el mismo texto no cambia content_hash.
    """

def stamp_finding_text(finding: Finding) -> Finding:
    """Conveniencia: usa finding.excerpt como text si no se pasa explícito."""
```

**Puntos de integración en el monorepo** (cambios mínimos):

| Sitio | Cambio | Esfuerzo |
|---|---|---|
| `jw_core.wol_client.WOLClient.get_article` | después de parse, stamp citation con `accessed_at=now()`, `published_date=parsed.date`, hash sobre `parsed.body_text` | ~10 líneas |
| `jw_core.wol_client.WOLClient.get_bible_chapter` | igual, `revision` se rellena con el código NWT del manifest | ~10 líneas |
| `jw_rag.indexers.jwpub` | al indexar pasajes, propagar `published_date` desde JWPUB metadata; hash sobre el chunk de texto | ~5 líneas |
| `jw_agents.*` | sin cambios — los parsers ya stampean | 0 |

## Integración con Fase 39 (NLI re-run)

Cuando `ProvenanceValidator.check(citation)` devuelve `status="changed"` y existe `nli_provider`:

1. El validator re-fetcha el texto actual (ya lo tiene del paso anterior).
2. Extrae el premise actual (texto canónico del passage).
3. Recupera el `claim` original — convención: `citation.metadata["nli_claim"]` (escrito por Fase 39 al original wrap). Si no está, no re-run.
4. Llama `nli_provider.evaluate_entailment(claim, premise_now)`.
5. Compara con `citation.metadata["nli_verdict"]` original. Si pasa de `entails` a otra cosa → `verdict.nli_rerun = {"changed": True, "from": "entails", "to": "neutral", "score": 0.42}`.

Esto crea el **bucle de fidelidad en runtime** completo: cambio de contenido detectado → revalidación semántica automática.

## CLI

`jw provenance check` — nuevo subcomando en `jw-cli`:

```
jw provenance check --agent-output result.json
jw provenance check --agent-output result.json --since 2026-01-01
jw provenance check --agent-output result.json --with-nli   # requiere Fase 39 setup
jw provenance check --agent-output result.json --report md --out drift.md
jw provenance stamp --finding finding.json                  # one-off stamp utility
```

Inputs aceptados: archivo JSON con shape `AgentResult.to_dict()` o un dict embebido en stdin.

Outputs: `ProvenanceReport` serializado (JSON por default; markdown legible con `--report md`).

Exit codes: `0` cuando todo `match`, `2` cuando hay ≥1 `changed`, `3` para errores de fetcher.

## MCP

Nueva herramienta en `jw-mcp`:

```python
@mcp.tool()
async def verify_provenance(
    agent_output: dict,
    since: str | None = None,
    with_nli: bool = False,
) -> dict:
    """Re-check that each citation's content_hash still matches the live page.
    Returns a ProvenanceReport dict."""
```

Documentación del tool deja claro que **requiere red** y respeta el throttle del WOLClient inyectado.

## Telemetría — relación con Fase 9

Cuando `provenance_check` devuelve `changed`, lo registramos como **un nuevo tipo de drift event** en `jw_core.telemetry`:

```python
telemetry.record_event("provenance_drift", {
    "url": verdict.url,
    "delta_chars": verdict.delta_chars,
    "original_accessed_at": verdict.accessed_at_original,
    "ts": time.time(),
})
```

Esto deja una traza local opt-in del envejecimiento del corpus, paralela al drift de shape de API que Fase 9 ya captura. No envía nada — `JW_TELEMETRY_ENABLED` sigue siendo el switch.

## Reglas duras de diseño

1. **No red en tests**: `ProvenanceValidator` recibe fetcher inyectado. Tests usan `FakeFetcher(canned_responses={url: body})`. CI público nunca toca jw.org.
2. **Multi-idioma**: `published_date` y `revision` son strings opacos — funcionan idénticos en en/es/pt. Los textos de error y las descripciones CLI/MCP se traducen vía el mismo sistema i18n que el resto del CLI.
3. **Spanish prose, English identifiers**: este spec lo respeta; nombres de clases/funciones/módulos en inglés (`ProvenanceValidator`, `check_since`, `canonicalize_text`), prosa explicativa en español.
4. **Backwards compatible**: ningún test existente cambia porque `Citation.metadata` ya acepta cualquier dict. Las nuevas claves son opcionales para leer; el validador degrada a `status="no_record"` cuando faltan.
5. **No extras**: Fase 40 reusa el `httpx` ya presente para Fase 23. Cero nuevas deps en `pyproject.toml`. Pydantic ya está. Hatchling/Python 3.13/GPL-3.0 sin cambios.

## Modelos de tests (semilla)

`packages/jw-core/tests/test_provenance/`:

- `test_models.py` — round-trip `ProvenanceRecord.from_citation_metadata` ↔ dict.
- `test_hashing.py` — `canonicalize_text` idempotente; mismas reglas en ASCII y unicode (NFC). Cambio cosmético (doble espacio) no cambia hash; cambio real (palabra distinta) sí.
- `test_validator.py` — con `FakeFetcher`: caso `match`, caso `changed` (hash distinto), caso `unreachable` (fetcher tira excepción), caso `no_record` (citation sin `content_hash`), caso `since` filtra correctamente por fecha.
- `test_validator_nli.py` — fake `NLIProvider` retorna `entails` antes y `neutral` después → `nli_rerun.changed=True`.
- `test_propagation.py` — `stamp_citation` es idempotente sobre el mismo texto; mismos campos preservados; distinto texto → distinto hash.
- `test_cli.py` — `jw provenance check` con fixture JSON local, exit codes correctos.

Tres golden cases nuevos en `jw-eval/fixtures/golden_qa/l2/` ejercen la integración: un mismo URL con hash original vs HTML modificado en el snapshot disparan `changed`.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Ruido por cambios cosméticos (whitespace, html re-pretty) | `canonicalize_text` colapsa whitespace antes del hash |
| 2 | Falsos `changed` cuando WOL re-deploya HTML idéntico con `<meta>` distinto | extractor convierte a texto plano antes del hash; HTML structure se ignora |
| 3 | Costos de re-fetch en MCP | `since` filtra por fecha; concurrency=4 igual que Fase 23; respeta throttle |
| 4 | Texto largo → hash colisión | sha256, riesgo despreciable |
| 5 | Cita sin `content_hash` en agentes legacy | verdict `no_record`, no error — backwards compat |
| 6 | Re-NLI duplica costo cuando muchas changed | Re-NLI solo cuando `nli_provider` se pasa explícito; CLI flag `--with-nli` opcional |
| 7 | `published_date` ausente en WOL HTML | Campo es `str | None`; ausencia no rompe nada |
| 8 | Revisión NWT cambia citas masivamente al alinear con `rev. 2023` | Operativo: una sola corrida `jw provenance check --since 2023-01-01` muestra todo lo afectado en un reporte. No es bug, es feature |

## Métricas de éxito

- ✅ 100% de las `Citation` emitidas por `WOLClient` y `JWPUB` ingest llevan los 4 campos.
- ✅ `provenance_check` con `FakeFetcher` detecta correctamente `match` / `changed` / `unreachable` / `no_record` en tests.
- ✅ `jw provenance check --since 2026-01-01 --report md` produce reporte legible.
- ✅ Integración con Fase 39: cuando `nli_provider` está activo y un hash cambia, el reporte muestra el delta de verdict NLI.
- ✅ Telemetría opt-in registra `provenance_drift` events distinguibles de los drift events existentes.
- ✅ Cero regresiones en los 1984+ tests existentes.
- ✅ Sin nuevas deps en `pyproject.toml` (reusa `httpx` + `pydantic`).

## Cómo verificar al cerrar

```bash
uv sync --all-packages

# Tests del módulo aislado
.venv/bin/python -m pytest packages/jw-core/tests/test_provenance -v

# Smoke CLI con archivo de fixtures
uv run jw provenance check \
    --agent-output packages/jw-core/tests/fixtures/agent_results/apologetics_trinity.json \
    --report md

# Integración con Fase 39 (requiere NLI configurado)
JW_NLI_PROVIDER=deberta uv run jw provenance check \
    --agent-output result.json --with-nli

# MCP
.venv/bin/python -m pytest packages/jw-mcp/tests/test_provenance_tool.py
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-40-content-provenance-plan.md` (a escribir tras aprobar este spec).

1. Scaffold `packages/jw-core/src/jw_core/provenance/` + tests vacíos.
2. `hashing.py` + `models.py` con tests determinísticos.
3. `validator.py` con `FakeFetcher` — sin red.
4. `propagation.py` + integración en `WOLClient.get_article` / `get_bible_chapter`.
5. Integración con `jw_rag.indexers.jwpub`.
6. CLI `jw provenance check` + reporte md/JSON.
7. MCP tool `verify_provenance`.
8. Hook con Fase 39 — re-NLI cuando `nli_provider` está disponible.
9. Telemetría `provenance_drift` events.
10. 3 golden cases L2 en `jw-eval/fixtures/` que ejercen el flujo completo.
11. Guía en `docs/guias/content-provenance.md` + audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones.
