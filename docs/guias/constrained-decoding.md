# Constrained decoding (`jw_core.grammar`)

> Fase 35. Spec en `docs/superpowers/specs/2026-05-31-fase-35-constrained-decoding-design.md`.

## Qué resuelve

Cuando un LLM externo (Claude Desktop, Claude Code, MCP client) consume un
`AgentResult`, puede:

1. Eliminar las citas.
2. Inventar URLs con apariencia de `wol.jw.org`.
3. Truncar el JSON estructurado.
4. Mutar el shape del objeto.

Esta fase blinda esos cuatro vectores a nivel de **decodificación**:

- Gramática GBNF sobre el sampler local (Ollama / llama-cpp-python).
- Tool-use con `input_schema` en Anthropic.
- `response_format=json_schema strict=true` en OpenAI.
- Reconciliación que rechaza URLs no presentes en el resultado procedural.

## Uso CLI

```bash
# Auto-detecta provider (Ollama → Anthropic → OpenAI → Fake).
JW_LLM_PROVIDER=auto uv run jw constrained ask \
    --agent verse_explainer \
    --input '{"text":"John 3:16","language":"en"}'

# Forzar Anthropic (requiere ANTHROPIC_API_KEY + extra grammar-claude).
JW_LLM_PROVIDER=anthropic uv run jw constrained ask --agent apologetics \
    --input '{"question":"Is the Trinity biblical?","language":"en"}'

# Forzar llama-cpp local con modelo .gguf.
JW_LLAMA_CPP_MODEL=~/models/llama3.1.gguf JW_LLM_PROVIDER=llama-cpp \
    uv run jw constrained ask --agent verse_explainer \
    --input '{"text":"Juan 3:16","language":"es"}'
```

El `--input` admite alias comunes para mantener una superficie estable
frente a los kwargs reales de cada agente:

| Alias en `--input`        | Kwarg real del agente |
| ------------------------- | --------------------- |
| `reference`, `verse`      | `text`                |
| `query`, `topic`, `prompt`| `question`            |

Cualquier clave desconocida se descarta silenciosamente.

## Uso programático

```python
from jw_agents.constrained import run_with_citations
from jw_agents.verse_explainer import verse_explainer

result = await run_with_citations(
    prompt="Explain John 3:16 in pastoral tone.",
    agent=lambda inp: verse_explainer(text="John 3:16", language="en"),
)
```

## Uso vía MCP

El MCP server expone `run_constrained`:

```json
{
  "name": "run_constrained",
  "arguments": {
    "agent_name": "verse_explainer",
    "input": {"text": "John 3:16", "language": "en"},
    "provider": "auto"
  }
}
```

Devuelve el `AgentResult` serializado (`to_dict()`), con las mismas
garantías que el helper Python.

## Extras opcionales

| Extra | Habilita | Instalación |
|---|---|---|
| `grammar-claude` | `AnthropicAdapter` | `uv pip install -e packages/jw-core[grammar-claude]` |
| `grammar-openai` | `OpenAIAdapter` | `uv pip install -e packages/jw-core[grammar-openai]` |
| `grammar-local` | `LlamaCppAdapter` | `uv pip install -e packages/jw-core[grammar-local]` |

Sin extras, la suite funciona contra Ollama (sin SDK extra) o contra
`FakeConstrainedCaller` (default en CI).

## Garantías

- **Shape**: Pydantic + gramática → `AgentResultModel.model_validate_json`
  nunca lanza sobre la salida.
- **URL**: regex `^https://wol\.jw\.org/[a-z]{2,3}/.+` aplicada por GBNF y
  por Pydantic.
- **Anti-forja**: cada `Finding.citation.url` debe existir en el
  `AgentResult` procedural; si no, `CitationForgeryError`.
- **Property test**: 100 prompts adversarios pasan en CI (offline).

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `CitationForgeryError` | LLM intentó inventar URL | revisa el procedural pipeline; quizás falten findings |
| Ollama responde sin shape | `JW_OLLAMA_HOST` apunta a versión <0.5 | actualiza Ollama o pásate a `[grammar-local]` |
| `NotImplementedError: grammar=` | pasaste GBNF crudo a Anthropic/OpenAI | usa `json_schema=` en su lugar |
| Test lento | property test corre 100 ejemplos | usa `-k 'not property'` en dev loop |
