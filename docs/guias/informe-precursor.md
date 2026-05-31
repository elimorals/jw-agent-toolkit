# Informe mensual de precursor

> Guía de uso de `jw report`. Audiencia: precursores regulares,
> auxiliares y especiales que quieran llevar sus cifras del mes en local.

## En 30 segundos

```bash
# 1. (recomendado) genera tu clave y guárdala en tu gestor de contraseñas
export JW_PRIVACY_KEY=$(jw keygen)

# 2. registra horas y estudios cuando te ocurren
jw report log-hours --hours 2.5 --tag street --note "parque central"
jw report log-study --student-alias maria --started 2026-05-01
jw report met-today --student-alias maria

# 3. al cierre del mes, genera el informe
jw report --month 2026-05                   # markdown a stdout
jw report --month 2026-05 --format csv --out informe.csv
jw report --month 2026-05 --format pdf --out informe.pdf
```

## ¿Qué almacena y dónde?

- DB local: `~/.jw-agent-toolkit/field_service.db` (override con `JW_FIELD_DB`).
- Notas y alias de estudiantes están cifrados si `JW_PRIVACY_KEY` está set.
- Horas, fechas y modalidad (`street`, `cart`...) se guardan planas — sin ellas no se podría sumar.
- Las revisitas no se duplican: se leen del store de `jw ministry revisit` (Fase 12) solo en lectura.

## Cifrado

- **Activado**: define `JW_PRIVACY_KEY` (Fernet base64 — usa `jw keygen` para generar una).
- **Desactivado**: no definas la variable. Verás un warning al primer uso.
- **Silenciar el warning** sin activarlo: `export JW_FIELD_DISABLE_ENCRYPTION=1`. No recomendado.
- **Si pierdes la clave**: los datos cifrados son irrecuperables. Guarda la clave en tu gestor de contraseñas.

## Modalidades (tags)

Vocabulario por defecto: `street, return_visit, bible_study, online, phone, cart, letter, other`.

Para añadir locales propios (ej. `hospital`, `prison`) crea
`~/.jw-agent-toolkit/field_service_tags_local.json`:

```json
{"add": ["hospital", "prison"], "remove": []}
```

## Reglas de agregación importantes

- **Horas**: suma directa de las entries del mes. Display redondeado a múltiplos de 5 min según práctica vigente.
- **Cursos bíblicos activos**: se reporta el **máximo** durante el mes. Un curso empezado el 4 y cerrado el 25 cuenta, así como uno empezado el 25 y aún abierto al cierre. Esta convención evita penalizar cierres mediados del mes.
- **Revisitas**: cuenta de entradas en `revisit_tracker` cuya fecha de actualización cae dentro del mes. Se muestra aparte de `tag.return_visit` (que son horas, no contactos).

## Una semana en la vida de un precursor

```bash
# lunes
jw report log-hours --hours 3.0 --tag street --note "centro"
jw report log-study --student-alias luis --started 2026-05-01

# martes
jw report log-hours --hours 2.0 --tag cart
jw report met-today --student-alias luis

# miércoles
jw report log-hours --hours 1.5 --tag return_visit

# jueves
jw report log-hours --hours 4.0 --tag online --note "Zoom con tres revisitas"

# viernes
jw report log-hours --hours 2.0 --tag letter

# sábado
jw report log-hours --hours 5.0 --tag street
jw report met-today --student-alias luis

# domingo
jw report log-hours --hours 1.5 --tag phone

# fin de semana del mes
jw report --month 2026-05
```

## MCP

Tres herramientas equivalentes para Claude Desktop / cualquier cliente MCP:

- `field_log_hours(hours_decimal, date, tag, note)`
- `field_log_study(student_alias, started, closed, met_today, note)`
- `field_monthly_report(month, include_revisits, format)`

## Lo que no hace (por diseño)

- No exporta a S-21 oficial — esto es uso personal.
- No sincroniza entre dispositivos.
- No envía nada a la nube ni a la congregación.
- No reemplaza el informe que entrega el precursor: lo asiste.
