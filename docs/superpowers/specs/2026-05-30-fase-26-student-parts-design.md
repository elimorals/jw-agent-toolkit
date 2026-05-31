# Fase 26 — `student_part_helper`: asistente de partes del estudiante (Vida y Ministerio)

> **Fecha**: 2026-05-30
> **Estado**: Diseño (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (especializado pero único)
> **Tamaño**: M (~4-5 días)
> **Depende de**: ninguna fase bloqueante. Se mide con Fase 22 (golden cases). Reutiliza Fase 11 (workbook scraper).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)
> **Punto de VISION**: #2 — Asistente de partes del estudiante V&M

## Motivación

Cada semana, los publicadores reciben asignaciones del Vida y Ministerio que requieren preparar un guion breve (3-5 min) ajustado al **punto de oratoria del mes**. El estudiante tiene que coordinar tres cosas a la vez: el tipo de asignación (lectura, conversación, revisita, demostración de estudio bíblico), el versículo o tema asignado, y el punto de oratoria activo en el folleto **Mejore su predicación** (`th`). Hoy el toolkit no tiene una herramienta dedicada que ensamble esas tres piezas en un script estructurado y verificable.

Fase 26 cubre ese hueco con un agente **procedural** (`student_part_helper`) que produce un guion plantillado, paramétrico, con citas resueltas vía `parsers.reference` y, cuando el usuario pide "esta semana", enriquecido con la salida del scraper del workbook (Fase 11). **Sin LLM en el camino**: el LLM downstream (Claude Desktop, etc.) reescribe la prosa.

## Objetivos (orden de prioridad)

1. **4 tipos de asignación** soportados con su pedagogía propia: `bible_reading`, `starting_conversation`, `return_visit`, `bible_study`.
2. **Hook al punto de oratoria del mes** — el guion aplica explícitamente el punto activo (controlled vocabulary de ~50 puntos del libro `th`).
3. **Tiempo objetivo como dato** — el script reporta `time_target_seconds`; ni recorta automáticamente ni se mete a optimizar.
4. **Citas verificables** — toda referencia bíblica resuelve a `BibleRef.wol_url()`.
5. **Multilenguaje** `en`/`es`/`pt` desde el día 1, con fallback elegante.
6. **Cero red en tests** — fixtures + templates locales; el cliente WOL solo se usa cuando el usuario pide "this week".

## No-objetivos (boundaries vinculantes)

- **No** generar la asignación oficial (qué versículo / qué casa); eso lo asigna el coordinador del CCC.
- **No** distribuir la **letra completa** del libro `th` (copyright). El registro almacena solo `id`, `key_phrase` (≤120 caracteres) y `brief_description` (≤300 caracteres) — paráfrasis breves, no transcripción.
- **No** sustituir el ensayo con el padre/madre/superintendente del CCC. El script ayuda, no certifica.
- **No** entrenar audio (ritmo, dicción): Fase 11 ya entregó `audio_helper`; este agente no se mete con TTS.
- **No** registrar quién recibió qué asignación. Eso sería tracker de hermanos sin opt-in (prohibido).

## Arquitectura

Reutiliza el patrón **agente procedural** vigente (`meeting_helper`, `public_talk_outline`, `conversation_assistant`):

```
jw-cli (`jw student …`) ─┐
                         │
jw-mcp (`student_part_help`) ──┐
                               ▼
                jw-agents.student_part_helper
                               │
                ┌──────────────┴────────────┐
                ▼                           ▼
   jw-core.data.oratory_points    jw-core.data.student_parts_templates
   (registro de 50 puntos)        (plantillas kind × audience × point)
                ▲                           ▲
                └──── jw-core.parsers.reference
                       (resolución de versículos)
                └──── (opcional) jw-core.parsers.workbook
                       (cuando topic == "this week")
```

### Datos nuevos en `jw-core`

#### `jw_core/data/oratory_points.py`

Registro inmutable, hand-curated, de los **~50 puntos de oratoria** del libro **Mejore su predicación** (`th`). Cada punto se identifica por su número canónico (1-50). El registro NO incluye el desarrollo doctrinal del libro, solo:

