# jw-agent-toolkit

> Ecosistema agéntico, multimodal y local-first para contenido de **jw.org / wol.jw.org**. Monorepo Python (uv workspace, `>=3.13`) con 12 paquetes que cubren acceso HTTP, parsers offline (JWPUB AES-128-CBC), RAG híbrido, agentes procedurales, fine-tuning local con alineamiento doctrinal (Unsloth/MLX + RLAIF + DPO/ORPO + Constitutional AI), **interpretabilidad mecanicista** (probing lineal + steering + Gemma/Qwen Scope), generación multimodal con guardrails, second-brain GraphRAG, y un servidor MCP con **129 herramientas** + **28 endpoints REST** para apps cliente (Tauri, Obsidian, extensión WOL).

**Stats actuales** — 540+ commits · ~131 k LoC Python · **2 716 tests** Python passing (475 archivos) · **80 fases** roadmap (F0–F80 cerradas). CI: ruff + mypy strict + pytest (con cassettes `pytest-recording`) + bandit.

---

## Mapa rápido

```
┌────────────────────────────────────────────────────────────────────────┐
│ Skills Markdown (5)   │   Apps (Tauri desktop)   │   Web (Astro docs)  │
├────────────────────────────────────────────────────────────────────────┤
│ Superficies                                                            │
│   jw-cli (Typer+Rich)    jw-mcp (FastMCP, 129 tools + 28 REST)        │
│                              jw-rag (BM25+vec+RRF)                     │
├────────────────────────────────────────────────────────────────────────┤
│ Agentes procedurales (jw-agents) · Second-brain (jw-brain)             │
│ Generación segura (jw-gen) · Evaluación doctrinal (jw-eval)            │
│ Meeting media (jw-meeting-media) · Meta-orchestrator (F65)             │
├────────────────────────────────────────────────────────────────────────┤
│ jw-core — librería base                                                │
│   6 clientes HTTP · 9 parsers · modelos Pydantic                       │
│   Infra Fase 9: cache SQLite · token-bucket throttle · telemetry · JWT │
├────────────────────────────────────────────────────────────────────────┤
│ jw.org · wol.jw.org · b.jw-cdn.org · data.jw-api.org · JWPUB offline   │
└────────────────────────────────────────────────────────────────────────┘
```

Regla de dependencias: el flujo **solo va hacia abajo**. `jw-core` no depende de ningún otro paquete del workspace.

---

## Paquetes

