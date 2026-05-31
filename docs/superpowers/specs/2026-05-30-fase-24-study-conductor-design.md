# Fase 24 — `study_conductor`: preparación de lecciones + registro de progreso del estudiante

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (alto valor recurrente)
> **Tamaño**: L (~7-10 días)
> **Depende de**: Fase 11 (cifrado de notas, `FieldEncryptor`), Fase 22 (eval doctrinal — para protegerlo). Reutiliza Fase 5.5 (`parsers.jwpub`), Fase 12 (patrón `RevisitStore`), Fase 4 (`topic_index`).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

El estudio bíblico personal con la publicación actual de la organización (hoy: **«Disfruta de la vida para siempre»**, código `lff`) es el bucle pedagógico central del discipulado: una lección por semana, con preguntas para anticipar, versículos para precargar y metas que el estudiante se va proponiendo (asistir, dejar un vicio, hacer culto en familia, encaminarse al bautismo).

Hoy el toolkit cubre **investigación** (`research_topic`, `apologetics`), **conversación** (`conversation_assistant`), **reuniones** (`workbook_helper`, `meeting_helper`) y **pastoral local de visitas** (`revisit_tracker`). **Falta el agente que acompañe la lección semanal del libro de estudio** y registre la trayectoria del estudiante.

Fase 24 cierra ese hueco con dos piezas hermanas:

1. **`study_conductor`** — agente procedural que, dada `(pub_code, chapter, language)`, extrae el contenido de la lección (desde JWPUB local cuando hay; desde WOL como fallback) y produce un `AgentResult` con: resumen, preguntas de anticipación generadas por **plantillas** (no LLM), versículos clave parseados, y sugerencias del Índice Temático.
2. **`StudentProgress`** — store SQLite local (`~/.jw-agent-toolkit/study_progress.db`) que registra `(student_id, book_pub, lesson) → estado + metas + notas`. Notas y metas-en-texto-libre cifradas con `FieldEncryptor` derivado de passphrase.

Esto se entrega expuesto por CLI (`jw study lesson`, `jw study log`, `jw study progress`) y por MCP (`prepare_lesson`, `log_student_progress`, `list_student_lessons`, `set_student_goal`).

## Objetivos (en orden de prioridad)

1. **Preparar una lección en <2s sin red**, leyendo JWPUB local cuando esté registrado en `meps_catalog` (Fase 19) y degradando a WOL si no.
2. **Registrar el ciclo de vida del estudiante** (lecciones, metas, asistencias, fecha objetivo de bautismo) en un store local cifrable.
3. **Generar preguntas de anticipación reproducibles y multilenguaje** (es/en/pt mínimo) desde plantillas controladas, sin alucinaciones.
4. **Documentar y enforzar la frontera pastoral**: el agente orienta y registra; no es directorio de hermanos, no sustituye al conductor humano, no aconseja en crisis.

## No-objetivos (líneas que NO cruza Fase 24)

Estas exclusiones son **vinculantes**:

- **No sustituye al conductor humano.** El agente NO genera un guion completo de estudio para leer en voz al estudiante. Genera material de **preparación personal previa** del conductor.
- **No es un directorio de hermanos.** El `student_id` es un alias elegido por el usuario (p.ej. `amelia2024`), **nunca** el nombre real en la BD. Si el usuario quiere ver «Amelia» en pantalla, la resolución alias→nombre vive en un JSON separado, opt-in, fuera del store cifrado de progreso.
- **No es un sistema de consejería pastoral.** Si la nota libre del estudiante contiene términos de crisis (suicidio, abuso, violencia), el agente añade un `warning` orientando a contactar a los ancianos y a recursos profesionales — pero **no** intenta resolver la crisis.
- **No envía datos a la nube.** El store es estrictamente local. No hay sync. No hay backup automático fuera del disco del usuario.
- **No genera con LLM las preguntas.** Las plantillas son procedurales (`data/study_prompts.py`) por idioma. El LLM (Claude Desktop) solo recibe el `AgentResult` para narrativizar al usuario si lo desea.
- **No incluye letra de cánticos** (copyright). Si la lección referencia un cántico, el agente expone número + tema, no la letra (alineado con Fase 30).

