---
title: "Verificador de citas en imágenes (Fase 70)"
description: "Defensa visual contra citas falsas en memes/screenshots: VLM + OCR + RAG F33 + NLI F39. Emite SUPPORTED/DISTORTED/FABRICATED/UNVERIFIABLE."
date: "2026-06-11"
---

# Verificador de citas en imágenes (Fase 70)

> Defensa contra desinformación visual. Toma una imagen (screenshot,
> meme, foto de publicación) y emite uno de 4 veredictos:
> `SUPPORTED`, `DISTORTED`, `FABRICATED`, `UNVERIFIABLE`. Pipeline
> 100% local-first con OCR + heurísticas visuales + RAG/NLI
> inyectables.

## Quick start

```bash
# Verificar imagen (requiere Tesseract si no usas --ocr-text)
jw verify-image check meme.jpg

# Bypass de Tesseract: OCR override manual
jw verify-image check meme.jpg --ocr-text "Texto pegado de la imagen..."

# Pasar descripción visual (de un VLM externo)
jw verify-image check meme.jpg --vlm-description "Cover with font mismatch"

# Modo breve
jw verify-image check meme.jpg --ocr-text "..." --brief

# Listar los 4 veredictos y acciones sugeridas
jw verify-image verdicts
```

## CLI

| Comando                  | Descripción                              |
|--------------------------|------------------------------------------|
| `jw verify-image check`  | Verifica una imagen y emite JSON         |
| `jw verify-image verdicts` | Lista los 4 veredictos posibles        |

### Flags de `check`

| Flag                  | Default | Efecto                                       |
|-----------------------|---------|----------------------------------------------|
| `--language` / `-l`   | `es`    | Idioma del OCR (`es` / `en` / `pt`)          |
| `--ocr-text`          | —       | Bypass Tesseract: provee texto directo       |
| `--vlm-description`   | —       | Hint visual desde un VLM externo             |
| `--brief`             | `False` | Solo verdict + confidence + suggested_action |

## MCP

| Tool                       | Descripción                              |
|----------------------------|------------------------------------------|
| `verify_image_quote_tool`  | Devuelve `ImageQuoteVerdict` dict        |

## Los 4 veredictos

| Verdict        | Significado                                        | Acción sugerida              |
|----------------|----------------------------------------------------|------------------------------|
| `SUPPORTED`    | Cita real, presentación sin anomalías visuales     | `share_with_correct_link`    |
| `DISTORTED`    | Cita real pero contexto/visual alterado, o contradice | `share_corrected_version` |
| `FABRICATED`   | Sin coincidencia + anomalías visuales              | `do_not_share`               |
| `UNVERIFIABLE` | Señal insuficiente para decidir                    | `discuss_with_elders`        |

## Arquitectura

```
   meme.jpg
      │
      ▼
 ┌─────────────────────┐
 │ load_image (PIL)    │
 │  - EXIF rotation    │
 │  - pHash 8x8        │
 └──────────┬──────────┘
            │
   ┌────────┴────────┐
   ▼                 ▼
 OCR              VLM description
 (Tesseract       (opcional)
  opt-guarded)
   │                 │
   ▼                 ▼
 cleanup_ocr     fingerprint
 extract_quote   - apparent_era
                 - apparent_publication
                 - visual_anomalies
                 - layout_consistency
            │
            ▼
   ┌────────────────────┐
   │ RAG retriever      │ (inyectable)
   │ -> [RAGHit, ...]   │
   └──────────┬─────────┘
              ▼
   ┌────────────────────┐
   │ NLI F39 verify     │ (inyectable)
   │ entails/contradicts│
   └──────────┬─────────┘
              ▼
   ┌────────────────────┐
   │ synthesize_verdict │
   │ -> SUPPORTED       │
   │    DISTORTED       │
   │    FABRICATED      │
   │    UNVERIFIABLE    │
   └────────────────────┘
```

## Detección de framing visual

`fingerprint.py` aplica heurísticas conservadoras (regex sobre VLM
caption + OCR text):

- **`apparent_era`**: extrae año de copyright o marcadores estilísticos
  (`primary colors bold` → 1980s, `pixelated logo` → 1990s, etc.).
- **`apparent_publication`**: detecta títulos `Atalaya`, `Watchtower`,
  `Despertad`, `Awake!`, `Sentinela`.
- **`visual_anomalies`**: `font_mismatch`, `logo_modified`,
  `layout_inconsistent`, `color_off`, `edited_composition`, etc.
- **`layout_consistency`**: `consistent` / `inconsistent` / `unknown`.

## Extracción de cita

`extractor.py` parsea:
- **`cleaned_quote`**: bloque más largo no-atribución.
- **`language_detected`**: sniffer barato sobre hint words es/en/pt.
- **`has_attribution`** + **`attribution_text`**: detecta URLs wol,
  pub codes (`w23.04`, `g23`, etc.), títulos de revista.

## Reglas de síntesis de veredicto

```python
no matches + short quote (<20 chars)        -> UNVERIFIABLE (0.3)
no matches + anomalías visuales              -> FABRICATED (0.7)
no matches + sin anomalías                   -> UNVERIFIABLE (0.4)
top match entails + score ≥0.85 + anomalías  -> DISTORTED (0.8)
top match entails + score ≥0.85 + clean      -> SUPPORTED (≤0.95)
top match contradicts                        -> DISTORTED (0.85)
otros (neutral, entails low score)           -> UNVERIFIABLE (0.35)
```

## Integración en F65 meta-orchestrator

Registrada como tool `verification.image_quote`. El planner F65 puede
componer:

```json
{"steps": [
  {"id": "s1", "tool": "verification.image_quote",
   "args": {"image_path": "/tmp/meme.jpg",
            "ocr_text_override": "<texto pegado>"}}
]}
```

## Dependencias opcionales

| Feature        | Dep                  | Fallback                       |
|----------------|----------------------|--------------------------------|
| OCR            | `pytesseract` + tesseract | `--ocr-text` manual       |
| Imagen + pHash | `Pillow`             | requerido                       |
| RAG retrieval  | F33 RAG store        | sin RAG → UNVERIFIABLE          |
| NLI verify     | F39 provider         | sin NLI → neutral en matches    |

## Estado actual

- 8 tasks TDD. **51 tests passing** (5 models + 6 preprocess + 12
  fingerprint + 9 extractor + 8 verdict + 6 engine + 3 CLI + 1 MCP +
  2 meta + 1 protocol delta).
- Pipeline end-to-end con `verify_image_quote()` async.
- 4 veredictos discretos con confidence + suggested_action.
- CLI `jw verify-image {check,verdicts}` + MCP tool.
- Meta tool `verification.image_quote` en F65.
- RAG retriever + NLI inyectables (Protocol-shaped).

## Pendiente (futuro)

- Wire-up con RAG real F33 (`from jw_rag.store import default_store`).
- Wire-up con NLI real via F65 nli_factory.
- VLM provider real Florence-2 (via Plugin SDK F41) para fingerprint.
- F48 browser extension: context menu "Verificar imagen" que llama
  `verify_image_quote_tool` con la imagen seleccionada.
- Golden dataset de 50 imágenes (25 reales + 15 distorsionadas + 10
  fabricadas) como tests de regresión.
