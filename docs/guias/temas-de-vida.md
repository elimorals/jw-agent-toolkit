# Temas de vida (`life_topics`)

> Fase 32 — asistente informativo. Spec: `docs/superpowers/specs/2026-05-30-fase-32-life-topics-design.md`.

## Para qué sirve

Cuando alguien necesita saber **qué publicó la Watchtower** sobre un tema personal — ansiedad, duelo, conflicto matrimonial, soledad, dudas en la fe — y quiere material con citas verificables.

## Esto NO es consejería

(Esta sección no es decorativa. Es parte del contrato de la herramienta.)

`life_topics` es un agregador informativo. **No** sustituye:

- A los ancianos de tu congregación (1 Pedro 5:1-3).
- A tu familia.
- A cualquier profesional médico que estés viendo.

Cada respuesta del agente incluye, **siempre**, un `disclaimer` Finding. Para temas marcados como *sensibles* (ansiedad, duelo, conflicto matrimonial, depresión, adicciones, dudas en la fe), también incluye un `elders_redirect` Finding. El LLM consumidor debe preservarlos.

## Temas iniciales

| Tema | Familia | Idiomas |
|---|---|---|
| anxiety | sensible | en/es/pt |
| grief | sensible | en/es/pt |
| marriage_conflict | sensible | en/es/pt |
| depression_signs | sensible | en/es/pt |
| addictions | sensible | en/es/pt |
| doubts_in_faith | sensible | en/es/pt |
| parenting | general | en/es/pt |
| loneliness | general | en/es/pt |
| conflict_with_brother | general | en/es/pt |

## Uso CLI

```bash
jw life "anxiety" --lang en
jw life "ansiedad" --lang es
jw life "luto" --lang pt --top 3 --fetch 2
jw life "parenting" --lang en --json
```

## Uso vía MCP

Herramienta: `life_topic_info(topic_or_alias: str, language: str = "en") -> dict`.

```python
out = await life_topic_info("ansiedad", language="es")
# out["findings"] incluye al menos un source='disclaimer'
# y, si es sensible, un source='elders_redirect'
```

## Cómo se resuelven los alias

El agente normaliza acentos y minúsculas; primero busca el alias en el idioma indicado, luego hace fallback cross-language. Si nada matches, devuelve solo el disclaimer genérico.

## Lo que el agente NO hace

- No genera versículos de la Biblia "de memoria". Solo cita los que aparecen en los artículos retornados o como referencias del Topic Index.
- No sugiere terapeutas, psicólogos ni médicos por nombre.
- No guarda lo que el usuario consulta. Stateless.
- No genera "consejo personalizado". Solo agrega excerpts de material publicado.

## Si no hay material

Devuelve `warnings` describiendo el fallo + disclaimer. Eso es válido. El próximo paso correcto es el ser humano, no más automatización.

## Política de cambios

- Añadir un tema nuevo a `REGISTRY` (`jw_core/data/life_topics.py`) requiere también: actualizar disclaimers si la familia es nueva, añadir mínimo 1 golden case L1 + 1 L3, documentar aquí.
- Cambiar la familia de un tema (de `general` a `sensitive` o viceversa) requiere PR independiente con justificación.
- El texto del `elders_redirect` deliberadamente NO menciona profesionales médicos por nombre. Cambiar eso es un PR de política, no de código.