## Arquitectura

Nuevo módulo en `jw-core` (`study/`) + nuevo agente en `jw-agents` + nuevo store local + integración CLI/MCP. Dependencias hacia abajo conforme a `ARCHITECTURE.md`.

```
packages/jw-core/src/jw_core/
├── data/
│   ├── study_books.py          # (NEW) Registro de pubs de estudio
│   └── study_prompts.py        # (NEW) Plantillas de preguntas (es/en/pt)
└── study/
    ├── personal_notes.py       # (existente)
    ├── flashcards.py           # (existente)
    └── lesson_extractor.py     # (NEW) Carga lección desde JWPUB | WOL

packages/jw-agents/src/jw_agents/
├── study_conductor.py          # (NEW) Agent: prepare_lesson
└── study_progress.py           # (NEW) StudentProgress + GoalCatalog + Store

packages/jw-cli/src/jw_cli/commands/
└── study.py                    # (NEW) jw study {lesson, log, progress, goals}

packages/jw-mcp/src/jw_mcp/
└── server.py                   # (MOD) +4 tools: prepare_lesson,
                                #               log_student_progress,
                                #               list_student_lessons,
                                #               set_student_goal

packages/jw-eval/fixtures/golden_qa/
├── l1/study_conductor_lff_ch1_es.yaml   # (NEW) golden case L1
└── l3/study_conductor_lff_ch1_es.yaml   # (NEW) golden case L3

docs/guias/
└── conductor-de-estudio.md     # (NEW) Guía de usuario en español
```

### Reglas duras de diseño

1. **`jw_agents.study_conductor`** no hace red en import time. Cliente WOL se construye perezosamente.
2. **`StudentProgress`** sigue el patrón de `RevisitStore`: SQLite + `FieldEncryptor` opcional, ON DEVICE only, sin sync.
3. **`student_id`** es texto libre validado por regex `^[a-z0-9_-]{3,32}$`. Cualquier intento de pasar un string con espacios, mayúsculas o acentos → `ValueError`.
4. **Las preguntas de anticipación son determinísticas**: misma entrada (pub, chapter, language) → misma salida. Sin random, sin LLM.
5. **Notas libres se cifran con un key derivado de passphrase** vía `derive_key_from_password`. El passphrase NO se almacena. El first-run pregunta y guarda solo el SALT en `~/.jw-agent-toolkit/study_progress.salt`.
6. **Detector de crisis** es lista de palabras-clave por idioma en `study_prompts.CRISIS_KEYWORDS`. Match → `warning` en `AgentResult.warnings`. No bloquea el guardado.
7. **`prepare_lesson`** devuelve `AgentResult.findings` con prioridad de fuentes (compatible con Fase 22 L1): `jwpub_chapter` > `wol_chapter` > `topic_index` > `verse_text`.

## Modelos

### Dataclasses para el agente (en `jw_agents.study_conductor`)

```python
@dataclass(frozen=True)
class AnticipationQuestion:
    """Una pregunta de anticipación generada por plantilla."""
    paragraph_index: int          # 1-based, vacío 0 para preguntas globales
    text: str
    template_id: str              # p.ej. "es.fact" | "es.application" | "es.scripture"
    related_verses: list[str]     # referencias canónicas detectadas en el párrafo

@dataclass(frozen=True)
class LessonPrep:
    """Material de preparación de una lección — payload del Finding."""
    pub_code: str
    chapter: int
    language: str
    title: str
    summary: str
    questions: list[AnticipationQuestion]
    key_verses: list[str]         # referencias canónicas (BibleRef-compatibles)
    supporting_topics: list[str]  # subjects from topic_index hits
    source: Literal["jwpub_local", "wol_fallback"]
```

### Pydantic models para el store (en `jw_agents.study_progress`)

