# Fase 22 — `jw-eval`: suite de evaluación doctrinal con regresión

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (infraestructura de confianza)
> **Depende de**: ninguna fase. Habilita medición para todas las posteriores.
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

El toolkit produce respuestas doctrinales a través de 12 agentes y ~60 herramientas MCP. Sin un benchmark dedicado, **cada cambio de prompt, parser, RAG o modelo puede introducir regresión doctrinal silenciosamente**. Hoy los 551 tests verifican mecánica (parsers, structures, throttling, cache), no contenido teológico.

Fase 22 cierra ese hueco: una suite de **Golden Q&A** que mide en cada commit / nightly:

1. Que los agentes devuelven la **estructura** esperada (L1).
2. Que las **citas** que emiten resuelven y respaldan la afirmación (L2).
3. Que la **respuesta en lenguaje natural** se acerca a la respuesta dorada (L3).

Esto convierte "confío en mí" en métrica auditable y protege todas las Fases 23-32 — cada nueva feature **debe** añadir sus Q&A doradas al merge.

## Objetivos (en orden de prioridad)

1. **Detectar regresión doctrinal antes de merge** (L1 + L2 snapshot, bloqueantes en CI).
2. **Detectar link-rot y drift de contenido externo** (L2 live, semanal, no bloqueante; abre issue automáticamente).
3. **Detectar deriva de calidad en lenguaje natural** (L3 nightly, reporte sin bloqueo).

## No-objetivos (boundaries vinculantes)

Estas líneas **no** las cruza Fase 22 — explícitas para evitar scope creep:

- **No** auto-extraction de Q&A desde Atalayas / Study Notes. Es territorio de `jw-finetune` y eventualmente Fase 24 (`study_conductor`). Aquí las Q&A doradas son **hand-curated por el usuario** (semilla 30, expansión incremental).
- **No** dashboard web. Solo reporte markdown / JSON. Un dashboard se construye sobre los JSON cuando exista la Fase de infra que lo justifique (ROADMAP M10 ya tiene REST listo).
- **No** modifica los agentes existentes. Fase 22 los **observa**. Si una eval falla, la corrección va en otro PR sobre la fase del agente afectado.

## Arquitectura

Nuevo paquete `packages/jw-eval/` siguiendo la convención del monorepo. Dependencias hacia abajo: importa `jw-core`, `jw-rag`, `jw-agents`; **no** lo importa nadie excepto `jw-cli` (para el comando `jw eval`) y `jw-mcp` (para la herramienta `run_eval_suite`).

```
packages/jw-eval/
├── pyproject.toml
└── src/jw_eval/
    ├── __init__.py
    ├── models.py             # GoldenCase, LayerResult, SuiteReport (Pydantic)
    ├── suite.py              # Suite — carga YAMLs, despacha por capa
    ├── layers/
    │   ├── __init__.py
    │   ├── structural.py     # L1
    │   ├── citations.py      # L2 — modo live + modo snapshot
    │   └── semantic.py       # L3 — embeddings + escalada
    ├── judges/
    │   ├── __init__.py
    │   ├── embeddings.py     # sentence-transformers (opcional)
    │   └── llm.py            # Ollama / Claude / OpenAI dispatcher
    ├── fixtures/
    │   └── golden_qa/
    │       ├── l1/           # estructural
    │       │   ├── verse_explainer_john_3_16.yaml
    │       │   └── ...
    │       ├── l2/           # citas resolverán + sustentan
    │       │   └── ...
    │       └── l3/           # Q&A natural + keywords + golden answer
    │           └── ...
    ├── snapshots/
    │   └── wol/              # HTML snapshots para L2 offline (CI público)
    ├── report.py             # SuiteReport → markdown + JSON
    └── cli.py                # entry-point para Typer
└── tests/
    ├── test_layers.py
    ├── test_judges.py
    ├── test_suite.py
    └── fixtures/             # mini-cases sintéticos para testear el evaluador
```

### Reglas duras de diseño

