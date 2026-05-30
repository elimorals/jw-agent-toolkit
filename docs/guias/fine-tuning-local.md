# Guía: fine-tuning local con `jw-finetune`

Esta guía cubre el flujo end-to-end de entrenar tu propio modelo JW personal
con tus publicaciones locales (JWPUB / EPUB) usando Unsloth como motor.

> ⚠️ **Disclaimer legal**: Las publicaciones JW son copyright de Watchtower
> Bible and Tract Society. Esta plataforma asume que el usuario aporta sus
> propios JWPUBs/EPUBs ya descargados oficialmente desde JW Library. El uso
> de los pesos del modelo resultante es responsabilidad del usuario.

## Antes de empezar — diagnóstico

Antes del primer entrenamiento, ejecuta:

```bash
jw-finetune doctor
```

Verifica: Python ≥3.13, `uv` instalado, GPU detectada (NVIDIA / Apple Silicon),
deps opcionales (`unsloth`, `transformers`, `fastapi`, `textual`, ...),
Ollama corriendo, JW Library detectada en macOS, workspace escribible.

Si todo va bien, salida típica:

```
jw-finetune doctor
===================
  ✓ python         ok    3.13.13
  ✓ uv             ok    uv 0.9.17
  ✓ gpu            ok    Apple Silicon (arm)
  ✓ fastapi        ok    installed
  ✓ textual        ok    installed
  · ollama         info  not running (run `ollama serve` to enable)
  ✓ jw_library     ok    app installed (macOS)
  ✓ workspace      ok    /Users/yo/jw-finetune-workspace
OK
```

## ¿Cuándo usar fine-tuning vs RAG?

| Usa **RAG** (`jw-rag`) cuando... | Usa **fine-tuning** (`jw-finetune`) cuando... |
|---|---|
| Necesitas citas exactas y verificables | Quieres estilo conversacional fluido |
| Tu biblioteca cambia frecuentemente | Tu biblioteca es estable |
| Tienes poco hardware (no GPU) | Tienes GPU o Apple Silicon |
| Quieres precisión factual sobre velocidad | Quieres respuestas rápidas offline |

**Ideal**: usa AMBOS. RAG para precisión + fine-tune para tono y fluidez.

## Requisitos

- Python 3.13+, `uv` instalado
- Para entrenamiento, uno de:
  - **NVIDIA** GPU 12GB+ (recomendado 24GB)
  - **Apple Silicon** M2/M3/M4
  - **AMD** GPU con ROCm
- Para data prep + synth: cualquier máquina con Ollama o cuenta Anthropic
- Tus publicaciones: archivos `.jwpub` y/o `.epub` descargados de JW Library

## Instalación

```bash
# Solo data prep (sin GPU)
uv sync --package jw-finetune

# NVIDIA GPU
uv sync --package jw-finetune --extra cuda

# Apple Silicon
uv sync --package jw-finetune --extra mlx

# AMD GPU
uv sync --package jw-finetune --extra rocm

# Q&A synthesis (Anthropic o Ollama)
uv sync --package jw-finetune --extra synth

# Dashboard web (FastAPI + WebSocket)
uv sync --package jw-finetune --extra monitor

# TUI interactiva (Textual)
uv sync --package jw-finetune --extra tui
```

## Tabla de modelos base por hardware

| VRAM / RAM | Modelo recomendado |
|---|---|
| 8GB VRAM | `unsloth/Qwen2.5-3B-bnb-4bit` |
| 12-16GB VRAM | `unsloth/Qwen2.5-7B-bnb-4bit` |
| 24GB+ VRAM | `unsloth/Qwen2.5-13B-bnb-4bit` o 7B en Q8 |
| Mac M2/M3 16GB | `unsloth/Qwen2.5-3B` o `unsloth/Llama-3.2-3B` |
| Mac M3/M4 32GB+ | `unsloth/Qwen2.5-7B` |

Otros modelos populares: Llama 3.1/3.2, Gemma 3, Mistral, Phi-4.

## Pipeline conceptual

```
JWPUB / EPUB  →  extract  →  dedupe  →  chunk
                                          │
                                          ├─► CPT (raw text)        ─► entrena estilo
                                          │
                                          └─► SFT (Q&A sintético)   ─► entrena Q&A
                                                  │
                                                  └─ vía Ollama o Anthropic Claude

                  →  train (Unsloth LoRA)
                  →  eval (citas + terminología)
                  →  export (GGUF / MLX / safetensors)
```

