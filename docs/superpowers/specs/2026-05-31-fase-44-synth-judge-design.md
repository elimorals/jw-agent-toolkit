# Fase 44 — `synth-judge`: filtro de calidad para Q&A sintético

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (comunidad / calidad de datos)
> **Depende de**: Fase 39 (`nli-runtime` — reusa `evaluate_entailment`)
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)
> **Predecesor conceptual**: Fase 22 (`jw-eval` — eval doctrinal offline)

## Motivación

`jw-finetune` orquesta hoy un pipeline `chunk → provider LLM → JSON Q&A → validators heurísticos → write JSONL`. Los `validators` actuales (`packages/jw-finetune/src/jw_finetune/synth/validators.py`) cubren tres ejes mecánicos:

1. `is_valid_bible_ref` — usa `jw_core.parsers.reference.parse_all_references`.
2. `length_ok` — rangos de longitud Q/A.
3. `lang_matches` — `langdetect` opcional.

Lo que **no** mide ningún validador:

- **Coherencia doctrinal** entre la respuesta y la fuente JW. Una respuesta puede tener buena longitud, idioma correcto y referencia bíblica válida, y aún así contradecir la enseñanza del pasaje citado.
- **Calidad pedagógica**. "¿Qué dice Juan 3:16?" → "Que Dios amó al mundo." pasa todos los validators heurísticos pero es inútil como ejemplo de entrenamiento (es la cita textual, no enseñanza).
- **Cita real a publicaciones JW**. Una respuesta puede mencionar "según los Testigos de Jehová..." sin citar `wol.jw.org` ni un código `w/g/jt/...`.

Sin este filtro, cada vez que el dataset sintético crezca, el ratio señal/ruido degradará el fine-tune. Fase 44 introduce un **judge en 3 etapas (heurística cheap → LLM judge opt-in → NLI runtime)** que descarta pares de baja calidad antes de que toquen `data/train.jsonl`.

## Objetivos

1. **Filtrar ≥30% de pares "ruidosos"** del baseline jw-finetune sin descartar pares válidos (precisión del filtro > 90% sobre golden set de 50 pares anotados).
2. **Cero red en el camino default**. Heurísticas son obligatorias; LLM judge y NLI son opt-in vía env.
3. **Configurable por receta**. Cada receta YAML puede sobreescribir thresholds (`strict|loose|off`).
4. **Auditable**. Cada par rechazado emite razón estructurada; las estadísticas se escriben al log de la extracción.

## No-objetivos (boundaries vinculantes)

- **No** reemplaza `validators.py`. El judge corre **después** de los validators heurísticos existentes — el orden es `validators (cheap) → judge (variable cost)`.
- **No** entrena un clasificador propio. Toda decisión es regla heurística + LLM/NLI opt-in.
- **No** produce métricas online; es exclusivamente para el pipeline de extracción/síntesis offline.
- **No** modifica el contrato de `QAPair` en `jw_finetune.data.formats`. Los scores van en `QAPair.metadata` cuando el par sobrevive; los descartados no se persisten.

## Decisión clave: ¿reusar Fase 22 (`jw-eval`) o vivir aparte?

Esta es la pregunta arquitectónica más cargada de la fase. Análisis explícito:

### Opción A — Reusar `jw-eval` directamente

`jw-eval` ya tiene:
- Judges (`embeddings.py` + `llm.py` dispatcher Ollama/Claude/OpenAI).
- Modelos `LayerResult` / `SuiteReport`.
- Patrón env-driven (`JW_EVAL_LLM`).

**Pros**:
- Una sola implementación de "judge LLM" en el monorepo.
- Test infra reutilizable (fakes determinísticos).

**Contras**:
- `jw-finetune` pasaría a depender de `jw-eval`. Hoy el grafo es `jw-finetune → jw-rag, jw-core`. Añadir `jw-eval` invierte la dirección natural: `jw-eval` mide agentes (de `jw-agents`), no datasets de entrenamiento.
- Los modelos de `jw-eval` (`GoldenCase`, `LayerResult`) están centrados en evaluar `AgentResult`, no `QAPair`. Forzar el match requiere adapters innecesarios.
- Acoplaría el ciclo de release: cambios en `jw-eval` (Fase 22-32+) podrían bloquear builds de `jw-finetune`.

### Opción B — Módulo independiente en `jw-finetune`

Crear `jw_finetune.synth.judge.*` con sus propios modelos (`QAScore`) y reutilizar **a nivel de Protocol/Provider**, no de paquete.