```python
class LessonStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    SKIPPED     = "skipped"

class GoalKind(str, Enum):
    ATTEND_MEETINGS         = "attend_meetings"
    DROP_ADDICTION_SMOKING  = "drop_addiction_smoking"
    DROP_ADDICTION_ALCOHOL  = "drop_addiction_alcohol"
    DROP_ADDICTION_OTHER    = "drop_addiction_other"
    PRAY_DAILY              = "pray_daily"
    FAMILY_WORSHIP          = "family_worship"
    BAPTISM                 = "baptism"
    OTHER                   = "other"          # extension hook

class StudentGoal(BaseModel):
    kind: GoalKind
    note: str = ""                  # encrypted at rest
    set_at_iso: str
    achieved_at_iso: str | None = None
    target_iso: str | None = None   # p.ej. fecha objetivo de bautismo

class LessonRow(BaseModel):
    student_id: str = Field(pattern=r"^[a-z0-9_-]{3,32}$")
    book_pub: str
    lesson: int
    status: LessonStatus = LessonStatus.NOT_STARTED
    notes: str = ""                 # encrypted at rest
    goals: list[StudentGoal] = []
    started_at_iso: str | None = None
    completed_at_iso: str | None = None
    attended_meetings_count: int = 0
    baptism_target_iso: str | None = None
    updated_at_iso: str
```

### Registry de libros (`jw_core.data.study_books`)

```python
@dataclass(frozen=True)
class StudyBook:
    pub_code: str                   # "lff"
    title_by_lang: dict[str, str]   # {"es": "Disfruta...", "en": "Enjoy...", "pt": "..."}
    languages: tuple[str, ...]      # ("en", "es", "pt", ...)
    total_chapters: int             # 60 in lff
    jwpub_symbol: str               # "lff" — symbol pattern in JWPUB filename

CURRENT_STUDY_BOOK = "lff"
REGISTRY: dict[str, StudyBook] = {
    "lff": StudyBook(
        pub_code="lff",
        title_by_lang={
            "es": "Disfruta de la vida para siempre",
            "en": "Enjoy Life Forever!",
            "pt": "Desfrute a vida para sempre",
        },
        languages=("en", "es", "pt", "fr", "de", "it", "ja", "ko"),
        total_chapters=60,
        jwpub_symbol="lff",
    ),
    # Históricos y reemplazos quedan registrables sin tocar el código del agente.
}
```

### Plantillas (`jw_core.data.study_prompts`)

```python
ANTICIPATION_TEMPLATES = {
    "es": {
        "fact":        "¿Qué punto principal enseña el párrafo {n}?",
        "application": "¿Cómo aplicaría usted personalmente lo del párrafo {n}?",
        "scripture":   "Lea {ref}. ¿Cómo apoya esto la idea del párrafo {n}?",
        "feeling":     "¿Cómo se siente respecto a lo que dice el párrafo {n}?",
    },
    "en": { ... }, "pt": { ... },
}

CRISIS_KEYWORDS = {
    "es": ["suicidio", "abuso", "violencia", "me quiero morir"],
    "en": ["suicide", "abuse", "violence", "want to die"],
    "pt": ["suicídio", "abuso", "violência", "quero morrer"],
}
```

## Flujos

### Flujo 1 — Preparación de una lección

```
Usuario:  jw study lesson lff 1 --lang es
   │
   ▼
study_conductor.prepare_lesson(pub_code="lff", chapter=1, language="es")
   │
   ├──► REGISTRY["lff"]  ✓  (valida pub_code + idioma soportado)
   │
   ├──► lesson_extractor.load(pub_code, chapter, language)
   │      │
   │      ├──► meps_catalog.find_jwpub_for(symbol="lff", lang="es")
   │      │      │
   │      │      ├── HIT → parsers.jwpub.parse_jwpub(path)
   │      │      │            → chapter title + paragraphs + scripture refs
   │      │      │            → source = "jwpub_local"
   │      │      │
   │      │      └── MISS → WOLClient.get_publication_page("lff", n=chapter)
   │      │                   → HTML → parser de párrafos
   │      │                   → source = "wol_fallback"
   │      │
   │      └── return LessonContent(title, paragraphs[…], refs[…])
   │
   ├──► generate_questions(paragraphs, language)
   │      └── for each paragraph p: emit (fact + application) template
   │          + if p has scripture refs: emit (scripture) template
   │
   ├──► topic_index.search_subjects(title) → top 3 subjects → supporting_topics
   │
   └──► return AgentResult(
            findings=[Finding(LessonPrep, citation=wol_url), …],
            warnings=[]
        )
```

