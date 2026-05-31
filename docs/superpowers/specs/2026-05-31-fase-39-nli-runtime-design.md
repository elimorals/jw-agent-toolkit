# Fase 39 — `nli-runtime`: entailment semántico en vivo sobre cada `Finding`

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (confianza en runtime)
> **Depende de**: ninguna fase nueva. Reutiliza `AgentResult`/`Finding`/`Citation` (Fase 7), patrón de provider triple-target (Fase 33), y golden cases L2 (Fase 22).
> **Habilita**: Fase 40 (`content-provenance`) reusa el `metadata` channel; Fase 44 (`synth-judge`) llama a `evaluate_entailment` para filtrar Q&A sintético.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

Hoy el toolkit garantiza que toda afirmación de un agente carga una `Citation` con URL canónica de wol.jw.org. Pero **no garantiza que el `summary` del `Finding` se desprenda lógicamente del passage citado**. El gap es real: un parser puede recortar un párrafo dejando una `excerpt` correcta y un `summary` que extrapola más allá del texto; un agente puede combinar dos findings y producir un resumen que ninguno de los dos sustenta individualmente; un futuro plugin (Fase 41) puede ser hostil o descuidado.

Fase 22 (`jw-eval`) cubre este riesgo **offline**, sobre golden cases curados, antes del merge. La Fase 39 lo cubre **online**, sobre cada output de cada agente, en cada llamada. Es la red de seguridad complementaria: cuando un usuario invoca `apologetics(question="…")` desde Claude Desktop o desde un script, cada `Finding` retornado lleva — opcionalmente — un veredicto NLI (`entails` / `neutral` / `contradicts`) y un score 0-1 que mide si el `summary` se desprende del `excerpt` que la `Citation` ancla.

Esto convierte una garantía cultural ("siempre citamos") en una garantía **semántica verificable en runtime** ("la cita realmente respalda lo que decimos"). Y deja la decisión última al consumidor (warn vs. reject) vía decorador configurable.

## Objetivos (en orden de prioridad)

1. **Verificar entailment claim ↔ premise** en cada `Finding` retornado por agentes envueltos con `@fidelity_wrap`, sin red por defecto en tests.
2. **Proveer 4 providers triple-target** (api / mlx / nvidia / cpu) con auto-detección y fallback determinístico, siguiendo el patrón de Fase 33 (embed/rerank).
3. **Anotar `Finding.metadata`** con `nli_verdict` + `nli_score` + `nli_provider` para que el LLM llamante decida cómo presentar al usuario, y para que Fase 43 (`agent-tracing`) registre veredictos en el trace.
4. **No bloquear por defecto**: el modo default es `on_fail="warn"` (se anota la advertencia en `AgentResult.warnings`). `on_fail="reject"` es opt-in para superficies estrictas (CLI/MCP en modo `--strict`, eval suite L4).
5. **Cero costo en CI público**: `FakeNLI` es determinista, sin red, sin pesos descargados. Es el fallback final del factory.

## No-objetivos (boundaries vinculantes)

Estas líneas **no** las cruza Fase 39 — explícitas para evitar scope creep y confusión con módulos vecinos:

- **No reemplaza `fact_checker` (Fase 9)**. `fact_checker` verifica que un claim **existe** en publicaciones JW oficiales (recall over JW corpus). NLI verifica que un `summary` **se desprende** del passage exacto ya citado (precision sobre la cita). Son ortogonales y complementarios. Un finding puede pasar `fact_checker` (la URL existe) pero fallar NLI (el resumen sobre-interpreta), y viceversa.
- **No es eval estática**. Fase 22 (`jw-eval`) sigue siendo el benchmark pre-merge sobre golden cases. Fase 39 es runtime, sobre cada llamada real, sobre datos arbitrarios. Las dos coexisten: Fase 22 puede usar Fase 39 como un layer adicional (L4 future), pero Fase 39 **no** depende de tener golden cases.
- **No enforza dogma específico JW**. NLI es un test puramente lógico: ¿el texto B se desprende del texto A? No mira si A es teológicamente correcto, ni si B es doctrinalmente sano. Sólo mide entailment textual. La autoridad doctrinal viene de la URL canónica, no del NLI.
- **No reescribe `Finding` ni `summary`**. La fase es **observacional**: añade metadata, dispara warnings, opcionalmente rechaza. No reescribe el summary para "arreglarlo" — eso sería poner LLM en el camino crítico, violando principio #1.
- **No persiste veredictos a disco**. La metadata vive en el AgentResult retornado. La persistencia (analytics, dashboards) es territorio de Fase 43 (`agent-tracing`).
- **No es decisión final para el usuario**. Un score 0.65 no significa "esta cita es mala"; significa "el LLM llamante debería mirarlo con más cuidado". El decorador es una vara de medir, no un censor.

