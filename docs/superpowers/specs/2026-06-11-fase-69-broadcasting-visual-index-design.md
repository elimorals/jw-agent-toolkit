# Fase 69 — `broadcasting-visual-index`: búsqueda multimodal frame-level

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (multimodal)
> **Capa**: B — Multimodal
> **Depende de**: F3 `broadcasting` (subtítulos WebVTT), F36 `vlm-ocr`, F37 `colpali-visual`, F49 `second-brain` (GraphRAG), F53 `polyglot-python` (venv aislado), F41 `plugin-sdk` (vlm_providers)
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F3 `broadcasting` index (solo transcripción, sin búsqueda visual)

## Motivación

`broadcasting.py` (F3) indexa transcripciones WebVTT de JW Broadcasting
con SQLite FTS5. Funciona para "muéstrame el momento donde dice 'amor'",
pero falla para:

- "muéstrame el mapa de los viajes de Pablo en algún video"
- "encuentra el clip donde aparece la portada de la Atalaya 2024 mayo"
- "videos con ilustraciones de la nueva Tierra"

Estos requieren **percepción visual** sobre los frames, no solo
transcripción.

## Objetivos

1. CLI `jw broadcasting visual-index <video.mp4>` extrae frames cada
   N segundos, los pasa por VLM para caption, los embedea con CLIP,
   los guarda en índice híbrido.
2. CLI `jw broadcasting visual-search "viajes de Pablo"` devuelve
   timestamps + thumbnails + transcripción concurrente.
3. **Fusión texto+visual**: la búsqueda combina FTS5 (transcripción)
   + CLIP cosine (frame embeddings) + RRF.
4. **Storage eficiente**: NUNCA frames en disco; solo captions +
   embeddings + thumbnail 256×144 (opcional).
5. VLM via Plugin SDK F41 (`jw_agent_toolkit.vlm_providers`).
6. Polyglot Python F53 si el VLM requiere torch+cuda en venv aparte.

## No-objetivos (boundaries vinculantes)

- **No** redistribuye frames. Solo captions textuales + embeddings
  vectoriales (no reconstruibles a imagen).
- **No** descarga videos automáticamente; el usuario provee el path
  local (TOS de JW Broadcasting respetado — descargas oficiales solo
  por la app/website de JW).
- **No** indexa videos cifrados o protegidos.
- **No** reemplaza el index F3; lo extiende.

## Decisión clave: ¿VLM cloud vs local-first?

### Opción A — Cloud VLM (GPT-4o, Claude vision, Gemini Pro Vision)

**Pros**: precisión alta, sin GPU local.
**Contras**: viola local-first; coste $0.005-0.01 por frame; un video
de 30 min con frame cada 5s = 360 frames = $1.80-$3.60 solo en VLM.

### Opción B — Local VLM (Llava-1.6, Qwen-VL-7B, Florence-2-large)

**Pros**: cero coste, cero red.
**Contras**: requiere GPU para tiempos razonables.

### Opción C — Híbrido por defecto local, opt-in cloud

Plugin SDK F41 permite registrar ambos. Default = `florence-2-base`
(quick captioning, CPU-friendly). Power user puede activar Claude
vision por env.

### Decisión: **Opción C** (híbrido vía Plugin SDK F41)

Justificación:
1. F41 ya tiene `vlm_providers` entry-point.
2. Florence-2-base (230M params) corre razonable en CPU para
   captioning corto.
3. CLIP embeddings se computan con un solo modelo small (ViT-B/32)
   independiente del VLM.

## Arquitectura

```
                  video.mp4
                       │
                       ▼
            ┌────────────────────┐
            │ 1. Frame sampler   │
            │    ffmpeg @ N=5s   │
            │    in-memory only  │
            └─────────┬──────────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
  ┌──────────┐ ┌──────────────┐ ┌──────────┐
  │ VLM      │ │ CLIP encoder │ │ OCR      │
  │ caption  │ │ (ViT-B/32)   │ │ (text in │
  │          │ │ → vector 512 │ │  frame)  │
  └────┬─────┘ └──────┬───────┘ └────┬─────┘
       │              │               │
       └──────────────┼───────────────┘
                      ▼
        ┌──────────────────────────────┐
        │ VisualIndex                  │
        │  - sqlite: frames table      │
        │  - vectors.npy: embeddings   │
        │  - thumbs/ (256x144 jpg)     │
        │  - WebVTT FTS5 linked        │
        └─────────────┬────────────────┘
                      │
                      ▼
            visual_search(query)
              ├─ FTS5 over caption + OCR + transcript
              ├─ CLIP text encoder(query) → vec
              ├─ cosine over embeddings
              └─ RRF fusion → top-K
```