## Quick start "100% gratis" (sin Anthropic ni Ollama)

Si tu corpus son Atalayas de estudio, puedes entrenar SIN tocar ningún LLM
externo:

```bash
# 1. Health check
jw-finetune doctor

# 2. Preparar usando Atalayas — extrae preguntas reales (no synth)
jw-finetune prepare \
    --recipe watchtower-questions-es-sft \
    --source ./mis-atalayas-es/

# 3. Entrenar
jw-finetune train --workspace ./jw-finetune-workspace/run-*

# 4. Exportar
jw-finetune export \
    --checkpoint ./jw-finetune-workspace/run-*/checkpoints/final \
    --format gguf --quant Q4_K_M
```

Tiempo total: ~30 min de prepare + training (depende del corpus).
Coste API: **$0**.

## Quick start (5 pasos)

### 1. Ver presets disponibles

```bash
jw-finetune presets
```

Salida: tabla con nombre, task, idiomas, modelo base, qa_style.

### 2. Inspeccionar / personalizar un preset

```bash
jw-finetune init --preset doctrinal-qa-es-sft --out my-recipe.yaml
```

Abre `my-recipe.yaml` y ajusta:
- `base_model` según tu hardware
- `epochs`, `lora_rank`, `learning_rate`
- `qa_per_chunk`: cuántos pares Q&A generar por chunk

Añade tus fuentes:

```yaml
sources:
  - kind: jwpub
    path: /Users/yo/Library/JW/w_S_202412.jwpub
    language: es
  - kind: epub
    path: /Users/yo/Library/JW/lff_S.epub
    language: es
```

### 3. Preparar dataset

```bash
jw-finetune prepare \
    --recipe-file my-recipe.yaml \
    --source /Users/yo/Library/JW/ \
    --synth-provider ollama \
    --synth-model "llama3.1:8b"
```

Esto crea `./jw-finetune-workspace/run-YYYYMMDD-HHMMSS/` con:
- `recipe.yaml` (copia del recipe)
- `dataset_qa.jsonl` (si SFT) o `dataset_raw.jsonl` (si CPT)
- `events.jsonl` (eventos del monitor, vacío hasta `train`)

> **Tip**: Si tu LLM local es lento, empieza con 5-10 publicaciones para
> validar pipeline antes de procesar toda tu biblioteca.

### 4. Entrenar

```bash
jw-finetune train --workspace ./jw-finetune-workspace/run-YYYYMMDD-HHMMSS
```

El monitor callback escribe eventos a `events.jsonl`. Puedes seguirlos en otra terminal:

```bash
tail -f ./jw-finetune-workspace/run-*/events.jsonl | jq -r '"\(.step): loss=\(.loss)"'
```

### 5. Exportar a GGUF (para Ollama)

```bash
jw-finetune export \
    --checkpoint ./jw-finetune-workspace/run-*/checkpoints/final \
    --format gguf \
    --quant Q4_K_M \
    --out ./mi-modelo-jw
```

Luego en Ollama:

```bash
cd ./mi-modelo-jw
cat > Modelfile <<EOF
FROM ./model-Q4_K_M.gguf
SYSTEM "Eres un asistente que responde preguntas doctrinales JW de forma respetuosa."
EOF
ollama create mi-jw -f Modelfile
ollama run mi-jw "¿Qué dice Mateo 24:14?"
```

## Pipeline end-to-end (un solo comando)

```bash
jw-finetune run \
    --recipe doctrinal-qa-es-sft \
    --source ./mis-jwpubs/ \
    --export gguf
```

Hace prepare → train → export en secuencia.

## Evaluación

```bash
# Crea un archivo de prompts
cat > ./prompts.txt <<EOF
¿Qué es el Reino de Dios según las Escrituras?
Explica Mateo 24:14.
¿Por qué los Testigos de Jehová no celebran cumpleaños?
EOF

jw-finetune evaluate \
    --checkpoint ./jw-finetune-workspace/run-*/checkpoints/final \
    --prompts ./prompts.txt \
    --language es \
    --out ./eval-report.json
```

El reporte incluye:
- `citation_accuracy`: % de respuestas con refs bíblicas válidas
- `terminology_score`: % de respuestas con vocabulario JW
- `answers`: las respuestas generadas

## Dos modos de generar dataset: **extracted** vs **synthesized**

`jw-finetune` soporta dos formas de construir el dataset de Q&A para SFT.
La elección importa: usar el modo correcto cuesta menos y produce un modelo
mejor.