1. `jw_eval` **no** importa nada que haga red en import time.
2. Cada layer tiene un contrato claro: `evaluate(case: GoldenCase) -> LayerResult`. El despachador `Suite` no conoce internals.
3. Judges son **inyectables**: tests del evaluador usan fakes determinísticos.
4. Snapshots de wol son **commitead**os al repo (HTML reducido, sin scripts ni imágenes — solo el árbol DOM necesario para citas).
5. **Cero costo en CI público**: L1 + L2-snapshot corren sin red ni API keys.

## Las tres capas

### L1 — Estructural (siempre activa, bloqueante)

**Qué mide**: que `agent(input)` devuelva `AgentResult.findings` con la estructura esperada — tipos de fuente, número mínimo de findings, presencia de citation_metadata, orden de prioridad de fuentes (Topic Index > question_refs > verse_text > study_note > cdn_search > rag, según `ARCHITECTURE.md`).

**Cómo**:

```yaml
# fixtures/golden_qa/l1/apologetics_trinity_es.yaml
id: l1_apologetics_trinity_es
agent: apologetics
input:
  question: "¿Es la Trinidad bíblica?"
  language: es
expected:
  min_findings: 3
  sources_in_order:               # los primeros N findings deben ser de estos sources
    - topic_index
    - verse_text
  must_have_source: topic_index   # al menos un finding de esta fuente
  must_have_citation: true        # cada finding con metadata.source debe tener URL
  forbidden_keywords_in_findings: # red flag si aparece en cualquier finding
    - "supuestamente"
    - "podría ser"
```

**Determinismo**: 100% determinista, sin red, sin LLM, sin embedding. Se ejecuta en `pytest -m eval_l1`. Falla CI si <100%.

### L2 — Integridad de citas

**Modo snapshot (siempre activo, bloqueante)**:

1. Cada `GoldenCase` L2 tiene `expected_citations: [URL, ...]`.
2. Para cada URL, hay un archivo en `snapshots/wol/<sha256(URL)>.html`.
3. La evaluación corre el agente, recoge las URLs emitidas, valida que **todas** las URLs esperadas estén presentes y que el **texto del snapshot** contenga al menos una de las `support_phrases` declaradas.

```yaml
# fixtures/golden_qa/l2/verse_john_3_16_es.yaml
id: l2_verse_john_3_16_es
agent: verse_explainer
input:
  reference: "Juan 3:16"
  language: es
expected_citations:
  - https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3
support_phrases:                  # debe encontrarse al menos una en el HTML snapshot
  - "amó tanto al mundo"
  - "Dios amó tanto"
```

**Modo live (cron semanal, no bloqueante)**:

- Re-descarga cada URL del `expected_citations` con `WOLClient` real.
- Compara fingerprint estructural contra snapshot (telemetry hash). Si difiere, abre issue GitHub vía `gh issue create` con label `link-drift`.
- Esto es el **disparador natural de Fase 23** — el citation_validator (Fase 23) será quien automatice la refresh del snapshot.

**Cómo se construye un snapshot**: script `scripts/build_eval_snapshots.py` (one-shot) que descarga las URLs declaradas y guarda HTML normalizado.

### L3 — Q&A semántico (nightly, no bloqueante)

**Pipeline**:

1. Correr `agent(input)` y serializar findings → texto plano `agent_answer` (concatenación de finding.text).
2. Embedder: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (143MB, multi-lingüe es/en/pt), opcional vía extra `[local-embeddings]`.
3. `cosine = cos(embed(agent_answer), embed(golden_answer))`.
4. Threshold logic:
   - `cosine ≥ 0.78` → **pass**.
   - `cosine < 0.55` → **fail**.
   - `0.55 ≤ cosine < 0.78` → escalar a `judge.llm` con prompt:

```
Eres un juez doctrinal de fidelidad. Compara la respuesta candidata
con la respuesta dorada. Responde estrictamente como JSON:
{"verdict": "pass" | "fail", "reason": "..."}

Respuesta dorada:
<golden_answer>

Respuesta candidata:
<agent_answer>

Keywords requeridas (al menos UNA debe aparecer en candidata, en
cualquier forma): <expected_keywords_any>
Keywords prohibidas (NINGUNA puede aparecer): <expected_keywords_none>
```

