# Integraciones priorizadas — roadmap de stars GitHub

> Análisis curado de las stars de GitHub del autor (cuentas `eliascipre` y `elimorals`) cruzado contra el estado del proyecto, para decidir qué proyectos externos integrar en próximas fases.
>
> **Fecha del análisis**: 2026-06-04. Estado del proyecto: F0-F55 completas, ~1887 tests passing.
> **Fuentes**: 356 stars de `eliascipre` + 2319 stars de `elimorals` = 2675 stars analizadas.

---

## Cómo leer este documento

- **TIER S** — integrar en próxima fase, cubre gap clave del BLOQUE E (capacidades pendientes de VISION.md).
- **TIER A** — alternativa superior o complemento valioso; fase siguiente.
- **TIER B** — vale la pena conocer para fases F60+.
- Cada recomendación incluye: gap cubierto, dónde integrar, licencia, justificación.

Para cada repo se respeta la decisión arquitectónica **"LLM no en camino crítico"** — frameworks pesados van como adapters opt-in en `jw-agents/research/`, no en core.

---

## Hallazgos JW-específicos (lo más valioso del análisis)

### `robertrouse/theographic-bible-metadata` (325★)

**Knowledge graph académico de personas, lugares, periodos y pasajes bíblicos** en JSON/CSV.

- **Gap cubierto**: enriquece `jw-brain` (DuckDB+Neo4j) con grafo pre-curado validado académicamente. Evita alucinaciones LLM en queries tipo *"qué profetas vivieron en Jerusalén durante el reinado de Ezequías"*.
- **Integración — Fase F58** (`jw-brain/imports/theographic/`):
  1. Loader que materializa `bible_people`, `bible_places`, `bible_periods`, `bible_passages` en DuckDB.
  2. Proyección a Neo4j para GraphRAG queries.
  3. Bridge con `BibleRef.fromWolUrl` (F56.5) y con citas de Atalaya/Insight.
- **Licencia**: revisar (probable CC-BY con atribución académica).
- **Por qué éste y no NLP extraction**: extraer personas/lugares con NER daría ~80% recall pero 60% precision (Pablo/Saulo/Paulo, coreference); Theographic ya resolvió esos problemas.

### `sircharlo/meeting-media-manager` (207★)

**App cross-platform (probable Electron/Vue+Quasar) que descarga y presenta medios de reuniones congregacionales JW** en cualquier idioma, sincronizada con programa semanal.

- **Gap cubierto**: el toolkit tiene WOL, jwlib, jwpub, organized-app... pero **NO tiene capa "reunión-en-vivo"** (download + presenter + scheduling alineado con `mwb`/`w`).
- **Integración — Fase F57** (`jw-meeting-media`):
  1. Portar lógica `getMeetingMedia(week, lang)` a Python (`jw_meeting/downloader.py`).
  2. Schema reusable desde `organized-app` (F51).
  3. Modo "presenter" como ventana Tauri (`jw-frontend/tauri/presenter/`).
  4. Hook con `jw-tts` para audio descripción en idiomas no soportados por jw.org.
- **Sinergias**: F20 (linkify) renderiza refs inline; F53 (omnilingual-ASR) transcribe comentarios locales en vivo.
- **Por qué no construir from-scratch**: 4 años de mantenimiento upstream, edge-cases ya resueltos (caching, fallback de idioma, sync con cambios Watchtower). Ahorra ~6 meses.

---

## TOP 15 prioritarios (impacto / esfuerzo)