### Modo **extracted** (recomendado cuando aplica)

Cuando la publicación JW *ya contiene* Q&A naturales, el pipeline las extrae
directamente sin llamar a ningún LLM externo. Cero coste de API, datos
canónicos de WBTS, máxima fidelidad doctrinal.

Ejemplos:
- **Atalaya de estudio** trae cada párrafo con sus preguntas de estudio
  italicizadas — el pipeline mapea `(párrafo, pregunta)` 1:1.
- **NWT Study Edition** trae notas de estudio alineadas a versículo —
  el pipeline mapea `(versículo, nota)` directamente.
- **Workbook (Vida y Ministerio)** trae asignaciones tituladas con su
  descriptivo — el pipeline mapea `(asignación, descriptivo)`.
- **Catálogo de objeciones** del toolkit ya curado por WBTS.
- **Tus propias notas** en JW Library (backup `.jwlibrary`) — preset
  personalizado a tu estudio.

Presets en este modo (con `synth_provider=None`):

| Preset | Fuente | Output |
|---|---|---|
| `watchtower-questions-es-sft` | Atalayas en EPUB/JWPUB | Pares (párrafo, pregunta) |
| `ministry-school-es-sft` | Workbooks `mwb*` | Pares (asignación, descriptivo) |
| `personal-study-companion-sft` | Backup `.jwlibrary` del usuario | Pares (título de nota, contenido) |

### Modo **synthesized**

Cuando los chunks son texto libre (libros doctrinales sin preguntas
estructuradas, artículos, párrafos del WOL), el pipeline llama a un LLM
externo (Anthropic Claude u Ollama local) para generar pares Q&A
sintéticos basados en el chunk.

Presets en este modo:

| Preset | Task | Idioma | Para qué sirve |
|---|---|---|---|
| `watchtower-style-es-cpt` | CPT | es | Que el modelo escriba en el estilo de Atalaya |
| `doctrinal-qa-es-sft` | SFT | es | Asistente Q&A doctrinal libre |
| `verse-explainer-multilang-sft` | SFT | es+en | Versículo → explicación |
| `apologetics-objections-sft` | SFT | es | Manejo de objeciones |

### ¿Cuál elegir?

Si tu corpus es 100% Atalayas de estudio + NWT Study Edition + Workbooks,
**usa solo presets extracted**: dataset gratuito, fiel y rápido.
Para todo lo demás (libros doctrinales como `bh`, `rr`, `lff`, `sjj`,
brochures, artículos), usa los presets `*-sft` regulares con synth.

Puedes mezclar: ejecuta dos `prepare` con presets distintos contra el mismo
`--workspace`, y entrena con un dataset combinado.

## Estructura del workspace

```
jw-finetune-workspace/
└── run-20260530-143022/
    ├── recipe.yaml
    ├── dataset_raw.jsonl       # si task=cpt
    ├── dataset_qa.jsonl        # si task=sft
    ├── events.jsonl            # eventos del monitor
    ├── checkpoints/
    │   ├── checkpoint-100/
    │   ├── checkpoint-200/
    │   └── final/
    └── export/
        └── <fmt>/              # gguf / mlx / merged / adapter
```

## Costos estimados de Q&A synthesis

Para preparar dataset con ~1000 chunks:

| Provider | Costo aprox | Velocidad |
|---|---|---|
| **Ollama** local (llama3.1:8b) | $0 (electricidad) | Lento (~30 min) |
| **Anthropic Haiku** | ~$0.20 | Rápido (~5 min) |
| **Anthropic Sonnet** | ~$2.00 | Rápido, mejor calidad |

## Troubleshooting

### "ModuleNotFoundError: No module named 'unsloth'"
No tienes el extra GPU instalado. Ejecuta:
```bash
uv sync --package jw-finetune --extra cuda  # o mlx, rocm
```

### "FileNotFoundError: missing.jwpub"
La ruta del JWPUB es relativa al directorio donde corres `jw-finetune`. Usa rutas absolutas o cambia a esa carpeta.

### El modelo entrena bien pero genera respuestas raras
- Aumenta `epochs` (default 2 → prueba 3-4)
- Aumenta `qa_per_chunk` para más pares por chunk
- Revisa `dataset_qa.jsonl` manualmente: ¿los pares Q&A se ven razonables?

### Ollama no responde
Asegúrate de que Ollama está corriendo: `ollama serve`. El modelo debe estar descargado: `ollama pull llama3.1:8b`.