5. Veredicto final con razones y diff en reporte.

**Selección del LLM judge** (env-driven, default seguro):

| `JW_EVAL_LLM` | Cliente | Coste | Privacidad |
|---|---|---|---|
| `ollama` (default) | `OllamaAdapter` (Fase 11) → `llama3.1:8b` | $0 | 100% local |
| `claude` | Anthropic SDK | $$ | red, opt-in |
| `openai` | OpenAI SDK | $$ | red, opt-in |
| `none` | desactiva escalada — solo embeddings | $0 | total |

```yaml
# fixtures/golden_qa/l3/trinity_doctrine.yaml
id: l3_apologetics_trinity_basic_es
agent: apologetics
input:
  question: "¿Es la Trinidad bíblica?"
  language: es
expected_citations:
  - https://wol.jw.org/es/wol/d/r4/lp-s/1101989140
expected_keywords_any:
  - "no es bíblica"
  - "fue formulada después"
  - "no enseñada por Jesús"
expected_keywords_none:
  - "doctrina central de la fe cristiana"
golden_answer: |
  La Trinidad no es una enseñanza bíblica. Las Escrituras presentan a Jehová
  como el único Dios verdadero (Deuteronomio 6:4; Juan 17:3), mientras que Jesús
  es su Hijo (Juan 14:28). La doctrina trinitaria se desarrolló siglos después
  de los apóstoles, influida por filosofía griega.
judge:
  primary: embeddings
  threshold_pass: 0.78
  threshold_review_min: 0.55
  threshold_review_max: 0.78
metadata:
  topic: doctrine.trinity
  added_by: elias
  added_at: 2026-05-30
```

## Modelos (Pydantic)

```python
# src/jw_eval/models.py
class GoldenCase(BaseModel):
    id: str
    agent: str                       # "apologetics" | "verse_explainer" | ...
    layer: Literal["l1", "l2", "l3"]
    input: dict                      # forwardeado al agente
    expected: dict                   # shape depende del layer
    metadata: dict = {}

class LayerResult(BaseModel):
    case_id: str
    layer: str
    verdict: Literal["pass", "fail", "skip", "error"]
    score: float | None              # 0..1 para L3; None para L1/L2
    reasons: list[str]               # explica el verdict
    duration_ms: int

class SuiteReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    layers_run: list[str]
    results: list[LayerResult]
    summary: dict[str, dict]         # {"l1": {"pass": 9, "fail": 1, ...}, ...}
    diff_vs_baseline: dict | None    # opcional comparación con run anterior
```

## Integración con el resto del toolkit

### CLI (`jw-cli`)

Nuevo comando `jw eval`:

```
jw eval --layer 1                       # solo L1 (rápido)
jw eval --layer 1,2                     # default CI
jw eval --layer 1,2,3                   # full nightly
jw eval --layer 2 --live                # L2 modo live (red)
jw eval --report md --out report.md     # genera markdown
jw eval --filter agent=apologetics      # subset
jw eval --baseline last-run.json        # diff contra baseline
```

### MCP (`jw-mcp`)

Nueva herramienta `run_eval_suite(layers: list[int] = [1], filter: dict = {}) -> SuiteReport`.

### CI (`.github/workflows/ci.yml`)

Nuevos jobs:

```yaml
eval-fast:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - run: uv run jw eval --layer 1,2  # offline, bloqueante
  # falla si L1 < 100% o L2-snapshot < 98%

eval-l2-live:
  needs: test
  if: github.event_name == 'schedule'
  schedule: "0 6 * * MON"             # lunes 06:00 UTC
  steps:
    - run: uv run jw eval --layer 2 --live --report json --out l2-live.json
    - run: |
        # parse json, si hay link-drift abre issues:
        uv run python scripts/eval_open_drift_issues.py l2-live.json

eval-nightly:
  needs: test
  if: github.event_name == 'schedule'
  schedule: "0 4 * * *"
  steps:
    - run: JW_EVAL_LLM=ollama uv run jw eval --layer 1,2,3 --report md
    - uses: actions/upload-artifact@v4
      with:
        name: eval-nightly-report
        path: report.md
```