```python
@dataclass(frozen=True)
class OratoryPoint:
    number: int                       # 1..50 (orden canónico del libro th)
    key_phrase_en: str                # p.ej. "Speak conversationally"
    key_phrase_es: str                # "Hable con naturalidad"
    key_phrase_pt: str                # "Fale com naturalidade"
    brief_en: str                     # ≤300 chars paráfrasis del consejo
    brief_es: str
    brief_pt: str
    category: Literal["preparation", "delivery", "content"]
    # qué tipos de asignación aplican naturalmente al punto
    applies_to: tuple[str, ...]       # ('bible_reading', 'starting_conversation', ...)


ORATORY_POINTS: tuple[OratoryPoint, ...] = (
    OratoryPoint(
        number=1,
        key_phrase_en="Choice of words",
        key_phrase_es="Elección de palabras",
        key_phrase_pt="Escolha das palavras",
        brief_en="Use words your audience understands; avoid jargon.",
        brief_es="Use palabras que su audiencia entienda; evite jerga.",
        brief_pt="Use palavras que sua audiência entenda; evite jargão.",
        category="content",
        applies_to=("bible_reading", "starting_conversation", "return_visit", "bible_study"),
    ),
    # ... 49 entries omitted from spec; full content in
    #     packages/jw-core/src/jw_core/data/oratory_points.py
)


def point_of_the_month(d: date, *, language: str = "en") -> OratoryPoint: ...
def get_point(number: int) -> OratoryPoint: ...
def points_applicable_to(kind: str) -> list[OratoryPoint]: ...
def key_phrase(point: OratoryPoint, language: str) -> str: ...
def brief(point: OratoryPoint, language: str) -> str: ...
```

**Mapping mes → punto**: el folleto `th` se trabaja en orden, ~4 puntos/mes en el ciclo del CCC. Para que el toolkit sea operativo sin sincronización en red, definimos un mapeo determinista basado en mes del año:

```
month_index (1-12) → starting point number (1, 5, 9, 13, ...) ciclo de 12 meses cubriendo
                     48 puntos; punto 49-50 caen en meses 12/1 del siguiente ciclo.
```

Si el usuario pasa `oratory_point=N` explícito, se respeta. Si no, `point_of_the_month(today)` decide. Mapeo concreto en `oratory_points.py`:

```python
_MONTH_TO_POINT_START: dict[int, int] = {1:1, 2:5, 3:9, 4:13, 5:17, 6:21,
                                          7:25, 8:29, 9:33, 10:37, 11:41, 12:45}

def point_of_the_month(d: date, *, language: str = "en") -> OratoryPoint:
    """Return the canonical 'first point of the month' for date `d`.

    The month → starting-point mapping is intentionally static. If a user
    needs a different active point (e.g. their congregation runs a slower
    cycle), pass `oratory_point=N` to the agent.
    """
    return get_point(_MONTH_TO_POINT_START[d.month])
```

**Validación legal en CI**: un test (`test_oratory_points_brief_length`) garantiza que todos los `brief_*` son ≤300 chars; otro test (`test_oratory_points_distinct_paraphrase`) garantiza que ningún `brief` es idéntico al lema oficial del libro (chequeo de hash contra un set blacklist vacío por defecto — la lista negra se pobla solo si alguien pega la frase literal).

#### `jw_core/data/student_parts_templates.py`

Plantillas en tres ejes (`kind`, `audience`, `language`). Estructura:

```python
@dataclass(frozen=True)
class PartTemplate:
    kind: Literal["bible_reading", "starting_conversation", "return_visit", "bible_study"]
    audience: Literal["default", "new", "religious", "atheist"]
    language: Literal["en", "es", "pt"]
    opening: str         # 1-2 sentences, with {placeholders}
    body: str            # 2-4 sentences, with {placeholders}
    transition: str      # 1 sentence
    close: str           # 1 sentence
    time_target_seconds: int   # 240 / 180 / 240 / 300 por defecto
    # placeholders que el agente debe rellenar antes de devolver
    required_placeholders: tuple[str, ...]
```

**Slots iniciales** (4 kinds × 4 audiences × 3 idiomas = 48 plantillas, pero con fallback a `audience=default` cuando el slot exacto no existe — lanzamos v1 con **4 kinds × {default, atheist, religious, new} × 3 langs = 48 plantillas**, todas pobladas).

**Lookup function**:

```python
def find_template(
    kind: str, audience: str, language: str,
) -> PartTemplate:
    """Returns the most specific template available, falling back gracefully:
      (kind, audience, language) → (kind, 'default', language) → (kind, 'default', 'en').
    Raises ValueError if `kind` is unknown.
    """
```

**Time targets** son data (no behavior):

| Kind | seconds |
|---|---|
| `bible_reading` | 240 (4 min) |
| `starting_conversation` | 180 (3 min) |
| `return_visit` | 240 (4 min) |
| `bible_study` | 300 (5 min) |

### Agente nuevo `jw_agents.student_part_helper`

```python
async def student_part_helper(
    kind: Literal["bible_reading", "starting_conversation", "return_visit", "bible_study"],
    topic_or_ref: str,
    *,
    language: str = "en",
    oratory_point: int | None = None,
    audience: Literal["default", "new", "religious", "atheist"] = "default",
    wol: WOLClient | None = None,
    today: date | None = None,
) -> AgentResult:
    """Compose a structured student-part script.

    Returns an AgentResult whose .findings are exactly four entries — one
    per section of the script (opening / body / transition / close) — plus
    metadata describing:
      - resolved scripture (if topic_or_ref parses as one)
      - time_target_seconds
      - oratory_point_applied (number + key phrase)
      - audience profile used
    """
```