## Arquitectura

Nuevo módulo `packages/jw-core/src/jw_core/fidelity/` (vive en `jw-core` porque el Protocol y los providers son reusables — Fase 44 los llamará desde `jw-finetune`). El decorador vive en `jw-agents` porque es donde se conoce `AgentResult`.

### File map

```
packages/jw-core/src/jw_core/fidelity/
├── __init__.py             # re-exporta NLIProvider, NLIVerdict, evaluate, factory
├── verdicts.py             # NLIVerdict dataclass + Literal["entails","neutral","contradicts"]
├── nli.py                  # NLIProvider Protocol + evaluate_entailment helper
├── factory.py              # get_default_nli_provider() + JW_NLI_PROVIDER env override
└── nli_providers/
    ├── __init__.py
    ├── deberta_mnli.py     # DeBERTa-v3-large-mnli (transformers, CPU/MPS/CUDA)
    ├── claude_nli.py       # ClaudeNLI (anthropic SDK, structured prompt)
    ├── openai_nli.py       # OpenAINLI (openai SDK, structured prompt)
    ├── ollama_nli.py       # OllamaNLI (llama3.1-based, local)
    └── fakes.py            # FakeNLI (deterministic stub for tests)

packages/jw-agents/src/jw_agents/
└── fidelity_wrap.py        # @fidelity_wrap decorator
```

### Provider Protocol (`fidelity/nli.py`)

```python
from typing import Protocol, runtime_checkable, Literal
from dataclasses import dataclass

Target = Literal["api", "mlx", "nvidia", "cpu"]
Verdict = Literal["entails", "neutral", "contradicts"]

@dataclass(frozen=True)
class NLIVerdict:
    verdict: Verdict       # discrete label
    score: float           # 0..1, confidence in verdict
    provider: str          # provider.name for traceability
    raw: dict              # provider-specific debug payload (optional)

@runtime_checkable
class NLIProvider(Protocol):
    name: str
    target: Target

    def is_available(self) -> bool: ...

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict: ...
```

Reglas duras de diseño (heredadas de Fase 33):

1. **Sin red en import time**. Los providers locales hacen `import transformers` lazy dentro de `is_available()`.
2. **`is_available()` es barato** (chequea env var, presencia del package, hardware). Llamado en cada `get_default_nli_provider()`.
3. **`evaluate` es sync** (no `async`). Si el provider es API-backed (Claude/OpenAI), wrappea con `anyio.from_thread.run_sync` en el call site; mantenemos la API simple porque el decorador en `jw-agents` ya es async-aware.
4. **`score` es siempre 0..1**, normalizado por el provider. DeBERTa devuelve softmax sobre 3 clases → tomamos `prob[entails]`. LLMs devuelven JSON estructurado con `confidence: float`.
5. **`language` es input para LLM providers** (afecta prompt); los modelos NLI multilingual (DeBERTa-v3-mnli es xnli-friendly) ignoran este parámetro internamente.

### Decorator (`jw_agents/fidelity_wrap.py`)

