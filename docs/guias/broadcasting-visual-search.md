---
title: "Búsqueda visual frame-level en Broadcasting (Fase 69)"
description: "Sampler de frames + VLM captioning + CLIP + RRF + OCR opcional sobre videos de JW Broadcasting. Frames nunca se almacenan, solo captions + embeddings."
date: "2026-06-11"
---

# Búsqueda visual frame-level en Broadcasting (Fase 69)

> Indexa videos locales por frame con VLM + CLIP + OCR. Búsqueda
> híbrida (FTS5 + cosine + RRF) que devuelve timestamps + captions +
> deep links a `tv.jw.org`. **Los frames nunca se almacenan**, solo
> captions textuales + embeddings vectoriales (no reconstruibles a
> imagen).

## Quick start

```bash
# Indexar (con ffmpeg real)
jw broadcasting-visual index path/to/video.mp4 --interval 5

# Smoke test sin ffmpeg
jw broadcasting-visual index path/to/video.mp4 --no-ffmpeg --video-id demo

# Buscar
jw broadcasting-visual search "viajes de Pablo" --top-k 5

# Stats del índice
jw broadcasting-visual stats

# Override del root del índice
jw broadcasting-visual stats --root /tmp/visual
```

## CLI

| Comando                            | Descripción                              |
|------------------------------------|------------------------------------------|
| `jw broadcasting-visual index`     | Indexa un video local                    |
| `jw broadcasting-visual search`    | Búsqueda híbrida FTS5 + CLIP cosine      |
| `jw broadcasting-visual stats`     | Stats del índice (videos, frames, MB)    |

### Flags de `index`

| Flag           | Default | Efecto                                       |
|----------------|---------|----------------------------------------------|
| `--interval`   | `5.0`   | Segundos entre frames sampled                |
| `--root`       | —       | Override del directorio del índice           |
| `--no-ffmpeg`  | `False` | Usa fake sampler (testing offline)           |
| `--video-id`   | basename| Override del id del video                    |

## MCP

| Tool                          | Descripción                              |
|-------------------------------|------------------------------------------|
| `broadcasting_visual_index`   | Indexa un video por frame                |
| `broadcasting_visual_search`  | Búsqueda híbrida con RRF                 |
| `broadcasting_visual_stats`   | Stats del índice                         |

## Variables de entorno

| Env                       | Default                                                 | Efecto                                  |
|---------------------------|---------------------------------------------------------|-----------------------------------------|
| `JW_VISUAL_INDEX_ROOT`    | `~/.jw-agent-toolkit/broadcasting/visual`               | Override del root del índice            |

## Arquitectura

```
   video.mp4
        │
        ▼
   ┌────────────────────────┐
   │ sampler (ffmpeg)       │ - import-guarded
   │  -> (ts, jpeg_bytes)   │
   └──────────┬─────────────┘
              │
     ┌────────┼─────────────┐
     ▼        ▼             ▼
   VLM     CLIP          OCR (opt)
   provider encoder
   caption  vector
              │
              ▼
   ┌────────────────────────┐
   │ VisualIndexer          │
   │  - sqlite (frames)     │
   │  - frames_fts (FTS5)   │
   │  - vectors.npy         │
   │  - thumbs/ (256x144)   │
   └──────────┬─────────────┘
              │
              ▼
   visual_search(query)
     ├─ FTS5 bm25 sobre caption||ocr||transcript
     ├─ CLIP text_encoder(query) -> cosine
     └─ RRF (k=60) -> top-K -> VisualSearchHit[]
```

## Storage layout

```
~/.jw-agent-toolkit/broadcasting/visual/
  index.sqlite           # frames table + FTS5 virtual
  vectors.npy            # (N, dim) float32 normalized
  meta.json              # provider versions, dim
  thumbs/                # opcional, 256x144 JPEG
    {video_id}/
      {timestamp}.jpg
```

## Provider abstraction (Plugin SDK F41)

Por defecto se usan `FakeVLMProvider` + `FakeCLIPEncoder`
deterministas. Los providers reales se cablean via Plugin SDK F41
con grupos de entry-points:

```toml
[project.entry-points."jw_agent_toolkit.vlm_providers"]
florence-2 = "florence2_provider:Florence2Provider"

[project.entry-points."jw_agent_toolkit.clip_encoders"]
vit-b-32 = "clip_provider:VitB32CLIP"
```

Cuando se instala el extra correspondiente:

```bash
uv add 'jw-core[broadcasting-visual]'
```

los providers reales se descubren automáticamente al `build_engine()`.

## Integración en F65 meta-orchestrator

`broadcasting.visual_search` está registrada como tool del
meta-orchestrator. El planner F65 puede invocarla con:

```json
{"steps": [
  {"id": "s1", "tool": "broadcasting.visual_search",
   "args": {"query": "mapa de Pablo", "top_k": 5}}
]}
```

Las `findings` devueltas incluyen `citation.url` con `deep_link` a
`tv.jw.org` con anchor `#t=<seconds>`.

## Privacidad

- Los frames **nunca** se almacenan en el filesystem.
- Solo se persisten captions textuales + embeddings vectoriales
  (no reconstruibles a imagen) + thumbs opcionales (256x144).
- Sin telemetría externa. Sin upload.
- Respetar TOS de tv.jw.org / JW Broadcasting — descargas oficiales
  solo a través de canales oficiales.

## Estado actual

- 7 tasks TDD completas. **30 tests passing** (5 models + 7 providers +
  3 sampler + 7 indexer + 5 search + 4 engine + 2 CLI + 2 MCP + 2 meta
  + protocol updates).
- VLM + CLIP provider Protocols + Fakes deterministas.
- Frame sampler con ffmpeg import-guarded + fake fallback para tests.
- VisualIndexer con SQLite + FTS5 + vectors.npy + meta.json.
- Hybrid search FTS5 + CLIP cosine + RRF (k=60).
- CLI `jw broadcasting-visual {index,search,stats}` + MCP 3 tools.
- Meta tool `broadcasting.visual_search` en F65.

## Pendiente (futuro)

- Provider real Florence-2-base via Plugin SDK F41 + extra
  `[broadcasting-visual]` con polyglot venv F53.
- CLIP real ViT-B/32 via Plugin SDK F41.
- OCR sobre frames (reuso F7 Tesseract) + ingest en `frames.ocr_text`.
- Thumbs JPEG 256x144 opt-in con flag `--with-thumbs`.
- Linkage al transcript de `broadcasting.py` (F3) cuando exista
  WebVTT del video.
- Tool dispatcher en F67 reasoner que rutee `tool_hint=broadcasting.frame_search`.
