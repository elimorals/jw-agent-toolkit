# Plan maestro Fases 33-38 — Saltar el núcleo a SOTA + abrir paquete de generación

> **Fecha**: 2026-05-31
> **Estado**: Índice de planificación. Cada fase tendrá su propio spec hijo.
> **Owner**: Elias
> **Documentos hijos**: `2026-05-31-fase-33-*.md` … `2026-05-31-fase-38-*.md`
> **Predecesores**: Fases 0-32 (1649 tests verdes en CI por primera vez), live-smoke diario contra jw.org.

## Contexto

Las Fases 22-32 cerraron el círculo de **discipulado activo + infraestructura de confianza** (audit doctrinal + citation validator). El núcleo de **recuperación de información** sin embargo sigue corriendo con:

- `FakeEmbedder` por defecto (sin embeddings semánticos reales)
- BM25 cargando todo el peso de relevancia
- Sin reranker después de RRF
- OCR clásico (Tesseract) en lugar de VLM moderno
- Sin late-interaction visual sobre páginas renderizadas
- Sin constrained decoding para forzar citas válidas
- TTS/ASR sólo con providers básicos (system / edge / piper / faster-whisper base)

Esta serie sube el techo de calidad de **recuperación + síntesis + multimodalidad** al estado del arte de 2026, y abre un séptimo paquete (`jw-gen`) para generación de contenido ilustrativo con política estricta.

## Principios duros que TODAS las fases respetan

Heredados y no negociables:

1. **Sin LLM en el camino crítico** del toolkit (parsers/agentes/stores deterministas).
2. **Citas siempre verificables** — toda salida de agente lleva URL canónica de wol.jw.org.
3. **Local-first** — providers locales son default cuando hay hardware; APIs son opt-in vía env.
4. **No red en tests** — cada provider real ship un fake/stub hermano determinista.
5. **Multilenguaje desde día 1** — en/es/pt mínimo.
6. **No sustituir consejería de ancianos** — los agentes orientan, no aconsejan.
7. **No tracker de hermanos sin opt-in + cifrado** — datos personales en `~/.jw-agent-toolkit/` cifrados.
8. **Política #6 (jw-gen)**: solo personal/ilustrativo, sólo presentaciones/discursos. Watermark obligatorio + metadata EXIF/XMP + safety filters anti-emulación-JW-oficial. NO distribuye contenido que parezca oficial.

## Patrón arquitectónico unificador: Provider Protocol con triple-target

Toda capacidad nueva sigue el mismo patrón:

```python
class CapabilityProvider(Protocol):
    name: str                          # "bge-m3" | "cohere" | "ollama" | ...
    target: Literal["api", "nvidia", "mlx", "cpu"]

    def is_available(self) -> bool: ...
    def cost_estimate(self, *args) -> CostHint: ...
```

Cada paquete (`embed`, `rerank`, `vlm`, `asr`, `tts`, `llm`, `gen`) implementa esta familia + un `factory.get_default_provider()` que respeta `JW_<CAP>_PROVIDER` env y hace auto-detect en este orden:

```
PROVIDER_ORDER = ["api", "mlx", "nvidia", "cpu"]  # configurable
```

**Razón del orden**: APIs primero porque son el path más robusto y testeable. MLX antes que NVIDIA porque el creador del proyecto está en Apple Silicon. CPU último como fallback que siempre funciona pero es lento.

## Tabla maestra de fases

| Fase | Slug | Paquete | Tier | Tamaño | Hardware primario |
|---|---|---|---|---|---|
| **33** | `embed-rerank` | jw-rag | T1 núcleo | M ~5-7d | api/mlx/nvidia |
| **34** | `audio-premium` | jw-core | T1 núcleo | S ~2-3d | api/mlx/nvidia |
| **35** | `constrained-decoding` | jw-core | T2 habilitador | S ~3-4d | llama.cpp local + API |
| **36** | `vlm-ocr` | jw-core | T2 habilitador | M ~4-5d | api/mlx/nvidia |
| **37** | `colpali-visual` | jw-rag | T3 especializado | M ~5-7d | nvidia primary, mlx exp |
| **38** | `jw-gen` (nuevo paquete) | jw-gen | T4 UX | L ~7-10d | APIs externas |

