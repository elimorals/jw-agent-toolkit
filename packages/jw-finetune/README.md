# jw-finetune

Plataforma local de fine-tuning para publicaciones JW, basada en [Unsloth](https://github.com/unslothai/unsloth).

> ⚠️ **Disclaimer**: Este paquete genera modelos derivados de publicaciones con copyright de Watchtower Bible and Tract Society. El uso de los pesos resultantes es responsabilidad del usuario y debe respetar los términos oficiales. El paquete NO distribuye pesos ni contenido.

## ¿Para quién es?

Para publicadores/programadores que quieren un asistente JW personal, local, offline, entrenado con su propia biblioteca (JWPUB / EPUB que ya descargaste desde JW Library).

## Pipeline

```
JWPUB / EPUB / WOL → extract → dedupe → chunk
        → (CPT raw)  o  (SFT Q&A sintéticos via Anthropic/Ollama)
        → train (Unsloth LoRA)
        → eval (citas + terminología)
        → export (GGUF / MLX / safetensors)
```

## Instalación

```bash
# Base (data prep + recipes, sin GPU)
uv sync --package jw-finetune

# NVIDIA
uv sync --package jw-finetune --extra cuda

# Apple Silicon
uv sync --package jw-finetune --extra mlx

# AMD
uv sync --package jw-finetune --extra rocm

# Synth Q&A
uv sync --package jw-finetune --extra synth
```

## Quick start

```bash
jw-finetune presets
jw-finetune prepare --recipe doctrinal-qa-es-sft --source ./mis-jwpubs/
jw-finetune train --workspace ./jw-finetune-workspace/run-*
jw-finetune export --checkpoint .../final --format gguf --quant Q4_K_M --out ./mi-modelo
```

Ver `docs/guias/fine-tuning-local.md` para la guía completa.