## Datos iniciales (semilla mínima)

Bootstrap de 30 Golden Cases distribuidas:

| Layer | # | Cobertura |
|---|---|---|
| L1 | 12 | 3 por agente principal: `apologetics`, `verse_explainer`, `research_topic`, `meeting_helper` |
| L2 | 12 | 3 versículos básicos (Juan 3:16, Romanos 6:23, Hechos 4:12) × 4 idiomas (en/es/pt + 1 sign lang base) + 4 doctrinas con cita autoritativa Topic Index |
| L3 | 6 | 6 doctrinas core: Trinidad, alma, infierno, identidad de Cristo, nombre de Dios, esperanza terrestre |

Cada Fase 23-32 **debe** añadir mínimo 3 Golden Cases nuevas (L1 + L2 + L3 si aplica) al merge. CI lo enforza con un check de cobertura por agente.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Snapshot wol envejece sin que nadie lo note | L2 live semanal + Fase 23 (auto-refresh snapshots) |
| 2 | Embeddings fallan en distinguir doctrinas próximas | Threshold conservador 0.78 + keywords negativas + escalada LLM |
| 3 | LLM judge alucina verdict | Prompt estructurado JSON-only; disagreement humano se loguea para iterar el prompt |
| 4 | 30 Q&A es poca cobertura | Política: cada PR de Fase 23-32 debe añadir 3+ casos. Después de 11 fases hay 30 + 33 = 63 casos |
| 5 | Coste de API en L3 | Default = Ollama local. APIs externas explícitamente opt-in vía env |
| 6 | Falsos positivos bloqueando merges | Solo L1 y L2-snapshot bloquean. L2-live y L3 reportan, no bloquean |
| 7 | sentence-transformers como dep pesado | Está como extra `[local-embeddings]`, no hard dependency. CI lo instala. Devs sin GPU pueden saltarlo |
| 8 | Privacy: APIs externas en L3 | Documentado en guía. `JW_EVAL_LLM=ollama` es default. CI público nunca tiene API key |

## Métricas de éxito de la fase

- ✅ `jw eval --layer 1,2` corre en <60s en CI público (Linux GitHub runner).
- ✅ Suite de Golden Cases v1 (30 casos) en repo.
- ✅ L1 falla CI cuando alguien rompe el contrato de un agente.
- ✅ L2 live abre issue cuando wol.jw.org cambia un URL crítico.
- ✅ Reporte markdown legible en PR como bot-comment o artifact.
- ✅ Documentado en `docs/guias/eval-doctrinal.md`.

## Pendientes explícitos (post-Fase 22)

- Auto-extracción de Q&A desde Atalayas / Study Notes → **Fase 24 / `jw-finetune`** territory.
- Dashboard web sobre los JSON de eval → fase futura de infra (no urgente).
- Modificar agentes para mejorar score → cada agente en su propia fase de mejora.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. L1 + L2 snapshot offline
uv run jw eval --layer 1,2

# 3. L2 live (requiere red)
uv run jw eval --layer 2 --live

# 4. L3 con Ollama
JW_EVAL_LLM=ollama uv run jw eval --layer 1,2,3

# 5. Suite de tests del propio evaluador
.venv/bin/python -m pytest packages/jw-eval/tests
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-30-fase-22-eval-doctrinal-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold del paquete (`packages/jw-eval/pyproject.toml` + estructura).
2. Modelos Pydantic en `models.py` con tests.
3. Layer 1 (estructural) + 12 Golden Cases L1.
4. Layer 2 modo snapshot + script `build_eval_snapshots.py` + 12 cases L2.
5. Layer 2 modo live + integración con `WOLClient` real.
6. Judges (embeddings + LLM dispatcher).
7. Layer 3 + 6 cases L3.
8. CLI `jw eval` + MCP tool `run_eval_suite`.
9. CI jobs + script `eval_open_drift_issues.py`.
10. Reporte markdown + JSON.
11. Guía en `docs/guias/eval-doctrinal.md` + audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones en los 551 tests existentes.