## Contratos de tipos

```python
# packages/jw-core/src/jw_core/broadcasting/visual/models.py

from pydantic import BaseModel, Field
from typing import Literal

class VisualFrame(BaseModel):
    video_id: str
    timestamp_s: float
    caption: str                    # del VLM
    ocr_text: str = ""              # texto detectado en pantalla
    embedding_id: int               # índice en vectors.npy
    thumb_path: str | None = None   # 256x144 jpg local
    transcript_concurrent: str = "" # texto WebVTT en ese momento

class VisualSearchHit(BaseModel):
    video_id: str
    timestamp_s: float
    score: float
    source: Literal["fts", "clip", "ocr", "hybrid"]
    caption: str
    transcript_concurrent: str
    thumb_path: str | None = None
    deep_link: str                  # jw.org broadcasting URL con #t=N

class IndexStats(BaseModel):
    videos_indexed: int
    frames_total: int
    embeddings_dim: int
    storage_mb: float
    avg_frame_per_video: float
```

## API pública

```python
# packages/jw-core/src/jw_core/broadcasting/visual/__init__.py

from jw_core.broadcasting.visual.indexer import VisualIndexer
from jw_core.broadcasting.visual.search import visual_search
from jw_core.broadcasting.visual.models import (
    VisualFrame, VisualSearchHit, IndexStats
)
from jw_core.broadcasting.visual.providers import (
    VLMProvider, CLIPEncoder, register_provider
)

__all__ = [
    "VisualIndexer",
    "visual_search",
    "VisualFrame",
    "VisualSearchHit",
    "IndexStats",
    "VLMProvider",
    "CLIPEncoder",
    "register_provider",
]
```

## CLI

```bash
# Indexar
jw broadcasting visual-index /path/to/video.mp4 --interval 5

# Buscar
jw broadcasting visual-search "viajes de Pablo"

# Buscar con filtro
jw broadcasting visual-search "mapa" --top-k 5 --min-score 0.4

# Inspeccionar estado
jw broadcasting visual-stats

# Provider info
jw broadcasting visual-providers list
```

## MCP tools

- `broadcasting_visual_index(video_path, interval_s=5, language="es") → IndexStats`
- `broadcasting_visual_search(query, top_k=10, min_score=0.0) → list[VisualSearchHit]`
- `broadcasting_visual_stats() → IndexStats`

## Provider abstraction (Plugin SDK F41)

```python
# packages/jw-core/src/jw_core/broadcasting/visual/providers.py

from typing import Protocol
from PIL import Image

class VLMProvider(Protocol):
    name: str
    requires_gpu: bool

    def caption(self, image: Image.Image, language: str = "en") -> str: ...

class CLIPEncoder(Protocol):
    name: str
    embedding_dim: int

    def encode_image(self, image: Image.Image) -> list[float]: ...
    def encode_text(self, text: str) -> list[float]: ...
```

Entry points:
- `jw_agent_toolkit.vlm_providers` ya existe (F41).
- Nuevo grupo `jw_agent_toolkit.clip_encoders` (extensión a F41).

Defaults builtin:
- VLM: `florence-2-base` (huggingface microsoft/Florence-2-base)
- CLIP: `openai/clip-vit-base-patch32`

## Polyglot Python F53

Florence-2 requiere `torch>=2.0` y `transformers>=4.40`. Si la versión
del monorepo es incompatible, se aplica patrón F53:

```
packages/jw-core/src/jw_core/broadcasting/visual/runners/
  __init__.py
  florence2_runner.py        # Python script standalone con sys.argv
  install.py                 # bootstrap del venv 3.12 dedicado
  ipc_protocol.py            # contrato JSON in/out

Estado en disco:
  ~/.jw-agent-toolkit/runners/florence2/
    .venv/                   # venv Python 3.12 dedicado
    state.json               # versión, fecha install
```

