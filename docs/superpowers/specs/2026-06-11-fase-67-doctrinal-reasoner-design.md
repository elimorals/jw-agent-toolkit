# Fase 67 — `doctrinal-reasoner`: chain-of-thought verificable con NLI

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (kernel agéntico)
> **Capa**: A — Agéntica
> **Depende de**: F4 `apologetics`, F35 `constrained-decoding`, F39 `nli-runtime`, F43 `agent-tracing`, F23 `citation-validator`
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F4 `apologetics` (ranquea fuentes, pero no expone razonamiento paso a paso)

## Motivación

`apologetics` ranquea fuentes por autoridad (topic_index >
question_refs > verse_text > study_note > cdn_search > rag) y devuelve
findings. El LLM consumidor sintetiza la respuesta.

Esa síntesis **es opaca**: no expone qué premisa lleva a qué
conclusión, ni cómo cada paso se apoya en evidencia.

Para preguntas multi-paso —"si Juan 1:1 dice que el Verbo era Dios,
¿cómo se concilia con Juan 14:28 ('el Padre es mayor que yo')?"— un
usuario necesita ver el **árbol de razonamiento** explícito,
verificable paso a paso.

## Objetivos

1. Un agente `doctrinal_reasoner(question)` que produce un
   `ReasoningTree` con nodos premisa → inferencia → conclusión.
2. Cada nodo se acompaña de cita verificable wol.jw.org y se valida
   con NLI F39 modo `reject` antes de incluirse.
3. **Output Markdown exportable** con el árbol completo + sumario
   en prosa (compatible con `exporters` F31).
4. Salida estructurada vía constrained decoding F35 (gramática GBNF
   para `ReasoningTree` JSON).
5. Tracing F43 con cada paso ReAct (`thought`, `action`, `observation`).
6. Determinista bajo `JW_REASONER_LLM=fake`.

## No-objetivos (boundaries vinculantes)

- **No** reemplaza al agente `apologetics`. Es un **modo de razonamiento
  largo** sobre las mismas fuentes.
- **No** produce opinión propia. Cada nodo es premisa de fuente JW
  + inferencia lógica trazable. Sin conclusiones "porque sí".
- **No** afirma doctrina si NLI F39 no valida la premisa al chunk
  citado. Si la cadena se rompe, el árbol se trunca y reporta el
  punto de falla.
- **No** se usa para apologética hostil. Las preguntas que carguen
  framing tipo "demuestra que X religión está equivocada" devuelven
  reformulación neutra antes de razonar.

## Decisión clave: ¿ReAct manual vs framework?

### Opción A — Framework externo (LangChain ReAct agent, etc.)

**Contras**: 50MB+, ciclo de release acoplado, modelos de eventos
distintos a F43.

### Opción B — Loop ReAct propio (~200 LOC) sobre `apologetics` tools

**Pros**:
- Reutiliza `apologetics` chain como "tool set".
- Tracing F43 sin adapters.
- Constrained F35 para JSON de cada paso.

### Decisión: **Opción B** (in-house)

Justificación idéntica a F65: el patrón procedural ya tiene la mitad
de lo que un framework ofrece.

## Arquitectura

```
        Pregunta multi-paso
              │
              ▼
   ┌─────────────────────┐
   │ Reformulator        │ — neutraliza framing tóxico,
   │ (LLM + safety       │   descompone en sub-preguntas
   │  guardrails)        │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Planner             │ — produce ReasoningStep[]
   │ (LLM constrained F35)│   con depends_on entre pasos
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ ReAct loop          │
   │  for each step:     │
   │   - thought         │
   │   - action (tool)   │
   │   - observation     │
   │   - NLI verify F39  │
   │   - reflect         │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ ReasoningTree       │ — nodos validados
   │ + Sumario en prosa  │
   │ + Exporter F31      │
   └─────────────────────┘
```

## Tools disponibles para el ReAct loop

| Tool                          | Backing                              |
|-------------------------------|--------------------------------------|
| `topic_index.search`          | `topic_index_client`                 |
| `topic_index.get_subject`     | `topic_index_client.get_subject_page`|
| `bible.get_verse`             | parser de versículos                 |
| `bible.get_study_notes`       | parser de notas nwtsty               |
| `bible.compare_translations`  | tool existente F3                    |
| `rag.semantic_search`         | RAG híbrido                          |
| `versification.map`           | F46 (mapeo entre tradiciones)        |
| `citation.validate`           | F23 validator                        |

Cada tool devuelve un `Observation` Pydantic.

## Contratos de tipos