## Privacidad

- **Todo corre local**, excepto si usas `--synth-provider anthropic` (entonces los chunks de tus publicaciones viajan a la API de Anthropic).
- Con `ollama` como provider, ningún byte sale de tu máquina.
- Los JWPUBs y EPUBs nunca se redistribuyen.
- Los pesos del modelo entrenado son personales — no los publiques sin entender las implicaciones de copyright.

## Dashboard web live (F2)

Mientras entrenas, abre un dashboard local con loss curve, métricas GPU/CPU y log de eventos:

```bash
# En otra terminal:
jw-finetune monitor --workspace ./jw-finetune-workspace/run-*
# o sin --workspace: usa el run más reciente automáticamente
jw-finetune monitor
```

Luego abre http://localhost:7860. El dashboard es 100% local (sin CDNs externos), reconecta automáticamente si pierde la conexión WebSocket.

## TUI interactiva (F3)

Si prefieres la terminal:

```bash
jw-finetune tui-wizard    # wizard interactivo para crear recipe
jw-finetune tui-monitor   # monitor inline en terminal
```

Requiere el extra `[tui]`: `uv sync --package jw-finetune --extra tui`.

## Web UI completa estilo Studio (F4)

Para una experiencia visual completa con browser de runs, catálogo de presets/modelos, dataset preview, y chat playground:

```bash
jw-finetune studio --workspace-root ./jw-finetune-workspace
```

Abre http://localhost:7860/studio. Incluye:
- **Runs**: lista de runs con su recipe, dataset preview, checkpoints
- **Presets**: catálogo visual de presets out-of-the-box
- **Models**: catálogo curado de modelos base (3B/7B/13B) con requisitos VRAM
- **Playground**: chat directo con cualquier checkpoint final entrenado

## Integración Unsloth — qué hace bien el toolkit por ti

La capa de training aplica automáticamente las tres prácticas más importantes
de Unsloth que se suelen olvidar al integrar:

1. **`get_chat_template`** — alinea el tokenizer al template del modelo base
   (chatml, qwen-2.5, llama-3, gemma, phi-4, mistral). Sin esto, el modelo
   entrena con un template incorrecto y degrada en inferencia.
2. **`train_on_responses_only`** — máscara los tokens del usuario/sistema,
   entrenando solo en los tokens del assistant. Sin esto, el modelo aprende
   a "repetir la pregunta" además de a responder.
3. **`standardize_sharegpt`** — convierte el dataset al formato canónico que
   trl espera. Sin esto, ciertos templates fallan silenciosamente.

Los puedes controlar desde la recipe:

```yaml
chat_template: qwen-2.5       # auto-aplicado
train_on_responses_only: true # mask user tokens
use_rslora: true              # rank-stabilized LoRA (mejor a rank ≥64)
packing: null                 # null = task default (CPT=true, SFT=false)
embedding_learning_rate_ratio: 0.1  # para CPT
```

### Templates soportados

`chatml`, `qwen-2.5`, `qwen-3`, `llama-3`, `llama-3.1`, `gemma`, `gemma-3`,
`phi-4`, `mistral`. Para uno custom, define manualmente:

```yaml
chat_template: my-custom
instruction_part: "<USER>"
response_part: "<BOT>"
```

## Cache de Q&A sintéticas — re-runs gratis

Cuando ejecutas `prepare` con un preset `synthesized`, cada par Q&A generado
se cachea en SQLite (`~/.cache/jw-finetune/synth.db`) con clave =
`SHA256(chunk_text + qa_style + language + n_pairs + provider + model)`.

Re-ejecutar `prepare` con el mismo corpus y recipe es **gratis**:

```bash
jw-finetune prepare --recipe doctrinal-qa-es-sft \
    --source ./mis-jwpubs/ --synth-provider anthropic
# Primera ejecución: ~$2 vía Anthropic, 5 min

jw-finetune prepare --recipe doctrinal-qa-es-sft \
    --source ./mis-jwpubs/ --synth-provider anthropic --workspace ./new-run
# Segunda ejecución: 100% cache hits, ~10s, $0
```

Inspeccionar/limpiar el cache:

```python
from jw_finetune.synth.cache import SynthCache
cache = SynthCache()  # ~/.cache/jw-finetune/synth.db
cache.stats()  # → {"entries": 1247, "total_pairs": 3741, ...}
cache.clear()  # → reset
```

## Concurrencia y retry/backoff