| Paquete | LoC | Propósito |
|---|---:|---|
| `jw-core` | 34 465 | Librería base. 6 clientes (CDN, WOL, PubMedia, Mediator, TopicIndex, Weblang) + 9 parsers (reference, verse, article, daily_text, study_notes, topic_index, EPUB, **JWPUB con descifrado AES-128-CBC**, JW Library backup). Modelos Pydantic (`Verse`, `StudyNote`, `Article`, `Epub`, `Jwpub`, `TopicSubject`…). Infra Fase 9: `DiskCache` (SQLite WAL + TTL), `Throttler` (token bucket por host, backoff con full-jitter), `Telemetry` (drift detector opt-in que hashea la shape estructural), `JWTManager`, `build_clients()` factory. Submódulos extra: `audio/` (ASR Whisper/WhisperX/Deepgram/Omnilingual + TTS Kokoro/XTTS/F5/ElevenLabs), `integrations/` (JW Library deep-links, Obsidian, MEPS), `book_camera/`, `ministry/`, `concordance/`, `fidelity/`, `grammar/`, `talk_lab/`, `news/`, `songs/`. |
| `jw-cli` | 5 431 | CLI Typer + Rich. Comandos: `jw verse`, `search`, `daily`, `chapter`, `download`, `languages`, `jwpub`, `topic`, **`jw brain {init,compile,query,lint,status}`**, **`jw finetune {train,eval,export}`**, **`jw meta {tools,plan,run}`** (F65), **`jw spar {personas,start,turn,voice-turn}`** (F66), **`jw reason ask`** (F67), **`jw talklab {analyze,history,compare,counsel-points}`** (F68). |
| `jw-mcp` | 6 157 | Servidor MCP (FastMCP) con **129 tools** sobre stdio agrupadas: Biblia/Referencia, Búsqueda, Publicaciones, Agentes, Ingest RAG, Audio/Fine-tuning, Integración JW Library / Obsidian / Broadcasting, Ministry, Avanzados F65–F68, Second-brain F49, Multimodal F69–F71, Drift F72, Voice F76. Además **28 endpoints REST** (`rest_api.py` + `rest/book_camera.py`) para apps cliente sin stdio: `/api/v1/{verse,daily,search,apologetics,workbook,conversation,linkify,convert_links,verse_markdown,cross_references,vault/{index,export,append}}` y `/presenter/sessions/*` (control del presenter de reuniones desde Tauri). Clientes lazy-loaded; RAG store configurable vía `JW_RAG_STORE_PATH`. |
| `jw-rag` | 4 064 | RAG híbrido. `Embedder` protocol (`FakeEmbedder` determinista offline + sentence-transformers / Cohere / VoyageAI opt-in). `VectorStore` con persistencia JSON, BM25 (`rank-bm25`), coseno (numpy) y **Reciprocal Rank Fusion**. Pipelines de ingest para capítulos bíblicos, artículos, EPUBs, JWPUB (descifrado), notas personales, PDF (marker opt-in, F62), Office (markitdown opt-in). Reranking sentence-transformers / Cohere. Visual late-interaction ColPali/ColQwen2 (GPU opt-in, F37). |
| `jw-agents` | 10 556 | 12+ agentes procedurales (sin LLM en el camino crítico) que devuelven `AgentResult` = `Finding[]` + `Citation[]` verificables: `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`, `public_talk_outline`, `workbook_helper`, `study_conductor`, `reverse_citation_lookup`, `conversation_assistant`, `news_monitor`, `personal_study`, `life_topics`. Especializados: `cross_lingual_research`, `fidelity_wrap`, `finetuned_assistant`, `apocrypha_detector`, `fact_checker`, `presentation_builder`, `letter_composer`, `convention_discovery`, `broadcasting_ingest`, `student_part_helper`, `revisit_tracker`, `recap_session`. Avanzados: `meta_orchestrator` (F65), `spar_session` (F66), `doctrinal_reasoner` (F67), `talk_lab` (F68). |
| `jw-finetune` | 7 151 | Plataforma local de fine-tuning estilo Unsloth Studio. Pipeline `extract → synth Q&A → LoRA train → export`. Providers de síntesis: Anthropic (Claude), Ollama; con `judge/` (oracle de calidad). Training: `sft.py`, `grpo.py`, `cpt.py` sobre CUDA (Unsloth+bitsandbytes+trl) / MLX (Apple) / ROCm. Exporters: **GGUF** (llama.cpp/Ollama), **MLX**, SafeTensors. Monitor FastAPI+WS + TUI Textual. Recetas pre-config. Cada usuario entrena su propio modelo; los pesos nunca se distribuyen. Ver [`docs/guias/fine-tuning-local.md`](docs/guias/fine-tuning-local.md). |
| `jw-eval` | 1 098 | Suite de regresión doctrinal: evaluadores contra cánon JW, fidelity checks, providers Ollama / Claude / OpenAI. |
| `jw-gen` | 1 525 | Generación de imagen/audio/vídeo con guardrails: `policy.py` (watermark XMP+EXIF), `safety.py` (rechaza retratar a personas JW reales, valida contexto de uso personal), factory de providers (Google GenAI, Replicate, ElevenLabs, RunwayML), i18n (en/es/pt). |
| `jw-brain` | 3 978 | **Second-brain compiler estilo Karpathy** (F49). Backends pluggables (`DuckDB` por defecto, `Neo4j` opt-in). Compilador LLM-driven que extrae triplas (entidad–relación–entidad) con caché por content-hash. Schema GraphRAG (Entity, Relationship, Document, provenance por edge). Registry de dominios (`builtin_tj`, fixture financiero); SDK plugin F41 (`jw_agent_toolkit.brain_domains`). Sync Obsidian con **dos protecciones independientes**: (a) frontmatter YAML estricto — cualquier parse error trata la nota como editada y NO la sobrescribe (`wiki/obsidian_writer.py:24,39,43`); (b) flag por nota `human_edited: true` honrado nota a nota (override granular). Multi-tenant via env vars `JW_BRAIN_HOME` (workspace) y `JW_BRAIN_BACKEND=duckdb|neo4j` (`backends/factory.py:14`). Linter (contradicciones, huérfanos). Importadores Biblia (65 libros × headwords expandidos F58.14), period/place catalogs. Multi-tenant via `--brain` flag + `JW_BRAIN_HOME`. |
| `jw-meeting-media` | 1 323 | Descubrimiento, descarga y presentación sincronizada de medios para reuniones congregacionales. Multi-congregación (F57.16). |
| `jw-interp` | 2 580 | **Interpretabilidad mecanicista (F80)**. Probing lineal por principio (sklearn), steering vectors + activation patching (numpy puro), captura de activaciones HF con forward hooks (`TorchActivationCapturer`, CUDA/MPS/CPU), adaptadores SAE para **Qwen-Scope** (TopK, residual stream) y **Gemma Scope** (JumpReLU, residual + MLP + attention) con interfaz cross-family. Persistencia de probes (`probe_store`: npz + JSON sidecar) y evaluador runtime (`ProbeEvaluator`) que actúa como Tier 4 del `fidelity_wrap`. Sin acoplamiento a `jw-agents` (callable contract). |
| `create-jw-agent` | — | Scaffolder de nuevas integraciones (F42). |