| # | Repo | ★ | Tier | Gap | Fase | Donde integrar |
|---|---|---|---|---|---|---|
| 1 | `robertrouse/theographic-bible-metadata` | 325 | S | JW-KG | **F58** | `jw-brain/imports/theographic/` |
| 2 | `sircharlo/meeting-media-manager` | 207 | S | reunión-en-vivo | **F57** | `jw-meeting-media/` (nuevo subpkg) |
| 3 | `HKUDS/LightRAG` | 36k | S | GraphRAG dual-level | F59 | `jw-brain/backends/lightrag.py` |
| 4 | `kuzudb/kuzu` | 4k | S | Embedded graph DB | F60 | `jw-brain/backends/kuzu.py` |
| 5 | `letta-ai/letta` | 23k | S | Memoria persistente agente | F61 | `jw-agents/memory/letta.py` |
| 6 | `datalab-to/marker` | 36k | S | PDF→Markdown alta precisión | F62.1 | `jw-corpus/loaders/marker.py` |
| 7 | `datalab-to/surya` | 21k | S | OCR layout 90+ idiomas | F62.2 | `jw_core.ocr_providers.surya` |
| 8 | `langfuse/langfuse` | 29k | S | Observability/dashboard LLM | F63 | `jw-obs/langfuse_tracker.py` |
| 9 | `m-bain/whisperX` | 22k | A | Diarización + word timestamps | F64 | `jw-asr/backends/whisperx.py` |
| 10 | `ionic-team/capacitor` | 16k | S | Frontend móvil offline-first | F65 | `apps/mobile/` |
| 11 | `upstash/context7` | 57k | S | MCP docs frescos | F66.1 | `jw-mcp/external/context7.py` |
| 12 | `hiyouga/LlamaFactory` | 72k | S | Fine-tune VLM | F66.2 | `jw-finetune/backends/llamafactory.py` |
| 13 | `PaddlePaddle/PaddleOCR` | 80k | S | OCR Atalayas escaneadas | F62.3 | `jw_core.ocr_providers.paddleocr` |
| 14 | `allenai/olmocr` | 17k | S | PDF→dataset fine-tuning | F62.4 | `jw-finetune/dataset_builders/olmocr.py` |
| 15 | `StarTrail-org/LEANN` | 12k | S | Vector DB con 97% ahorro storage | F60.5 | `jw-rag/vector_backends/leann.py` |

### Honorable mentions (top 10 también merecedores)

| Repo | ★ | Por qué |
|---|---|---|
| `myshell-ai/MeloTTS` | 7k | TTS multilingüe ES/EN/FR de alta calidad CPU |
| `Blaizzy/mlx-vlm` | 5k | VLM local en Mac M-series (Qwen-VL, Pixtral) |
| `rhasspy/piper` upstream | 11k | Pipeline training Piper voice-clone hermanos |
| `waybarrios/vllm-mlx` | 1.3k | Servidor OpenAI-compat M-series con tool-calling |
| `topoteretes/cognee` | 17.6k | GraphRAG + memoria agente (DuckDB+Neo4j alineado) |
| `BerriAI/litellm` | 49k | Gateway 100+ LLMs sin tocar código |
| `unslothai/notebooks` | 5.4k | 250+ recetas TTS/embedding/vision fine-tuning |
| `Blaizzy/mlx-audio` | 7k | Apple Silicon TTS+STT+STS unificado |
| `vibrantlabsai/ragas` | 14k | Eval RAG faithfulness para `jw-eval` |
| `xyflow/xyflow` | 37k | React Flow para visualizar KG bíblico interactivo |

---

## Clusters de intención detectados

Patrones en la concentración de stars que sugieren dirección del proyecto en próximos 6-12 meses:

1. **Audio infrastructure pesada** (43+26 repos TTS/ASR) → pipelines voz↔texto bilingües, probable dubbing de discursos JW entre idiomas. Sinergia con NLLB+Omnilingual ya integrados.
2. **Document intelligence enterprise** (35+57 repos OCR/agent) → ingesta masiva de PDFs y RAG/agentes encima. Patrón "research + decisión informada".
3. **Mobile-first deployment** (96 repos, **el bucket más voluminoso**) → app móvil personal JW offline-first. Indica priorizar F65.
4. **MCP power-user** (98 repos) → oportunidad de **publicar `jw-mcp` como server estándar** en Anthropic plugin directory.
5. **Multi-modal Apple Silicon** (57 repos: FastVLM, mlx-audio, nexa-sdk) → OCR+ilustraciones M-series local.
6. **Fine-tuning serio** (42 repos productivos: LlamaFactory, ms-swift, axolotl) → planea entrenar modelos JW propios.
7. **Operador eclesiástico+dev** → sigue activamente los pocos proyectos JW open-source existentes (meeting-media-manager, organized-app, obsidian-library-linker, theographic).

---

## Recomendaciones por categoría/bucket

### TTS / Voz generativa
- **TIER S**: MeloTTS (multilingüe CPU), Piper training upstream (voice-clone).
- **TIER A**: mlx-audio (M-series), MoonshotAI/Kimi-Audio, boson-ai/higgs-audio, SesameAILabs/csm.
- **TIER B**: Orpheus-TTS, Spark-TTS, OuteTTS, Tortoise-TTS (catálogo, elegir 1-2 tras benchmark ES).