El pipeline ahora corre en async con semáforo de concurrencia:
- **Anthropic**: 10 requests paralelos (rate-limit safe)
- **Ollama**: 4 requests paralelos (saturación de GPU local)

Fallos transitorios reintentan con exponential backoff (4 attempts, factor 2x,
con jitter). Si un chunk falla todos los retries, el resto del dataset
sobrevive.

## GRPO / Reinforcement Learning (F5)

Para hacer que el modelo aprenda con feedback en lugar de pares Q&A fijos,
usa una recipe con `task: grpo`. Reward functions built-in:

| Reward | Qué premia/penaliza | Default weight |
|---|---|---|
| `citation_reward` | Respuestas con ≥1 ref bíblica válida (vía `parse_reference`) | 0.45 |
| `terminology_reward` | Respuestas con vocabulario JW (10 idiomas) | 0.30 |
| `length_penalty` | Longitud 30-1500 chars; penaliza extremos | 0.15 |
| `apocrypha_penalty` | Penaliza mencionar libros apócrifos como canónicos | (opcional) |

GRPO config JW-tuned automáticamente:
- `max_completion_length=1024` (respuestas doctrinales suelen exceder 512)
- `num_generations=6` (más muestras → señal de reward más estable)

```bash
# Edita un recipe SFT y cambia task: grpo, luego:
jw-finetune train --workspace ./jw-finetune-workspace/run-*
```

### Reward custom (ej: combinar con tu RAG o con apocrypha penalty)

```python
from jw_finetune.train.grpo import (
    train_grpo, composite_reward,
    make_citation_reward, make_terminology_reward,
    make_length_penalty, make_apocrypha_penalty,
)

# Composite con apocrypha penalty incluido
reward = composite_reward(
    [
        make_citation_reward(expect_at_least=1),
        make_terminology_reward(language="es"),
        make_length_penalty(min_chars=30, max_chars=1500),
        make_apocrypha_penalty(),  # ← JW-specific
    ],
    weights=[0.40, 0.25, 0.15, 0.20],
)
train_grpo(recipe, dataset, workspace, reward_fn=reward)
```

### Reward que usa tu RAG

```python
def rag_consistency_reward(prompts, completions):
    """Premia respuestas coherentes con el contexto recuperado por jw-rag."""
    from jw_rag.store import VectorStore
    store = VectorStore(...)
    scores = []
    for prompt, answer in zip(prompts, completions):
        hits = store.search(prompt, top_k=3)
        # Tu lógica: compara `answer` contra hits[*].chunk.text
        scores.append(your_similarity_score(answer, hits))
    return scores
```

## Integración con jw-agents

Una vez tienes tu modelo entrenado y exportado a Ollama, hay tres niveles de
integración con `jw-agents`:

### Nivel 1 — Asistente directo

```python
from jw_agents.finetuned_model import build_client
from jw_agents.finetuned_assistant import finetuned_assistant
from jw_rag.store import VectorStore
from jw_rag.embed import FakeEmbedder

client = build_client(backend="ollama", model="mi-jw")
rag = VectorStore("./jw-rag-index", embedder=FakeEmbedder(dim=384))

result = finetuned_assistant(
    "¿Qué es el Reino de Dios?",
    client=client, rag_store=rag, top_k=3, language="es",
)
print(result.metadata["generated_answer"])
```

### Nivel 2 — Composición de agentes (recomendado para verses)

Encadena un agente procedural (que recupera contexto verificable) con tu
modelo fine-tuneado (que redacta la respuesta):

```python
from jw_agents.agent_pipeline import verse_explainer_with_finetuned

# verse_explainer trae el versículo + study notes + cross-refs
# y luego pasa todo eso como contexto a tu modelo fine-tuneado
result = await verse_explainer_with_finetuned(
    "Juan 3:16",
    finetuned_client=client,
    language="es",
)

# Las findings (con citas verificables) vienen de verse_explainer
for f in result.findings:
    print(f.citation.title, "—", f.summary[:80])

# La prosa generada por el fine-tuneado
print(result.metadata["generated_answer"])
```

Y para apologetics:

```python
from jw_agents.agent_pipeline import conversation_assistant_with_finetuned

result = await conversation_assistant_with_finetuned(
    "¿Por qué no celebran navidad?",
    finetuned_client=client,
    language="es",
)
```

### Nivel 3 — Directo contra checkpoint (más pesado)

```python
client = build_client(backend="unsloth", checkpoint_dir="./run-*/checkpoints/final")
```

## MCP tools para Claude Desktop

