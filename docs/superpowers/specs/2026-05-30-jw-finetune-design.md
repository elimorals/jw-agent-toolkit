# Diseño: `jw-finetune` — Plataforma local de fine-tuning de LLMs con publicaciones JW

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado pendiente de revisión final
> **Owner**: Elias
> **Issue/Spec**: (este documento)

## Resumen ejecutivo

`jw-finetune` es un nuevo paquete del monorepo que permite a cada publicador/programador
**entrenar localmente su propio modelo open-source** con sus propias publicaciones JW
(JWPUB / EPUB / NWT vía WOL). La plataforma se basa en **Unsloth** como motor de
entrenamiento y aporta una capa de dominio que habla en términos JW (publicación,
idioma, tipo de Q&A, presets doctrinales) y traduce a recetas Unsloth.

El producto NO distribuye pesos ni contenido: el usuario aporta su biblioteca local
(JWPUBs ya descargados desde JW Library) y obtiene un modelo personal que se queda
en su máquina. Esto alinea con la filosofía **privacidad local-first** del toolkit
(módulo 11) y minimiza el riesgo legal sobre copyright de WBTS.

## Motivación

El toolkit ya cubre el lado de **recuperación** (`jw-rag`: indexar y buscar tu
biblioteca local). Le falta el lado de **destilación**: un modelo que haya absorbido
estilo, terminología, exégesis y formato JW para conversación fluida sin necesidad
de red. Combinados:

- RAG → precisión factual con citas verificables
- Modelo fine-tuneado → estilo + intuición + Q&A fluida

Esto convierte al toolkit en una plataforma completa: indexa tu biblioteca, destila
un asistente personal, úsalo offline.

## Objetivos del modelo (multi-tarea, en orden de prioridad)

