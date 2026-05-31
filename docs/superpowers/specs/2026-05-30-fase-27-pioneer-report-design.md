# Fase 27 — Informe mensual de precursor (`field_report`)

> **Fecha**: 2026-05-30
> **Estado**: Diseño (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (especializado pero único)
> **Tamaño estimado**: S (~2-3 días)
> **Depende de**: ninguna fase. Lee (read-only) de `RevisitTracker` (Fase 12) y reutiliza `FieldEncryptor` (Fase 11).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

Los precursores —regulares, auxiliares y especiales— deben entregar un informe mensual a la congregación con tres cifras: **horas**, **cursos bíblicos activos** y, opcionalmente para uso personal, **revisitas realizadas**. Hoy ese conteo se lleva en libretas, apps de terceros (con privacidad cuestionable) o planillas ad hoc. El toolkit ya tiene la pieza más sensible — `RevisitTracker` (Fase 12) — pero **no agrega ni resume nada**.

Fase 27 cierra ese hueco con un módulo `jw_core.ministry.field_report` que:

1. Persiste horas y cursos en SQLite **cifrable**, totalmente local.
2. Lee revisitas del store de Fase 12 **sin escribirlo** (single source of truth).
3. Produce el informe mensual en **markdown**, **csv** y opcionalmente **PDF**.
4. Expone CLI (`jw report --month 2026-05`) y tres herramientas MCP.

> **Alcance explícito**: precursores. La organización JW simplificó el informe del publicador medio a "participación" (sí/no). No modelamos publicadores aquí — agregar más adelante una bandera `participation_only` si se justifica.

## Objetivos (en orden de prioridad)

1. **Capturar de forma frictionless** (un comando o una llamada MCP) horas + curso + reunión sin abrir SQLite a mano.
2. **Agregar correctamente** según convenciones JW vigentes (ver decisiones clave abajo).
3. **Cifrar por defecto** las columnas con PII (`note`, `student_id`); cifrado opt-out documentado pero **no** opt-in.
4. **Exportar** a markdown (siempre), csv (siempre) y PDF (extra `[pdf]`).
5. **Cero red**, cero LLM, 100% determinismo en el camino crítico.

## No-objetivos (boundaries vinculantes)

- **No** servicio de congregación: este módulo es **uso personal del precursor**. No exporta a S-21 oficial ni a hub centralizado.
- **No** identidad real del estudiante en cleartext: `student_id` es un alias arbitrario que el usuario decide (`john`, `interest_42`); se cifra de todas formas.
- **No** modificar `RevisitTracker`: se accede como provider inyectable, sin escrituras.
- **No** notificaciones push, recordatorios ni "gamificación".
- **No** integración con apps Watchtower oficiales — eso es scope legal/política JW fuera de este toolkit.
- **No** publicador-mode (publicadores entregan participación, no cifras).

## Arquitectura

Módulo nuevo dentro de `packages/jw-core/`, accesible para CLI y MCP. Diagrama de dependencias:

```
jw-cli (commands/report.py)
   ├─► jw_core.ministry.field_report   (store + aggregator)
   ├─► jw_core.ministry.exporters       (md/csv/pdf)
   └─► RevisitProviderAdapter           (envuelve RevisitStore en read-only)

jw-mcp (field_log_hours / field_log_study / field_monthly_report)
   └─► idem.

field_report
   ├─► jw_core.data.field_service_tags     (vocabulario)
   ├─► jw_core.privacy.encryption          (FieldEncryptor)
   └─► RevisitProvider (Protocol)
            ▲
            │ default impl
   jw_agents.revisit_tracker.RevisitStore    (read-only adapter en jw-cli)
```

### File map

Nuevos:

- `packages/jw-core/src/jw_core/data/field_service_tags.py` — vocabulario controlado.
- `packages/jw-core/src/jw_core/ministry/__init__.py` — paquete.
- `packages/jw-core/src/jw_core/ministry/field_report.py` — store + dataclasses + `MonthlyReport` aggregator + `RevisitProvider` Protocol.
- `packages/jw-core/src/jw_core/ministry/exporters.py` — `render_markdown`, `render_csv`, `render_pdf`.
- `packages/jw-core/src/jw_core/ministry/templates/monthly_report.html.j2` — template Jinja2 para PDF.
- `packages/jw-core/tests/test_field_report.py` — store + aggregator + exporters (fakes para revisitas).
- `packages/jw-cli/src/jw_cli/commands/report.py` — `jw report --month`.
- `docs/guias/informe-precursor.md` — guía de uso, opciones de cifrado, ejemplos.

Modifica:

- `packages/jw-core/pyproject.toml` — añadir `[project.optional-dependencies] pdf = ["weasyprint>=62", "jinja2>=3.1"]`.
- `packages/jw-cli/src/jw_cli/main.py` — registra `report` como subcomando.
- `packages/jw-mcp/src/jw_mcp/server.py` — registra `field_log_hours`, `field_log_study`, `field_monthly_report`.
- `docs/ROADMAP.md` — sección Fase 27.
- `docs/VISION_AUDIT.md` — fila Fase 27.

### Reglas duras de diseño

1. `field_report` **no** importa `jw_agents`. Si la CLI quiere pasar revisitas, instancia un adapter sobre `RevisitStore` y lo inyecta como `RevisitProvider`.
2. La DB vive en `~/.jw-agent-toolkit/field_service.db` (env override `JW_FIELD_DB`). Distinta DB que `ministry.db` (revisitas) para no entrelazar esquemas.
3. **Cifrado por defecto activo** cuando `JW_PRIVACY_KEY` está set; sin clave, log de warning y storage en cleartext (igual que el resto del toolkit). `JW_FIELD_DISABLE_ENCRYPTION=1` es escape hatch **documentado pero desincentivado**.
4. Sin red. Tests CPU-only.
5. Hatchling + src/ + Python 3.13 + GPL-3.0 (uniforme con el resto del monorepo).
6. Prosa de mensajes/labels en español; identificadores en inglés.

## Modelos (Pydantic v2)

```python
# packages/jw-core/src/jw_core/ministry/field_report.py
from datetime import date
from typing import Literal, Protocol
from pydantic import BaseModel, Field

ServiceTag = Literal[
    "street", "return_visit", "bible_study", "online",
    "phone", "cart", "letter", "other",
]

class HoursEntry(BaseModel):
    entry_id: str                          # uuid hex
    date: date                             # ISO date
    hours_decimal: float = Field(ge=0, le=24)  # 1.25 == 1h 15min
    tag: ServiceTag | None = None
    note: str = ""                         # ciphered at rest
    created_at_unix: float = 0.0

class StudyEntry(BaseModel):
    study_id: str                          # uuid hex
    student_id: str                        # alias chosen by user, ciphered
    started_at: date
    closed_at: date | None = None
    met_dates: list[date] = Field(default_factory=list)
    note: str = ""                         # ciphered

class MonthlyReport(BaseModel):
    month: str                             # "2026-05"
    total_hours: float                     # raw sum, full precision
    total_hours_display: str               # "37h 25min" (5-min rounded)
    breakdown_by_tag: dict[str, float]     # keys: ServiceTag values + "untagged"
    active_studies_max: int                # see decisions
    active_studies_ids: list[str]
    revisits_count: int                    # from injected provider
    entries_count: int                     # raw HoursEntry count
    days_with_service: int

class RevisitProvider(Protocol):
    def count_in_range(self, start: date, end: date) -> int: ...
```

## Decisiones clave (justificadas)

| Decisión | Justificación |
|---|---|
| **Horas como float decimal** (1.25 == 1h 15min) | Compatibilidad SQLite REAL, suma sin overflow, conversión a "Xh Ymin" en exporters. |
| **Display redondeado a 5 min** | Práctica JW vigente: el informe se entrega en incrementos de 5min/quart-hour. Redondeo `ROUND_HALF_UP` aplicado solo al display agregado, NUNCA al storage. |
| **Vocabulario `street, return_visit, bible_study, online, phone, cart, letter, other`** | Cubre formas modernas (testimonio público + cart + cartas + teléfono + online) sin convertirse en taxonomía oficial. |
| **Override de vocabulario** en `~/.jw-agent-toolkit/field_service_tags_local.json` | Permite añadir tags locales (`hospital`, `prison`) sin tocar el repo. JSON simple: `{"add": ["hospital"], "remove": []}`. |
| **Estudio activo = `started_at <= month_end AND (closed_at IS NULL OR closed_at > month_start)`** | Estándar conservador: un estudio empezado en abril y cerrado el 3 de mayo cuenta en mayo. |
| **Cantidad reportada = `max(active_studies during the month)`** | Es la convención JW moderna: durante el mes pudo haber 5 estudios pero al cierre 3. Se reporta el pico para no penalizar cierres mediados del mes. Documentado al usuario para transparencia. |
| **`revisits_count` viene de provider inyectable** | Acoplamiento débil. Tests no necesitan importar `jw_agents`. CLI sí lo conecta. |
| **PDF opt-in vía extra `[pdf]`** | Evita imponer `weasyprint` (~ 20 MB de Pango/cairo) a usuarios que solo quieren markdown. |
| **DB separada de revisitas** | Schema/encryption keys distintas; opcional borrar campo de actividad sin perder revisitas. |
| **No autoexport S-21** | Boundary con consejería oficial — el formato S-21 lo entrega el precursor, esta herramienta solo ayuda a llenar los huecos. |

## Privacy section

### Threat model

- Adversario realista: alguien con acceso físico al disco (laptop perdida, backup en la nube comprometido).
- **No** modela: rootkit, captura de memoria, RAM inspection.
- Objetivo: nadie con acceso casual al archivo `.db` puede leer notas, alias de estudiantes o desglose por tag.

### Columnas cifradas (Fernet 128-bit AES-CBC + HMAC-SHA256 vía `FieldEncryptor`)

| Tabla | Columna cleartext | Columna cifrada |
|---|---|---|
| `hours_entries` | `entry_id`, `date`, `hours_decimal`, `tag`, `created_at_unix` | `note` |
| `studies` | `study_id`, `started_at`, `closed_at`, `created_at_unix` | `student_id`, `note` |
| `studies_meetings` | `study_id` (FK), `met_date` | — |

Las columnas planas son necesarias para queries por mes/tag/fecha (no podemos cifrar `date`). El alias del estudiante y las notas — sí.

### Passphrase flow

`FieldEncryptor` reutiliza `JW_PRIVACY_KEY` (ya existente desde Fase 11). En la primera ejecución de `jw report` que vaya a escribir, si la variable no está set y el usuario no usó `--no-encryption`:

```
$ jw report log-hours ...
[!] Cifrado deshabilitado (no se encontró JW_PRIVACY_KEY).
    Tus notas y alias se guardarán en cleartext en
    ~/.jw-agent-toolkit/field_service.db.
    Para habilitarlo:
        export JW_PRIVACY_KEY=$(jw keygen)
    Para silenciar este aviso:
        export JW_FIELD_DISABLE_ENCRYPTION=1
```

(`jw keygen` ya existe desde Fase 11.) El flujo es **passive**: ningún prompt interactivo, ningún wallet propio. La filosofía es "tu shell, tu gestor de credenciales".

### Opt-out env var

`JW_FIELD_DISABLE_ENCRYPTION=1` **suprime el warning** pero no fuerza nada — el comportamiento sigue siendo "cifra si hay clave, cleartext si no". Documentado como "úsalo solo si entiendes que las notas quedan legibles en disco".

### Lo que NO se cifra

- `hours_decimal`, `tag`, `date`: necesarios para agregación con SQL `SUM`/`GROUP BY`. El **valor agregado** ya filtra individualidad (`SUM(hours_decimal) WHERE strftime('%Y-%m', date)=?`).
- `met_dates`: timestamps. Útiles para mostrar racha; no contienen PII más allá del calendario.

### Disclosure

Guía `docs/guias/informe-precursor.md` explica esto en la primera sección con framing "tus notas son tuyas; el cifrado se activa con una clave que tú generas y guardas tú".

## Integración con el resto del toolkit

### CLI (`jw-cli`)

```bash
# Registrar horas (acepta hoy por defecto)
jw report log-hours --hours 2.5 --tag street --note "trabajo en parque"
jw report log-hours --date 2026-05-15 --hours 2.5 --tag street

# Registrar/cerrar estudio
jw report log-study --student-alias maria --started 2026-04-01
jw report log-study --close --student-alias juan --closed 2026-05-12

# Marcar reunión hoy
jw report met-today --student-alias maria

# Generar informe (default markdown a stdout)
jw report --month 2026-05
jw report --month 2026-05 --format csv --out report.csv
jw report --month 2026-05 --format pdf --out report.pdf      # requires [pdf] extra

# Listar entradas del mes
jw report show --month 2026-05 --detail
```

### MCP (`jw-mcp`)

```python
@server.tool()
def field_log_hours(
    hours_decimal: float,
    date: str = "",                 # ISO; empty = today
    tag: str | None = None,
    note: str = "",
) -> dict[str, Any]: ...

@server.tool()
def field_log_study(
    student_alias: str,
    started: str = "",              # empty = today
    closed: str = "",
    met_today: bool = False,
    note: str = "",
) -> dict[str, Any]: ...

@server.tool()
def field_monthly_report(
    month: str,                     # "2026-05"
    include_revisits: bool = True,
    format: str = "json",           # "json" | "markdown" | "csv"
) -> dict[str, Any]: ...
```

### CI

- `pytest packages/jw-core/tests/test_field_report.py` corre con el resto de la suite.
- PDF test marca `pytest.importorskip("weasyprint")` para CI público sin Pango.
- Smoke: `uv run jw report --month 2026-05 --format md` corre con DB vacía y devuelve markdown válido.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Usuario malinterpreta "estudios activos = MAX" y subreporta | Sección dedicada en guía + footer en markdown report explicando el método de conteo |
| 2 | Cifrado pierde datos por clave perdida | `FieldEncryptor` ya lanza `EncryptionError` con mensaje claro; guía recomienda backup de la clave en gestor de contraseñas |
| 3 | Doble conteo de revisitas (entry tag=return_visit + provider) | El provider devuelve count separado; el reporte muestra ambas cifras (`hours_by_tag.return_visit` y `revisits_count`) en secciones distintas. Guía aclara la diferencia. |
| 4 | weasyprint pesado en CI | PDF como extra opcional. Tests skip cuando no está. |
| 5 | Hora 24+ por typo | `Pydantic ge=0, le=24` en `HoursEntry` rechaza. Validación en CLI antes de SQL. |
| 6 | Tags fuera del vocab | Pydantic `Literal` rechaza en el modelo; CLI sugiere `--tag other` con `--note`. |
| 7 | Mezclar zonas horarias en `date` | `date` es ISO local sin zona, normalizado en el set (no datetime). Documentado. |
| 8 | Race condition concurrente | SQLite `WAL` mode + `BEGIN IMMEDIATE` en escrituras. El uso esperado es single-process. |
| 9 | Privacidad post-export | El export queda en disco con el resto de archivos. Guía recomienda guardar en directorio cifrado del SO o borrar tras enviar. |
| 10 | Provider de revisitas falla (DB inexistente) | Adapter atrapa `OperationalError` y devuelve `0` + reason en el reporte; nunca crashea el report. |

## Métricas de éxito

- ✅ `jw report --month YYYY-MM` produce markdown legible en <100 ms con DB de <500 entradas.
- ✅ Todos los tests verdes; cobertura >= 95% para `field_report.py` y `exporters.py`.
- ✅ Cifrado por defecto cuando `JW_PRIVACY_KEY` está presente; verificado por test e2e.
- ✅ CSV importable a Excel/Google Sheets (UTF-8, comma-separator, encabezados en español).
- ✅ PDF opcional renderiza con tipografía limpia (no requiere imágenes embebidas).
- ✅ Guía `informe-precursor.md` con ejemplo "una semana en la vida de un precursor".

## Pendientes explícitos (post-Fase 27)

- **Reportes anuales / históricos** (`jw report --year 2026`) — fase futura si el usuario lo pide.
- **Backup cifrado de la DB** — depende de Fase 23 (citation validator) infraestructura de respaldo.
- **Sync entre dispositivos** — explícitamente fuera de scope (rompe local-first).
- **Modo publicador** (participación sí/no) — añadir si la organización lo formaliza más.
- **Integración con `study_conductor` (Fase 24)** para auto-marcar `met_today` desde la lección — bonito pero acoplamiento opcional; se hace en Fase 24 si conviene.

## Plan de implementación (alto nivel)

Plan hijo: [`2026-05-30-fase-27-pioneer-report-plan.md`](../plans/2026-05-30-fase-27-pioneer-report-plan.md).

Pasos cronológicos (orden TDD):

1. `data.field_service_tags` con vocab + override JSON.
2. `ministry.field_report` modelos Pydantic.
3. `FieldReportStore` SQLite con cifrado columnar; CRUD horas + estudios.
4. `RevisitProvider` Protocol + fake.
5. `MonthlyReport` aggregator (horas, estudios MAX, breakdown, days_with_service).
6. Exporter markdown con footer documentando MAX-rule.
7. Exporter CSV (csv stdlib, UTF-8).
8. Exporter PDF (Jinja2 + weasyprint, behind `[pdf]` extra).
9. CLI `report` subcomando + sub-sub (log-hours/log-study/met-today/show).
10. Adapter `RevisitProviderAdapter` sobre `RevisitStore` en jw-cli (read-only).
11. MCP tools `field_log_hours`, `field_log_study`, `field_monthly_report`.
12. Guía `docs/guias/informe-precursor.md`.
13. ROADMAP + VISION_AUDIT.
14. Audit completo y smoke.

Cada paso: test fallando → impl → test pasando → commit. Sin red. Sin LLM.

## Cómo verificar al cerrar

```bash
# 1. Instalar (con extra pdf opcional)
uv sync --all-packages
uv pip install -e 'packages/jw-core[pdf]'

# 2. Smoke
export JW_PRIVACY_KEY=$(jw keygen)
jw report log-hours --date 2026-05-15 --hours 2.5 --tag street --note "parque"
jw report log-study --student-alias maria --started 2026-05-01
jw report met-today --student-alias maria
jw report --month 2026-05                             # markdown a stdout
jw report --month 2026-05 --format csv --out /tmp/r.csv
jw report --month 2026-05 --format pdf --out /tmp/r.pdf

# 3. Tests
.venv/bin/python -m pytest packages/jw-core/tests/test_field_report.py -v

# 4. MCP smoke
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"field_monthly_report","arguments":{"month":"2026-05"}}}' | uv run jw-mcp
```