`jw-finetune` expone 6 herramientas MCP para que Claude Desktop u otros
clientes MCP puedan introspeccionar y operar tus runs sin que tengas que
escribir código.

Para activarlas, edita `packages/jw-mcp/src/jw_mcp/server.py` y añade:

```python
from jw_finetune.mcp_tools import register_jw_finetune_tools
register_jw_finetune_tools(mcp, workspace_root=Path("./jw-finetune-workspace"))
```

Tools disponibles:

| Tool | Qué hace |
|---|---|
| `list_finetune_runs` | Lista runs con su task, dataset, checkpoints |
| `get_finetune_run` | Detalle de un run: recipe + dataset preview + checkpoints |
| `get_finetune_events` | Últimos N eventos de training (loss, eval, etc.) |
| `list_finetune_presets` | Catálogo de presets con metadata |
| `chat_with_finetune_checkpoint` | Chat one-shot contra un checkpoint final |
| `doctor_finetune` | Health check del entorno (igual que `jw-finetune doctor`) |

Casos de uso desde Claude Desktop:
- "¿Cuál fue la última loss de mi run más reciente?" → `get_finetune_events`
- "Muéstrame el preset apologetics-objections-sft" → `list_finetune_presets`
- "Prueba esta pregunta en mi modelo entrenado" → `chat_with_finetune_checkpoint`

## Reproducibilidad: README auto-generado en cada export

Cada `jw-finetune export` escribe un `README.md` junto al modelo exportado
con:

- Recipe completa usada (incluyendo `chat_template`, `use_rslora`, etc.)
- Stats del dataset (rows, mode)
- Eval scores (citation accuracy, terminology score)
- Checkpoint hash determinístico (SHA256 sobre safetensors)
- Snippet listo para cargar en Ollama
- Snippet de cómo consumirlo desde `jw-agents`
- Disclaimer de copyright

Para desactivarlo: `jw-finetune export ... --no-readme`.

## Comparar dos checkpoints (`jw-finetune diff`)

¿Vale la pena un epoch más? ¿Mejora con `use_rslora`?

```bash
cat > ./prompts.txt <<EOF
¿Qué es el Reino de Dios?
Explica Mateo 24:14.
¿Por qué no celebran cumpleaños?
EOF

jw-finetune diff \
    --a ./run-baseline/checkpoints/final \
    --b ./run-experiment/checkpoints/final \
    --prompts ./prompts.txt \
    --language es \
    --out ./diff-report.json
```

Salida:

```
A: citation 67% · terminology 50%
B: citation 100% · terminology 75%
```

El JSON tiene cada (prompt, answer_a, answer_b, score_a, score_b) para
inspección manual.

## Limitaciones actuales

- El dashboard web no persiste métricas históricas; cada `jw-finetune monitor` empieza con el buffer en memoria más los eventos disponibles en disco
- El chat playground del studio requiere stack Unsloth instalado (no funciona con Ollama-only). Para Ollama use el adapter `jw_agents.finetuned_model.OllamaFinetunedClient` desde Python.
- `score_terminology` para japonés/coreano/chino: el `\b` de regex Python no funciona perfectamente con CJK; la métrica puede subestimar la cobertura. Para CJK, usar `terms=` override con un set ya tokenizado.
- Multi-GPU está expuesto vía `Recipe.use_multi_gpu=True` pero requiere `accelerate config` previo; no tenemos un wizard para esa parte.
- `enrich_chunk_with_verses` (cross-ref enrichment) hace red durante prepare — bookkeeping correcto cuando lo usas en producción de dataset; para experimentación, considera cachear `_url, html` aparte.

## Comandos CLI completos

```
jw-finetune doctor       # health check
jw-finetune presets      # listar presets
jw-finetune init         # generar recipe yaml desde preset
jw-finetune prepare      # extraer + dedupe + chunk + (synth | extract)
jw-finetune train        # SFT | CPT | GRPO según recipe.task
jw-finetune evaluate     # eval con prompts.txt → eval-report.json
jw-finetune diff         # comparar dos checkpoints con mismos prompts
jw-finetune export       # GGUF | MLX | merged | adapter + README auto
jw-finetune monitor      # dashboard web live
jw-finetune studio       # web UI completa (runs / presets / models / playground)
jw-finetune tui-wizard   # wizard interactivo (Textual)
jw-finetune tui-monitor  # monitor inline en terminal
jw-finetune run          # pipeline end-to-end: prepare → train → export
```