1. **Asistente conversacional Q&A** (doctrinal/bíblico). SFT con pares Q&A sintéticos.
2. **Generador de estilo** (predicación, comentarios). Continued pretraining.
3. **Especialista bíblico** (exégesis, refs cruzadas, Strong's). SFT con datasets
   estructurados versículo→explicación.
4. *(Opcional / futuro)* Multi-tarea combinando todo lo anterior.

## Hardware soportado

El mismo que Unsloth oficial:
- **Apple Silicon** (M1/M2/M3/M4) vía MLX — modelos chicos (≤8B), QLoRA
- **NVIDIA** (RTX 30/40/50, A100, H100) — todo el espectro hasta 70B
- **AMD** (ROCm) — soporte vía Unsloth ROCm builds
- **CPU only** — solo data prep y eval; no training

## Decisión arquitectónica clave

**Base = Unsloth directo** (no abstracción genérica, no subprocess), porque queremos
heredar 100% de las features de Unsloth: RL/GRPO, kernels custom, fixes para gpt-oss/
Qwen3/Llama4, observabilidad nativa, exports a GGUF/MLX.

La capa de dominio JW se construye **encima** de Unsloth, no al lado. Es una capa
delgada de **recetas** (`Recipe` dataclass) + **presets** que mapean conceptos JW
(`publication_kind=watchtower`, `language=es`, `qa_style=doctrinal`) a configuraciones
Unsloth (`base_model`, `lora_rank`, `lr`, `max_seq_len`, `dataset_format`).

## Estructura del paquete

```
packages/jw-finetune/
├── pyproject.toml          # extras opcionales: [cuda], [mlx], [rocm], [synth], [monitor]
├── README.md
├── src/jw_finetune/
│   ├── __init__.py
│   ├── data/               # Stage 1-4: extracción → dataset
│   │   ├── extract.py      # JWPUB/EPUB/WOL → ParagraphRecord
│   │   ├── dedupe.py       # simhash + opcional embeddings (vía jw-rag)
│   │   ├── chunk.py        # delega a jw_rag.chunker
│   │   ├── synth.py        # Q&A sintéticos (Anthropic | Ollama)
│   │   └── formats.py      # Alpaca, ShareGPT, raw text
│   ├── recipes/
│   │   ├── base.py         # Recipe dataclass + validación
│   │   ├── presets.py      # 4+ presets out-of-the-box
│   │   └── templates/      # prompts Jinja2 para synth
│   ├── train/
│   │   ├── sft.py          # SFTTrainer (Unsloth + trl)
│   │   ├── cpt.py          # continued pretraining
│   │   └── grpo.py         # RL (Fase 5)
│   ├── eval/
│   │   ├── doctrinal.py    # uso de terminología JW
│   │   ├── refs.py         # exactitud citas bíblicas
│   │   └── runner.py       # eval en checkpoints
│   ├── export/
│   │   ├── gguf.py
│   │   ├── mlx.py
│   │   └── safetensors_export.py
│   ├── monitor/
│   │   ├── app.py          # FastAPI + HTMX
│   │   ├── callback.py     # TrainerCallback → WebSocket
│   │   └── metrics.py      # GPU/CPU/throughput
│   └── cli.py              # comandos Typer
└── tests/
    ├── test_recipes.py
    ├── test_extract.py
    ├── test_synth.py       # con LLM fake
    ├── test_train_tiny.py  # tiny-gpt2, sin GPU
    └── test_cli.py
```

## Reutilización del toolkit existente

| Necesidad | Componente reusado |
|---|---|
| Parsear JWPUB cifrado | `jw_core.parsers.jwpub.parse_jwpub` |
| Parsear EPUB | `jw_core.parsers.epub.parse_epub` |
| Parsear artículos WOL | `jw_core.parsers.article.parse_article` |
| Fetch chapters/articles | `jw_core.clients.wol.WOLClient`, `CDNClient` |
| Detección y registro de idiomas | `jw_core.languages` |
| Chunking de párrafos | `jw_rag.chunker.chunk_paragraphs` |
| Deduplicación semántica opcional | `jw_rag.embed.Embedder` + `jw_rag.store.VectorStore` |
| Telemetría opt-in | `jw_core.observability` (Fase 9) |

Cero duplicación: `jw-finetune` consume APIs existentes.

## Pipeline de datos

```
[JWPUB / EPUB / WOL]
        │
        ▼
   extract.py ──► ParagraphRecord(text, pub_code, lang, doc_id, ref, kind)
        │
        ▼
   dedupe.py   ──► (simhash near-dup + opcional embedding)
        │
        ▼
   chunk.py    ──► Chunk(text, source_id, metadata)
        │
        ├──► [CPT path] dataset_raw.jsonl     {"text": "..."}
        │
        └──► synth.py ─► [SFT path] dataset_qa.jsonl
                          {"messages": [{role, content}, ...]}
                          │ (Anthropic / Ollama generan Q&A
                          │  desde el contexto del chunk;
                          │  validación: refs bíblicas, longitud, lang)
                          ▼
                    [Train via Unsloth]
                          │
                          ▼
                  [Eval JW-specific]
                          │
                          ▼
        [Export: GGUF | MLX | safetensors | adapter-only]
```

Cada stage es **idempotente** y persiste a disco en `./jw-finetune-workspace/<run-id>/`,
así el usuario puede reanudar si se le corta el entrenamiento.

## Modelo de datos

### `ParagraphRecord`
```python
@dataclass(frozen=True)
class ParagraphRecord:
    text: str
    pub_code: str         # "w24", "wp23", "lff", etc.
    language: str         # ISO 639-1: "es", "en", ...
    doc_id: str           # MEPS doc id si está disponible
    section_ref: str      # "w24 12 p.7", "lff lección 5", etc.
    kind: Literal["watchtower", "awake", "book", "brochure", "bible", "article"]
    paragraph_pid: int | None
    source_path: str      # ruta al JWPUB/EPUB local o URL
```

### `Recipe`
```python
@dataclass
class Recipe:
    name: str
    task: Literal["cpt", "sft", "grpo"]
    sources: list[SourceSpec]
    languages: list[str]
    publication_kinds: list[str]
    qa_style: Literal["doctrinal", "verse-explain", "objection-handling"] | None
    base_model: str                       # ej: "unsloth/Qwen2.5-7B-bnb-4bit"
    lora_rank: int = 16
    lora_alpha: int = 32
    max_seq_len: int = 2048
    epochs: int = 1
    batch_size: int = 2
    gradient_accumulation: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    synth_provider: Literal["anthropic", "ollama"] | None = "ollama"
    synth_model: str | None = None        # "claude-opus-4-7" o "llama3.1:8b"
    output_dir: str = "./jw-finetune-workspace"
```

### Presets out-of-the-box (Fase 1)

| Preset | Task | Idioma | Uso |
|---|---|---|---|
| `watchtower-style-es-cpt` | CPT | es | Estilo de Atalaya en español |
| `doctrinal-qa-es-sft` | SFT | es | Q&A doctrinal en español |
| `verse-explainer-multilang-sft` | SFT | es+en | Versículo → explicación |
| `apologetics-objections-sft` | SFT | es | Manejo de objeciones |

## Generación de Q&A sintéticos

`synth.py` toma chunks y produce pares Q&A usando un LLM externo (Anthropic Claude o
Ollama local). Para cada chunk:

1. **Template Jinja2** (`templates/qa_doctrinal.j2`, etc.) construye el prompt según
   `qa_style`. Incluye instrucciones de:
   - Mantener el idioma del chunk
   - Citar referencias bíblicas en formato canónico
   - Evitar terminología no-JW
   - Generar N pares por chunk (default: 3)
2. **LLM provider**: Anthropic (cloud) u Ollama (local). Configurable por usuario.
3. **Validación**: cada par pasa filtros:
   - Lang detection coincide con `chunk.language`
   - Refs bíblicas regex-válidas (libro abreviado + cap:vers)
   - Longitud razonable (Q: 10-200 chars, A: 50-800 chars)
   - No filtración de prompt
4. **Output**: JSONL ShareGPT format con metadata de origen.

## Capa de entrenamiento

Wrapper delgado sobre Unsloth. Ejemplo conceptual SFT:

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig

def train_sft(recipe: Recipe, dataset_path: Path, workspace: Path) -> Path:
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=recipe.base_model,
        max_seq_length=recipe.max_seq_len,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=recipe.lora_rank,
        lora_alpha=recipe.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    dataset = load_dataset("json", data_files=str(dataset_path), split="train")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            output_dir=str(workspace / "checkpoints"),
            num_train_epochs=recipe.epochs,
            per_device_train_batch_size=recipe.batch_size,
            gradient_accumulation_steps=recipe.gradient_accumulation,
            learning_rate=recipe.learning_rate,
            warmup_ratio=recipe.warmup_ratio,
            logging_steps=10,
            save_steps=100,
            report_to="none",  # usamos nuestro callback custom
        ),
        callbacks=[JWMonitorCallback(workspace=workspace)],
    )
    trainer.train()
    return workspace / "checkpoints" / "final"
