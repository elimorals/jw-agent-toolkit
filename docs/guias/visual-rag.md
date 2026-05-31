# Visual RAG (Fase 37) — guía de uso

> Estado: implementado en `jw_rag.visual`. Opt-in vía `[visual]` extra. Requiere GPU.

## ¿Qué resuelve?

El RAG textual (Fase 33) recupera párrafos. Cuando la respuesta está en una **figura**
(mapa de viajes de Pablo, tabla de bestias de Daniel, diagrama del tabernáculo) el
texto extraído no alcanza. Fase 37 añade un segundo store que indexa **páginas
rasterizadas** con embeddings late-interaction (ColPali / ColQwen2) y los fusiona
con el RAG textual vía RRF.

## Instalación

NVIDIA (Linux, >=12 GB VRAM):

```bash
uv sync --extra visual
```

Apple Silicon (M2 o superior, experimental):

```bash
uv sync --extra visual-mlx
```

Sin GPU el módulo simplemente no se activa. El RAG textual (Fase 33) funciona
igual.

## Pipeline

```
JWPUB / EPUB / PDF
        |
        v
PageRasterizer (Playwright | pdf2image)
        |   (200 dpi, viewport 768x1024)
        v
PIL.Image por pagina
        |
        v
ColQwen2Embedder.embed_image()  -> (n_patches, 128) float16
        |
        v
VisualVectorStore.add()  -> vectors.npy + mask.npy + chunks.jsonl
```

## Comandos

```bash
# Ingesta
JW_VISUAL_ENABLED=1 uv run jw rag ingest-visual ./pubs/sample.jwpub

# Busqueda hibrida (text + visual)
JW_VISUAL_ENABLED=1 uv run jw rag search-visual "viajes de Pablo" --top-k 5
```

## Variables de entorno

| Var | Default | Propósito |
|-----|---------|-----------|
| `JW_VISUAL_ENABLED` | `1` | Pon `0` para desactivar todo el módulo |
| `JW_VISUAL_TARGET` | autodetect | Forzar `nvidia` o `mlx` |

## Troubleshooting

- **`ConfigError: No GPU disponible...`** — instala con `--extra visual` en máquina
  con GPU NVIDIA >=12 GB, o `--extra visual-mlx` en Apple Silicon. Para correr tests
  usa `FakeColPaliEmbedder`.
- **`VisualStoreMismatchError`** — el store en disco fue generado por otro modelo /
  revisión / `patch_size`. Re-ingesta con `--force`.
- **OOM durante ingesta** — baja `dpi` a `150` o reduce el viewport del EPUB.

## Benchmarks (5090, 32 GB VRAM)

| Volumen | ~50 páginas | ~500 páginas | ~5000 páginas |
|---------|-------------|--------------|---------------|
| Ingest  | <60 s       | ~10 min      | ~90 min       |
| Search  | 80 ms       | 250 ms       | 1.5 s         |
| Storage | 6 MB        | 60 MB        | 600 MB        |
