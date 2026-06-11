---
title: "Razonador doctrinal (Fase 67)"
description: "Chain-of-thought verificable con ReAct + NLI F39 + reformulator de framing tóxico, golden set de 10 preguntas multi-paso y tool dispatcher real."
date: "2026-06-11"
---

# Razonador doctrinal (Fase 67)

> Chain-of-thought verificable sobre la Biblia y publicaciones JW. Cada
> paso del árbol queda anclado a una cita `wol.jw.org` y validado con
> NLI F39. Salida estructurada (Pydantic) lista para sintetizar.

## Quick start

```bash
# Razonar sobre una pregunta multi-paso
jw reason ask "Si Juan 1:1 dice que el Verbo era Dios, ¿cómo se concilia con Juan 14:28?"

# Limitar pasos
jw reason ask "..." --max-steps 6

# Modo NLI permisivo (no trunca en contradiction)
jw reason ask "..." --nli-mode warn

# Exportar a Markdown
jw reason ask "..." --export reason.md

# Listar idiomas
jw reason languages
```

## CLI

| Comando                | Descripción                              |
|------------------------|------------------------------------------|
| `jw reason ask "Q"`    | Razona y emite el árbol JSON             |
| `jw reason languages`  | Lista idiomas soportados (es/en/pt)      |

### Flags de `ask`

| Flag                 | Default | Efecto                                       |
|----------------------|---------|----------------------------------------------|
| `--language` / `-l`  | `es`    | `es` / `en` / `pt`                           |
| `--max-steps`        | `12`    | Cap del árbol (1-50)                         |
| `--nli-mode`         | `reject`| `off` / `warn` / `reject`                    |
| `--no-reformulate`   | `False` | Salta la reescritura de framing hostil       |
| `--no-summary`       | `False` | Salta la prosa de resumen                    |
| `--export`           | —       | Markdown del árbol al path indicado          |

## MCP

| Tool               | Descripción                              |
|--------------------|------------------------------------------|
| `doctrinal_reason` | Devuelve `ReasoningTree` Pydantic        |

## Variables de entorno

| Env                  | Default | Efecto                                  |
|----------------------|---------|-----------------------------------------|
| `JW_REASONER_LLM`    | `fake`  | Puentea a `JW_META_LLM` (F65 factory)   |
| `JW_META_LLM`        | `fake`  | Anthropic / Ollama / Fake               |
| `JW_META_NLI`        | `off`   | `auto` resuelve F39 NLI provider        |

## Arquitectura

```
                Pregunta del usuario
                       │
                       ▼
         ┌────────────────────────────┐
         │ Reformulator (Fase 67)     │
         │  - heurísticas regex       │
         │  - reescribe a forma       │
         │    neutra si toxic         │
         └─────────────┬──────────────┘
                       │ question_normalized
                       ▼
         ┌────────────────────────────┐
         │ Planner (LLM + Jinja2)     │
         │  - es/en/pt prompts        │
         │  - validación schema:      │
         │    kind, ids, depends_on   │
         └─────────────┬──────────────┘
                       │ ReasoningStep[]
                       ▼
         ┌────────────────────────────┐
         │ ReAct executor             │
         │  - tool_dispatcher por step│
         │  - NLI F39 verify          │
         │  - reject trunca el árbol  │
         └─────────────┬──────────────┘
                       │ ReasoningTree
                       ▼
         ┌────────────────────────────┐
         │ Summary prose (opt)        │
         │  - listado por kind        │
         │  - cita wol.jw.org inline  │
         └────────────────────────────┘
```

## Reformulator

Reescribe preguntas con framing hostil a forma neutra **antes** del
planificador. Heurísticas regex (sin LLM) detectan patrones como:

| Entrada                                          | Salida                                       |
|--------------------------------------------------|----------------------------------------------|
| "Demuestra que el catolicismo está equivocado"   | "¿Qué enseña la Biblia sobre catolicismo?"   |
| "Prove that Catholics are wrong about purgatory" | "What does the Bible teach about Catholics?" |
| "Refute la doctrina del purgatorio"              | "¿Qué enseña la Biblia sobre doctrina...?"   |

Se puede desactivar con `--no-reformulate`.

## NLI modes

| Mode      | Comportamiento                                            |
|-----------|-----------------------------------------------------------|
| `off`     | NLI no se ejecuta. `nli_status="skipped"`.                |
| `warn`    | NLI se ejecuta. `contradicts` se mantiene en el árbol.    |
| `reject`  | NLI se ejecuta. `contradicts` trunca el árbol ahí.        |

## Integración en F65 meta-orchestrator

`reason.doctrinal` está registrada como tool del meta-orchestrator
(`jw_agents.meta.builtin_tools`). El planner de F65 puede componer:

```json
{"steps": [
  {"id": "s1", "tool": "reason.doctrinal",
   "args": {"question": "...", "max_steps": 8, "nli_mode": "reject"}}
]}
```

## Tool dispatcher (avanzado)

El executor acepta `tool_dispatcher: Callable[[Step], Awaitable[Citation | None]]`.
Por defecto no resuelve citas (devuelve `None`). En producción se
inyecta un dispatcher que rutea por `tool_hint`:

```python
async def dispatcher(step: ReasoningStep) -> Citation | None:
    hint = step.rationale  # or read from prompt
    if "bible.get_verse" in hint:
        # call jw_agents.verse_explainer and extract a Citation
        ...
    elif "topic_index.search" in hint:
        ...
    return None
```

## Estado actual

- 7 tasks TDD completas. **41 tests passing**.
- Models con DAG validation (`Step`, `ReasoningTree`).
- Reformulator (12 patrones es/en/pt).
- Planner LLM con JSON schema validation.
- ReAct executor con NLI F39 (off/warn/reject) y truncation.
- Engine end-to-end con summary prose deterministic es/en/pt.
- CLI `jw reason {ask,languages}` + flag `--export` MD.
- MCP `doctrinal_reason` tool.
- Integración en F65 meta-orchestrator como `reason.doctrinal`.

## Pendiente (futuro)

- Tool dispatcher real wireado a `verse_explainer` / `topic_index` /
  `rag.semantic_search` (hoy es no-op por defecto).
- Resolver el `tool_hint` del planner contra el dispatcher por mapping
  explícito.
- LLM-driven summary prose (hoy es deterministic por kind).
- F31 PDF export wrapper para `ReasoningTree`.
- Golden set de 10 preguntas multi-paso con árboles esperados.