```python
from typing import Callable, Awaitable, Literal
from functools import wraps
from jw_agents.base import AgentResult
from jw_core.fidelity import get_default_nli_provider, NLIProvider

OnFail = Literal["warn", "reject", "annotate_only"]

def fidelity_wrap(
    *,
    min_score: float = 0.7,
    on_fail: OnFail = "warn",
    provider: NLIProvider | None = None,
    min_excerpt_chars: int = 32,
) -> Callable:
    """Wrap an async agent so every Finding gets NLI-checked.

    Args:
        min_score: threshold below which the verdict counts as failure.
        on_fail:
          - "annotate_only" → just attach nli_* metadata, no warnings.
          - "warn"          → also append AgentResult.warnings entry.
          - "reject"        → also drop the Finding from the result.
        provider: explicit NLIProvider, else `get_default_nli_provider()`.
        min_excerpt_chars: skip NLI when excerpt is shorter than this
                           (avoids meaningless evaluation on labels).
    """
    def deco(fn: Callable[..., Awaitable[AgentResult]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> AgentResult:
            result = await fn(*args, **kwargs)
            nli = provider or get_default_nli_provider()
            kept: list = []
            for f in result.findings:
                if len(f.excerpt) < min_excerpt_chars:
                    f.metadata["nli_verdict"] = "skipped"
                    kept.append(f)
                    continue
                v = nli.evaluate(claim=f.summary, premise=f.excerpt,
                                 language=result.metadata.get("language", "en"))
                f.metadata["nli_verdict"] = v.verdict
                f.metadata["nli_score"] = round(v.score, 4)
                f.metadata["nli_provider"] = v.provider
                failed = v.verdict != "entails" or v.score < min_score
                if not failed:
                    kept.append(f)
                    continue
                if on_fail == "annotate_only":
                    kept.append(f)
                elif on_fail == "warn":
                    result.warnings.append(
                        f"Low NLI fidelity ({v.verdict}, score={v.score:.2f}) "
                        f"for citation {f.citation.url}"
                    )
                    kept.append(f)
                elif on_fail == "reject":
                    result.warnings.append(
                        f"Rejected finding (NLI={v.verdict}, score={v.score:.2f}) "
                        f"for citation {f.citation.url}"
                    )
                    # do NOT append → finding dropped
            result.findings = kept
            result.metadata["nli_min_score"] = min_score
            result.metadata["nli_on_fail"] = on_fail
            return result
        return wrapper
    return deco
```

Decisiones de diseño:

- **`claim = Finding.summary`, `premise = Finding.excerpt`** por defecto. Es el matching natural: el resumen debe desprenderse del excerpt verbatim que la cita ancla.
- **`min_excerpt_chars=32`** evita evaluar findings tipo `Citation kind=verse` con excerpt `"Juan 3:16"` (la referencia es la cita, no la premise lógica).
- **`on_fail="reject"` modifica `result.findings`** — esta es la única vez que la fase modifica el resultado. Documentado en el changelog del agente.

### Triple-target factory (`fidelity/factory.py`)

Mismo patrón que `jw_rag.rerank_providers.factory`:

```python
PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]
ENV_NLI = "JW_NLI_PROVIDER"  # explicit override (e.g. "claude", "fake-deberta")
ENV_ORDER = "JW_PROVIDER_ORDER"  # shared with embed/rerank

def get_default_nli_provider() -> NLIProvider: ...
def list_available_providers() -> list[NLIProvider]: ...
```

Registry order (priorizando precisión > velocidad > coste):
1. `ClaudeNLI` (api) — calidad SOTA, multi-lingual, opt-in.
2. `OpenAINLI` (api) — calidad SOTA, opt-in.
3. `DeBERTaV3MNLI(target="mlx")` — Apple Silicon optimizado vía `mlx-transformers`.
4. `DeBERTaV3MNLI(target="nvidia")` — CUDA si está disponible.
5. `DeBERTaV3MNLI(target="cpu")` — fallback PyTorch CPU.
6. `OllamaNLI` — local server-based, multi-modelo (Llama 3.1, Qwen 2.5).
7. `FakeNLI` — siempre disponible, determinístico.

## Cada provider en detalle

### `ClaudeNLI` (api / extra `[nli-anthropic]`)

- **Modelo**: `claude-sonnet-4-5-20250929` por default (env `JW_NLI_CLAUDE_MODEL`).
- **Prompt** (system): `"You are an NLI judge. Decide if the CONCLUSION strictly entails from the PREMISE. Reply JSON-only: {\"verdict\": \"entails\"|\"neutral\"|\"contradicts\", \"score\": 0.0-1.0, \"reason\": \"...\"}."`.
- **Prompt** (user): `"PREMISE:\n{premise}\n\nCONCLUSION:\n{claim}\n\nLanguage: {language}"`.
- **Parsing**: `json.loads` con fallback a `verdict="neutral", score=0.5` ante parse error.
- **Cost guard**: si `len(premise) + len(claim) > 8000 chars` (~2000 tokens), trunca premise por el final preservando los primeros 6000 chars.
- **Caching**: aprovecha Anthropic prompt caching marcando el system prompt como `cache_control: {"type": "ephemeral"}` — reduce coste ~80% en runs repetidos del mismo agente.
- **`is_available()`**: `anthropic` instalado **Y** `os.getenv("ANTHROPIC_API_KEY")` definido.

### `OpenAINLI` (api / extra `[nli-openai]`)