**Pros**:
- Dependencias limpias: `jw-finetune → jw-core (NLI de Fase 39)` y reusa el `LLMProvider` que ya existe en `jw_finetune.synth.provider` (mismo provider abstraction que `anthropic_provider.py`).
- Modelos especializados para Q&A (no adaptadores).
- Sin acoplamiento de release.

**Contras**:
- Eventual duplicación parcial del dispatcher LLM (Ollama vs Claude vs OpenAI). Mitigable: el dispatcher es ~30 LOC; cada paquete puede tener el suyo sin DRY-pain real.

### Decisión: **Opción B** (módulo independiente)

Justificación:
1. La dirección natural del grafo se respeta (`jw-finetune` ya importa `jw-core`; añadir `jw_core.fidelity.nli` es un import descendente más).
2. El `LLMProvider` de `jw_finetune.synth` ya existe y es el provider correcto: las llamadas LLM del judge usan el mismo abstraction que la síntesis (factory env-driven).
3. `jw-eval` mide **agentes** (`AgentResult` + citations); el judge mide **datasets** (`QAPair`). Son dominios distintos aunque ambos usen LLM-as-judge bajo el capó.
4. Si en el futuro emerge un patrón común de "LLM judge", se extrae a `jw_core.judges/` como librería compartida — pero **eso es refactor reactivo**, no decisión preventiva.

Esta separación queda explícita en `docs/VISION_AUDIT.md` al cerrar Fase 44.

## Arquitectura

Nuevo subpaquete `packages/jw-finetune/src/jw_finetune/synth/judge/`:

```
packages/jw-finetune/src/jw_finetune/synth/judge/
├── __init__.py            # re-exports score_qa_pair, QAScore, JudgeMode
├── models.py              # QAScore, RejectionReason (Pydantic)
├── heuristics.py          # cites_jw_publication, has_minimum_substance
├── judge.py               # score_qa_pair + Judge orquestador
├── factories.py           # build_judge() env-driven
├── thresholds.py          # JudgeMode enum + default cutoffs
├── prompts/
│   ├── pedagogical_es.j2
│   ├── pedagogical_en.j2
│   └── pedagogical_pt.j2
└── stats.py               # JudgeStats — accumulator por run
```

Tests en `packages/jw-finetune/tests/synth/judge/`:

```
tests/synth/judge/
├── test_heuristics.py
├── test_judge_with_fakes.py
├── test_factories.py
├── test_thresholds.py
└── fixtures/
    └── golden_50_pairs.jsonl   # 50 pares anotados manualmente (25 pass + 25 fail)
```

### Reglas duras de diseño

1. `jw_finetune.synth.judge` **no** importa `anthropic` ni `ollama` en import time. Lazy a través de factories.
2. NLI provider se obtiene de `jw_core.fidelity.nli` (Fase 39). Si Fase 39 no está disponible (entorno sin extra `[fidelity]`), el judge corre **sin** la etapa NLI y emite warning una sola vez.
3. Heurísticas son **siempre activas**; LLM judge y NLI son opt-in.
4. Tests del judge usan **exclusivamente fakes** (`FakeLLMProvider`, `FakeNLIProvider`). Cero red.

## Modelos (Pydantic)

```python
# src/jw_finetune/synth/judge/models.py
from typing import Literal
from pydantic import BaseModel, Field

class RejectionReason(BaseModel):
    code: Literal[
        "no_jw_citation",
        "insufficient_substance",
        "nli_contradicts",
        "nli_neutral_low",
        "pedagogical_low",
        "overall_below_threshold",
    ]
    detail: str = ""

class QAScore(BaseModel):
    cites_jw_publication: bool
    has_minimum_substance: bool
    nli_score: float | None = Field(default=None, ge=0.0, le=1.0)
    nli_verdict: Literal["entails", "neutral", "contradicts"] | None = None
    pedagogical_quality: int | None = Field(default=None, ge=0, le=3)
    overall: float = Field(ge=0.0, le=10.0)
    kept: bool
    reasons: list[RejectionReason] = Field(default_factory=list)
```

### Fórmula `overall` (transparente, no caja negra)

```
base = 4.0
+ 1.5 si cites_jw_publication
+ 1.5 si has_minimum_substance
+ 2.0 * nli_score (si nli_verdict == "entails")
- 3.0 si nli_verdict == "contradicts"
+ pedagogical_quality (0..3)
clamp [0, 10]
```

