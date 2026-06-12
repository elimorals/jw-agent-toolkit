# jw-interp

Mechanistic interpretability for JW fine-tuned models (F80 — Fase 80).

This package provides the analysis tools the spec describes:

- **Linear probing per principle** (F80.1, implemented)
- **Steering vectors and activation patching** (F80.2, scaffolded)
- **Qwen-Scope feature discovery** (F80.3, planned)
- **Gemma Scope cross-family validation** (F80.4, planned)
- **Transfer to production 0.8B** (F80.5, planned)

Design and roadmap: [`docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md`](../../docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md).

## Install

```bash
# Core only (numpy + sklearn) — no model needed, mock capturer included.
uv sync

# With torch / nnsight / transformers for real model probing
uv sync --extra torch

# With SAELens for Gemma Scope (F80.4)
uv sync --extra sae
```

## What's implemented now (F80.1 scaffolding)

```python
from jw_interp import (
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
    train_probe,
)
from jw_interp.activations import MockActivationCapturer

# 1. Build a contrastive dataset for a principle
builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
dataset = builder.build("PF001-canon-only")
print(f"{dataset.n_pairs} pairs / {dataset.n_prompts} prompts")

# 2. Capture activations (mock now; torch capturer comes when checkpoint exists)
capturer = MockActivationCapturer(hidden_size=64)
batches = capturer.capture(dataset, layers=[0, 4, 8, 12])

# 3. Train a probe per layer
for batch in batches:
    result = train_probe(batch, "PF001-canon-only")
    print(f"layer {result.layer}: acc={result.accuracy:.3f} auc={result.auc:.3f}")
```

## Why mock first

The real Qwen3.5-0.8B fine-tuned checkpoint may not exist yet at the moment
you read this. The `MockActivationCapturer` produces deterministic,
linearly-separable activations by design — so the **probe pipeline itself**
is correct before we ever touch a GPU. When the checkpoint lands, swap the
capturer to a `TorchActivationCapturer` (under construction in
`torch_capture.py`) and the rest of the pipeline keeps working.

## Status

This package is at F80.1 scaffolding. Probing math works end-to-end on
synthetic data. The real-model capturer (nnsight-based) is the next
deliverable, gated on either (a) the user's Qwen3.5-0.8B DPO checkpoint
being available, or (b) a stand-in checkpoint (e.g. Qwen3.5-0.8B-Base
without fine-tune) being chosen as proxy.