```

## CLI

```bash
jw-finetune init                                # workspace + config wizard
jw-finetune prepare --recipe doctrinal-qa-es-sft
jw-finetune prepare --recipe-file ./my-recipe.yaml
jw-finetune train --workspace ./run-2026-05-30
jw-finetune eval --checkpoint ./run.../checkpoint-200
jw-finetune export --format gguf --quant Q4_K_M
jw-finetune monitor                              # abre http://localhost:7860
jw-finetune models                               # lista catálogo Unsloth filtrable
jw-finetune run --recipe ...                     # pipeline end-to-end
```

Integrable con `jw-cli` cuando `jw-finetune` está instalado (entry-point Typer).

## Monitoreo / Observabilidad

**Dashboard local** en `http://localhost:7860` (FastAPI + HTMX, server-side rendering,
sin frontend pesado):

- Live loss curve (WebSocket desde `TrainerCallback`)
- GPU/CPU usage (`pynvml` / `psutil` / `mlx.metal` según backend)
- Throughput: tokens/s, samples/s, ETA
- Memoria: VRAM allocated/reserved, RAM
- **JW-specific live evals** (cada N steps sobre un eval set fijo):
  - Citation accuracy: % refs bíblicas correctamente formateadas
  - Doctrinal terminology: % uso de términos JW vs alternativos
  - Language consistency: respuesta en idioma esperado