### ASR / Audio
- **TIER A**: m-bain/whisperX (diarización + word-timestamps), cjpais/Handy (Rust desktop offline STT).
- **TIER B**: TEN-framework/ten-vad (VAD ligero C), modelscope/FunASR (170x realtime, 50+ langs).

### OCR / Document parsing
- **TIER S**: PaddleOCR, olmocr, datalab-to/marker, datalab-to/surya.
- **TIER A**: deepseek-ai/DeepSeek-OCR (contexts optical compression), microsoft/markitdown, getomni-ai/zerox (zero-shot VLM).
- **TIER B**: GOT-OCR2.0, dots.ocr, GLM-OCR.

### Vector DB / RAG
- **TIER S**: LEANN (97% storage saving), HKUDS/LightRAG (GraphRAG simplificado).
- **TIER A**: kuzudb/kuzu (embedded property graph con Cypher+vector+FTS), IntelLabs/fastRAG.
- **TIER B**: neuml/txtai, tursodatabase/turso (SQLite vector-ready).

### Knowledge graph
- **TIER S**: theographic-bible-metadata (datos), kuzudb/kuzu (motor).
- **TIER A**: neo4j-contrib/mcp-neo4j, memgraph/ai-toolkit, graphistry/pygraphistry (GPU viz), Canner/WrenAI (text2SQL grounded en KG), FalkorDB.

### LLM runtimes locales
- **TIER S**: LiteLLM (gateway 100+ LLMs), waybarrios/vllm-mlx (Apple Silicon OpenAI-compat).
- **TIER A**: sgl-project/sglang (RadixAttention cachea prefijos JW), mozilla-ai/llamafile, mudler/LocalAI, lmstudio-ai/lms (CLI LM Studio).
- **TIER B**: microsoft/BitNet (1-bit edge), exo-explore/exo (cluster casero), qualcomm/nexa-sdk (GPU+NPU+CPU).

### Frameworks agente (adapters opt-in, no core)
- **TIER S**: DSPy, smolagents.
- **TIER A**: pydantic-ai (type-safe), langchain-ai/deepagents, langchain-ai/open_deep_research.
- **TIER B**: crewAI, AutoGen, parlant (interaction control para chatbot público), emcie-co/parlant.

### Fine-tuning
- **TIER S**: LlamaFactory (VLM fine-tune que Unsloth no cubre), Unsloth notebooks (recetas).
- **TIER A**: modelscope/ms-swift (600+ LLMs, GRPO), arcee-ai/mergekit (verificar BSL), arcee-ai/DistillKit, OpenPipe/ART (RL post-training).
- **TIER B**: axolotl-ai-cloud/axolotl, meta-pytorch/torchtune, bitsandbytes, h2oai/h2o-llmstudio.

### VLM / Multimodal
- **TIER S**: mlx-vlm (Mac M-series VLM local).
- **TIER A**: apple/ml-fastvlm (CVPR 2025), qualcomm/nexa-sdk (mobile-ready), QwenLM/Qwen3-VL.
- **TIER B**: OpenGVLab/InternVL, NVlabs/VILA.

### MCP ecosystem
- **TIER S**: upstash/context7 (docs frescos para LLMs).
- **TIER A**: ComposioHQ/composio (1000+ toolkits), github/github-mcp-server.
- **TIER B**: a2aproject/A2A (Agent2Agent protocol), yamadashy/repomix.

### Mobile native
- **TIER S**: ionic-team/capacitor (reusa codebase TS del plugin Obsidian + WOL extension).
- **TIER A**: expo/expo (alternativa RN), Nozbe/WatermelonDB (DB reactiva offline-first), mobile-dev-inc/Maestro (E2E testing).
- **TIER B**: mrousavy/react-native-vision-camera (escanear publicaciones físicas).

### Memoria persistente / sesión
- **TIER S**: letta-ai/letta, thedotmack/claude-mem.
- **TIER A**: FareedKhan-dev/all-agentic-architectures (35 patterns: Reflexion, LATS, MemGPT, Voyager).

