# Fase 25 — Monitor de novedades jw.org (`news_monitor`)

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (alto valor recurrente)
> **Tamaño**: M (~4-5 días)
> **Depende de**: ninguna fase bloqueante. Se beneficia de Fase 22 (eval) y Fase 23 (citation validator) para protección, pero no las requiere.
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

jw.org publica continuamente: nuevos números de Atalaya, libros, folletos, videos de JW Broadcasting y los workbooks mensuales (`mwb`, `w`). Hoy el usuario tiene que entrar manualmente a jw.org / tv.jw.org / WOL para enterarse de qué cambió. El toolkit ya tiene los **tres clientes** necesarios (`MediatorClient`, `PubMediaClient`, `JWBroadcastingClient`) y el **scraper de workbook** (Fase 11), pero nadie los compone en un único "qué hay nuevo desde la última vez".

Fase 25 cierra ese hueco. Un comando `jw news digest` que:

1. Consulta los **tres canales** (publicaciones, broadcasting, programas mensuales).
2. Diffea contra una snapshot local de lo que ya se vio (`news_seen.db`).
3. Imprime un digest markdown deterministista agrupado por idioma y canal.

Sin daemon, sin LLM en el camino crítico, sin red en tests, citas verificables a wol.jw.org / tv.jw.org en cada item.

## Objetivos (en orden de prioridad)

1. **Detección determinista de novedades**. Mismo estado de `news_seen.db` + misma respuesta API ⇒ digest byte-idéntico.
2. **Citas verificables**. Cada item en el digest tiene URL canónica resoluble por el usuario.
3. **Local-first, sin tracking**. La snapshot vive en `~/.jw-agent-toolkit/news_seen.db`. Nada se envía a ninguna parte.
4. **Multilenguaje**. en/es/pt mínimo; el digest agrupa por idioma; el usuario filtra con `--languages`.
5. **Composable**. El builder de digest es puro (sources inyectables) — tests con stubs, MCP tool con clientes reales.

## No-objetivos (boundaries vinculantes)

- **No daemon, no servicio en background.** Documentamos una entrada cron de ejemplo en la guía, pero el toolkit nunca instala nada automático.
- **No reescribe `pub_media` / `mediator` / `broadcasting`.** Solo los compone. Si alguno carece de un método (`list_recent_publications`), se añade en su módulo, no en `news`.
- **No descarga binarios (PDF/EPUB/MP4).** Solo metadata. La descarga ya la cubre `pub_media.download()` / `broadcasting_ingest`.
- **No notifica externamente** (no Slack, no email, no push). Solo escribe a stdout / archivo.
- **No reemplaza la telemetría drift** (Fase 9). Esa detecta cambios en la *forma* de la API; ésta detecta cambios en el *catálogo* de contenido.
- **No predice futuros workbooks.** Si el `mwb` del próximo mes aún no está publicado, no aparece — la fuente es la respuesta real del API.

## Arquitectura

Tres carpetas tocadas:

```
packages/jw-core/src/jw_core/news/         (nuevo)
├── __init__.py
├── store.py          # SeenStore — SQLite (channel, item_id, first_seen, ...)
├── sources.py        # NewsSource protocol + 3 implementaciones
└── digest.py         # build_digest(sources, store, since) → DigestReport (markdown)

packages/jw-agents/src/jw_agents/
└── news_monitor.py   # thin wrapper que cablea sources reales para CLI/MCP

packages/jw-cli/src/jw_cli/commands/
└── news.py           # `jw news digest`

packages/jw-mcp/src/jw_mcp/
└── server.py         # registra `news_digest(...)` tool
```

### Reglas duras

