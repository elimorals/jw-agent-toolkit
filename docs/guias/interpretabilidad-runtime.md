# Interpretabilidad en runtime: Tier 4 de `fidelity_wrap` (F80.5)

Última fase de la pila de alineamiento. Empotra evidencia interpretable
(probes lineales entrenados en F80.1) en la validación de runtime de los
agentes, sin tocar producción ni romper el contrato actual.

## Pila completa

```
PRODUCCIÓN  ── agente genera Finding ──▶ fidelity_wrap
                                          ├─ Tier 1: regex principios (F77, cheap)
                                          ├─ Tier 2: NLI entailment (F39, semantic)
                                          ├─ Tier 3: judge oracle (F78, training-time)
                                          └─ Tier 4: probes lineales (F80.5, interpretable)
```

Los **Tier 1–3** ya existían. **Tier 4 es el nuevo**: por cada Finding,
evalúa todos los probes lineales entrenados (uno por principio doctrinal)
sobre el texto del Finding y anota los scores en metadata. **Nunca veta
un Finding por sí solo** — es evidencia observacional.

## Diseño honesto

Tres reglas de oro:

1. **Probe miss ≠ rechazo.** Si un probe miss bloqueara un Finding, una
   probe mal calibrada apagaría producción. Tier 4 solo anota.
2. **Cero acoplamiento.** `fidelity_wrap` recibe un `Callable[[str], dict
   [str, float]]`. Nada de imports de `jw_interp`. El usuario inyecta el
   evaluador, sea real (vía `jw_interp.runtime.ProbeEvaluator`) o mock.
3. **Coherence cross-tier.** Cuando el probe contradice o confirma el
   regex tier, el metadata lo dice. El humano (o tooling posterior)
   decide qué hacer con esa información.

## Categorías de coherence

`finding.metadata["probe_coherence"]` toma uno de cuatro valores:

| Coherence | Regex hard violation | Probe miss | Significado |
|---|---|---|---|
| `clear` | no | no | Todo limpio. |
| `confirms` | sí | sí (mismo PF) | Probe y regex coinciden — alta confianza en el reject. |
| `conflicts` | sí | no | Regex flag pero probe dice principio internalizado — revisar regex o aceptar como falso positivo. |
| `silent` | no | sí | **Shortcut sospechoso**: superficie limpia pero internamente el principio no se activó. Esto es lo que F80 existe para detectar. |

## Quick start

### 1. Entrenar probes con F80.1

```python
from jw_interp import (
    PrincipleContrastiveBuilder,
    ProbeStoreManifest,
    TorchActivationCapturer,
    TorchCaptureConfig,
    build_default_contrastive_specs,
    save_probe_set,
    train_probes_for_principle,
)

capturer = TorchActivationCapturer(
    "Qwen/Qwen3.5-0.8B",  # o tu checkpoint DPO local
    config=TorchCaptureConfig(dtype="float16"),
)
builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())

results = []
for pid in builder.principle_ids:
    ds = builder.build(pid)
    # Capturamos en una capa media — F80.1 te dirá cuál es mejor
    batches = capturer.capture(ds, layers=[12])
    results.extend(train_probes_for_principle(batches, pid))

save_probe_set(
    results,
    probes_dir="~/jw-probes/qwen35-0.8b-dpo",
    manifest=ProbeStoreManifest(
        model_name="Qwen/Qwen3.5-0.8B",
        hidden_size=capturer.hidden_size,
        n_layers=capturer.n_layers,
    ),
)
```

### 2. Construir el evaluador

```python
from jw_interp.runtime import build_probe_evaluator

evaluator = build_probe_evaluator(
    probes_dir="~/jw-probes/qwen35-0.8b-dpo",
    # capturer queda lazy: si torch está, se construye uno default
    # apuntando al model_name del manifest.
)
```

### 3. Enchufar en `fidelity_wrap`

```python
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_eval.principles import load_principles

@fidelity_wrap(
    on_fail="warn",
    principles=load_principles(),
    probe_evaluator=evaluator,
    probe_min_score=0.5,
)
async def apologetics(query: str): ...
```

Las metadatas que aparecen en cada Finding:

```python
finding.metadata["probe_scores"]     # JSON: {"PF001-canon-only": 0.92, "PF002-cite": 0.41, ...}
finding.metadata["probe_misses"]     # CSV: "PF002-cite,PF012-respect-conscience"
finding.metadata["probe_coherence"]  # "clear" | "confirms" | "conflicts" | "silent"
finding.metadata["probe_min_score"]  # threshold usado, e.g. "0.5"
```

A nivel `AgentResult`:

```python
result.metadata["probe_tier4_enabled"] = "true"
result.metadata["probe_min_score"] = "0.5"
```

## Latencia esperada

Spec F80 puso un budget de **<50ms p95** para Tier 4. El path eager
(default `build_probe_evaluator`) hace **un forward pass del modelo
fine-tuneado por Finding**, lo cual a 0.8B en M4 Max con MLX es ~30–80ms
por inferencia. Para producción de baja latencia hay tres optimizaciones
fáciles:

1. **Cache de activaciones**: si el agente ya generó el Finding pasando
   por el modelo, conserva el hidden state y pasa por `score_cached()`
   en lugar de re-tokenizar.
2. **Solo capas decisivas**: F80.1 te dice qué capa(s) tiene la mejor
   accuracy. Configura el manifest para incluir solo esas; el capturer
   solo correrá hooks en ellas.
3. **Modo asíncrono**: cuando latencia bloqueante es inaceptable, mover
   Tier 4 a una cola post-respuesta y registrar el reporte después.

## Modo mock para tests

Cualquier caller (test o producción) puede inyectar un evaluador mock que
devuelve dict canned:

```python
from jw_interp.runtime import mock_evaluator

evaluator = mock_evaluator({"PF001-canon-only": 0.95, "PF002-cite": 0.40})

@fidelity_wrap(probe_evaluator=evaluator)
async def my_agent(): ...
```

Esto te permite escribir tests deterministas de Tier 4 sin GPU ni
modelo.

## Próximos pasos

Cuando tengas el checkpoint Qwen3.5-0.8B DPO real:

1. Re-entrenar los probes contra el modelo doctrinal (no contra el base).
2. Comparar `probe_coherence` distribuciones entre el base y el DPO. El
   DPO debe mover el agregado hacia `clear`/`confirms` y reducir
   `silent`.
3. Ajustar `probe_min_score` por percentiles del corpus de calibración
   para que ~5% del tráfico legítimo caiga en `silent` (target de
   sensibilidad razonable).
