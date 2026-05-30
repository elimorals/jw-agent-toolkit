# jw-agents

Agentes procedurales multipaso sobre `jw-core` + `jw-rag`.

## Filosofía

Los agentes **no son LLM-driven** — son **orquestadores procedurales** que componen clientes/parsers de `jw-core` + recuperación de `jw-rag` en pipelines deterministas que producen resultados **estructurados** (`AgentResult` con `Finding`s + `Citation`s).

El paso de **síntesis** se delega al LLM llamante (Claude Desktop, etc.), que lee la salida estructurada y genera prosa con citas verificables.

Esto los hace:

- **Testeables**: no requieren mockear un LLM.
- **Deterministas**: misma entrada → misma salida.
- **Baratos**: cero coste de API.
- **Composables**: puedes encadenarlos desde tu propia lógica LLM.

## Agentes incluidos

| Agente | Entrada | Pipeline | Salida típica |
|---|---|---|---|
| `verse_explainer` | "Juan 3:16" | resolve → fetch capítulo → versículo objetivo + notas de estudio + cross-refs | `Finding`s con verso, comentario y URLs |
| `research_topic` | "el día de Jehová" | búsqueda CDN → fetch top K → cosecha extractos | `Finding`s con extractos + URLs de artículos |
| `meeting_helper` | URL o ref bíblica | fetch → parse artículo → sugerencias de comentarios + prompts de prep | `Finding`s + `prep_prompts` + cross-refs |
| `apologetics` | Pregunta doctrinal | índice temático → refs explícitas → CDN search → RAG (opcional) | `Finding`s con `source` para ranking por autoridad |

## API base

```python
from jw_agents import AgentResult, Citation, Finding
```

Cada agente devuelve un `AgentResult` con:

- `query`: la entrada original
- `agent_name`: nombre del agente
- `findings: list[Finding]`: cada uno con `summary`, `excerpt`, `citation` y metadata
- `warnings: list[str]`: advertencias no fatales
- `metadata: dict`: contexto adicional (chapter_title, search_hits, etc.)

## Ejemplo

```python
import asyncio
from jw_agents import verse_explainer

async def main():
    result = await verse_explainer("Juan 3:16", language="es")
    for f in result.findings:
        print(f.summary)
        print(f.excerpt)
        print(f.citation.url)
        print("---")

asyncio.run(main())
```

## Referencia detallada

Ver [`docs/referencia/jw-agents.md`](../../docs/referencia/jw-agents.md) para los pipelines detallados, opciones y políticas de fallback de cada agente.