1. `news.store`, `news.sources` y `news.digest` **no se importan entre sí** vía side-effects de import — son módulos planos sin globals.
2. `NewsSource` es un Protocol async: `async def fetch(self, *, languages, since) -> list[NewsItem]`. Cualquier implementación lo cumple.
3. El digest builder es **síncrono** sobre `list[NewsItem]` ya recolectados. La concurrencia (asyncio.gather) vive en `news_monitor.py`, no en `digest.py`.
4. Tests del store + digest builder **no tocan red** — sólo SQLite local y stubs.
5. El store se inicializa lazy en `~/.jw-agent-toolkit/news_seen.db`. Misma carpeta que `cache.DiskCache` (consistencia).

### Diagrama de flujo

```
                     ┌──────────────────┐
   jw news digest →  │ news_monitor.py  │ ── cablea ──┐
                     └────────┬─────────┘             │
                              │                       ▼
                              │             ┌───────────────────┐
                              │             │   3 NewsSource    │
                              │             │ ─ publications    │
                              │             │ ─ broadcasting    │
                              │             │ ─ programs        │
                              │             └─────────┬─────────┘
                              │   asyncio.gather      │
                              ▼                       ▼
                       ┌──────────────┐       list[NewsItem]
                       │   SeenStore  │ ◄────────────┐
                       │ (SQLite)     │   diff       │
                       └──────┬───────┘              │
                              │                      │
                              ▼                      │
                       ┌──────────────┐              │
                       │ build_digest │ ◄────────────┘
                       └──────┬───────┘
                              ▼
                       Markdown digest
```

## Tres canales

### Canal 1 — Publicaciones (`PublicationsSource`)

**Qué detecta**: cuando aparece un nuevo `item_code` en el catálogo del `MediatorClient.find_item` para un conjunto de códigos seed (Atalaya pública `wp`, Atalaya de estudio `w`, ¡Despertad! `g`, libros recientes `lff`/`bhs`, brochures `ed`/`fg`/...).

**Por qué no usa "list_recent"**: el mediator endpoint **no expone una lista cronológica**. Tiene `finder?item=...`. La estrategia es:

1. Seed list de pub codes mantenida en `news/seeds.py` (hardcoded, ~40 entradas que cubren las publicaciones activas).
2. Para cada combinación `(pub_code, language)` consultar `pub_media.get_publication(pub_code, language)`.
3. Cada `PubMediaFile` con `file_format in {EPUB, JWPUB, PDF}` se convierte en un `NewsItem` con `item_id = f"{pub_code}_{language}_{issue or 'NA'}"`.

**Item ID estable**: para magazines uses `pub_code + "_" + lang + "_" + str(issue_yyyymm)`. Para libros (sin issue) usa `pub_code + "_" + lang`. Para publicaciones que vuelven a publicarse en una nueva edición el `pub_code` cambia → otro item.

**Cache TTL del cliente**: 6h (justificación: el catálogo de publicaciones cambia lento — mediator devuelve issues nuevas con latencia de horas, pero el usuario quiere correr `jw news digest` varias veces al día sin re-fetch innecesario).

### Canal 2 — JW Broadcasting (`BroadcastingSource`)

**Qué detecta**: nuevos videos en categorías raíz watcheadas (`VideoOnDemand` y sus inmediatas hijas — por defecto `LatestVideos` cuando exista, fallback a `VideoOnDemand` con `max_depth=1` y `limit=200`).

**Item ID**: `video.guid` (estable a través de re-publicaciones; campo del API).

**Cache TTL del cliente**: 24h (justificación: la lista de "últimos videos" se actualiza diaria. Si el usuario quiere "ahora", puede pasar `--no-cache`).

**Reutilización**: `JWBroadcastingClient.discover_all_videos(language=..., root="VideoOnDemand", max_depth=1, limit=200)` ya existe.

### Canal 3 — Programa mensual (`ProgramsSource`)

**Qué detecta**: la aparición de los nuevos workbook (`mwb_E_YYYYMM.epub`) y Watchtower study (`w_E_YYYYMM.epub`) cada mes.

