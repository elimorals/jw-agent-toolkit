# SL-CAI: self-critique para datasets de fine-tune (Fase 80.0)

> **Estado**: implementado en F80 fase 0. Prerrequisito de las fases de
> interpretabilidad mecanicista (F80.1–F80.5).

SL-CAI es la mitad **supervised** de Constitutional AI aplicada a la
generación de datasets, **no** a un asistente generalista. Por cada par
`(question, answer)` generado, pedimos al LLM que:

1. Lea los principios doctrinales aplicables al contexto del agente.
2. Critique la respuesta contra ellos.
3. Si hay violación `hard`, devuelva una respuesta revisada que mantenga
   la enseñanza y la cita pero corrija la violación.

El resultado entra al pipeline de SFT / DPO / ORPO sustituyendo a la
respuesta original. La original queda preservada en metadata para
auditoría.

## Por qué existe

F77 introdujo principios YAML. F78 introdujo el judge que evalúa pares
y produce `PreferenceVerdict`. F79 entrenó DPO/ORPO sobre `(chosen,
rejected)`.

El gap: el dataset de entrenamiento **antes del judge** puede contener
respuestas con violaciones soft o hard que el modelo aprende como
"normales" durante SFT, y el DPO posterior solo corrige a nivel
preferencia, no a nivel ejemplo. SL-CAI corrige aguas arriba: lo que
entra al SFT ya está revisado contra los 5 principios.

Beneficio medible esperado (criterio de éxito F80.0): **−50% hard
violations** en el dataset de entrenamiento del próximo round SFT.

## Arquitectura

```
SFT dataset (dataset_qa.jsonl)
         │
         ▼
  ┌─────────────────────────────────┐
  │ batch_critique(pairs, principles)│
  │  ├─ filter principles by agent   │
  │  ├─ regex tier (violations_for)  │
  │  │   └─ no hits → return as-is   │
  │  ├─ hard hit → LLM revise         │
  │  │   ├─ render critique prompt    │
  │  │   ├─ call provider             │
  │  │   └─ fallback on empty/error   │
  │  └─ stamp metadata:               │
  │      sl_cai_revised, principles,  │
  │      original_answer              │
  └─────────────────────────────────┘
         │
         ▼
SFT dataset revisado (dataset_qa_critique.jsonl)
         │
         ▼
SFT entrenamiento normal (jw-finetune train)
```

El **regex tier** corre primero: si no hay match, no se llama al LLM. En
un corpus limpio el coste extra es prácticamente nulo. En un corpus con
violaciones, el coste es +1 llamada LLM por par afectado (~30% extra de
tokens si todos los pares fueran tocados).

## Quick start

### 1. Generar el dataset SFT base

```bash
uv run jw-finetune prepare \
  --recipe doctrinal-qa-es-sft-qwen35 \
  --sources /ruta/jwpubs \
  --workspace /ruta/ws/sft-001
```

Esto produce `/ruta/ws/sft-001/dataset_qa.jsonl`.

### 2. Correr SL-CAI sobre el dataset

```bash
uv run jw-finetune build-critique-dataset \
  --workspace /ruta/ws/sft-001 \
  --synth-provider anthropic \
  --synth-model claude-haiku-4-5-20251001
```

Output: `/ruta/ws/sft-001/dataset_qa_critique.jsonl`. Por defecto
preserva la respuesta original en `metadata.original_answer`.

### 3. Auditar los cambios

```bash
# Cuántos pares fueron revisados
grep '"sl_cai_revised":"true"' /ruta/ws/sft-001/dataset_qa_critique.jsonl | wc -l

# Qué principios se violaron más
jq -r '.metadata.sl_cai_principles // empty' \
  /ruta/ws/sft-001/dataset_qa_critique.jsonl | sort | uniq -c | sort -rn
```

### 4. Entrenar SFT sobre el dataset revisado

Apuntar el SFT trainer al dataset corregido — copiar/symlink al nombre
que la recipe espera (`dataset_qa.jsonl`) o pasar `--dataset`:

```bash
cp /ruta/ws/sft-001/dataset_qa_critique.jsonl \
   /ruta/ws/sft-002/dataset_qa.jsonl
uv run jw-finetune train --workspace /ruta/ws/sft-002
```

## Filtrar por agente

Cada principio declara `applies_to: list[str]` (vacío = global). Si el
dataset es para un agente específico, pasar `--agent`:

```bash
uv run jw-finetune build-critique-dataset \
  --workspace /ruta/ws/apologetica \
  --agent apologetics
```

Sin `--agent` se aplican todos los principios sin filtrar.

## Flags

| Flag | Default | Descripción |
|---|---|---|
| `--workspace` | — | Workspace existente con `dataset_qa.jsonl`. |
| `--input` | `<workspace>/dataset_qa.jsonl` | Ruta alternativa del dataset SFT. |
| `--output` | `<workspace>/dataset_qa_critique.jsonl` | Ruta del dataset revisado. |
| `--synth-provider` | de la recipe, o `ollama` | `ollama` o `anthropic`. |
| `--synth-model` | de la recipe, o default del provider | Modelo específico. |
| `--agent` | `None` | Filtrar principios por `applies_to`. |
| `--principles/--no-principles` | `--principles` | Cargar principios builtin desde `jw_eval`. |
| `--preserve-original/--no-preserve-original` | `--preserve-original` | Guardar `original_answer` en metadata. |

## Integración programática

```python
from jw_eval.principles import load_principles
from jw_finetune.data.formats import QAPair
from jw_finetune.synth.critique import batch_critique
from jw_finetune.synth.anthropic_provider import AnthropicProvider

pairs = [QAPair(question=..., answer=..., source_chunk_id=..., language="es")]
principles = list(load_principles())
provider = AnthropicProvider(model="claude-haiku-4-5-20251001")

revised, changed = batch_critique(
    pairs,
    principles=principles,
    llm_provider=provider,
    agent="doctrinal_reasoner",
)
print(f"revised={changed}/{len(revised)}")
```

`batch_critique` devuelve `(revised_pairs, changed_count)`. Para una
sola pasada con resultado estructurado completo, usar `self_critique`
que devuelve un `CritiqueResult` con `changed`, `violated_principle_ids`,
y `original_answer`.

## Comportamiento ante fallos

| Situación | Comportamiento |
|---|---|
| No hay principio aplicable al agente | Devuelve original sin llamar al LLM. |
| Regex tier no detecta nada | Devuelve original sin llamar al LLM. |
| LLM provider lanza excepción | Devuelve original, registra el id del principio en `violated_principle_ids`. Logging WARNING. |
| LLM devuelve texto vacío | Devuelve original. |
| LLM devuelve el mismo texto | `changed=False`, no se sobrescribe nada. |

Nunca se devuelve una respuesta vacía: si la revisión falla, el par
queda intacto y la pipeline sigue.

## Cómo SL-CAI se relaciona con el judge (F78) y el `fidelity_wrap` (F77)

| Componente | Cuándo actúa | Qué hace | Costo |
|---|---|---|---|
| SL-CAI (F80.0) | aguas arriba, sobre dataset SFT | **reescribe** respuestas violadoras | +1 LLM por par afectado |
| Judge `score_pair` (F78) | comparación de pares para DPO | **selecciona** chosen vs rejected | 2 scores + comparación |
| `fidelity_wrap` (F77) | runtime en el agente | **rechaza/anota** findings malos | regex + NLI por finding |

Los tres comparten la **fuente única** `jw_eval.principles`. Cambiar un
principio actualiza el comportamiento de los tres.

## Próximo paso: CoT visible y Fase 80.1

F80.0 cierra el gap de pipeline. La siguiente fase (F80.1) entrena un
probe lineal por principio sobre activaciones del modelo SFT-revisado
para responder: "los 5 principios viven en la representación del 0.8B,
o son shortcut estilístico?". El SL-CAI mejora la señal de
entrenamiento; los probes diagnostican si esa señal se internalizó.

Ver [`docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md`](../superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md).