- **Modelo**: `gpt-4o-mini` por default (env `JW_NLI_OPENAI_MODEL`).
- **Structured output**: usa `response_format={"type": "json_schema", "json_schema": {...}}` para garantizar shape.
- **`is_available()`**: `openai` instalado **Y** `OPENAI_API_KEY` definido.

### `DeBERTaV3MNLI` (mlx / nvidia / cpu, extra `[nli-local]`)

- **Modelo**: `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` (≈440MB, Apache 2.0). Alternativa multilingual: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` para es/pt.
- **Implementación**:
  - target=`mlx`: vía `mlx-transformers` (opt-in). Si no disponible → instancia no se incluye en registry.
  - target=`nvidia`: vía `transformers` + `torch.cuda` checks.
  - target=`cpu`: vía `transformers` (siempre fallback).
- **Inference**: tokeniza `(premise, claim)` como pair-sequence, softmax sobre 3 logits (`contradiction=0, neutral=1, entailment=2`).
- **Score**: `prob[entailment]`. Verdict: `argmax`.
- **Truncation**: `max_length=512` con `truncation="only_first"` (preserva claim, recorta premise).
- **`is_available()`**: `transformers` + `torch` instalados; para mlx además `mlx_transformers`; para nvidia además `torch.cuda.is_available()`.
- **Carga lazy + singleton**: el modelo se carga la primera vez que `evaluate` es llamado, no en `__init__`. Cacheado a nivel de instancia.

### `OllamaNLI` (local server)

- **Modelo default**: `llama3.1:8b-instruct` (env `JW_NLI_OLLAMA_MODEL`).
- **Endpoint**: `http://localhost:11434/api/chat` (env `OLLAMA_HOST`).
- **Prompt**: idéntico a Claude/OpenAI con `format=json` flag de Ollama.
- **`is_available()`**: GET a `${OLLAMA_HOST}/api/tags` exitoso **Y** el modelo configurado aparece en la lista. (Cacheado por proceso.)
- **Útil para**: usuarios sin API key y sin GPU NVIDIA — la opción "buena" gratis local.

### `FakeNLI` (siempre disponible)

- **Algoritmo determinista** sin pesos descargados:
  - `verdict = "entails"` si `set(words(claim)) <= set(words(premise))` con cobertura ≥ 80%.
  - `verdict = "contradicts"` si aparece negación explícita (`"no es"`, `"is not"`, `"não é"`) en exactamente uno de los dos.
  - else `verdict = "neutral"`.
  - `score = round(jaccard(words(claim), words(premise)), 2)`.
- **Propósito**: tests determinísticos del decorador y del factory; default cuando ningún provider real está disponible.
- **Nombre**: `name = "fake-nli"`; target `"cpu"`.

## Integración con el resto del toolkit

### Agentes (default opt-in)

Los 12 agentes existentes **no se modifican** en esta fase. Se publica el decorador y se documenta cómo aplicarlo. En la Fase 39.1 (follow-up del PR principal) se envuelven los 4 agentes más usados con `@fidelity_wrap(min_score=0.7, on_fail="warn")`:

- `apologetics`
- `verse_explainer`
- `research_topic`
- `meeting_helper`

El wrap es **idempotente**: aplicarlo dos veces no produce metadata duplicada (chequea `nli_verdict` presente).

### CLI (`jw-cli`)

Nuevo flag global `--fidelity {off,warn,reject}` (default `warn` cuando hay provider disponible; `off` si solo `FakeNLI`):

```bash
jw apologetics --question "..." --fidelity reject
jw apologetics --question "..." --fidelity off    # disable for speed
jw verse --reference "Juan 3:16" --fidelity warn  # default
```

Implementación: el comando aplica `fidelity_wrap` al callable del agente justo antes de invocarlo si el flag no es `off`.

### MCP (`jw-mcp`)

Cada tool de agente gana un parámetro opcional `fidelity: Literal["off","warn","reject"] = "warn"`. Implementación idéntica al CLI: wrap al callable antes de despachar.

Nueva tool standalone `evaluate_nli(claim: str, premise: str, language: str = "en") -> dict`:

```json
{"verdict": "entails", "score": 0.87, "provider": "claude-nli"}
```

Útil para integraciones externas (un cliente puede pedir verificación de un par texto sin invocar un agente completo).

### Eval suite (Fase 22)

