# VLM-OCR (Fase 36)

`jw_core.vision.vlm` replaces the legacy Tesseract OCR path with a typed,
structured Vision-Language-Model pipeline that returns one block per
typographic element on the page.

## Quick start

```python
from jw_core.vision import extract_bible_reference_from_image_v2

out = extract_bible_reference_from_image_v2(
    "path/to/page.png", language="es"
)
print(out["reference"])         # parsed BibleRef.model_dump() or None
print(out["text"])              # raw text fallback (compat)
for block in out["structured_page"].blocks:
    print(block.kind, block.text)
```

## Choosing a provider

| Hardware | Provider | Install |
|---|---|---|
| Apple Silicon | `qwen3vl_local` (mlx) | `uv pip install jw-core[vlm-mlx]` + `huggingface-cli download mlx-community/Qwen3-VL-2B-Instruct-4bit` |
| NVIDIA GPU | `qwen3vl_local` (vllm) | `uv pip install jw-core[vlm-nvidia]` |
| CPU only | `qwen3vl_local` (gguf) | `uv pip install jw-core[vlm-cpu]` + download GGUF |
| API only | `claude_vision` | `uv pip install jw-core[vlm-anthropic]` + `ANTHROPIC_API_KEY` |
| API only | `openai_vision` | `uv pip install jw-core[vlm-openai]` + `OPENAI_API_KEY` |
| API only | `qwen3vl_api` | `uv pip install jw-core[vlm-api-qwen]` + `JW_QWEN3VL_API_KEY` + `JW_QWEN3VL_API_BASE` |
| Last resort | `tesseract_fallback` | `brew install tesseract` + `uv pip install jw-core[vlm-tesseract]` |

The factory picks the first available backend from this chain:
`qwen3vl_local → qwen3vl_api → claude_vision → openai_vision → tesseract_fallback`.

Force a provider:
```bash
export JW_VLM_PROVIDER=claude_vision
```

Model overrides:
- `JW_CLAUDE_VISION_MODEL` — default `claude-haiku-4-5`. ClaudeVisionProvider is
  an *adapter* over the `anthropic` SDK; Claude is natively multimodal.
- `JW_OPENAI_VISION_MODEL` — default `gpt-4o-mini`.
- `JW_QWEN3VL_LOCAL_MODEL` — model id / path for local Qwen3-VL backend.
- `JW_QWEN3VL_LOCAL_TARGET` — `mlx` | `nvidia` | `cpu`.

## CLI

```bash
JW_VLM_PROVIDER=fake jw image extract path/to/page.png --language es
JW_VLM_PROVIDER=fake jw image ingest  path/to/page.png --language es \
    --store ~/.jw-toolkit/rag
```

## MCP

The MCP server exposes two new tools:

- `extract_structured_page(image_path, language)` → `StructuredPage` JSON.
- `ingest_image_to_rag(image_path, language)` → `{"chunks": n}`.

## Migrating from `ocr_image()`

`ocr_image()` still works but emits `DeprecationWarning`. Drop-in replacement:

```python
from jw_core.vision import migrate_to_vlm

ocr_image = migrate_to_vlm()   # callable with same (path, language=) signature
text = ocr_image("page.png", language="es")
```

## Boundaries

- One image per call. Multi-page PDFs: see Fase 37 (colpali-visual).
- Pesos locales no se distribuyen — el usuario los baja con `huggingface-cli`.
- No fine-tuning aquí (ver Fase 11 / `jw-finetune`).