**Pipeline**:

1. Validar `kind`. Devuelver `AgentResult` con warning si es desconocido.
2. Resolver punto de oratoria:
   - Si `oratory_point` no es None → `get_point(oratory_point)`.
   - Si es None → `point_of_the_month(today or date.today(), language=language)`.
   - Si el punto no aplica a `kind` (`kind not in point.applies_to`), agregar warning pero continuar (el usuario manda).
3. Resolver `topic_or_ref`:
   - `parse_reference(topic_or_ref)` → si no es None, es una asignación de versículo. Para `bible_reading`, obtenemos el chapter HTML solo cuando `wol` se pasa (evita red obligatoria); si no, solo la URL de wol y el `display()`.
   - Si el `topic_or_ref` es exactamente `"this week"` (case-insensitive), llamar a `workbook_helper` con `today` para extraer el assignment del workbook que matchee `kind`. Esto requiere `wol`.
   - En cualquier otro caso, `topic_or_ref` se trata como tema libre (string slot).
4. Construir el script:
   - `tpl = find_template(kind, audience, language)`.
   - Rellenar placeholders: `{topic}`, `{verse_display}`, `{verse_text}` (vacío si no fetch), `{oratory_phrase}`, `{oratory_brief}`, `{next_visit_hook}` (kind=return_visit).
   - Generar `Finding` x4 (opening, body, transition, close).
5. Setear metadata: `time_target_seconds`, `oratory_point_applied = {number, key_phrase}`, `audience`, `kind`, `language`, `resolved_reference` (si aplica).

**Sin LLM**. El agente es 100% determinista; tests fijan `today` para evitar drift por fecha del sistema.

### Convención de Findings

Cada `Finding` tiene `metadata["source"] = "student_part_template"` y `metadata["section"] ∈ {"opening","body","transition","close"}`. La citation apunta al WOL URL del versículo si lo hay; si no hay versículo, `Citation(url="", title=topic_or_ref, kind="topic_anchor")`.

### Reglas duras de diseño

1. **Templates son data, no código** — viven en un módulo Python pero solo como tuplas de dataclasses. Nunca se ejecutan strings.
2. **Cero IO en import**. Todo el registro de plantillas y puntos está en literales.
3. **`student_part_helper` no importa nada de `jw-rag`** — es trivialmente reutilizable sin el RAG montado.
4. **El fetch del workbook es opcional**. Si `wol is None`, "this week" produce un warning y se cae al modo "tema libre".
5. **Idempotente para misma entrada + misma `today`** — cero aleatoriedad.

## Modelos (Dataclasses)

```python
# jw_core/data/oratory_points.py
@dataclass(frozen=True)
class OratoryPoint: ...  # ver arriba

# jw_core/data/student_parts_templates.py
@dataclass(frozen=True)
class PartTemplate: ...  # ver arriba
```

No introducimos `BaseModel` Pydantic aquí — los datos son `@dataclass(frozen=True)` siguiendo la convención de `jw_core.data.objections.Objection`.

## Integración con el resto del toolkit

### CLI (`jw-cli`)

Nuevo comando `jw student`:

```
jw student bible_reading "Romanos 12:1-2" --lang es                    # 4-min reading script
jw student conversation "Genesis 1:1" --audience atheist --lang en
jw student revisit "John 3:16" --lang en --hook "next week we'll discuss Adam"
jw student study "Disfruta de la vida, lección 5" --audience new --lang es
jw student bible_reading "this week" --lang es                          # uses workbook scraper (network)
jw student bible_reading "Romans 12:1-2" --lang en --point 7            # explicit oratory point
```

### MCP (`jw-mcp`)

Nueva herramienta `student_part_help(kind, topic_or_ref, language="en", oratory_point=None, audience="default") -> dict` que envuelve el agente y retorna `result.to_dict()`. **No** acepta `today` por contrato — usa `date.today()` siempre.

### Eval (`jw-eval`)

Cada Fase 23-32 debe añadir golden cases. Para Fase 26: **4 L1 cases**, uno por kind, validando estructura:

```yaml
# fixtures/golden_qa/l1/student_part_bible_reading_es.yaml
id: l1_student_part_bible_reading_es
agent: student_part_helper
layer: l1
input:
  kind: bible_reading
  topic_or_ref: "Romanos 12:1-2"
  language: es
  audience: default
  oratory_point: 1
expected:
  min_findings: 4                          # opening + body + transition + close
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "supuestamente"
    - "tal vez"
metadata:
  topic: student_parts.bible_reading.es
  added_at: 2026-05-30
```