Además: `skills/` (5 skills Markdown para Claude: `jw-verse-lookup`, `jw-daily-text`, `jw-research`, `jw-meeting-prep`, `jw-apologetics`), `apps/desktop/` (Tauri), `docs/superpowers/specs/` (specs F65–F76), `tools/pytest-cookbook/`, y `scripts/` para reverse-engineering JWPUB y grabación de cassettes.

---

## Inicio rápido

```bash
# Instalar dependencias (uv workspace)
uv sync --all-packages

# Servidor MCP (Claude Desktop / Code / cualquier cliente MCP)
uv run jw-mcp

# CLI
uv run jw verse "Juan 3:16" --with-notes
uv run jw daily
uv run jw search "amor" --lang es
uv run jw jwpub /ruta/al/archivo.jwpub --extract
uv run jw topic "fe" --limit 5

# Second-brain
uv run jw brain init && uv run jw brain compile docs/
uv run jw brain query "trinidad"

# Fine-tuning local
uv run jw-finetune init
uv run jw-finetune prepare --input /ruta/publicaciones/
uv run jw-finetune train --recipe llama3-8b-lora-qlora
uv run jw-finetune export --format gguf
```

> **macOS bajo `~/Documents` o `~/Desktop`:** sigue la receta de [`docs/guias/setup-macos.md`](docs/guias/setup-macos.md) *antes* del `uv sync`. macOS marca los `.venv/` como `UF_HIDDEN` en esas rutas, lo que rompe los imports editables con un `ModuleNotFoundError` silencioso. La guía deja un fix permanente con `venv/` + symlink.

---

## Flujos end-to-end

### 1. Verse lookup
```
CLI: jw verse "Juan 3:16" --lang es
  → parse_reference()                # parsers/reference.py
  → WOLClient.get_bible_chapter()    # vía Throttler + DiskCache + Telemetry
  → parse_verse() / parse_study_notes() / parse_cross_references()
  → AgentResult(Finding[verse], Finding[notes], Finding[refs])
  → Rich formatted output con URL canónica a wol.jw.org
```

### 2. RAG híbrido
```
MCP: semantic_search("¿qué es la trinidad?")
  → VectorStore.hybrid_search()
      ├─ BM25 top-k          (rank-bm25)
      ├─ cosine top-k        (embeddings: Fake | sentence-transformers | Cohere | VoyageAI)
      └─ Reciprocal Rank Fusion → ranking unificado
  → retrieve.dedup_by_source() + filter_by_metadata()
  → (opcional) cross-encoder rerank
  → LLM externo (Claude/Ollama) sintetiza prosa con citas verificables
```