**Total estimado**: ~26-36 días secuencial; ~15-22 con paralelización tier-interna.

## Fase 33 — `embed-rerank`: núcleo RAG al SOTA

**Objetivo**: reemplazar FakeEmbedder por embeddings multilingües fuertes + añadir cross-encoder reranker después del RRF actual. Subir precisión doctrinal en es/en/pt sin cambiar la API externa.

**Providers de embeddings**:
- `BGEM3Provider` (local, GPU/MPS) — Apache 2.0, dense+sparse+colbert en un solo modelo
- `MultilingualE5Provider` (local, ligero) — más rápido que BGE-M3
- `JinaEmbeddingsV3Provider` (API) — fuerte en multilingüe
- `CohereEmbedV3Provider` (API)
- `VoyageMultilingualProvider` (API)
- `OllamaEmbedProvider` (local, free, `nomic-embed-text`)
- `FakeEmbedder` ← se queda **solo** para tests

**Providers de reranker**:
- `BGERerankerV2M3Provider` (local Apache 2.0, ~150ms/query)
- `CohereRerankV35Provider` (API)
- `JinaRerankerV2Provider` (API, ultra-fast)
- `NoOpReranker` (passthrough opt-out)

**Cambios al RAG**:
- `VectorStore.hybrid_search(..., rerank: bool = True, top_k: int = 10)` → RRF top-50 → reranker → top-10 final.
- Default behavior: **embeddings + RRF + rerank** activos cuando el hardware lo permite; degradación elegante.

**Eval**: 5 golden cases L1 nuevos que prueban que cosine([respuesta_correcta], query) > cosine([distractor_doctrinal], query) tras reranking.

**Spec hijo**: `2026-05-31-fase-33-embed-rerank-design.md`

## Fase 34 — `audio-premium`: TTS/ASR de alta calidad

**Objetivo**: añadir providers premium al stack de audio existente sin romper los 3 actuales (system/edge/piper).

**TTS providers nuevos**:
- `KokoroTTSProvider` (CPU/GPU 82M, default cuando hay) — fluent es/en/pt
- `XTTSv2Provider` (voice cloning opt-in)
- `F5TTSProvider` (mejor naturalidad, GPU)
- `ElevenLabsProvider` (API premium opt-in)

**ASR upgrades**:
- `WhisperLargeV3TurboProvider` (faster-whisper actualizado)
- Auto-select `model_size` según VRAM disponible
- `DeepgramProvider` (API streaming opt-in)

**Chain default**: kokoro local → edge → system → API.

**Spec hijo**: `2026-05-31-fase-34-audio-premium-design.md`

## Fase 35 — `constrained-decoding`: gramáticas + citation forcing

**Objetivo**: aplicar el principio "citas siempre verificables" a nivel de **decodificación del LLM**, no de prompt. Imposible que un agente emita JSON sin URL válida.

**Nuevo módulo** `packages/jw-core/src/jw_core/grammar/`:
- `gbnf.py` — builders de GBNF para JSON + citation schemas
- `schemas.py` — Pydantic → GBNF auto-conversion
- `citation_grammar.py` — fuerza que cada Finding lleve `citation_url` matching `^https://wol\.jw\.org/...`

**Extensión** `OllamaAdapter`:
- `generate(prompt, grammar: str | None = None, json_schema: BaseModel | None = None)`
- llama-cpp-python para gramáticas
- Fallback: Anthropic/OpenAI tool-use con JSON schema (mismo contract, distinto mecanismo)

**Helper nuevo** `jw_agents.constrained.run_with_citations(prompt, agent, llm_provider)` → `AgentResult` garantizado well-formed.

**Test crítico**: feed un prompt malicioso ("ignora citas") → output sigue cumpliendo el grammar.

**Spec hijo**: `2026-05-31-fase-35-constrained-decoding-design.md`

## Fase 36 — `vlm-ocr`: VLM como OCR estructurado