### Flujo 2 — Registro de progreso

```
Usuario:  jw study log amelia2024 lff 3 --status completed
                                       --note "Le costó el tema del nombre divino"
                                       --goal attend_meetings
   │
   ▼
StudentProgressStore.upsert(
    LessonRow(student_id="amelia2024", book_pub="lff", lesson=3,
              status=COMPLETED, notes="<encrypted>",
              goals=[StudentGoal(ATTEND_MEETINGS, set_at=now)],
              completed_at=now, updated_at=now))
   │
   ├──► _validate_student_id("amelia2024") ✓
   ├──► CRISIS_KEYWORDS scan en "note"  →  no match  →  no warning
   ├──► FieldEncryptor(derived).encrypt(notes)  →  Fernet ciphertext
   ├──► INSERT … ON CONFLICT (student_id, book_pub, lesson) DO UPDATE
   │
   └──► return LessonRow (con notas descifradas in-memory para confirmación)
```

### Flujo 3 — First-run privacy onboarding

```
Usuario invoca por primera vez `jw study log ...`
   │
   ▼
Existe ~/.jw-agent-toolkit/study_progress.salt?
   ├── NO →  CLI muestra disclosure (3 puntos):
   │           • Esto guarda datos personales de personas reales.
   │           • Necesita su consentimiento explícito y una passphrase.
   │           • Los datos viven SOLO en este disco. No salen.
   │         Prompt: ¿continuar? (y/N)
   │           → N: abort
   │           → y: prompt passphrase (oculto, dos veces para confirmar)
   │                 → derive key → guardar SALT (no key, no passphrase) en disco
   │                 → cifrar/test
   │
   └── SÍ →  prompt passphrase en cada sesión (cacheada en proceso)
              → derive key → instanciar FieldEncryptor
```

## Privacidad — sección detallada

| Vector | Mitigación |
|---|---|
| **Identidad real del estudiante** | `student_id` es alias regex-validado. Resolución a nombre real vive en un JSON separado, opt-in, no cifrado por diseño (porque es el usuario el que decide si meterse en ese contrato). |
| **Notas libres con datos sensibles** | Cifradas con Fernet (key derivada de passphrase PBKDF2-HMAC-SHA256 200k iters + salt persistente). Sin passphrase no hay lectura. |
| **Metas + status + fechas** | NO cifradas (necesarias para queries). Considerar separar a un store cifrado en Fase 27 si surge necesidad. |
| **First-run sin consentimiento** | Bloqueante. CLI exige `y` + passphrase antes de crear el `.db`. |
| **Crisis detection** | Match local de keywords → `warning` en CLI. No envía nada externo. No bloquea el guardado para no dejar al usuario sin la nota. |
| **Backups** | El usuario decide. Documentado en la guía: si el disco no está cifrado (FileVault/LUKS), recomendar moverlo. |
| **Exportación** | `jw study export <student>` solo si pasa `--i-confirm`; produce JSON con notas YA descifradas — el usuario asume la custodia. |
| **MCP** | Las tools que tocan notas exigen el passphrase via env `JW_STUDY_PASSPHRASE` (no parámetro de tool, no llega al transcript). |
| **Telemetría drift** | Excluida explícitamente para este store. Nada de `JW_TELEMETRY_ENABLED` afecta a `study_progress.db`. |

## Integración con el resto del toolkit

### CLI (`jw-cli`)

Nuevo grupo `study`:

```
jw study lesson <pub> <ch> [--lang es]            # preparar
jw study lessons <pub>                            # listar lecciones del libro
jw study log <student> <pub> <ch>                 # registrar
    [--status completed|in_progress|skipped]
    [--note "..."]
    [--goal attend_meetings|drop_addiction_smoking|...]
    [--target-iso 2026-08-15]                     # solo si --goal baptism
jw study progress <student>                       # ver lifecycle del estudiante
jw study goals                                    # listar taxonomía
jw study export <student> --i-confirm             # exportar a JSON (descifrado)
jw study directory set <alias> <display_name>     # opt-in alias → nombre
jw study directory clear                          # borra el JSON de directorio
```

### MCP (`jw-mcp`)

Cuatro herramientas nuevas (firmas):

```python
@mcp.tool()
def prepare_lesson(pub_code: str, chapter: int, language: str = "es") -> dict: ...

@mcp.tool()
def log_student_progress(
    student_id: str, book_pub: str, lesson: int,
    status: str = "in_progress", note: str = "", goals: list[str] | None = None,
    target_iso: str | None = None,
) -> dict: ...

@mcp.tool()
def list_student_lessons(student_id: str, book_pub: str | None = None) -> dict: ...

@mcp.tool()
def set_student_goal(
    student_id: str, kind: str, target_iso: str | None = None, note: str = "",
) -> dict: ...
```

Todas devuelven `{"error": "..."}` ante fallo (patrón existente). La passphrase se lee de `JW_STUDY_PASSPHRASE`. Sin passphrase → respuesta `{"error": "JW_STUDY_PASSPHRASE not set"}`.

### `jw-eval` — protección por golden cases

PR debe añadir mínimo:

- **1 L1** (`fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml`): valida shape — `min_findings: 1`, `must_have_source: jwpub_chapter` o `wol_chapter`, `must_have_citation: true`, `forbidden_keywords: ["supuestamente", "talvez"]`.
- **1 L3** (`fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml`): valida respuesta semántica para el capítulo 1 («¿Existe alguien que se preocupe por nosotros?»). Golden answer redactada por el usuario; keywords `expected_keywords_any: ["Jehová", "se preocupa", "Padre amoroso"]`; `expected_keywords_none: ["pasajes oscuros", "inalcanzable"]`.

### CI

Sin nuevos jobs. Los existentes `test` y `eval-fast` cubren:

- `test`: unit tests del agente, store y CLI.
- `eval-fast` (`jw eval --layer 1,2`): los 2 golden cases nuevos suben el total a 30 → 32+.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Pérdida de passphrase → datos irrecuperables | Documentado fuerte en la guía. El SALT por sí solo no permite recuperar. Comportamiento explícito por diseño. |
| 2 | Usuario olvida que es tracker de personas reales | First-run disclosure bloqueante + recordatorio en cada `jw study log` la primera vez del día. |
| 3 | Crisis detection falla en idiomas no soportados | Lista ampliable en `study_prompts.CRISIS_KEYWORDS`; fallback en inglés cuando idioma no está. |
| 4 | JWPUB no disponible localmente | Fallback graceful a WOL con `source = "wol_fallback"` y warning visible en `AgentResult`. |
| 5 | Preguntas de plantilla suenan robóticas | Aceptable — son material **personal** del conductor. La guía aclara que se reformulan al hablar con el estudiante. |
| 6 | Drift de la pub `lff` (capítulos renumerados) | Registry permite añadir suplementos sin tocar agente; tests de regresión por `total_chapters`. |
| 7 | Estudiante quiere ver su progreso | El export opt-in produce JSON legible. El usuario decide imprimir/enseñar. |
| 8 | Cambio de pub de estudio (2027+) | Cambiar `CURRENT_STUDY_BOOK` y añadir entry. Las filas existentes con `book_pub="lff"` siguen siendo legibles. |
| 9 | Crisis match en falso positivo (la nota es académica) | El warning no bloquea. Documentado. |
| 10 | Confusión con `revisit_tracker` | Guía explícita: `revisit_tracker` = puerta a puerta / interesados nuevos; `study_conductor` = ciclo formal de un libro de estudio con un estudiante regular. |