Cuando una etapa no corre (LLM judge off, NLI off), su componente vale **el valor neutro** (no penaliza ni premia). Documentado en `thresholds.py`.

## Etapas del judge

### Etapa 1 — Heurística (siempre)

`heuristics.py`:

```python
import re
from jw_finetune.synth.judge.models import RejectionReason

# Códigos de publicación JW conocidos (extensible vía constant set)
_JW_PUB_CODES = re.compile(
    r"\b(w|g|jt|bh|sjj|sjjm|jy|rs|it|ws|km|yb|sg|cl|ws|wt|lvs|lff|lr|sjm)\d*\b",
    re.IGNORECASE,
)
_WOL_URL = re.compile(r"https?://(?:www\.)?wol\.jw\.org/", re.IGNORECASE)

def cites_jw_publication(answer: str) -> bool:
    """True si la respuesta contiene URL wol.jw.org o un código pub conocido."""
    return bool(_WOL_URL.search(answer) or _JW_PUB_CODES.search(answer))

_GENERIC_ANSWERS = {"sí.", "no.", "depende.", "sí", "no", "tal vez", "puede ser"}

def has_minimum_substance(question: str, answer: str) -> bool:
    """True si la respuesta tiene contenido enseñable, no truncado."""
    a = (answer or "").strip().lower()
    if len(a) < 40:
        return False
    if a in _GENERIC_ANSWERS:
        return False
    # Si la respuesta repite literal la pregunta (sin enseñanza), rechazar
    q = (question or "").strip().lower()
    if q and a.startswith(q) and len(a) < len(q) + 30:
        return False
    return True
```

Ambas heurísticas corren **siempre**; son la primera barrera.

### Etapa 2 — LLM judge pedagógico (opt-in)

`judge.py` invoca al LLM provider con un prompt que devuelve **solo** un entero 0-3:

```jinja
{# prompts/pedagogical_es.j2 #}
Eres un evaluador de calidad de datos para fine-tuning de un asistente que
enseña doctrina de los Testigos de Jehová. Evalúa el siguiente par Q&A.

Pregunta: {{ question }}
Respuesta: {{ answer }}

Criterios (puntúa la respuesta de 0 a 3):
0 = No es enseñanza útil (vacía, genérica, repite la pregunta, sin contenido)
1 = Información mínima, sin desarrollo doctrinal claro
2 = Buena enseñanza con explicación, pero podría profundizar más
3 = Enseñanza clara, con cita o explicación, útil para aprender

Responde ÚNICAMENTE con un dígito (0, 1, 2 o 3). Nada más.
```

El LLM judge usa **el mismo `LLMProvider` abstraction** de `jw_finetune.synth.provider`. La factory:

```python
# factories.py
def build_llm_judge_provider() -> LLMProvider | None:
    name = os.environ.get("JW_SYNTH_JUDGE_LLM", "").lower()
    if name in ("", "off", "none"):
        return None
    if name == "anthropic":
        from jw_finetune.synth.anthropic_provider import AnthropicProvider
        return AnthropicProvider()  # Haiku-cheap
    if name == "ollama":
        from jw_finetune.synth.ollama_provider import OllamaProvider
        return OllamaProvider(model=os.environ.get("JW_SYNTH_JUDGE_OLLAMA_MODEL", "llama3.1:8b"))
    raise ValueError(f"Unknown JW_SYNTH_JUDGE_LLM: {name}")
```

Parsing tolerante: regex `\b[0-3]\b` sobre la respuesta. Si no matchea, `pedagogical_quality = None` (vale neutro en la fórmula).

### Etapa 3 — NLI runtime (opt-in, reusa Fase 39)

Cuando hay citation detectada en la respuesta (heurística pasó), el judge intenta NLI:

```python
# judge.py (extracto)
def _nli_check(answer: str, *, nli_provider) -> tuple[str, float] | None:
    """
    Extrae el claim principal de la respuesta y la cita inline (si la hay).
    Si la respuesta incluye comilla del texto JW, usa el texto como premise.
    """
    premise = _extract_quoted_passage(answer)
    if not premise:
        return None  # No hay premise verificable
    claim = _strip_quotation(answer)
    verdict = nli_provider.evaluate_entailment(claim=claim, premise=premise)
    return (verdict.verdict, verdict.score)
```

`_extract_quoted_passage` busca texto entre comillas tipográficas (`"..."`, `«...»`) o citas directas marcadas por `dice:` / `según ... declara:` y captura el siguiente bloque.

