# Fidelidad NLI en runtime (`jw_core.fidelity`)

> Fase 39 — verificación de entailment semántico claim ↔ premise sobre cada `Finding` que devuelve un agente. Spec: `docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md`.

## Para qué sirve

Garantiza, en cada llamada real, que el `summary` de un `Finding` se desprende lógicamente del `excerpt` verbatim que su `Citation` ancla. Complementa Fase 22 (eval doctrinal offline pre-merge) extendiendo la red al runtime.

Cada finding verificado lleva en `metadata`:

```json
{
  "nli_verdict": "entails | neutral | contradicts | skipped",
  "nli_score": 0.87,
  "nli_provider": "claude-nli"
}
```

## Modos de operación

| Modo | Qué hace | Cuándo |
|---|---|---|
| `off` | No evalúa, no anota. | CLI con `--fidelity off` para máxima velocidad. |
| `annotate_only` | Sólo añade metadata, sin warnings ni drops. | Uso programático, telemetría. |
| `warn` (default) | Metadata + warning en `AgentResult.warnings` si score < threshold. | CLI y MCP por defecto. |
| `reject` | Warn + DROP del finding del resultado. | Superficies estrictas (`--fidelity reject`). |

## Providers disponibles

Orden de auto-detección (puede sobreescribirse con `JW_NLI_PROVIDER`):

1. **`claude-nli`** — Anthropic Claude (mejor calidad, multi-lingüe). Extra `[nli-anthropic]` + `ANTHROPIC_API_KEY`.
2. **`openai-nli`** — OpenAI gpt-4o-mini. Extra `[nli-openai]` + `OPENAI_API_KEY`.
3. **`deberta-v3-mnli`** — DeBERTa-v3-large-mnli, local. Extra `[nli-local]` (instala torch + transformers). Detecta automáticamente Apple Silicon (MLX), CUDA (NVIDIA), CPU.
4. **`ollama-nli`** — Llama 3.1 local vía Ollama HTTP. Requiere `ollama serve` corriendo.
5. **`fake-nli`** — heurística pura (containment del claim + detección de negación asimétrica). Siempre disponible, determinista, sin red. Default en CI.

## Uso desde CLI

```bash
# Modo warn (default) — siempre se anota, warnings si falla
uv run jw apologetics "¿Es la Trinidad bíblica?" --fidelity warn

# Off (sin verificación, máxima velocidad)
uv run jw apologetics "?" --fidelity off

# Reject (drop estricto de findings que no aprueban)
uv run jw apologetics "?" --fidelity reject

# Forzar provider específico
JW_NLI_PROVIDER=claude-nli uv run jw apologetics "?" --fidelity warn
```

## Uso desde MCP

El tool `apologetics` gana un parámetro opcional `fidelity` con los mismos valores. Nuevo tool standalone:

```json
{
  "name": "evaluate_nli",
  "arguments": {
    "claim": "La Trinidad no es bíblica",
    "premise": "Las Escrituras presentan a un solo Dios",
    "language": "es"
  }
}
```

Devuelve `{"verdict": "entails|neutral|contradicts", "score": 0.87, "provider": "claude-nli"}`.

## Uso desde Python

```python
from jw_core.fidelity import evaluate_entailment

v = evaluate_entailment(
    claim="The Trinity is not a Bible teaching.",
    premise="The Bible teaches there is one God, the Father.",
    language="en",
)
print(v.verdict, v.score, v.provider)
```

Para envolver un agente custom:

```python
from jw_agents.fidelity_wrap import fidelity_wrap

@fidelity_wrap(min_score=0.7, on_fail="warn")
async def my_agent(question: str) -> AgentResult:
    ...
```

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_NLI_PROVIDER` | (auto) | Override: `claude-nli`, `openai-nli`, `deberta-v3-mnli`, `ollama-nli`, `fake-nli`. |
| `JW_NLI_CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Modelo Anthropic. |
| `JW_NLI_OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI. |
| `JW_NLI_OLLAMA_MODEL` | `llama3.1:8b-instruct` | Modelo local Ollama. |
| `JW_NLI_DEBERTA_MODEL` | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | Modelo HF. |
| `JW_PROVIDER_ORDER` | `api,mlx,nvidia,cpu` | Reordena el ranking de targets (compartido con Fase 33). |
| `OLLAMA_HOST` | `http://localhost:11434` | Servidor Ollama. |
| `ANTHROPIC_API_KEY` | — | Necesario para `claude-nli`. |
| `OPENAI_API_KEY` | — | Necesario para `openai-nli`. |

## Algoritmo del FakeNLI

`FakeNLI` no usa red ni modelos. Calcula la proporción de tokens del claim presentes en el premise (containment) y detecta negación explícita asimétrica (`is not`/`no es`/`não é`/etc.).

- Si negación aparece en exactamente uno de claim/premise → `contradicts`.
- Si containment ≥ 0.5 → `entails`.
- En cualquier otro caso → `neutral`.
- `score = round(containment, 2)`.

Esto lo hace 100% determinista y suficientemente útil para CI: las suites pueden assertear sobre verdict sin instalar dependencias pesadas ni hablar con APIs externas.

## Costes orientativos

| Provider | Coste por 1k findings (premise ≤2k tokens) | Latencia P50 |
|---|---|---|
| `claude-nli` (Sonnet 4.5, con prompt caching) | ~$0.30 | ~250ms |
| `openai-nli` (gpt-4o-mini) | ~$0.15 | ~400ms |
| `deberta-v3-mnli` (CPU) | $0 | ~800ms |
| `deberta-v3-mnli` (CUDA) | $0 | ~50ms |
| `ollama-nli` (llama3.1:8b) | $0 | ~1500ms |
| `fake-nli` | $0 | <1ms |

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `nli_verdict="skipped"` en todos los findings | excerpts <32 chars | revisa parser; o baja `min_excerpt_chars` en el decorador |
| `nli_verdict="contradicts"` en findings buenos | paráfrasis sinonímica + provider estricto | usa `claude-nli` o sube `min_excerpt_chars` |
| `RuntimeError: not available` al iniciar | `JW_NLI_PROVIDER` apunta a un provider sin deps/keys | quita el env var o instala el extra correspondiente |
| ~1s/finding extra en CLI | DeBERTa CPU es lento | usa `--fidelity off`, o `JW_NLI_PROVIDER=claude-nli` |
| Costes API explotan | sin caching o muchos findings | habilita Anthropic prompt caching (default), baja agentes o usa `fake-nli` para dev |

## Política para fases nuevas

Toda fase que añada un agente nuevo debe documentar si lo envuelve con `@fidelity_wrap` y bajo qué modo por defecto. Las superficies CLI/MCP heredan automáticamente el flag `--fidelity` cuando se basan en estos decoradores.

## Test surface

- 4 tests Protocol (`test_fidelity_nli_protocol.py`)
- 7 tests `NLIVerdict` (`test_fidelity_verdicts.py`, incluyendo NaN-safety)
- 10 tests `FakeNLI` (`test_fidelity_fakes.py`)
- 8 tests factory (`test_fidelity_factory.py`)
- 10 tests `ClaudeNLI` con FakeAnthropicClient (`test_fidelity_claude.py`)
- 7 tests `OpenAINLI` con FakeOpenAIClient (`test_fidelity_openai.py`)
- 7 tests `DeBERTaV3MNLI` con fake tokenizer/model
- 6 tests `OllamaNLI` con `httpx.MockTransport`
- 29 tests del decorator (`test_fidelity_wrap.py`)
- 3 tests integración (`test_fidelity_integration.py`)
- 5 tests CLI (`test_cli_fidelity.py`)
- 5 tests MCP (`test_mcp_nli.py`)
- 6 hypothesis properties (`test_fidelity_property.py`)

**Total: ~107 tests nuevos.** Toda la suite global pasa: 2063 passed, 52 skipped.
