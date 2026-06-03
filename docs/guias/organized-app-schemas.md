---
title: "Schemas organized-app en Pydantic v2 (Fase 51)"
description: "Port verbatim de los tipos TS de sws2apps/organized-app: PersonType, SchedWeekType, S-21 post-2023."
date: "2026-06-02"
---

# Guía — Schemas organized-app en Pydantic v2 (Fase 51)

> Modelos Pydantic v2 portados verbatim de `sws2apps/organized-app` (MIT) —
> la PWA React que cientos de congregaciones usan para gestionar
> programas de reunión, asignaciones y reportes S-21. El toolkit ahora
> habla el mismo dialecto de datos sin depender de su runtime.

## ¿Por qué?

Antes de F51, `jw_core` tenía sus propios modelos para `WorkbookWeek`,
`MonthlyReport`, etc. Esos modelos:

- No estaban validados por una comunidad amplia.
- No interoperaban con backups producidos por la PWA organized-app
  (que ya está adoptada por congregaciones reales).
- Duplicaban modelado: cada nueva feature creaba su propia estructura.

F51 importa los tipos TypeScript del `src/definition/` de organized-app
como modelos Pydantic, conservando exactamente la misma forma JSON. Eso
habilita:

1. Leer y escribir backups producidos por la PWA (ver F55.5).
2. Compartir validación con cientos de despliegues reales.
3. Tener una **fuente de verdad común** para conceptos como S-21,
   schedule semanal, person.

## Estructura del módulo

```
packages/jw-core/src/jw_core/models_organized/
├── __init__.py              ← re-exports + docstring
├── common.py                ← Timestamped[T] (CRDT envelope)
├── assignment.py            ← AssignmentCode IntEnum + Literal types
├── person.py                ← PersonType + sub-shapes
├── week.py                  ← Week IntEnum + WeekType
├── meeting_attendance.py    ← MeetingAttendanceType (mes con 5 semanas)
├── field_service_groups.py  ← FieldServiceGroupType
├── field_service_report.py  ← UserFieldService{Daily,Monthly}ReportType
└── schedule.py              ← SchedWeekType (mid-week + weekend)
```

## El patrón CRDT: `Timestamped[T]`

organized-app sincroniza estado entre dispositivos sin servidor central.
Cada campo mutable lleva su propio `updatedAt` para resolver conflictos
last-write-wins por atributo:

```python
from jw_core.models_organized import Timestamped

# JSON shape:  {"value": true, "updatedAt": "2026-06-02T10:00:00Z"}
flag: Timestamped[bool] = Timestamped(value=True, updatedAt="2026-06-02T10:00:00Z")
```

Eso aparece en `PersonType`, `MeetingAttendanceType`, etc. en
prácticamente cada campo no-id.

## Tipos clave

### `Week` (enum)

```python
from jw_core.models_organized import Week

assert Week.NORMAL == 1
assert Week.MEMORIAL == 5
assert Week.WATCHTOWER_STUDY == 13
assert Week.NO_MEETING == 20
```

Valores numéricos **idénticos al TS source**. Si los cambias, rompes
sync con la PWA.

### `AssignmentCode` (enum)

```python
from jw_core.models_organized import AssignmentCode

assert AssignmentCode.MM_BibleReading == 100
assert AssignmentCode.WM_WTStudyConductor == 130
assert AssignmentCode.MINISTRY_HOURS_CREDIT == 300
```

100 = mid-week parts. 110+ = roles. 300 = horas de servicio acreditadas
(pioneros).

### `PersonType`

Estructura completa del registro de un publicador:

```python
from jw_core.models_organized import PersonType

person = PersonType.model_validate({
    "_deleted": {"value": False, "updatedAt": "2026-06-01T00:00:00Z"},
    "person_uid": "uid-abc-123",
    "person_data": {
        "person_firstname": {"value": "Ana", "updatedAt": "..."},
        "person_lastname": {"value": "García", "updatedAt": "..."},
        "person_display_name": {"value": "Ana García", "updatedAt": "..."},
        "male": {"value": False, "updatedAt": "..."},
        "female": {"value": True, "updatedAt": "..."},
        "birth_date": {"value": None, "updatedAt": "..."},
        "assignments": [],
        "timeAway": [],
        "archived": {"value": False, "updatedAt": "..."},
        "disqualified": {"value": False, "updatedAt": "..."},
        "email": {"value": "", "updatedAt": "..."},
        "address": {"value": "", "updatedAt": "..."},
        "phone": {"value": "", "updatedAt": "..."},
        "publisher_baptized": {
            "active": {"value": True, "updatedAt": "..."},
            "anointed": {"value": False, "updatedAt": "..."},
            "other_sheep": {"value": True, "updatedAt": "..."},
            "baptism_date": {"value": None, "updatedAt": "..."},
            "history": [],
        },
        "publisher_unbaptized": {"active": {...}, "history": []},
        "midweek_meeting_student": {"active": {...}, "history": []},
        "privileges": [],
        "enrollments": [],
        "emergency_contacts": [],
        "family_members": {"head": True, "members": [], "updatedAt": "..."},
    },
})

print(person.person_data.person_display_name.value)  # "Ana García"
```