## Métricas de éxito de la fase

- ✅ `jw study lesson lff 1 --lang es` corre en <2s (con JWPUB local) y <5s (fallback WOL con cache caliente).
- ✅ 100% de las 60 lecciones de `lff` cargan en es/en/pt sin error (test de integración con cassettes WOL para fallback).
- ✅ `pytest packages/jw-agents/tests/test_study_conductor.py packages/jw-agents/tests/test_study_progress.py` verde.
- ✅ Round-trip cifrado: notas con caracteres unicode → escritas → leídas → byte-idénticas.
- ✅ Eval L1 y L3 para `study_conductor` añadidos a `jw-eval` y verdes en `eval-fast`.
- ✅ Documentado en `docs/guias/conductor-de-estudio.md` con sección «Pérdida de passphrase: datos perdidos por diseño».
- ✅ Audit 1:1 en `docs/VISION_AUDIT.md` añadiendo fila Fase 24 → VISION #1.
- ✅ `docs/ROADMAP.md` actualizado con sección Fase 24.

## Pendientes explícitos (post-Fase 24)

- **Recordatorios temporales** («te toca la lección 4 esta semana») → fase futura de scheduler local opcional, alineada con Fase 25.
- **Integración con el reporte de precursor** (Fase 27) — `attended_meetings_count` ya está modelado para alimentar futuros agregados.
- **Gráficas de progreso** — JSON export ya las habilita externamente.
- **Sync entre múltiples conductores del mismo estudiante** — explícitamente fuera de scope (atenta contra «sin sync sin opt-in»).
- **Modo familia** (varios estudiantes en un mismo `book_pub`) — el modelo lo permite; UI/CLI lo expone después.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests unitarios
.venv/bin/python -m pytest packages/jw-agents/tests/test_study_conductor.py \
                           packages/jw-agents/tests/test_study_progress.py -v

# 3. Eval doctrinal (los 2 nuevos casos quedan cubiertos por L1+L3)
uv run jw eval --layer 1,3 --filter agent=study_conductor

# 4. Demo end-to-end (con JWPUB de lff registrado en meps_catalog)
JW_STUDY_PASSPHRASE="demo-passphrase" uv run jw study lesson lff 1 --lang es
JW_STUDY_PASSPHRASE="demo-passphrase" uv run jw study log demo_student lff 1 \
    --status in_progress --note "Buena receptividad" --goal attend_meetings
JW_STUDY_PASSPHRASE="demo-passphrase" uv run jw study progress demo_student

# 5. MCP smoke
uv run jw-mcp  # en otra terminal; usar inspector MCP para invocar las 4 tools
```

## Plan de implementación (alto nivel)

Plan hijo: [`docs/superpowers/plans/2026-05-30-fase-24-study-conductor-plan.md`](../plans/2026-05-30-fase-24-study-conductor-plan.md).

Secuencia cronológica (cada paso con su PR-able commit + tests sin regresiones en los 551+ tests existentes):

1. Registry `study_books` + plantillas `study_prompts` (datos puros).
2. `lesson_extractor`: ruta JWPUB local + fallback WOL.
3. `StudentProgress` modelos Pydantic + enums.
4. `StudentProgressStore`: SQLite + Fernet + first-run salt.
5. `study_conductor.prepare_lesson` agent (compone 1-3).
6. Crisis detector + integración en `log`.
7. CLI `jw study lesson`, `jw study log`, `jw study progress`, `jw study goals`.
8. CLI `jw study directory` (alias→nombre opt-in).
9. MCP tools (4).
10. Golden cases L1 + L3 para `jw-eval`.
11. Guía `docs/guias/conductor-de-estudio.md` + actualizar ROADMAP + VISION_AUDIT.

Cada paso con TDD: test rojo → implementación → test verde → commit.