- Logs streaming: loss, lr, grad_norm
- Checkpoint browser: lista checkpoints, "test prompt" contra cualquiera

## Exportación

| Formato | Uso | Implementación |
|---|---|---|
| GGUF | Ollama, llama.cpp | `model.save_pretrained_gguf()` (Unsloth) |
| MLX | macOS nativo | `mlx-lm convert` (subproceso) |
| safetensors 16-bit | HuggingFace, vLLM | `model.save_pretrained_merged()` |
| Adapter only | LoRA portátil | `model.save_pretrained()` |

## Testing strategy

| Tipo | Cobertura | Hardware |
|---|---|---|
| Unit | Recipe→config, validators, regex de refs, templates Jinja | CPU |
| Synth | Provider LLM fake con fixtures | CPU |
| Integration | Training real con `sshleifer/tiny-gpt2` (~5MB) | CPU |
| GPU smoke | Marker `@pytest.mark.gpu`, no corre en CI default | GPU local |
| CLI | `typer.testing.CliRunner` | CPU |

`pyproject.toml` define markers `gpu`, `mlx`, `cuda` para skip selectivo.

## Consideraciones legales y éticas

1. **Cada usuario aporta sus propios JWPUBs/EPUBs** ya descargados de JW Library
   bajo los términos de uso oficiales. El toolkit no redistribuye contenido.
2. **No se distribuyen pesos** del modelo entrenado por defecto. Los pesos son
   personales y se quedan en la máquina del usuario.
3. El README del paquete debe advertir explícitamente: "Este paquete genera
   modelos derivados de publicaciones con copyright. El uso, exportación o
   distribución de los pesos resultantes es responsabilidad del usuario y debe
   respetar los términos de uso de Watchtower Bible and Tract Society."
4. Continued pretraining sobre corpus copyright produce derivados claramente
   reconocibles. SFT sobre Q&A sintéticos genera derivados menos directos pero
   aun derivados.

## Fases de entrega

| Fase | Entrega | Estimación |
|---|---|---|
| **F1 (MVP)** | `data/` + `recipes/` + `train/` (SFT+CPT) + `export/` + CLI | 1-2 semanas |
| **F2** | Monitoreo web + JW-specific evals | 3-5 días |
| **F3** | TUI interactiva (textual) + wizards | 3-5 días |
| **F4** | Web UI completa estilo Studio | 1-2 semanas |
| **F5** | GRPO/RL + integración con `jw-agents` para consumir el modelo entrenado | 1 semana |

## Criterios de éxito (definition of done para F1)

- [ ] Un usuario puede ejecutar `jw-finetune run --recipe doctrinal-qa-es-sft
      --source ./mi-jwpub-folder` y obtener un modelo entrenado + GGUF exportado.
- [ ] El pipeline es idempotente (puede reanudar desde checkpoint).
- [ ] Tests unitarios pasan sin GPU.
- [ ] Test de integración con tiny-gpt2 pasa en CI.
- [ ] README explica copyright y términos de uso.
- [ ] `jw-finetune --help` muestra todos los comandos.
- [ ] Los 4 presets iniciales producen datasets válidos verificables manualmente.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Unsloth no instala en Mac/AMD/CPU sin GPU | Extras opcionales `[cuda]`, `[mlx]`, `[rocm]`. Sin extras, solo data-prep funciona. |
| Coste de generar Q&A con Anthropic | Ollama como provider default (gratis, local). Anthropic opt-in. |
| Memorización literal de copyright | Documentación clara sobre uso personal; recomendar QLoRA r=16 (capacidad limitada) por defecto. |
| Cambios breaking en Unsloth API | Pin version range en `pyproject.toml`, smoke tests semanales en CI. |
| Datasets de mala calidad → modelo mediocre | JW-specific evals durante entrenamiento; eval set curado manualmente. |

## Out of scope (este spec)

- Modelo distribuido oficial
- Servir el modelo en cloud
- Soporte de modelos multimodales (visión)
- Reinforcement learning desde feedback humano (RLHF) — solo GRPO en F5
- Integración con plataformas comerciales de fine-tuning (OpenAI, Anthropic FT)
