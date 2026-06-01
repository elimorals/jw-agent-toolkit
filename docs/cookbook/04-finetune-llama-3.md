# Fine-tune de Llama 3 sobre tu biblioteca JW

> **Tiempo estimado**: 1-3 horas (GPU)
> **Requisitos**: jw-finetune con extras `[unsloth]`, GPU NVIDIA o Apple Silicon.
> **Slug URL**: `/cookbook/04-finetune-llama-3`

## ¿Qué construyes?

Pipeline completo: JWPUBs locales → Q&A extraídos (preset `synth_provider=None`) → LoRA fine-tune sobre Llama 3.1 8B → export GGUF para inference local.

## Código (copy-pasteable)

```python
# test slow
# Slow test: requires GPU + jw-finetune extras. Skipped unless `-m slow`.
# Real workflow shown; verify only that the pipeline modules import cleanly.

import importlib
modules = [
    "jw_finetune.synth.async_orchestrator",
    "jw_finetune.data.chunk",
]
for m in modules:
    spec = importlib.util.find_spec(m)
    assert spec is not None, f"{m} not importable"
```

## Por qué funciona

`synth_provider=None` extrae Q&A **reales** de Atalayas/Study Notes/Workbooks en lugar de sintetizarlos. Eso garantiza fidelidad doctrinal: el modelo entrenado responde con citas verificables, no con paráfrasis aproximadas.

## Variaciones

- `synth_provider="claude"` para complementar con Q&A sintéticos cuando hay pocos datos extraíbles.
- `target="mlx"` para Apple Silicon en lugar de Unsloth/NVIDIA.
- Cambiar `base_model="llama3.1:8b"` por modelos más pequeños (Qwen2.5 0.5B) para iterar rápido.

## Próximo paso

→ [05 — Plugin parser para un formato custom](05-add-parser.md)