**Item ID**:
- Workbook: `f"mwb{YY}.{MM}"` (p.ej. `mwb26.07`).
- Watchtower estudio: `f"w{YY}.{MM}"`.

**Cómo se detecta sin scrapear**: igual que el flujo live-verified de `workbook_helper`:

```
PubMediaClient.get_publication(pub_code="mwb", language="E", issue=202607)
```

Si `Publication.files` no está vacío ⇒ ese workbook existe y es un item; en caso contrario no aparece.

**Cache TTL del cliente**: 7 días (justificación: el `mwb`/`w` de un mes determinado se publica una vez y nunca cambia; sólo aparecen items *nuevos* a fin de mes. Una semana de cache evita pegarle al endpoint redundantemente).

**Ventana**: se consulta `[mes_actual, mes_actual + 2)` para no perder un workbook recién publicado para el próximo mes.

## Cadencia y modos de ejecución

**Solo on-demand**. Tres formas de invocar:

```bash
# Desde el último run registrado (más común)
jw news digest --since=last_run

# Desde una fecha ISO concreta
jw news digest --since=2026-05-23

# Forzar redescubrimiento total (ignora seen-store, no escribe)
jw news digest --since=epoch --no-update
```

**Cron opcional documentado** (en la guía, no shipped):

```cron
# Lunes 07:00 — digest semanal a stdout, salvado a ~/Documents/jw-news/
0 7 * * MON  /usr/local/bin/jw news digest --since=last_run --out ~/Documents/jw-news/$(date +\%F).md
```

El toolkit jamás instala esa entrada automáticamente.

## Modelos (`news/__init__.py`)

```python
class NewsItem(BaseModel):
    channel: Literal["publications", "broadcasting", "programs"]
    item_id: str
    title: str
    language: str
    url: str
    description: str = ""
    first_published: datetime | None = None   # del API si está
    metadata: dict[str, Any] = Field(default_factory=dict)

class SeenRecord(BaseModel):
    channel: str
    item_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

class DigestReport(BaseModel):
    generated_at: datetime
    since: datetime | None
    languages: list[str]
    channels: list[str]
    new_items: list[NewsItem]
    retired_items: list[SeenRecord]      # presentes en store, ausentes en respuesta actual
    markdown: str                         # texto renderizado, byte-estable

    def stats(self) -> dict[str, int]:
        return {
            "new": len(self.new_items),
            "retired": len(self.retired_items),
            "by_channel:publications": sum(1 for i in self.new_items if i.channel == "publications"),
            "by_channel:broadcasting": sum(1 for i in self.new_items if i.channel == "broadcasting"),
            "by_channel:programs": sum(1 for i in self.new_items if i.channel == "programs"),
        }
```

## Store local (`news/store.py`)

SQLite con una sola tabla:

```sql
CREATE TABLE IF NOT EXISTS news_seen (
    channel TEXT NOT NULL,
    item_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (channel, item_id)
);
CREATE INDEX IF NOT EXISTS idx_news_seen_last_seen ON news_seen(last_seen_at);

-- Single-row tabla auxiliar para `--since=last_run`.
CREATE TABLE IF NOT EXISTS news_runs (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT NOT NULL
);
```

API mínima:

```python
class SeenStore:
    def __init__(self, path: Path | str | None = None) -> None: ...
    def is_seen(self, channel: str, item_id: str) -> bool: ...
    def mark_seen(self, item: NewsItem, *, now: datetime | None = None) -> None: ...
    def all_seen(self, channel: str | None = None) -> list[SeenRecord]: ...
    def last_run_at(self) -> datetime | None: ...
    def set_last_run_at(self, when: datetime) -> None: ...
    def close(self) -> None: ...
```

Decisiones:

- Path default `~/.jw-agent-toolkit/news_seen.db`. Override por env `JW_NEWS_SEEN_DB`.
- `datetime` se persisten como ISO-8601 UTC (`isoformat()`); leídos con `fromisoformat`.
- `metadata` se persiste como `json.dumps(separators=(",", ":"), sort_keys=True)` → byte-estable.
- WAL mode (igual que `DiskCache`).

## Diff y digest (`news/digest.py`)

Algoritmo determinista:

```python
async def collect_items(sources, *, languages, since) -> list[NewsItem]:
    # asyncio.gather sobre source.fetch(...) — preserva orden por (channel, language, item_id)

def diff_against_store(items, store) -> tuple[list[NewsItem], list[SeenRecord]]:
    new = [i for i in items if not store.is_seen(i.channel, i.item_id)]
    current_keys = {(i.channel, i.item_id) for i in items}
    retired = [r for r in store.all_seen() if (r.channel, r.item_id) not in current_keys]
    return new, retired

def render_markdown(new_items, retired, *, generated_at, since, languages, channels) -> str:
    # Agrupa por language → channel; cada item: "- [{title}]({url}) — {first_published} {description}"
    # Sección "Retired (log-only)" si len(retired) > 0.
```

**Determinismo**:

1. `items` se sortean por `(language, channel, item_id)` antes de diffear.
2. `retired` se sortea por `(channel, item_id)`.
3. Cada section markdown tiene **header fijo** y **listado ordenado**.
4. `generated_at` aparece en la primera línea (variable) — pero los items mismos son idénticos a igual input.

## Formato del digest (markdown)

```markdown
# JW News Digest

- Generado: 2026-05-30T08:14:00+00:00
- Ventana: desde 2026-05-23T00:00:00+00:00 (last_run)
- Idiomas: en, es
- Canales: publications, broadcasting, programs
- Nuevos: 4 · Retirados: 0

## 🇬🇧 English

### Publications
- [The Watchtower — June 2026 (Study)](https://b.jw-cdn.org/...w_E_202606.epub) — Issue 202606. EPUB.

### Broadcasting
- [What Will Tomorrow Bring? (15 min)](https://tv.jw.org/...) — Published 2026-05-28.

### Programs
- [Meeting Workbook July 2026 — mwb26.07](https://b.jw-cdn.org/...mwb_E_202607.epub)

## 🇪🇸 Español

### Publications
- [La Atalaya — Junio 2026 (estudio)](https://...) — Edición 202606. EPUB.

---

## Retired (log-only)
- (none)
```

Cada item lleva su URL canónica (cumple "citas verificables").

## Filtros CLI

```
jw news digest [OPTIONS]

  --since TEXT         "last_run" (default) | ISO date | "epoch"
  --languages TEXT     CSV. Default "en,es,pt"
  --channels TEXT      CSV de {publications,broadcasting,programs}. Default todos.
  --out PATH           Si se da, escribe a archivo además de stdout.
  --no-update          No marca seen ni avanza last_run (modo "dry").
  --format TEXT        "md" (default) | "json"
  --json               Atajo para --format=json.
  --verbose / -v       Logging DEBUG.
```

## Tool MCP

```python
@mcp.tool
async def news_digest(
    since: str | None = None,             # "last_run" | ISO date | None ≡ "last_run"
    languages: list[str] | None = None,   # default ["en", "es", "pt"]
    channels: list[str] | None = None,    # default ["publications", "broadcasting", "programs"]
    update: bool = True,                  # marca seen + actualiza last_run
) -> dict[str, Any]:
    """Genera digest de novedades jw.org desde last_run / fecha dada."""
```

Devuelve `DigestReport.model_dump()` con `markdown` ya renderizado para que el cliente LLM lo pase verbatim.

## Eval golden cases (Fase 22)

Política de la Fase 22: cada Fase nueva añade ≥3 cases. Para Fase 25 añadimos uno L1 mínimo:

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/news_monitor_digest_en.yaml
id: l1_news_monitor_digest_en
agent: news_monitor
layer: l1
input:
  since: epoch
  languages: [en]
  channels: [publications]
  # Stub sources via dependency injection in the eval shim — see eval/agent_adapters.py