CLI bootstrap:
```bash
jw broadcasting install-visual-runners --vlm florence-2 --clip vit-b-32
```

## Storage layout

```
~/.jw-agent-toolkit/broadcasting/visual/
  index.sqlite           # frames table + metadata
  vectors.npy            # (N, 512) float32 normalized
  thumbs/
    {video_id}/
      {timestamp}.jpg    # 256x144 jpg quality 70
  meta.json              # provider versions, dim, etc.
```

Tamaño estimado: 360 frames × (caption 200B + embedding 2KB +
thumb 8KB) ≈ 3.6 MB por video de 30 min.

## Fusión búsqueda (RRF)

Igual patrón que RAG F33 BM25+vector:

```python
def visual_search(query: str, top_k: int = 10) -> list[VisualSearchHit]:
    # 1. FTS5 sobre caption || ocr || transcript
    fts_hits = sqlite_fts5_search(query, limit=50)

    # 2. CLIP text → cosine over vectors
    qvec = clip_encoder.encode_text(query)
    clip_hits = cosine_top_k(qvec, vectors, k=50)

    # 3. RRF
    fused = {}
    for rank, hit in enumerate(fts_hits):
        fused[hit.frame_id] = fused.get(hit.frame_id, 0) + 1 / (60 + rank)
    for rank, hit in enumerate(clip_hits):
        fused[hit.frame_id] = fused.get(hit.frame_id, 0) + 1 / (60 + rank)
    return sorted(fused.items(), key=-score)[:top_k]
```

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `VisualFrame` Pydantic round-trip                             | Unit        |
| ffmpeg frame sampler extrae N frames                          | Integration |
| FakeVLMProvider devuelve caption determinista                 | Unit        |
| FakeCLIPEncoder devuelve vector dim correcto                  | Unit        |
| Indexer crea sqlite + vectors.npy                             | Integration |
| Búsqueda FTS5 funciona con caption fake                       | Unit        |
| Búsqueda CLIP funciona con vectores fake                      | Unit        |
| RRF fusiona correctamente con ties                            | Unit        |
| OCR en frame con texto detecta correctamente                  | Integration |
| Multi-video index mantiene `video_id` correcto                | Integration |
| `visual_stats()` reporta sizes correctos                      | Unit        |
| MCP tools serializan / deserializan                           | Integration |
| Provider via Plugin SDK F41 descubierto                       | Integration |
| Polyglot runner bootstrap genera venv                         | E2E (slow)  |

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| ffmpeg no instalado                                     | Check + mensaje claro instalación brew/apt          |
| Florence-2 lento en CPU                                 | Default interval 10s; opt-in 5s para precisión      |
| CLIP+VLM ocupan ~600MB RAM                              | Lazy load; unload tras index si flag                |
| Indexer corrupto a mitad de video                       | Transaction sqlite; resume desde último frame OK    |
| Caption en idioma incorrecto                            | Pass `language` al VLM; fallback en                 |
| User indexa video no-oficial / privado                  | No verify, queda en disco del user; warning legal   |
| Disco se llena con thumbs                               | `--no-thumbs` flag; tamaño con `visual-stats`       |
| Embeddings drift entre upgrades de modelo               | `meta.json` traquea provider versions; reindex CLI  |

## Métricas de éxito

- **Precisión @5**: ≥80% de queries golden devuelven el clip correcto
  en top-5 sobre dataset interno (50 queries anotadas).
- **Velocidad**: indexar 30 min de video <120s en MacBook M1 con
  Florence-2-base.
- **Storage**: <5MB por video de 30 min.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/broadcasting_visual.py`.
- MCP: 3 tools nuevas.
- F41 plugin SDK: nuevo entry-point `jw_agent_toolkit.clip_encoders`.
- F49 second-brain: opt-in poblar GraphRAG con `(video_id, frame_id,
  caption)` triples para queries cruzadas.

## Guía resultante

`docs/guias/broadcasting-visual-search.md` — quick start,
provider registration, polyglot install, ejemplos de queries.
