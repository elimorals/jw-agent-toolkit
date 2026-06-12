# Probing lineal por principio (F80.1)

Diagnóstico interpretabilidad de bajo coste: ¿los 5 principios doctrinales
viven en la representación interna del modelo fine-tuneado, o son shortcut
estilístico?

## Idea

Para cada principio (PF001-canon-only, …, PF012-respect-conscience):

1. Construir un **dataset contrastivo**: pares `(prompt_positivo,
   prompt_negativo)` con la misma superficie pero distinta relevancia para
   el principio.
2. Pasar todos los prompts por el modelo y capturar **activaciones
   residuales** en varias capas.
3. Entrenar una **regresión logística** (probe lineal) por capa para
   separar positivos de negativos.
4. Reportar **accuracy** y **AUC** en una partición held-out.

Si el probe logra ≥ 0.80 accuracy en alguna capa, el principio "vive" en
la representación. Si todas las capas dan ≤ 0.70, el modelo está
respondiendo doctrinalmente por **shortcut**, no por internalización.

## Quick start

### Con activaciones sintéticas (sin GPU)

Útil para validar la maquinaria. El `MockActivationCapturer` produce datos
linealmente separables por construcción → el probe debe hit ≥ 0.95.

```python
from jw_interp import (
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
    train_probes_for_principle,
)
from jw_interp.activations import MockActivationCapturer

builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
dataset = builder.build("PF001-canon-only")

cap = MockActivationCapturer(hidden_size=64)
batches = cap.capture(dataset, layers=[0, 4, 8, 12, 16, 20])
results = train_probes_for_principle(batches, "PF001-canon-only")
for r in results:
    print(f"L{r.layer:02d}: acc={r.accuracy:.3f} auc={r.auc:.3f}")
```

### Con modelo real (Qwen3.5-0.8B-Base como proxy, M4 Max o RTX 5090)

Requiere la extra `torch`:

```bash
uv sync --extra torch
```

```python
from jw_interp import (
    PrincipleContrastiveBuilder,
    TorchActivationCapturer,
    TorchCaptureConfig,
    build_default_contrastive_specs,
    train_probes_for_principle,
)

cap = TorchActivationCapturer(
    "Qwen/Qwen3.5-0.8B",  # o ruta a tu DPO checkpoint local
    config=TorchCaptureConfig(
        device=None,        # None = auto: cuda > mps > cpu
        dtype="float16",
        max_input_tokens=512,
        pooling="last_token",
    ),
)

builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
for principle_id in builder.principle_ids:
    dataset = builder.build(principle_id)
    # Asumiendo Qwen3.5-0.8B con 24 capas, muestreamos cada 4
    batches = cap.capture(dataset, layers=list(range(0, 24, 4)))
    results = train_probes_for_principle(batches, principle_id)
    print(f"=== {principle_id} ===")
    for r in results:
        print(f"  L{r.layer:02d}: acc={r.accuracy:.3f}")
```

## Datasets contrastivos

Cada principio trae un `ContrastiveSpec` de **seed** (3–4 slots). Para
correr probes serios necesitas **≥ 50 pares por principio**, ideally
diversos.

Para extender, añade un spec local antes de pasar al builder:

```python
from jw_interp import ContrastiveSpec, PrincipleContrastiveBuilder, build_default_contrastive_specs

extra_specs = [
    ContrastiveSpec(
        principle_id="PF001-canon-only",
        positive_template="Explícame {topic}",
        negative_template="Qué día se publicó la Atalaya de {topic}",
        slots=[
            {"topic": "el limbo"},
            {"topic": "el rezo a Maria"},
            {"topic": "los siete sacramentos"},
            # ... ~50 más
        ],
    ),
]

specs = build_default_contrastive_specs() + extra_specs
builder = PrincipleContrastiveBuilder(specs)
```

## Cómo interpretar los resultados

| Resultado | Interpretación |
|---|---|
| Accuracy ≥ 0.90 en una capa media (L10–L16) | El principio está claro en la representación. Bueno. |
| Accuracy 0.75–0.90 con pico claro en una capa | Principio presente pero más débil. Considera más datos contrastivos o mover SL-CAI a más muestras. |
| Accuracy ≤ 0.65 en todas las capas | **Shortcut detectado.** El modelo responde correctamente pero no por internalización del principio. Acción: revisar dataset DPO de F79. |
| Accuracy ≥ 0.95 en capa 0 ya | Sospecha: el contraste está en la superficie textual, no en semántica. Revisar templates negativos. |

## Próximos pasos

- F80.2: convertir probes en **steering vectors** y validar causalidad.
- F80.3: comparar probes con features Qwen-Scope sobre Qwen3.5-2B-Base.
- F80.5: persistir probes al disco y usarlos como Tier 4 en `fidelity_wrap`.

Spec completa: [`docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md`](../superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md).