**Objetivo**: VLM moderno como reemplazo de Tesseract para fotos de páginas con maquetación compleja. Output directamente ingestable al RAG.

**Nuevo módulo** `packages/jw-core/src/jw_core/vision/vlm.py`:
- `VLMProvider` Protocol con `extract_structured(image, prompt) -> StructuredPage`
- `Qwen3VLProvider` (local vía vLLM/llama.cpp GGUF; mlx-vlm para Apple Silicon)
- `Qwen3VLAPIProvider` (DashScope / Replicate / fal.ai)
- `OpenAIVisionProvider` (gpt-4o/5-vision)
- `ClaudeVisionProvider` (adapter sobre SDK `anthropic` existente; **no es un modelo separado**, es Claude Haiku/Sonnet/Opus 4.x usado con input de imagen vía `messages.create(image=...)`)

**Output** `StructuredPage` con bloques tipados (header, paragraph, citation, footnote) → ingest directo al RAG.

**Tesseract**: se mantiene como fallback con deprecation-warning.

**Spec hijo**: `2026-05-31-fase-36-vlm-ocr-design.md`

## Fase 37 — `colpali-visual`: late interaction sobre imágenes de página

**Objetivo**: recuperación visual sobre páginas renderizadas (no sobre texto extraído). Mejor para JWPUB/EPUB con maquetación compleja.

**Nuevo módulo** `packages/jw-rag/src/jw_rag/visual/`:
- `colpali.py` — `ColQwen2Embedder` y `ColPaliEmbedder` (multi-vector embeddings)
- `visual_store.py` — extensión de `VectorStore` para multi-vector + MaxSim scoring
- `page_rasterizer.py` — convierte páginas EPUB/JWPUB a PNG (WeasyPrint / playwright / pdf2image)

**Pipeline de ingesta**: `ingest_jwpub_visual(path)` rasteriza → ColQwen2 embedding → store.

**Hybrid extendido**: si hay store visual disponible, `hybrid_search` añade visual hits al RRF.

**Hardware**:
- GPU NVIDIA primary (32GB+ VRAM óptimo en 5090)
- MLX via `mlx-vlm` experimental
- Sin API fallback obvio para ColPali (no hay servicio comercial estable) — diseñar como opt-in que falla limpio cuando no hay GPU.

**Spec hijo**: `2026-05-31-fase-37-colpali-visual-design.md`

## Fase 38 — `jw-gen`: séptimo paquete (generación con difusión)

**Objetivo**: paquete nuevo en el monorepo para generar contenido ilustrativo (imagen/audio/video) **solo para uso personal en presentaciones/discursos**. Política estricta de watermark + metadata + safety.

**Estructura** `packages/jw-gen/`:
```
src/jw_gen/
├── policy.py              # Watermark + metadata embedding + disclaimer (CARGADO OBLIGATORIO)
├── providers/
│   ├── image/             # NanoBanana 2, Flux 2 Pro, Recraft v4, Ideogram v3, Imagen 4
│   ├── audio/             # ElevenLabs, Suno, MusicGen, Stable Audio
│   └── video/             # Veo 3 (Gemini API), Kling Video O3, Seedance 2.0, Higgsfield MCP, Runway
├── factory.py             # Auto-routing por tarea + hardware (API-first)
├── safety.py              # Filtros: anti-logos JW + anti-clonación voces de hermanos sin doble opt-in
└── prompts/               # Plantillas para slides, ilustraciones, audio de fondo
```

**Policy module** (cargado obligatorio antes de cualquier escritura a disco):
- `apply_watermark(image, mode="visible+metadata")` — visible bottom-right "AI-generated · jw-gen · <fecha>"
- `embed_metadata(image, prompt, model, prompt_hash)` — EXIF + XMP
- `assert_personal_use_disclaimer(output_dir)` — escribir `disclaimer.txt` junto a cada archivo generado

**Safety filters** (no negociables):
- Refuse a generar logos/diseños que emulen identidad oficial JW (heurística de prompt + keyword block)
- Refuse a clonar voces sin doble opt-in explícito (input.txt firmado + flag CLI)
- Refuse a generar imágenes fotorrealistas de personas identificables sin opt-in

