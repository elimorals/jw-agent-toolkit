# Asistente de partes del estudiante (Vida y Ministerio)

Genera un guion estructurado de **4 secciones** (apertura / cuerpo / transición / cierre) para cualquiera de las cuatro asignaciones típicas del estudiante en la reunión de Vida y Ministerio, ajustado al **punto de oratoria del mes**.

## Tipos de asignación

| `kind` | Tiempo objetivo | Cuándo |
|---|---|---|
| `bible_reading` | 4 min | Lectura de la Biblia |
| `starting_conversation` | 3 min | Empezar conversación |
| `return_visit` | 4 min | Revisita |
| `bible_study` | 5 min | Demostración de estudio |

## CLI

```bash
# Lectura de la Biblia, español, punto explícito
jw student bible_reading "Romanos 12:1-2" --lang es --point 1

# Empezar conversación, ateo, punto auto por mes
jw student conversation "el sentido del sufrimiento" --audience atheist --lang es

# Revisita, religioso
jw student revisit "Juan 3:16" --audience religious --lang es

# Estudio bíblico, persona nueva
jw student study "esperanza de resurrección" --audience new --lang es

# JSON para canalizar a otro proceso
jw student bible_reading "Juan 3:16" --lang es --json
```

## Audiencias

- `default` — neutral.
- `new` — alguien que no conoce la Biblia.
- `religious` — alguien con trasfondo religioso.
- `atheist` — alguien sin compromiso religioso.

Si pasa una audiencia desconocida, el agente cae a `default` y deja un warning.

## Punto de oratoria

El folleto **Mejore su predicación** (`th`) tiene ~50 puntos. Cada mes el toolkit asume un punto activo (1 en enero, 5 en febrero, 9 en marzo, …). Override con `--point N`.

Lista completa en `jw_core.data.oratory_points.ORATORY_POINTS`.

## Modo "this week"

Cuando `topic_or_ref` es exactamente `this week`, el agente delega en el scraper del workbook (Fase 11) para localizar la asignación de la semana actual. Requiere red — si no hay `WOLClient` o el scraping falla, el guion se compone con tema libre y un warning.

## MCP

Herramienta `student_part_help(kind, topic_or_ref, language="en", oratory_point=None, audience="default")` disponible en `jw-mcp`. Devuelve `AgentResult.to_dict()`.

## Lo que el agente NO hace

- No reescribe la prosa: produce **plantillas** rellenadas; el LLM downstream redacta.
- No respeta automáticamente el tiempo: `time_target_seconds` es informativo.
- No registra quién recibió qué asignación.
- No reproduce la letra completa del libro `th`: usa paráfrasis ≤300 chars.