```python
# packages/jw-agents/src/jw_agents/reasoner/models.py

from pydantic import BaseModel, Field
from typing import Literal, Any

StepKind = Literal[
    "premise",        # establece una premisa con cita
    "inference",      # deriva algo de premisas previas
    "harmonization",  # concilia 2 textos aparentemente contradictorios
    "conclusion",     # síntesis final
]

NLIStatus = Literal["entails", "neutral", "contradicts", "skipped"]

class Citation(BaseModel):
    text: str
    wol_url: str
    source_kind: Literal[
        "verse", "study_note", "cross_ref", "topic_index",
        "topic_subheading", "cdn_search", "rag",
    ]

class ReasoningStep(BaseModel):
    id: str
    kind: StepKind
    statement: str                  # afirmación en prosa
    depends_on: list[str] = []      # ids de pasos previos
    rationale: str                  # por qué este paso sigue de las premisas
    citation: Citation | None = None
    nli_status: NLIStatus = "skipped"
    nli_score: float | None = None
    rejected_reason: str | None = None  # set si NLI rejected y se descartó

class ReasoningTree(BaseModel):
    question_original: str
    question_normalized: str            # tras reformulator
    sub_questions: list[str] = []
    steps: list[ReasoningStep]
    truncated: bool = False             # True si se cortó por NLI fail
    summary_prose: str = ""             # generado al final
    trace_path: str | None = None
    nli_provider_used: str | None = None

class ReasonerConfig(BaseModel):
    language: Literal["en", "es", "pt"] = "es"
    max_steps: int = 12
    nli_mode: Literal["off", "warn", "reject"] = "reject"
    reformulate_toxic: bool = True
    include_summary_prose: bool = True
```

## API pública

```python
# packages/jw-agents/src/jw_agents/reasoner/__init__.py

from jw_agents.reasoner.engine import doctrinal_reasoner
from jw_agents.reasoner.models import (
    ReasoningTree,
    ReasoningStep,
    StepKind,
    Citation,
    NLIStatus,
    ReasonerConfig,
)

__all__ = [
    "doctrinal_reasoner",
    "ReasoningTree",
    "ReasoningStep",
    "StepKind",
    "Citation",
    "NLIStatus",
    "ReasonerConfig",
]
```

## CLI

```bash
# Razonar sobre una pregunta multi-paso
jw reason "Si Juan 1:1 dice que el Verbo era Dios, ¿cómo se concilia con Juan 14:28?"

# Limitar max steps
jw reason "..." --max-steps 6

# Modo NLI estricto (default) vs permisivo
jw reason "..." --nli-mode warn

# Exportar el árbol a Markdown
jw reason "..." --export reason.md

# Tracing explícito
jw reason "..." --trace ~/.jw-traces/reason.jsonl
```

## MCP tools

- `doctrinal_reason(question, language="es", max_steps=12, nli_mode="reject") → ReasoningTree`
- `export_reasoning_tree(tree, format="markdown") → str | bytes`

## Reformulator (neutralización de framing)

Antes del planner, un paso opcional reformula preguntas hostiles a
forma neutra:

```
Input:  "Demuestra que el catolicismo está equivocado sobre la
         Trinidad"
Output: "¿Qué enseña la Biblia sobre la naturaleza de Dios y
         cómo se relaciona con la doctrina de la Trinidad?"
```

Implementación: LLM con system prompt + lista de heurísticas de
detección (`prove X is wrong`, `disprove`, `refute X religion`,
patterns es/en/pt).

Opcional vía `reformulate_toxic=False`.

## Prompt del planner (es)

```jinja
{# packages/jw-agents/src/jw_agents/reasoner/prompts/planner_es.j2 #}
Eres un planificador de razonamiento doctrinal sobre la Biblia y
publicaciones de los Testigos de Jehová. Recibes una pregunta y
descompones la cadena de razonamiento en pasos verificables.

Pregunta: {{ question_normalized }}
{% if sub_questions %}
Sub-preguntas detectadas:
{% for sq in sub_questions %}- {{ sq }}
{% endfor %}
{% endif %}

Devuelve un JSON estricto con la siguiente estructura:
{
  "steps": [
    {
      "id": "p1",
      "kind": "premise",
      "statement": "afirmación clara",
      "depends_on": [],
      "rationale": "por qué establecer esto",
      "tool_hint": "topic_index.search | bible.get_verse | rag.semantic_search"
    },
    {
      "id": "i1",
      "kind": "inference",
      "statement": "...",
      "depends_on": ["p1"],
      "rationale": "...",
      "tool_hint": "..."
    },
    {
      "id": "c1",
      "kind": "conclusion",
      "statement": "...",
      "depends_on": ["p1", "i1"],
      "rationale": "..."
    }
  ]
}

Máximo {{ max_steps }} pasos. Cada `statement` debe ser cite-able
con fuentes JW (Biblia o publicaciones). Si la cadena requiere un
paso de `harmonization`, márcalo explícitamente.
```

Constrained F35.

## ReAct loop (ejecutor)

Para cada `step` del plan:

1. **Thought**: el LLM genera razonamiento corto sobre qué buscar.
2. **Action**: se invoca el `tool_hint` con args derivados de
   `statement`.
3. **Observation**: el tool devuelve un `Observation` Pydantic
   (típicamente un `Finding` o `Verse`).
4. **NLI verify**: si `nli_mode == "reject"`, se ejecuta
   `evaluate_entailment(claim=step.statement, premise=observation.excerpt)`.
   Si verdict != `entails`, el step se marca `truncated=True` y el
   árbol corta ahí.
5. **Reflect**: si NLI pasa, el step se commit con `citation`
   poblada. Si falla y `nli_mode == "warn"`, se mantiene con
   `nli_status="contradicts"` para que el usuario decida.

## Summary prose (post-procesamiento)

Tras armar el `ReasoningTree`, un LLM genera 3-5 párrafos de prosa que
narra el razonamiento siguiendo el grafo. Cita los `wol_url` en línea.

Opt-out via `include_summary_prose=False` (útil para tests).

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `ReasoningStep` rechaza `depends_on` ciclos                   | Unit        |
| `ReasoningTree` Pydantic round-trip                           | Unit        |
| Reformulator detecta framing tóxico (10 cases)                | Unit        |
| Reformulator no toca preguntas neutras (10 cases)             | Unit        |
| Planner con FakeLLM devuelve plan válido                      | Unit        |
| Planner valida `tool_hint` contra registry                    | Unit        |
| ReAct loop ejecuta steps en orden topológico                  | Unit        |
| NLI=entails marca step `nli_status="entails"`                 | Unit        |
| NLI=contradicts en mode `reject` trunca árbol                 | Unit        |
| NLI=contradicts en mode `warn` mantiene step                  | Unit        |
| Summary prose se genera tras árbol                            | Unit        |
| Exporter Markdown produce árbol legible                       | Integration |
| Exporter integra con F31 (PDF, DOCX, Anki)                    | Integration |
| Trace F43 emite 1 evento por step                             | Integration |
| Constrained F35: plan + summary siempre parseable             | Property    |
| Golden: 10 preguntas multi-paso producen árboles aceptables   | E2E         |

## Golden set (E2E)

`tests/reasoner/fixtures/golden/`:

10 preguntas multi-paso anotadas con:
- Árbol esperado (al menos sub-pasos clave).
- NLI verdicts esperados por paso.
- Sumario prose con criterios mínimos.

Ejemplos:
1. "Juan 1:1 vs Juan 14:28 — naturaleza del Verbo"
2. "1 Cor 15:29 — bautismo por los muertos"
3. "Lucas 23:43 — paraíso 'hoy' o futuro"
4. "Mateo 24:34 — generación que no pasará"
5. "Apocalipsis 14 — los 144,000 literal o simbólico"
6. "Eclesiastés 9:5 vs Lucas 16 — qué pasa al morir"
7. "Génesis 1:26 'hagamos al hombre' — ¿plural divino?"
8. "Salmo 110:1 — el SEÑOR y el Adoni"
9. "Hebreos 1:8 — ¿el Padre llama 'Dios' al Hijo?"
10. "Mateo 28:19 — fórmula trinitaria"

## Riesgos / mitigaciones

| Riesgo                                                     | Mitigación                                       |
|------------------------------------------------------------|--------------------------------------------------|
| LLM alucina premisa que no tiene cita                      | NLI F39 modo `reject` corta el árbol             |
| Árbol crece sin acotamiento                                | `max_steps=12` hard cap                          |
| Cita con drift (URL ya no resuelve a contenido alegado)    | F23 citation validator opt-in re-fetch           |
| Reformulator suaviza preguntas legítimas                   | Heurística conservadora; opt-out flag            |
| Output Markdown muy extenso                                | Summary prose acota a 3-5 párrafos; árbol completo en collapsible Markdown |
| Sumario contradice el árbol                                | Se valida con NLI antes de devolver              |
| Costo LLM (planner + N steps + summary)                    | Ollama default; tokens reportados                |

## Métricas de éxito

- **Cobertura**: ≥85% del golden de 10 preguntas produce árbol no
  truncado.
- **Auditabilidad**: 100% de steps con `nli_status="entails"` tienen
  `citation` poblada con URL válida (F23 check).
- **Calidad sumario**: ≥4/5 evaluadores humanos lo califican como
  "fiel al árbol" en blind review.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/reason.py` — `jw reason {ask,show,export}`.
- MCP: 2 tools nuevas.
- F31 exporter: handler nuevo `ReasoningTree → StudySheet`.
- F65 meta-orchestrator: tool `reason.doctrinal` registrada
  automáticamente.

## Guía resultante

`docs/guias/doctrinal-reasoner.md` — quick start, interpretación de
NLI status, export a Anki, ejemplos del golden set.