Si Fase 39 no está disponible (`ImportError`), `_nli_check` retorna `None` silenciosamente (y el log emite warning **una vez** por proceso).

Factory NLI:

```python
def build_nli_provider() -> "NLIProvider | None":
    name = os.environ.get("JW_SYNTH_JUDGE_NLI", "off").lower()
    if name == "off":
        return None
    try:
        from jw_core.fidelity.nli_providers import factory_for_name
        return factory_for_name(name)  # "deberta" | "claude" | "ollama" | ...
    except ImportError:
        logger.warning("NLI requested but jw_core.fidelity not available; skipping NLI stage")
        return None
```

## Thresholds y modos

```python
# thresholds.py
from enum import Enum

class JudgeMode(str, Enum):
    OFF = "off"      # No corre el judge en absoluto
    LOOSE = "loose"  # Default: cutoff overall < 5.0; solo heurísticas obligatorias
    STRICT = "strict"  # cutoff overall < 6.5; exige NLI != "contradicts"

DEFAULT_CUTOFFS = {
    JudgeMode.OFF: None,
    JudgeMode.LOOSE: 5.0,
    JudgeMode.STRICT: 6.5,
}
```

Override por receta (en el YAML de la recipe):

```yaml
# recipes/doctrinal_qa.yaml
synth:
  judge:
    mode: strict
    overall_cutoff: 7.0   # override fino
    require_nli_entails: true
```

## Integración con el pipeline `data extract`

`jw_finetune.data.extract` (función actual) hoy llama a `synthesize_chunk` y persiste todo lo que pasa los validators heurísticos. Cambio:

```python
# Pseudocódigo del cambio en data/extract.py
def extract(recipe: Recipe, *, judge_mode: JudgeMode = JudgeMode.LOOSE) -> ExtractStats:
    judge = build_judge(mode=judge_mode, recipe_overrides=recipe.judge_overrides)
    stats = ExtractStats()
    for chunk in chunks:
        result = synthesize_chunk(chunk, provider=synth_provider, ...)
        for pair in result.pairs:
            score = judge.score(pair.question, pair.answer)
            if score.kept:
                pair.metadata["judge_score"] = score.model_dump(exclude_none=True)
                writer.write(pair)
                stats.kept += 1
            else:
                stats.rejected += 1
                stats.rejection_reasons[score.reasons[0].code] += 1
    return stats
```

Nuevo CLI flag (Typer):

```bash
jw-finetune data extract --judge=strict|loose|off  # default: loose
jw-finetune data extract --judge-llm=anthropic     # override env
jw-finetune data extract --judge-nli=deberta       # override env
```

Output de stats al terminar:

```
Extraction complete.
  Pairs generated: 1240
  Pairs kept:      872 (70.3%)
  Rejected:        368 (29.7%)
    no_jw_citation:           142
    pedagogical_low:           98
    insufficient_substance:    62
    nli_contradicts:           41
    overall_below_threshold:   25
```

## Triple-target (consistente con principio #7 del overview)

| Variante | LLM judge | NLI provider |
|---|---|---|
| `api` | Anthropic Haiku / OpenAI / Claude | `ClaudeNLI` |
| `mlx` | Ollama (llama3.1) | `DeBERTaV3MNLI` via mlx-transformers |
| `nvidia` | Ollama (llama3.1) | `DeBERTaV3MNLI` via transformers CUDA |
| `cpu` | Ollama (llama3.1:8b-q4) | `DeBERTaV3MNLI` CPU |
| `off` | none | none |

Auto-detección hereda de Fase 39; el judge no replica detección.

## Multilingüe (en/es/pt mínimo)

- Heurística `cites_jw_publication`: regex agnóstico a idioma.
- Heurística `has_minimum_substance`: `_GENERIC_ANSWERS` localizado por idioma; carga el set según `pair.language`.
- Prompt pedagógico: templates `pedagogical_es.j2`, `pedagogical_en.j2`, `pedagogical_pt.j2`. Selector via `pair.language`.
- NLI: el provider DeBERTa-MNLI soporta multilingüe en su variante xnli (decisión hereda Fase 39).

## Tests (sin red, fakes determinísticos)