### 3. Fine-tuning local
```
JWPUB / EPUB local
  → jw_finetune.data.extract_jwpub()           # texto estructurado
  → synth.orchestrator (Anthropic | Ollama) + judge oracle
      → datasets/qa_pairs.jsonl                 # HF-compatible
  → train.sft.train_lora() (Unsloth | MLX | ROCm)
      → adapter weights
  → export.{gguf,mlx,safetensors}              # llama.cpp / Apple / Meta
```

### 4. Meta-orchestrator (F65)
```
CLI: jw meta plan "preparar reunión del domingo"
  → meta_orchestrator detecta workbook semanal y tema central
  → selecciona N de los 12+ agentes aplicables
  → plan JSON (DAG de tool calls) + diagrama Mermaid
  → meta_orchestrator.run_plan() ejecuta paso a paso
      ├─ replan si un paso falla
      ├─ critique para refinar
      └─ CustomEvent tracing (F43)
  → result + export Markdown/PDF
```

### 5. JWPUB offline
```
.jwpub local
  → parse_jwpub()                              # parsers/jwpub.py
      ├─ derive key: SHA256(f"{lang}_{symbol}_{year}") XOR _XOR_KEY
      ├─ AES-128-CBC decrypt (pycryptodome)
      └─ extract SQLite + docs + paragraphs
  → JwpubDocument[]
  → ingest_jwpub() → RAG
  → second-brain compile
```

---

## Roadmap

Ver [`docs/ROADMAP.md`](docs/ROADMAP.md) y [`docs/VISION.md`](docs/VISION.md). Resumen:

| Bloque | Fases | Hitos |
|---|---|---|
| **Núcleo (F0–F10)** | ✅ | uv workspace, 6 clientes, 9 parsers, JWPUB AES-128-CBC (F5.5), infra Fase 9 (cache+throttle+telemetry+JWT), 29 tools MCP iniciales, CI con cassettes. **Plan original cerrado al 100%**. |
| **Intermedias (F11–F48)** | ✅ | JW Library integration (F19), Obsidian vault (F20), PDF export (F31), fine-tuning local Unsloth (F32), embeddings/rerank reales (F33), ASR/TTS multimodal (F34), visual RAG ColPali (F37), NLI runtime (F39), Plugin SDK (F41), scaffolding (F42), tracing CustomEvent (F43). |
| **Avanzadas (F49–F56)** | ✅ | Second-brain GraphRAG (F49, 81 tests), jwpub-writer (F50, derivado de `html2jwpub`), organized-schemas (F51, port de `sws2apps`), `.jwlibrary` writer (F52, port de `jwlmanager`), Omnilingual ASR (F53, 1.672 idiomas vía venv 3.12), NLLB-200 (F54, 200 idiomas, CC-BY-NC-4.0, CTranslate2 INT8). |
| **Website + Sync (F57–F66)** | ✅ | Mirror landing/whats-new/roadmap en ES+EN, multi-congregation meeting media (F57.16), conversation-sparring (F66). |
| **Agentic & Voice (F65–F76)** | ✅ | Meta-orchestrator (F65, plan/replan/critique sobre 12 agentes), Spar simulator (F66, voice mode + personas multiidioma), Doctrinal reasoner (F67, ReAct + NLI), Talk-lab (F68, prosody + SVG timeline + PDF), Predictive + voice + family (F69–F76). |
| **Alineamiento doctrinal (F77–F79)** | ✅ | Principios YAML versionados (F77, 5 builtin), judge como preference model + SL-CAI (F78), trainers DPO/ORPO con Unsloth sobre Qwen3.5-0.8B (F79). |
| **Interpretabilidad mecanicista (F80)** | ✅ | Probing lineal por principio (F80.1), steering vectors + activation patching (F80.2), Qwen-Scope adapter (F80.3), Gemma Scope wrapper (F80.4), runtime probe store + `fidelity_wrap` Tier 4 (F80.5). Paquete nuevo `jw-interp`. |
| **Visión (F81+)** | 🔭 | Distribución PyPI, bots de mensajería, idiomas adicionales. |