Layer 4 futuro (opcional, no obligatorio en esta fase): `eval/layers/fidelity.py` aplica NLI sobre los findings emitidos en L3 y bloquea si > X% caen bajo `min_score`. Documentado como follow-up.

### `jw-finetune` (Fase 44)

Fase 44 (`synth-judge`) llamará `evaluate_entailment(claim=qa.answer, premise=passage)` para filtrar Q&A sintético. La API es la misma — no se duplica nada.

## Extras de `pyproject.toml`

```toml
[project.optional-dependencies]
nli-anthropic = ["anthropic>=0.40,<1.0"]
nli-openai = ["openai>=1.50,<2.0"]
nli-local = [
  "transformers>=4.45,<5.0",
  "torch>=2.4",
  "sentence-transformers>=3.0,<4.0",  # used for tokenizer utilities
]
nli-mlx = [
  "mlx>=0.18; platform_system=='Darwin' and platform_machine=='arm64'",
  "mlx-transformers>=0.1; platform_system=='Darwin' and platform_machine=='arm64'",
]
nli-all = ["jw-core[nli-anthropic,nli-openai,nli-local,nli-mlx]"]
```

CI público instala `nli-local` (CPU torch) **únicamente en el job nocturno**; el job estándar usa `FakeNLI`. El extra `nli-mlx` se compila solo en self-hosted runner macOS si lo añadimos en el futuro.

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_NLI_PROVIDER` | (auto) | Override explícito: `claude`, `openai`, `deberta`, `ollama`, `fake-deberta`, `fake-nli` |
| `JW_NLI_CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Modelo Anthropic |
| `JW_NLI_OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI |
| `JW_NLI_OLLAMA_MODEL` | `llama3.1:8b-instruct` | Modelo local Ollama |
| `JW_NLI_MIN_SCORE` | `0.7` | Threshold default si el decorador no especifica |
| `JW_PROVIDER_ORDER` | `api,mlx,nvidia,cpu` | Compartido con embed/rerank (Fase 33) |
| `ANTHROPIC_API_KEY` | — | Necesario para ClaudeNLI |
| `OPENAI_API_KEY` | — | Necesario para OpenAINLI |
| `OLLAMA_HOST` | `http://localhost:11434` | Servidor Ollama |

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | NLI rechaza paráfrasis legítimas (falsos negativos) | `on_fail="warn"` default; `min_score=0.7` permisivo; threshold configurable por agente; documentar que paráfrasis sinonímica es esperada |
| 2 | El `excerpt` está vacío o trivial → NLI evalúa basura | `min_excerpt_chars=32` skip + `nli_verdict="skipped"` explícito |
| 3 | NLI con sesgo cultural/doctrinal del corpus de entrenamiento | Default `on_fail="warn"` nunca rechaza; multi-modelo (Claude + DeBERTa + Ollama) permite cross-check; documentar que NLI mide lógica textual, no doctrina |
| 4 | Latencia alta en runtime (especialmente DeBERTa-large CPU: ~1s/finding) | Tres mitigaciones: (a) modelo `base` opcional (~80MB, ~150ms); (b) `on_fail="off"` siempre disponible; (c) paralelización: el decorador puede lanzar `n` evaluaciones concurrentes via `asyncio.gather` cuando el provider es API |
| 5 | Coste API en producción heavy users | Prompt caching Anthropic (~80% reducción); `fake-nli` para dev; documentar costes por 1k findings |
| 6 | DeBERTa max_length=512 trunca premises largas | `truncation="only_first"` preserva el `claim` (más corto); para excerpts >512 tokens se documenta como limitación y se sugiere chunking previo |
| 7 | LLM judge alucina JSON inválido | Try/except → fallback `verdict="neutral", score=0.5` con warning logueado; nunca raise |
| 8 | Provider locales aumentan footprint del paquete | Todos detrás de extras `[nli-*]`; default `FakeNLI` no añade nada al base install |
| 9 | El decorador modifica `findings` con `on_fail="reject"` → cambio semántico | Documentado en docstring; warning siempre acompaña al drop; default es `"warn"` no `"reject"` |
| 10 | Race condition en lazy model loading bajo concurrencia | Lock por instancia en primer `evaluate`; modelo singleton garantizado |

## Métricas de éxito de la fase