### Observability / Eval
- **TIER S**: langfuse/langfuse (self-hostable, MIT).
- **TIER A**: vibrantlabsai/ragas, Arize-ai/phoenix.
- **TIER B**: open-compass/VLMEvalKit, traceloop/openllmetry.

### Frontend UI
- **TIER A**: CopilotKit/CopilotKit (AG-UI protocol), xyflow/xyflow (KG viz), reflex-dev/reflex (Python puro), zauberzeug/nicegui.
- **TIER B**: e2b-dev/E2B (sandbox código), tauri 2.0 producción.

### Data / Synth
- **TIER A**: argilla-io/distilabel (synthetic pipelines verificables).

---

## Áreas BLOQUE E aún sin cubrir tras este análisis

- **CRDT/sync E2E** (Yjs, Automerge, Iroh, libp2p) — los buckets sync_e2e fueron falsos positivos. Buscar explícitamente o aceptar como gap abierto.
- **FSRS spaced repetition** (algoritmo moderno) — bucket anki_spaced no contiene FSRS-rs/py.
- **Sign language**: `google-ai-edge/mediapipe` (35k★) detectado mal-clasificado en bucket llm_runtime — promover a TIER A para detección de Lenguaje de Señas Americano en JW Broadcasting.
- **Bots Telegram/Discord/Matrix** — bucket bot_messaging quedó muy pobre (1 repo). VISION §10 sigue abierto.

---

## Notas arquitectónicas y de licencia

- **Patrón `extras_require` granular** para mantener instalación base liviana: `[ocr-paddle]`, `[ocr-surya]`, `[tts-melo]`, `[vector-leann]`, `[mac-silicon]`, `[agent-research]`, `[memory-letta]`, `[graph-kuzu]`, `[mobile-capacitor]`.
- **Mantener "LLM no en camino crítico"**: LangChain/cognee/deepagents/letta van en `jw-agents/research/` o `jw-agents/memory/` como adapters opt-in, NO en core.
- **Verificar licencias antes de redistribuir**:
  - `mergekit` (BSL — atención al uso comercial)
  - `arcee-ai/DistillKit` (verificar)
  - `theographic-bible-metadata` (probable CC-BY con atribución académica)
  - `surya` (GPL3 dual-license — verificar comercial)
  - `apple/ml-fastvlm` (Apple license)
- **Riesgo de stack joven** (<2 años): LEANN, vllm-mlx, parallax, honcho, LightRAG. Wrappear con interfaces estables para que swap futuro no rompa el resto.
- **Stars con counts inflados** (>300k★) detectados como noise/spam (openclaw, ECC, obra/superpowers reportan números irreales). Filtrar en futuros análisis.

---

## NO recomendados (descartados explícitamente)

- **WhatsApp APIs** (Baileys, evolution-api, wechaty): riesgo legal/comunitario para TJ — VISION.md los lista en "evitar". Si fuera bot personal: Baileys MIT, pero no integrar en core.
- Infra genérica no aplicable: Vaultwarden, WireGuard, headscale, traccar, mattermost, Adguard, caddy/nginx (matchearon por sustring), Polymarket, fintech.
- Repos "claw/openclaw/clawdia/hermes-agent": parecen spam/lore con star counts inflados artificialmente.

---

## Artefactos del análisis (locales, no versionar)

Toda la data cruda se generó en `/tmp/jw-stars/`:
- `eliascipre/all.json` (356 stars cuenta del proyecto)
- `elimorals/all.json` (2319 stars cuenta principal)
- `elimorals/bucket_*.tsv` (20 buckets temáticos)
- `elimorals/buckets_for_agent.txt` (input al agente clasificador)

Para re-generar: `gh api /users/{login}/starred?per_page=100&page=N` con N en 1..ceil(total/100), merge a JSON, filtrar con el regex del BLOQUE E.

---

## Cómo se relaciona con el ROADMAP

Este documento NO sustituye [ROADMAP.md](../ROADMAP.md) (operacional, F0-F55 completas) ni [VISION.md](../VISION.md) (capacidades pendientes alto nivel). Es un **mapa de "qué tomar de afuera para no reinventar"**.

El orden de las fases F57+ propuestas arriba es ilustrativo — el orden real lo decide la prioridad del autor en el momento. Las fases F57 (meeting-media) y F58 (theographic-bible) tienen sinergia única con el dominio TJ y deberían considerarse independientemente de su número de star count.
