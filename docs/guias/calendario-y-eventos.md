# Calendario y eventos (Módulo 6)

> Cubre el ítem #6 de [VISION.md](../VISION.md): Memorial anual con countdown, asambleas/circuito, visita del superintendente.

## Capas

| Archivo | Función |
|---|---|
| `jw_core/calendar/memorial.py` | Tabla oficial 2024-2030 + heurística para años fuera de tabla |
| `jw_core/calendar/events.py` | SQLite store genérico para asambleas/circuito/conventos |
| `jw_core/calendar/visit.py` | Checklists localizados (superintendente, ancianos) |

## Memorial

**Tabla oficial:**

```python
from jw_core.calendar import memorial_date_for_year, countdown_to_memorial

# Año en tabla → source='published'
md = memorial_date_for_year(2026)
print(md.iso_date, md.source)   # 2026-04-02 published

# Año fuera de tabla → source='estimated' + warning
md = memorial_date_for_year(2099)
print(md.warning)  # "Date is approximated. Confirm against jw.org..."

# Countdown desde hoy
info = countdown_to_memorial()
print(f"{info['days_remaining']} días hasta el {info['memorial_iso']}")
```

**Heurística:** primera luna llena después del equinoccio de marzo, usando la fórmula Conway/Meeus de sinódico ~29.53 días. Stay within ±3 días del valor oficial para nuestra ventana verificada.

**Checklist de preparación localizado:**
```python
from jw_core.calendar import memorial_preparation_checklist
for item in memorial_preparation_checklist("es"):
    print(item["id"], "—", item["task"])
```

## Eventos generales

```python
from jw_core.calendar import Event, EventStore, upcoming_for_user

with EventStore() as store:
    store.upsert(Event(
        kind="circuit",
        title="Visita del Superintendente",
        start_iso="2026-06-15",
        end_iso="2026-06-21",
        location="Salón del Reino A",
        language="es",
    ))
    # Próximos 90 días
    for e in upcoming_for_user(horizon_days=90):
        print(e.start_iso, "—", e.title, f"({e.kind})")
```

**Kinds soportados:** `memorial`, `assembly`, `circuit`, `convention`, `elder_visit`, `custom`.

**Privacidad:** todo local en `~/.jw-agent-toolkit/calendar.db` (override `JW_CALENDAR_DB`).

## Checklists de visita

```python
from jw_core.calendar import circuit_overseer_checklist, elder_visit_checklist

for item in circuit_overseer_checklist("es"):
    print(item["id"], "—", item["task"])
```

Ítems: `week_minus_4 / -3 / -2 / -1 / week_of / post_visit`.

## Tests

10 tests en `packages/jw-core/tests/test_calendar_module.py`:
- Tabla published vs heurística estimated.
- Countdown rolea de año correctamente.
- Localización de checklists.
- Event store upsert + upcoming + horizon.

```bash
uv run pytest packages/jw-core/tests/test_calendar_module.py -v
```

## Pendiente

- Detección automática de fechas de asamblea desde jw.org/eventos (requiere análisis del formato HTML por congregación o un endpoint público autorizado).
- Recordatorios push/email (integrarse con bots del Módulo 10).