- ✅ `evaluate_entailment(claim, premise)` funciona para los 5 providers (4 reales + 1 fake) sobre 20 pares de prueba.
- ✅ `@fidelity_wrap` aplicado a los 4 agentes principales **no rompe** ninguno de los 1984 tests existentes (modo default = `warn` no muta findings).
- ✅ Sobre los 30 golden cases L1+L2 de Fase 22, ≥95% de los findings emitidos pasan NLI con `score ≥ 0.7` usando `ClaudeNLI` (medido en el job nightly de CI).
- ✅ `FakeNLI` es 100% determinístico: misma input → misma output, sin red, sin pesos.
- ✅ `jw apologetics --fidelity warn` añade `nli_*` a cada finding y muestra warnings en stderr cuando aplica.
- ✅ MCP tool `evaluate_nli` documentada en `docs/referencia/jw-mcp.md`.
- ✅ Latencia P50 < 800ms por finding con DeBERTa-base CPU; < 250ms con ClaudeNLI (con caching tras primer call).
- ✅ Guía nueva en `docs/guias/fidelity-nli.md` con ejemplos, costes, troubleshooting.
- ✅ Audit 1:1 actualizado en `docs/VISION_AUDIT.md`.

## Cómo verificar al cerrar

```bash
# 1. Instalar extras NLI local CPU
uv sync --all-packages --extra nli-local

# 2. Tests deterministas (sin red, sin pesos)
.venv/bin/python -m pytest packages/jw-core/tests/test_fidelity_*.py
.venv/bin/python -m pytest packages/jw-agents/tests/test_fidelity_wrap.py

# 3. Smoke con FakeNLI sobre apologetics
JW_NLI_PROVIDER=fake-nli uv run jw apologetics --question "¿Qué es el alma?" --fidelity warn

# 4. Smoke con DeBERTa CPU (descarga modelo la primera vez)
JW_NLI_PROVIDER=deberta uv run jw apologetics --question "¿Qué es el alma?" --fidelity warn

# 5. Smoke con Claude API (requiere ANTHROPIC_API_KEY)
JW_NLI_PROVIDER=claude uv run jw apologetics --question "¿Qué es el alma?" --fidelity warn

# 6. Eval suite L1+L2 sigue verde (Fase 22 no regresiona)
uv run jw eval --layer 1,2
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-39-nli-runtime-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos (cada uno = 1 PR atómico con tests):

1. **Scaffold `jw_core/fidelity/`** con `verdicts.py` + `nli.py` (Protocol) + `__init__.py` re-exports. Tests Pydantic.
2. **`FakeNLI`** en `nli_providers/fakes.py` con algoritmo determinista + tests de 10 pares conocidos.
3. **`factory.py`** con `get_default_nli_provider()` + `JW_NLI_PROVIDER` env + tests del registry order.
4. **`DeBERTaV3MNLI`** (cpu target primero) con tokenization + inference + score normalization. Tests con `transformers` instalado en el job nightly; `pytest.skip` en CI estándar.
5. **`ClaudeNLI`** con prompt + JSON parse + prompt caching. Tests con `FakeAnthropicClient` que devuelve JSONs canned.
6. **`OpenAINLI`** con structured output. Tests con `FakeOpenAIClient`.
7. **`OllamaNLI`** con HTTP client + `format=json`. Tests con `respx` mocking del endpoint.
8. **`DeBERTaV3MNLI` targets mlx + nvidia** (auto-detect; tests skip si no hay hardware).
9. **`@fidelity_wrap`** en `jw_agents/fidelity_wrap.py` con `on_fail={annotate_only,warn,reject}` + skip por `min_excerpt_chars` + idempotencia. Tests con `FakeNLI`.
10. **Aplicar `@fidelity_wrap` a 4 agentes** (`apologetics`, `verse_explainer`, `research_topic`, `meeting_helper`) en modo `warn`. Tests verifican que findings no se modifican en modo `warn` con `FakeNLI`.
11. **CLI flag `--fidelity`** en `jw-cli` con tests de Typer.
12. **MCP param `fidelity`** + tool `evaluate_nli` en `jw-mcp` con tests del transport.
13. **Pyproject extras `[nli-*]`** + CI matrix nightly que instala `nli-local` y corre tests + 30 golden cases con score reporting.
14. **Guía `docs/guias/fidelity-nli.md`** con ejemplos, costes API, troubleshooting (descarga modelo, timeouts Ollama, Apple Silicon mlx).
15. **Audit 1:1** en `docs/VISION_AUDIT.md` + entry en `CHANGELOG.md`.

Cada paso con su PR + tests + sin regresiones en los tests existentes (target = 1984 → 2050+ tras esta fase).