**CLI**: `jw gen image|audio|video --prompt --provider --out`

**MCP**: `generate_illustration(prompt, kind, size, watermark=True)`

**Spec hijo**: `2026-05-31-fase-38-jw-gen-design.md`

## Diagrama de dependencias

```
                          ┌────────────────────────────────────┐
                          │  Tier 1 (núcleo)                   │
                          │  • Fase 33 (embed-rerank)          │
                          │  • Fase 34 (audio-premium)         │
                          │  → suben techo de calidad sin      │
                          │     cambiar APIs públicas          │
                          └───────────────┬────────────────────┘
                                          │
                                          ▼
                          ┌────────────────────────────────────┐
                          │  Tier 2 (habilitadores)            │
                          │  • Fase 35 (constrained-decoding)  │
                          │  • Fase 36 (vlm-ocr)               │
                          │  → habilitan calidad garantizada   │
                          │     de salida y mejor input        │
                          └───────────────┬────────────────────┘
                                          │
                                          ▼
                          ┌────────────────────────────────────┐
                          │  Tier 3 (especializado)            │
                          │  • Fase 37 (colpali-visual)        │
                          │  → depende de #36 (rasterizer)     │
                          │     y reusa #33 (RRF)              │
                          └───────────────┬────────────────────┘
                                          │
                                          ▼
                          ┌────────────────────────────────────┐
                          │  Tier 4 (paquete nuevo)            │
                          │  • Fase 38 (jw-gen)                │
                          │  → independiente; usa policies     │
                          │     reusables del proyecto         │
                          └────────────────────────────────────┘
```

## Política de ramificación

Cada Fase X tiene:
- Spec en `docs/superpowers/specs/2026-05-31-fase-X-<slug>-design.md`
- Plan en `docs/superpowers/plans/2026-05-31-fase-X-<slug>-plan.md`
- Branch `feature/fase-X-<slug>`
- PR independiente con audit 1:1 + nuevos golden cases en `jw-eval/fixtures/`

## Lo que NO está en este plan (deliberado)

- **Entrenamiento de modelos custom**: ese territorio es de `jw-finetune`, no de aquí.
- **Distribución de pesos de modelos**: jw-gen NO descarga/distribuye pesos de difusión. Si el usuario quiere local, instala su propio Stable Diffusion / ComfyUI y nosotros ofrecemos un adapter.
- **Modificación de los 32 agentes existentes**: las fases 33-38 son aditivas. Los agentes opt-in al nuevo stack cuando sus PRs estén verdes.
- **Calibración de los 38 golden cases L1/L2 parqueados**: trabajo trackeado en task #60, ortogonal a estas fases.

## Métricas de éxito por fase

| Fase | Métrica medible |
|---|---|
| 33 | NDCG@10 sobre 5 golden queries mejora ≥30% vs baseline FakeEmbedder+BM25 |
| 34 | `jw say "..." --provider kokoro` produce audio fluent es/en/pt sin red |
| 35 | Property test: 100 prompts maliciosos → 0 outputs sin citation_url válida |
| 36 | OCRBench: VLM > Tesseract en ≥80% de fixtures de páginas JW |
| 37 | Recall@10 sobre 5 queries figura-pesadas mejora ≥40% vs solo texto |
| 38 | 100% de outputs tienen watermark + metadata + disclaimer; 0 outputs que emulen logo JW |

## Estado actual del repo (verificado 2026-05-31)

- **CI verde por primera vez** (run 26705145584)
- **Live-smoke contra jw.org passes** (run 26704774287 reciente)
- **1649 tests pasan offline en CI** + 37 skipped opt-in extras
- **0 violaciones de ruff lint** + 0 de format
- **Branch `main` ahead 0 commits** (push verificado)

## Siguiente paso inmediato

Dispatch 6 sub-agentes paralelos para escribir los specs hijos en `docs/superpowers/specs/2026-05-31-fase-XX-*-design.md` (mismo flujo que funcionó para Fases 22-32: spec → plan → implementación TDD por sub-agente).