Los otros 3 (conversation_en, return_visit_pt, bible_study_es) siguen el mismo patrón.

### Docs

- `docs/guias/partes-del-estudiante.md` — guía operativa con ejemplos por kind y audience.
- `docs/VISION_AUDIT.md` — fila nueva para VISION #2 marcando "completado en Fase 26".
- `docs/ROADMAP.md` — sección "Fase 26 — Student Parts (completado YYYY-MM-DD)".

## Mapping del libro `th` (consideración de derechos)

El folleto **Mejore su predicación** (`th`) es propiedad de la Watch Tower Bible and Tract Society. Nuestro registro de 50 puntos contiene **solo**:

- El número canónico del punto.
- Una **paráfrasis** corta del título (`key_phrase_*`), no la frase oficial.
- Una paráfrasis breve (`brief_*`) del consejo, redactada de cero.
- Categoría (`preparation` / `delivery` / `content`).
- Qué tipos de asignación aplican.

**Procedimiento de redacción**:
1. El autor parafrasea de memoria/lectura.
2. Tests CI validan longitudes y que el `brief` no sea idéntico a snippets conocidos del libro (lista negra vacía por defecto — opt-in).
3. Si la Sociedad publicara una versión revisada con puntos renumerados, este registro se versionaría (no se reescribe sobre el actual).

Esto sigue la misma política que ya aplica el toolkit con citas: orientación con paráfrasis, no transcripción.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Plantillas muy genéricas → scripts indistinguibles entre kinds | Differentiation by `kind × audience`; 16 slots base (4×4), cada una con tono distinto. |
| 2 | El mapping mes→punto no coincide con el cronograma real del CCC del usuario | `oratory_point=N` siempre overridable; el mapping está documentado en la guía. |
| 3 | Workbook scraper falla cuando JW cambia layout | El agente cae a "tema libre" + warning; nunca rompe el flujo. |
| 4 | Riesgo legal por reproducir texto del libro `th` | Solo paráfrasis ≤300 chars + test de hash blacklist. Documentado en spec. |
| 5 | `parse_reference` falla en idiomas raros | Cae a tratar `topic_or_ref` como string libre + warning. |
| 6 | El usuario pide kind/audience inválidos | Validación en agente; `ValueError` mapeado a `AgentResult.warnings` (no excepción al cliente MCP). |
| 7 | Multi-versículo en `bible_reading` (rango "Rom 12:1-2") | `parse_reference` ya soporta rangos; tests cubren el caso. |
| 8 | Test de plantilla cambia accidentalmente el `time_target_seconds` | Test snapshot con valores hardcoded por kind. |

## Métricas de éxito de la fase

- `jw student bible_reading "Juan 3:16" --lang es` corre en <500 ms (sin red).
- 4 kinds × 4 audiences × 3 idiomas = **48 plantillas** en repo.
- **4 L1 golden cases** añadidos a `jw-eval` (uno por kind) — fase suma a la cobertura V&M.
- Tests del agente verdes en CI con 0 red.
- Guía `docs/guias/partes-del-estudiante.md` legible, con un ejemplo por kind.

## Pendientes explícitos (post-Fase 26)

- **TTS / ensayo de audio**: ya cubierto por `audio_helper` (Fase 11). No reabrir.
- **Detectar el mes corriente del CCC desde wol.jw.org**: requiere mediator + un endpoint que no existe documentado. Out of scope.
- **Punto de oratoria dinámico desde JW Library** (si en el futuro existe API): tracking en Fase 32 territory.
- **Plantillas para audiencias adicionales** (e.g. `child`, `teenager`): post-v1 si hay demanda.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests del paquete
.venv/bin/python -m pytest packages/jw-core/tests/test_oratory_points.py \
                            packages/jw-agents/tests/test_student_part_helper.py -v

# 3. CLI smoke
uv run jw student bible_reading "Juan 3:16" --lang es
uv run jw student conversation "creación" --audience atheist --lang es
uv run jw student revisit "John 3:16" --lang en
uv run jw student study "esperanza de resurrección" --audience new --lang es

# 4. Eval (4 golden L1 cases nuevos)
uv run jw eval --layer 1 --filter agent=student_part_helper

# 5. MCP tool listed
uv run jw-mcp --list-tools | grep student_part_help
```

## Plan de implementación

Spec hijo: [`2026-05-30-fase-26-student-parts-plan.md`](../plans/2026-05-30-fase-26-student-parts-plan.md). 14 tareas TDD ordenadas: bottom-up — data primero (`oratory_points`, `student_parts_templates`), luego agente, luego CLI/MCP, luego golden cases, luego docs.