Notas de diseño:

- **`_deleted` se renombró a `deleted`** en Python para evitar la
  convención de "atributos privados con `_`" — pero el alias preserva
  el JSON original: `model_dump(by_alias=True)` emite `_deleted`.
- **`first_report` es opcional**. Algunos backups no lo traen.
- **`StatusHistory` modela toda la historia** del publicador (cuando
  estuvo activo, inactivo, bautizado).

### `SchedWeekType`

Estado autoritativo de una semana de reunión:

```python
from jw_core.models_organized import SchedWeekType

sched = SchedWeekType.model_validate({
    "weekOf": "2026-06-01",
    "midweek_meeting": {
        "chairman": {
            "main_hall": [{"type": "main", "name": "Carlos M.", "value": "uid-1", "updatedAt": "..."}],
            "aux_class_1": {"type": "aux1", "name": "", "value": "", "updatedAt": "..."},
        },
        "opening_prayer": [{"type": "main", "name": "Pedro V.", "value": "uid-2", "updatedAt": "..."}],
        "tgw_talk": [...],
        "tgw_gems": [...],
        "tgw_bible_reading": {
            "main_hall": [...],
            "aux_class_1": {...},
            "aux_class_2": {...},
        },
        "ayf_part1": {
            "main_hall": {"student": [...], "assistant": [...]},
            "aux_class_1": {"student": {...}, "assistant": {...}},
            "aux_class_2": {"student": {...}, "assistant": {...}},
        },
        "ayf_part2": {...},
        "ayf_part3": {...},
        "ayf_part4": {...},
        "lc_part1": [...],
        "lc_part2": [...],
        "lc_part3": [...],
        "lc_cbs": {"conductor": [...], "reader": [...]},
        "closing_prayer": [...],
        "circuit_overseer": {...},
        "week_type": [...],
    },
    "weekend_meeting": {
        "chairman": [...],
        "opening_prayer": [...],
        "public_talk_type": [...],
        "speaker": {"part_1": [...], "part_2": [...], "substitute": [...]},
        "wt_study": {"conductor": [...], "reader": [...]},
        "closing_prayer": [...],
        "circuit_overseer": {...},
        "week_type": [...],
        "outgoing_talks": [],
    },
})
```

Cada slot es un `AssignmentCongregation` con `type/name/value/updatedAt`,
opcionalmente `solo`, `id`, `_deleted`. El `value` típicamente es un
`person_uid` apuntando a `PersonType`.

### `UserFieldServiceMonthlyReportType` (S-21 post-2023)

```python
from jw_core.models_organized import UserFieldServiceMonthlyReportType

report = UserFieldServiceMonthlyReportType.model_validate({
    "report_date": "2026-06",
    "report_data": {
        "deleted": False,
        "updatedAt": "2026-06-30T23:59:00Z",
        "shared_ministry": True,
        "hours": {
            "field_service": {"daily": "0", "monthly": "12"},
            "credit": {"daily": "0", "monthly": "2"},
        },
        "bible_studies": {"daily": 0, "monthly": 3, "records": ["uid-a", "uid-b"]},
        "comments": "",
        "record_type": "monthly",
        "status": "submitted",
    },
})
```

Notas de la S-21 post-2023:

- **Publicadores no-pioneros reportan solo bible_studies y did-something**.
  `hours.field_service.monthly` queda en `"0"`.
- **Pioneros sí reportan horas** como string (legacy, evita float drift).
- **`status`**: `"pending"` → `"submitted"` → `"confirmed"` por el secretary.

## Re-exports vs. duplicación

F51 NO migra `models_meeting.py` ni `ministry/field_report.py` a usar
estos modelos directamente. Sus formas siguen siendo apropiadas para:

- `WorkbookWeek` (contenido del workbook semana JW): no es schedule, es
  contenido de la publicación.
- `MonthlyReport` local: aggregate keyed por columnas SQLite del store
  local; no necesita CRDT envelopes.

En cambio, F55.6 añade un **bridge converter** (`organized_bridge.py`):
`to_organized_monthly_report(local_report, *, pioneer, status, ...)`
convierte cuando hace falta interoperar.

## Tests

`packages/jw-core/tests/test_organized_schemas.py` (10 tests):

- `Week` y `AssignmentCode` numéricos verbatim TS.
- `Timestamped[T]` envelope JSON correcto.
- `PersonType` build desde minimal payload.
- `_deleted` alias preservado en `model_dump(by_alias=True)`.
- `MeetingAttendanceType` con 5 semanas siempre.
- `FieldServiceGroupType` con members.
- `UserFieldServiceMonthlyReportType` con status submitted.
- `SchedWeekType` skeleton mínimo válido.

## Crédito y licencia

Schemas portados de `sws2apps/organized-app` `src/definition/`
(TypeScript, MIT). El runtime React/Firebase/IndexedDB NO se porta — el
toolkit habla solo el formato de datos.

Ver `README.md` raíz para atribución completa.