expected:
  min_findings: 1
  must_have_source: news_monitor
  must_have_citation: true
metadata:
  topic: news.publications
  added_at: 2026-05-30
```

(El adapter en `jw-eval` cablea `news_monitor` con fuentes stub deterministas; sin red.)

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Falsos positivos: API devuelve item nuevo que ya existía con otro ID | `item_id` para magazines incluye `pub_code + lang + issue` → estable. Para broadcasting se usa GUID estable del API. Para programs se usa `mwb{YY}.{MM}` → único. |
| 2 | `pub_media` falla parcialmente (un pub_code da 404) | Source captura `PubMediaError` por item y añade warning al digest sin abortar. |
| 3 | Spam de digest si la primera ejecución usa store vacío | Documentar y proveer `--since=2026-05-30` para "marcar todo como visto sin imprimir". También: la primera corrida emite warning explícito y sugiere `--no-update` para preview. |
| 4 | Seed list de pub_codes envejece (publicaciones discontinuadas → 404) | Mantenida en `news/seeds.py` con audit anual. Items que dan 404 se loguean a `result.warnings`, no rompen el digest. |
| 5 | Cron del usuario corre 12 veces/día y satura jw.org | Cache TTL razonable (6h/24h/7d) en clientes + token bucket existente. Si aún así satura, doc recomienda intervalo mínimo de 1h. |
| 6 | Multilenguaje explota el número de requests | `languages` lo controla. Default `en,es,pt` = 3 idiomas. Cache hace que la segunda corrida del día sea casi gratis. |
| 7 | Store crece sin límite | `news_seen.db` ~ 1KB/row × ~10k items = 10MB en 10 años. Aceptable. Sin GC programado. |
| 8 | Retired items confunden al usuario | Aparecen en sección separada con header "log-only — does not require action". |

## Métricas de éxito

- ✅ `jw news digest --since=epoch --languages=en --channels=programs` completa en <10s sin red (cache caliente).
- ✅ Mismo store + mismo cache de clientes ⇒ misma salida byte-a-byte (excepto la línea `Generado:`).
- ✅ Tests unitarios completos con stubs, sin red.
- ✅ 1 case L1 en `jw-eval`.
- ✅ Guía `docs/guias/monitor-de-novedades.md`.
- ✅ Tool MCP `news_digest` accesible vía Claude Desktop.

## Lo que NO está en esta fase

- Notificación push / email / Slack → cualquier integración exterior es del consumidor.
- Resumen LLM del digest → fuera del toolkit. El cliente que reciba el `DigestReport.markdown` puede pedirle a Claude que lo resuma.
- Detección de cambios *dentro* de un artículo ya visto (link rot) → eso es Fase 23.
- Watch list por tema (avisarme cuando publiquen sobre "ansiedad") → Fase 32 territory.

## Cómo verificar al cerrar

```bash
# 1. Install
uv sync --all-packages

# 2. Tests
.venv/bin/python -m pytest packages/jw-core/tests/test_news_store.py \
                            packages/jw-core/tests/test_news_sources.py \
                            packages/jw-core/tests/test_news_digest.py -v

# 3. CLI (primera corrida marca todo como visto)
uv run jw news digest --since=epoch --languages=en --channels=programs --out /tmp/digest.md

# 4. Segunda corrida — debe imprimir 0 nuevos
uv run jw news digest --since=last_run --languages=en --channels=programs

# 5. MCP smoke
uv run jw-mcp # luego desde Claude Desktop: news_digest(since="epoch", channels=["programs"])
```

## Plan de implementación

Spec hijo: [`docs/superpowers/plans/2026-05-30-fase-25-news-monitor-plan.md`](../plans/2026-05-30-fase-25-news-monitor-plan.md).