---

## Testing y CI

- **Test runner:** `pytest` con `pytest-recording` (las cassettes hacen que 2 716 tests Python — 475 archivos — corran sin red).
- **CI** (`.github/workflows/ci.yml`): ruff format-check + lint, mypy strict (`continue-on-error` temporal), pytest, bandit, caché uv.
- **Conteo aproximado por paquete:** jw-core ~780, jw-mcp ~100, jw-rag ~144, jw-agents ~937 (incluye F77 + F80.5 Tier 4), jw-cli ~72, jw-finetune ~352 (incluye F77–F79 + F80.0 SL-CAI), jw-eval ~58 (principios), jw-gen ~52, jw-brain ~96, jw-interp ~64 (probing + steering + SAE + runtime).

---

## Decisiones de diseño

1. **Monorepo uv** — Tipos cambian frecuente; un workspace elimina la fricción de PRs cross-repo y permite `uv sync --all-packages` para un dev-loop unificado.
2. **LLM fuera del camino crítico** — Los agentes son procedurales y devuelven `Finding[] + Citation[]` deterministas. La síntesis en prosa la hace el cliente LLM (Claude Desktop, Claude Code, propio). Esto preserva la **verificabilidad** y permite *swap* de modelos sin tocar la lógica.
3. **Citas siempre verificables** — toda respuesta enlaza a `wol.jw.org`, jamás se inventa contenido.
4. **JWPUB descifrado in-process** — el algoritmo redescubierto (AES-128-CBC + key derivation `SHA256 ⊕ const`) permite acceso offline al canon JW sin telemetría de terceros.
5. **RAG híbrido por defecto** — BM25 captura matchings literales (citas, símbolos, nombres propios); embeddings capturan paráfrasis; RRF combina ambos sin tuning de pesos.
6. **Infra Fase 9 opt-in pero recomendada** — cache/throttle/telemetry se inyectan a clientes; los tests legacy siguen funcionando sin ella.
7. **Plugin SDK (F41)** — extensiones de dominio (`brain_domains`) sin fork.
8. **Local-first multimodal** — ASR y TTS por defecto en disco; el audio no sale del equipo salvo configuración explícita de provider cloud.

---

## Licencia y créditos

GPL-3.0-only. Incorpora código derivado de:

- [`allejok96/jwlib`](https://github.com/allejok96/jwlib) — GPL-3.0 (broadcasting/parser).
- [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) — MIT (algoritmo de descifrado JWPUB, F5.5).
- [`darioragusa/html2jwpub`](https://github.com/darioragusa/html2jwpub) — MIT (algoritmo de generación JWPUB + schema SQLite, F50).
- [`sws2apps/organized-app`](https://github.com/sws2apps/organized-app) — MIT (schemas `src/definition/` portados a Pydantic v2 en `jw_core.models_organized`, F51).
- [`erykjj/jwlmanager`](https://github.com/erykjj/jwlmanager) — MIT (pipeline de escritura `.jwlibrary` portado a `jw_core.writers.jw_library_backup`, F52; el merge basado en `libjwlCore` queda fuera).
- [`facebookresearch/omnilingual-asr`](https://github.com/facebookresearch/omnilingual-asr) — Apache-2.0 (ASR Meta para 1 672 idiomas, integrado vía venv Python 3.12 dedicado; bootstrap `jw omnilingual install`, F53).
- [`facebook/nllb-200`](https://huggingface.co/facebook/nllb-200-3.3B) — **CC-BY-NC-4.0** (NLLB-200 Meta para 200 idiomas, CTranslate2 INT8; `is_commercial_safe=False`. Extra: `uv add 'jw-core[translation-nllb]'`, F54).

---

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — manual de arquitectura.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — hoja de ruta operacional F0–F76+.
- [`docs/VISION.md`](docs/VISION.md) — visión a largo plazo.
- [`docs/conceptos/`](docs/conceptos/) — glosario JW.org, decisiones, estrategia multi-idioma, inventario de endpoints, flujos end-to-end, CI y testing.
- [`docs/guias/`](docs/guias/) — guías prácticas (resolución de citas, clientes HTTP, agentes, RAG, parsers, MCP, Fase 9, scripts de exploración, fine-tuning local, second-brain, meta-orchestrator, talk-lab).
- [`docs/referencia/`](docs/referencia/) — referencia exhaustiva módulo por módulo.

---

## Fidelidad al canon publicado y supervisión escalable

El toolkit sirve contenido doctrinalmente cargado: el riesgo no es que el modelo *invente nuevas doctrinas*, sino que un fine-tune local o un agente generativo se **aleje del canon publicado** (Atalayas, Estudio de las Escrituras, libros de la organización). La fuente de verdad es el material vigente publicado por la organización; este proyecto solo *refleja* ese canon. Las técnicas siguientes son ingeniería de alineamiento aplicada con ese objetivo.

### Técnicas y fuente

| Técnica | Idea central | Fuente |
|---|---|---|
| **RLHF (PPO)** | SFT → reward model con preferencias humanas → PPO sobre la política. Pesado y caro de operar. | Christiano et al., 2017. |
| **Constitutional AI (CAI)** | Reemplaza la mayoría del feedback humano por **autocrítica del modelo guiada por una lista de principios explícitos**. Fase 1 (SL-CAI): el modelo critica y reescribe sus propias respuestas contra los principios. Fase 2 (RL-CAI): se entrena un preference model con comparaciones generadas por IA. | Bai et al. (Anthropic), arXiv:2212.08073. |
| **RLAIF** | RL con preferencias generadas por un anotador IA (el judge) en lugar de humanos. Escala sin caer en costes/sesgos de anotación. | Idem. |
| **DPO** | Re-deriva la relación política↔recompensa y optimiza la política **directamente** sobre pares `(y_w, y_l)` con pérdida log-σ. Sin reward model, más estable que PPO. | Rafailov et al., 2023. |
| **IPO / KTO** | Variantes. IPO añade regularización cuadrática (mejor control de KL, robusto a ruido). KTO acepta binarios `(deseable, indeseable)` en lugar de pares. | — |
| **ORPO** | Fusiona SFT y preference learning en **una sola fase** sin modelo de referencia, usando pérdida de *odds-ratio*. Reduce coste y deriva contra el baseline SFT; viable en MLX/ROCm con LoRA. | Hong et al., arXiv:2403.07691. |

### Implementación en este repo

Las siguientes piezas están implementadas (F77–F80) y se enumeran en orden de dependencia:

#### F77 · Criterios de fidelidad versionados (`packages/jw-eval/src/jw_eval/principles/`)

YAML versionado con principios de fidelidad. Cada principio:

```yaml
id: PF001-canon-only
version: 1
severity: hard          # hard → bloqueo · soft → warning anotado
applies_to: [apologetics, doctrinal_reasoner, finetuned_assistant]
source: lvs cap. 1
rationale: >
  Toda afirmación doctrinal debe poder respaldarse en publicaciones JW
  vigentes; no presentar como canónicas referencias apócrifas ni
  doctrinas externas.
detect:
  forbidden_phrases: ["según los apócrifos", "el libro de Tobías enseña"]
```

Loader: `jw_eval.principles.load_principles(root)` devuelve `list[Principle]` Pydantic. Consumido por el judge (sección F78) y por la suite de regresión.

#### F78 · Judge como preference model + SL-CAI

El judge existente (`jw_finetune/synth/judge/`) ya devuelve `QAScore` con heuristics + NLI + LLM pedagogical. Se añade:

- **`Judge.score_pair(question, ans_w, ans_l, language)`** → `PreferenceVerdict(winner: "a"|"b"|"tie", margin: float, reasons: list[str])`. Reutiliza el scoring por sample y compara los `overall`, los flags `hard` violados de los principios, y un tie-breaker NLI.
- **`jw_finetune.synth.critique.self_critique(qa_pair, principles, llm) -> QAPair`** — pipeline SL-CAI: el LLM revisa la respuesta contra principios; si viola alguno `hard`, reescribe. La versión revisada reemplaza a la original.
- **`jw_finetune.synth.preference.build_preference_dataset(chunks, providers, judge) -> Path`** — genera N candidatos por chunk con temperaturas distintas, los puntúa por pares con el judge, y exporta un JSONL `{prompt, chosen, rejected}` listo para DPO/ORPO.

#### F79 · Trainers DPO y ORPO con Unsloth

- **`jw_finetune.train.dpo.train_dpo(recipe, dataset_path, workspace)`** — usa `trl.DPOTrainer` + `unsloth.FastLanguageModel`. Reutiliza el mismo `Recipe` (con `task="dpo"`), incluyendo LoRA rank, `chat_template`, `use_rslora`.
- **`jw_finetune.train.orpo.train_orpo(...)`** — `trl.ORPOTrainer`. Una sola fase, sin modelo de referencia; recomendado en MLX/ROCm o datasets pequeños.

**Receta builtin de ejemplo** — `doctrinal-qa-es-dpo-qwen35` sobre **Qwen3.5-0.8B** (Apache-2.0), `chat_template="qwen-3"`, LoRA rank 16, 1 epoch. Se invoca:

```bash
uv run jw-finetune train --recipe doctrinal-qa-es-dpo-qwen35 \
                         --dataset workspace/preference_pairs.jsonl
uv run jw-finetune export --format gguf      # o mlx
```

#### F80 · Interpretabilidad mecanicista tri-modelo (`packages/jw-interp/`)

Cierra el loop: F77–F79 entrenan, F80 audita **por qué** el modelo responde como responde. Pregunta operativa: ¿el modelo internalizó los principios o aprendió un *shortcut* estilístico? El spec completo está en [`docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md`](docs/superpowers/specs/2026-06-12-fase-80-interpretability-tri-model-design.md).

- **F80.0 SL-CAI critique pipeline** — CLI `jw-finetune build-critique-dataset` que reescribe respuestas violadoras antes del SFT. Reduce hard violations aguas arriba. Guía: [`docs/guias/sl-cai.md`](docs/guias/sl-cai.md).
- **F80.1 probing lineal por principio** — `ContrastiveSpec` declarativos → `MockActivationCapturer` o `TorchActivationCapturer` (HF forward hooks, CUDA/MPS/CPU auto) → `LinearProbe` (sklearn) por capa × principio. Accuracy ≥0.80 = principio en la representación; <0.65 = shortcut. Guía: [`docs/guias/probing.md`](docs/guias/probing.md).
- **F80.2 steering vectors + activation patching** — `compute_steering_vector` (diferencia de medias), `apply_steering_to_residual`, `project_out` (ablación), `evaluate_patching_effect`. Valida causalidad: si la conducta no cambia bajo ±α·v, el probe captura correlación, no causa.
- **F80.3 Qwen-Scope adapter** — `QwenScopeSAE` carga `SAE-Res-Qwen3.5-2B-Base-W32K-L0_50` (TopK k=50, residual stream, 24 capas) con `torch.load(weights_only=True)`. Encode/decode + `summarize_feature_activations` para mapear principios → features SAE candidatas.
- **F80.4 Gemma Scope wrapper** — `GemmaScopeSAE` envuelve SAELens nativo (JumpReLU, residual + MLP + attention, todas las capas). Interfaz numpy idéntica a Qwen-Scope para validación cross-family de features morales.
- **F80.5 runtime probe store + `fidelity_wrap` Tier 4** — `save_probe_set` / `load_probe_set` (npz + JSON sidecar, sin pickle), `RuntimeProbe.predict_proba` (sigmoid numpy estable, igual sklearn). `ProbeEvaluator` se enchufa a `fidelity_wrap(probe_evaluator=…)`. Tier 4 es **observacional**, jamás veta un Finding solo: anota `probe_scores`, `probe_misses` y `probe_coherence` (`clear` / `confirms` / `conflicts` / `silent`). Guía: [`docs/guias/interpretabilidad-runtime.md`](docs/guias/interpretabilidad-runtime.md).

**Arquitectura tri-modelo:**

```
PRODUCCIÓN              LAB QWEN                    LAB GEMMA
Qwen3.5-0.8B            Qwen3.5-2B-Base             Gemma-2-2B-PT
(DPO/ORPO doctrinal)    + Qwen-Scope público        + Gemma Scope público
  │                       │                           │
  │                       └──── features SAE ─────────┘
  │                                  │
  │                       cross-family agreement matrix
  │                                  │
  └────── steering vectors / probes transferidos ──────┘
```

Producción nunca se toca. Los SAEs nunca corren en el modelo de 0.8B (la literatura indica que a esa escala las features son polisemánticas). En su lugar, los descubrimientos del lab se transfieren al 0.8B como probes lineales y steering vectors. Hardware: training en CUDA (RTX 5090 / H100), inferencia + probing en M4 Max via MPS.

### Cómo se conecta con lo que ya había

- `jw_core.fidelity.nli` (F39) — sigue siendo el motor de entailment; el judge lo usa como tie-breaker en `score_pair`.
- `jw_agents.fidelity_wrap` — decorador `@fidelity_wrap(on_fail="reject")` para agentes en producción; ahora puede leer principios cargados y aplicar los `hard` antes de devolver `AgentResult`. **F80.5 añade** un argumento opcional `probe_evaluator: Callable[[str], dict[str, float]]` para Tier 4 interpretable; tipo local, sin import de `jw-interp` (cero acoplamiento).
- `jw_agents.apocrypha_detector` y `fact_checker` — siguen como checks orientados a *runtime*; los principios YAML duplican y formalizan las reglas que estos agentes implementaban en código.
- `jw_gen.safety` (`refuse_jw_logo_emulation`, `refuse_voice_cloning_without_double_optin`, `refuse_realistic_faces_without_optin`) — política de generación, ortogonal al alineamiento del modelo.

### Modos de operación con guardrails

Niveles de autonomía aplicados al toolkit (no a capacidades de modelo frontera). Cuanto más autónomo es el agente, más checks. Es ingeniería defensiva, no clasificación de riesgo.

| Modo | Aplica a | Guardrails mínimos |
|---|---|---|
| **Asistido** | `jw verse`, `search`, `daily`, parse JWPUB, RAG read-only. | Citas canónicas obligatorias; cero generación libre. |
| **Generativo con citas** | `verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`. | `fidelity_wrap` activo, principios `hard` consultados antes de devolver, cada `Finding` con `Citation` verificable. |
| **Agéntico** | `meta_orchestrator`, `spar_session`, `doctrinal_reasoner`, `talk_lab`. | Plan visible (Mermaid export), tracing F43, judge gate antes de cada efecto externo (descarga, generación, escritura a Obsidian), dry-run por defecto. |
| **Autónomo** (futuro) | Bots de mensajería, batch scheduled. | Modo anterior + circuit breaker por tasa de violaciones del judge, kill-switch, auditoría humana periódica. |

### Principios anclados en código existente

- **No suplantación** — ya implementado en `jw_gen/safety.py` (`refuse_jw_logo_emulation`, `refuse_voice_cloning_without_double_optin`, `refuse_realistic_faces_without_optin`). Se formaliza como principio `PF010-no-impersonation` (`severity: hard`).
- **Humildad epistémica** — `PF002-cite-before-paraphrase`: ante incertidumbre, devolver fuente literal antes que paráfrasis. Aplicable a `apologetics`, `doctrinal_reasoner`, `finetuned_assistant`.
- **Citas obligatorias** — `PF003-citation-required` para todo agente que produzca contenido derivado de publicaciones JW; consumido por `fidelity_wrap` en modo `reject`.

Cuatro fases incrementales que no requieren rediseño: criterios (F77) → preference model (F78) → trainers (F79) → interpretabilidad mecanicista (F80). Las recetas Qwen3.5-0.8B son el punto de entrada práctico (modelo pequeño, Apache-2.0, encaja en MLX); la interpretabilidad vive en modelos 2B del lab (Qwen3.5-2B-Base y Gemma-2-2B-PT) donde los SAEs públicos ya existen.