1. `test_heuristics.py` — 30 casos de heurística (positivos/negativos por idioma).
2. `test_judge_with_fakes.py` — `FakeLLMProvider` que retorna "3" / "0" según fixture, `FakeNLIProvider` que retorna verdict prefijado. Verifica fórmula `overall`.
3. `test_factories.py` — env vars resuelven al provider correcto; off retorna `None`.
4. `test_thresholds.py` — modes `off|loose|strict` aplican cutoffs correctos; overrides de receta ganan.
5. `tests/fixtures/golden_50_pairs.jsonl` — 50 pares anotados (25 deberían pasar, 25 deberían rechazarse). Test mide **precisión del filtro**: ≥ 90% de aciertos en modo `loose`, ≥ 95% en modo `strict`.

CI: el suite corre como parte de `pytest packages/jw-finetune/tests` — sin extras de red ni GPU.

## Métricas de éxito de la fase

- ✅ `jw-finetune data extract --judge=loose` descarta ≥30% de los pares de un baseline ruidoso de 1000 pares.
- ✅ Precisión del filtro ≥90% sobre golden de 50 pares (modo loose).
- ✅ Tests offline corren <10s en CI.
- ✅ `QAPair.metadata["judge_score"]` se persiste para pares aceptados; auditable.
- ✅ Documentado en `docs/guias/synth-judge.md` con ejemplos por idioma.
- ✅ Audit 1:1 en `docs/VISION_AUDIT.md`.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | LLM judge alucina puntaje (devuelve "5" cuando max es 3) | Regex `\b[0-3]\b`; si no matchea, valor neutro (no penaliza par válido) |
| 2 | NLI rechaza claims correctos por paráfrasis | Threshold conservador; NLI solo penaliza con `contradicts`, no con `neutral` |
| 3 | Regex `_JW_PUB_CODES` produce falsos positivos | Set conservador de códigos conocidos; cobertura extensible vía constant |
| 4 | Pipeline más lento con judge activo | LLM/NLI son opt-in; default loose solo corre heurísticas (~0ms por par) |
| 5 | Receta sobreescribe a `off` sin querer | CLI flag tiene precedencia explícita sobre YAML; warning si receta dice off |
| 6 | Acumulación silenciosa de rejected | Stats al final del run + log de razones top-5; opcional `--dump-rejected path.jsonl` |
| 7 | Fase 39 retrasada bloquea Fase 44 | `_nli_check` retorna `None` silenciosamente si import falla; judge corre sin NLI |
| 8 | Privacidad: Anthropic ve datos sintéticos | Default judge LLM = off; Ollama local recomendado en docs |

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages --extra synth

# 2. Heurísticas solamente (default)
uv run jw-finetune data extract --recipe doctrinal --judge=loose

# 3. Con LLM judge local (Ollama)
JW_SYNTH_JUDGE_LLM=ollama uv run jw-finetune data extract --recipe doctrinal --judge=strict

# 4. Full (LLM + NLI)
JW_SYNTH_JUDGE_LLM=anthropic JW_SYNTH_JUDGE_NLI=deberta \
  uv run jw-finetune data extract --recipe doctrinal --judge=strict

# 5. Tests offline
uv run pytest packages/jw-finetune/tests/synth/judge -v

# 6. Verificación de precisión sobre golden
uv run python -m jw_finetune.synth.judge.eval_precision \
  --fixture packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl
```

## Pendientes explícitos (post-Fase 44)

- **Ensemble de LLM judges** (Anthropic + OpenAI con majority vote) — fase futura cuando se vea drift de un solo judge.
- **Auto-tuning de thresholds** con datos de fine-tunes reales — requiere métricas comparativas pre/post de calidad de modelo entrenado.
- **Web UI** para revisar pares rechazados antes de descartarlos — fuera de scope; CLI dump basta.
- **Extracción del LLM-as-judge a `jw_core.judges`** como librería compartida con `jw-eval` — solo si emerge patrón duplicado real.

## Plan de implementación (alto nivel)

Spec hijo de plan: `docs/superpowers/plans/2026-05-31-fase-44-synth-judge-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold de `synth/judge/` + modelos Pydantic con tests.
2. Heurísticas (`cites_jw_publication`, `has_minimum_substance`) + tests por idioma.
3. Thresholds + JudgeMode + tests.
4. Prompts pedagógicos (3 idiomas) + LLM judge stage con `FakeLLMProvider`.
5. Factories env-driven + tests.
6. Integración con NLI (Fase 39) detrás de import guard + `FakeNLIProvider`.
7. Wiring en `data/extract.py` + nuevo CLI flag + stats output.
8. Golden 50 pares + test de precisión.
9. Guía `docs/guias/synth-judge.md` + audit 1:1.

Cada paso con PR + tests + sin regresiones en los 1984 tests existentes.
