# Fase 36 — `vlm-ocr`: VLM como OCR estructurado

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (habilitador)
> **Depende de**: ninguna fase previa estrictamente; reutiliza patrón triple-target (Fases 33-34).
> **Documento padre**: [`2026-05-31-fases-33-38-overview.md`](2026-05-31-fases-33-38-overview.md)
> **Plan hijo**: `2026-05-31-fase-36-vlm-ocr-plan.md`

## Motivación

Hoy `jw_core.vision.ocr` usa Tesseract sobre fotos de páginas de la Biblia o de publicaciones. Tesseract:

- Aplana toda la maquetación a texto plano (pierde estructura: títulos, citas, notas al pie).
- Se atraganta con páginas en dos columnas, marginalia y referencias de Atalayas.
- No distingue cita bíblica de párrafo normal — el RAG ingesta basura.
- Requiere binarios nativos (`brew install tesseract`) y diccionarios por idioma.

Un VLM moderno (Qwen3-VL, Claude Vision, GPT-4o/5 vision) hace dos saltos a la vez:

1. Reconoce caracteres en multilenguaje con menos errores.
2. **Estructura** el output — devuelve bloques tipados que el RAG ingesta con `source_id` por bloque, no como un blob.

Fase 36 reemplaza Tesseract como **default** cuando hay VLM disponible y lo deja como **fallback** con `DeprecationWarning`. Es el upgrade simétrico de Fase 33 (embed-rerank): no rompe API, sube techo de calidad.

## Objetivos (en orden de prioridad)

1. **Output estructurado tipado** — `StructuredPage` con bloques que ingestan al RAG con metadata útil.
2. **Triple target** — API, MLX (Apple Silicon), NVIDIA, CPU; auto-detect en factory.
3. **Adapter sobre el SDK `anthropic` existente** — `ClaudeVisionProvider` no es un modelo nuevo, es un wrapper sobre `messages.create(content=[{type:"image",...}, {type:"text",...}])` aplicable a Haiku 4.5 / Sonnet 4.6 / Opus 4.7.
4. **No red en tests** — `FakeVLMProvider` determinista; los providers reales fallan limpio si falta SDK / API key / hardware.
5. **Tesseract deprecado pero vivo** — `ocr_image()` sigue funcionando con `DeprecationWarning` + `migrate_to_vlm()` helper.
6. **Ingesta directa al RAG** — `jw_rag.ingest.ingest_image(path, language)` consume `StructuredPage` y emite chunks por bloque.

## No-objetivos (boundaries vinculantes)

- **No** entrenar / fine-tunear pesos. Pesos de Qwen3-VL local los baja el usuario (`huggingface-cli download`); el toolkit no distribuye modelos.
- **No** soportar PDFs multi-página directos — Fase 37 (`colpali-visual`) cubre rasterización + recuperación visual. Aquí sólo una imagen a la vez.
- **No** reescribir la API de `ocr_image()` — se mantiene compatible para que `extract_bible_reference_from_image()` y los 32 agentes no rompan.
- **No** wrappear el `mlx-vlm` / `vllm` / `llama-cpp-python` con CLIs propias — adaptamos sus SDK Python.

## Arquitectura

### Layout

```
packages/jw-core/src/jw_core/vision/
├── __init__.py
├── maps.py                          # existente
├── slides.py                        # existente
├── ocr.py                           # MODIFICADO — DeprecationWarning + migrate_to_vlm()
├── vlm.py                           # NUEVO — Protocol, StructuredPage, bloques
└── vlm_providers/                   # NUEVO
    ├── __init__.py
    ├── factory.py                   # JW_VLM_PROVIDER + auto-detect chain
    ├── fakes.py                     # FakeVLMProvider (determinista)
    ├── qwen3vl_local.py             # MLX / vLLM / llama-cpp-python
    ├── qwen3vl_api.py               # DashScope / Replicate / fal.ai (httpx)
    ├── openai_vision.py             # openai SDK
    └── claude_vision.py             # anthropic SDK adapter
```

### Contract central — `VLMProvider`

```python
class VLMProvider(Protocol):
    name: str                                  # "qwen3vl_local" | "claude_vision" | ...
    target: Literal["api", "nvidia", "mlx", "cpu"]

    def is_available(self) -> bool: ...
    def cost_estimate(self, image: Path | bytes) -> CostHint: ...
    def extract_structured(
        self,
        image: Path | bytes,
        prompt: str | None = None,
        *,
        language: str = "en",
    ) -> StructuredPage: ...
```

`is_available()` chequea SDK + credenciales + hardware **sin lanzar excepción**. La factory itera providers hasta encontrar uno disponible.

### Modelo de datos

```python
class StructuredBlock(BaseModel):
    """Un bloque tipado en una página."""

    kind: Literal["header", "paragraph", "citation", "footnote", "bible_ref", "caption"]
    text: str
    bbox: tuple[float, float, float, float] | None = None   # x1,y1,x2,y2 normalizado [0,1]
    lang_hint: str = "en"                                   # ISO-639-1
    confidence: float | None = None                          # 0..1, si el provider lo da
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredPage(BaseModel):
    """Output canónico de un VLM aplicado a una página."""

    blocks: list[StructuredBlock]
    source_image: str | None = None     # path absoluto o URL
    provider_name: str
    target: str                          # "api" | "nvidia" | "mlx" | "cpu"
    raw_text_fallback: str               # texto plano por compatibilidad con código viejo
    language_detected: str | None = None
```

`raw_text_fallback` permite que `extract_bible_reference_from_image()` siga parseando contra texto plano cuando el caller no quiere bloques.

### Providers concretos

| Provider | target | Backend | SDK | Auth |
|---|---|---|---|---|
| `Qwen3VLProvider` | mlx | `mlx-vlm` | `mlx-vlm>=0.1.0` (extra) | local, peso descargado |
| `Qwen3VLProvider` | nvidia | `vllm` | `vllm>=0.6` (extra) | local, peso descargado |
| `Qwen3VLProvider` | cpu | `llama-cpp-python` (GGUF) | `llama-cpp-python>=0.3` | local |
| `Qwen3VLAPIProvider` | api | DashScope / Replicate / fal.ai vía `httpx` | — | `JW_QWEN3VL_API_KEY` + `JW_QWEN3VL_API_BASE` |
| `OpenAIVisionProvider` | api | `openai` SDK | `openai>=1.40` (extra) | `OPENAI_API_KEY` |
| `ClaudeVisionProvider` | api | `anthropic` SDK | `anthropic>=0.34` (extra) | `ANTHROPIC_API_KEY` |
| `FakeVLMProvider` | cpu | hardcoded | — | — |

**ClaudeVisionProvider no es un modelo aparte**: usa los modelos Claude existentes (`claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-7`) vía `messages.create(messages=[{role:"user", content:[{type:"image", source:{type:"base64", media_type, data}}, {type:"text", text:prompt}]}])`. El env `JW_CLAUDE_VISION_MODEL` selecciona modelo, default `claude-haiku-4-5`.

### Factory + chain default

```python
# vlm_providers/factory.py

DEFAULT_CHAIN = ["qwen3vl_local", "qwen3vl_api", "claude_vision", "openai_vision", "tesseract_fallback"]

def get_default_provider() -> VLMProvider:
    """
    1. Si JW_VLM_PROVIDER está set, intenta ese exacto. Si no disponible, raise.
    2. Si no, itera DEFAULT_CHAIN. Devuelve el primer is_available()=True.
    3. Si ninguno: devuelve TesseractFallbackProvider que envuelve `ocr_image()`
       y emite DeprecationWarning.
    """
```

`tesseract_fallback` no es un provider real — es un wrapper que:
- llama a `ocr_image()` viejo,
- mete todo el texto en un solo `paragraph` block,
- emite `DeprecationWarning("Usando Tesseract fallback. Instala mlx-vlm o configura ANTHROPIC_API_KEY para output estructurado.")`.

### Prompt template (parametrizable)

```
DEFAULT_VLM_PROMPT = """You are an OCR system specialized in JW publications and Bible pages.
Read the image and return STRICT JSON with this schema:

{
  "blocks": [
    {"kind": "header|paragraph|citation|footnote|bible_ref|caption",
     "text": "...",
     "bbox": [x1, y1, x2, y2] | null,
     "lang_hint": "en|es|pt|...",
     "confidence": 0.0..1.0 | null}
  ],
  "language_detected": "en|es|pt|..."
}

Rules:
- bbox coordinates are normalized in [0,1] with origin top-left.
- Output ONLY valid JSON, no markdown fences, no commentary.
- Preserve original spelling and punctuation.
- "bible_ref" applies to inline scripture references (e.g. "John 3:16").
- "citation" applies to footnote-style citations of WT publications.
"""
```

Cada provider envuelve este prompt a su API. Los providers cuyo modelo no produce JSON fiable (Tesseract fallback) generan un único bloque `paragraph` con todo el texto.

### Integración con jw-rag

Nuevo método en `packages/jw-rag/src/jw_rag/ingest.py`:

```python
async def ingest_image(
    store: VectorStore,
    image_path: Path | str,
    *,
    language: str = "en",
    provider: VLMProvider | None = None,
) -> int:
    """Ingesta una foto de página al RAG con bloques tipados.

    - Llama al VLM via factory (o el provider inyectado).
    - Por cada StructuredBlock genera un chunk con source_id=f"image:{hash}:{i}:{kind}".
    - bible_ref blocks llevan metadata `{"kind": "bible_ref", "parsed": <BibleRef|None>}`
      intentando `parse_reference(block.text)`.
    """
```

### Path de migración para callers existentes

```python
def extract_bible_reference_from_image_v2(
    image_path: str | Path,
    *,
    language: str = "en",
    provider: VLMProvider | None = None,
) -> dict[str, object]:
    """Versión 2: prefiere VLM, fallback a tesseract.

    Devuelve `{
        "structured_page": StructuredPage,
        "reference": BibleRef.model_dump() | None,
        "text": str,                # = page.raw_text_fallback (compat)
        "language_hint": str,
    }`.
    """
```

`extract_bible_reference_from_image()` (V1) sigue funcionando pero con `DeprecationWarning`.

## Reglas duras de diseño

1. `vlm.py` y `vlm_providers/factory.py` **no importan ningún SDK en module level** — lazy imports dentro de cada provider concreto.
2. Cada provider real ship un fake hermano (todos comparten `FakeVLMProvider` parametrizado por nombre).
3. `JW_VLM_PROVIDER` env se respeta antes que cualquier auto-detect.
4. Test pyramid:
   - unit tests con `FakeVLMProvider` para lógica de factory + ingest,
   - integration tests **opt-in** con `pytest -m vlm_real` que sólo corren si la env señala disponibilidad.
5. `StructuredPage.raw_text_fallback` es **obligatorio** — incluso si el provider falla en estructura, debe llenar este campo para no romper a callers V1.
6. Cero red en CI público.

## Hardware y disponibilidad

| Hardware target | Provider preferido | Modelo concreto |
|---|---|---|
| Apple Silicon M2/M3/M4 | `Qwen3VLProvider` (mlx) | `mlx-community/Qwen3-VL-2B-Instruct-4bit` |
| NVIDIA 24GB+ VRAM | `Qwen3VLProvider` (vllm) | `Qwen/Qwen3-VL-8B-Instruct` |
| CPU-only Linux/Windows | `Qwen3VLProvider` (gguf) | `bartowski/Qwen3-VL-2B-Instruct-GGUF` Q4_K_M |
| Sin GPU + con API key | `Qwen3VLAPIProvider` o `ClaudeVisionProvider` | DashScope o Haiku 4.5 |
| Sin nada | `TesseractFallbackProvider` | tesseract |

## CLI y MCP

CLI (extiende `jw-cli`):

```
jw image extract IMAGE.png --language es --provider auto
jw image ingest IMAGE.png --language es                # ingesta al RAG global
```

MCP (`jw-mcp`):

```
extract_structured_page(image_path: str, language: str = "en") -> StructuredPage
ingest_image_to_rag(image_path: str, language: str = "en") -> {"chunks": int}
```

## Métricas de éxito

- ✅ `Qwen3VLProvider` (MLX) en M2 procesa una página estándar de la Atalaya en <8 s con bloques tipados.
- ✅ `ClaudeVisionProvider` con `claude-haiku-4-5` procesa la misma página en <4 s vía API.
- ✅ `FakeVLMProvider` permite que la suite de tests corra 100% offline.
- ✅ OCRBench-style fixture: VLM > Tesseract en bloques correctamente clasificados ≥80% de páginas JW de testset.
- ✅ `jw eval --layer 1` sigue verde tras integrar el nuevo path en agentes que dependen de imágenes.
- ✅ 0 importaciones top-level de SDKs opcionales.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Qwen3-VL local devuelve JSON malformado | Validar con Pydantic; si falla, degradar a un único bloque `paragraph` con el output como texto |
| 2 | Claude/OpenAI cuestan dinero en CI | API providers nunca son default en CI; chain default arranca por local |
| 3 | mlx-vlm no instalable en CI Linux | `extras_require['vlm-mlx']`; CI omite el extra; tests opt-in via `pytest -m vlm_real` |
| 4 | Tesseract sigue siendo el único path real para muchos usuarios | Mantener `ocr_image()` con DeprecationWarning sin romper API |
| 5 | Cambio de schema de prompt entre proveedores | Prompt central en `vlm.DEFAULT_VLM_PROMPT`; cada provider hace `_pack_prompt(prompt)` específico |
| 6 | RAG se llena de bloques de baja confianza | `ingest_image` filtra `confidence < 0.3` por defecto (configurable) |
| 7 | Coordenadas bbox inconsistentes entre providers | Normalizamos a [0,1] top-left siempre; documentado en docstring de `StructuredBlock` |
| 8 | Detección de idioma falla en páginas multilenguaje | `lang_hint` por bloque; `language_detected` es best-effort, no autoritativo |

## Datos iniciales

`packages/jw-core/tests/fixtures/vlm/`:
- `wt_2024_page_es.png` (1 página de Atalaya en español, alta-res) — fixture nuevo, derivado de captura propia
- `bible_john_3_es.png` (1 página NWT español)
- `wt_2024_page_en.png` (mismo número, inglés)
- `expected_structured/<sha>.json` — golden output por fixture (usado por `FakeVLMProvider`)

## Documentación

Nueva guía `docs/guias/vlm-ocr.md`:

- Qué hace `StructuredPage`
- Cómo elegir provider (matriz hardware/coste/privacy)
- Cómo migrar de `ocr_image()` a `extract_structured()`
- Cómo descargar pesos Qwen3-VL para uso local (link a HF, no distribuir)
- Limitaciones (multi-página → ver Fase 37)

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests offline (FakeVLMProvider)
uv run pytest packages/jw-core/tests/test_vlm_providers.py packages/jw-core/tests/test_vlm_factory.py packages/jw-core/tests/test_vlm_structured_page.py packages/jw-rag/tests/test_ingest_image.py

# 3. Demo end-to-end con fake
uv run python -c "
from jw_core.vision.vlm import extract_bible_reference_from_image_v2
out = extract_bible_reference_from_image_v2('packages/jw-core/tests/fixtures/vlm/bible_john_3_es.png', language='es')
print(out['reference'])
"

# 4. Live (opt-in, requiere API key o hardware)
JW_VLM_PROVIDER=claude_vision uv run pytest -m vlm_real
```

## Pendientes explícitos (post-Fase 36)

- Fase 37 (`colpali-visual`) usa rasterización multi-página y recuperación visual sobre páginas enteras — extiende lo que aquí se acota a una imagen.
- Fine-tuning de Qwen3-VL sobre páginas JW es territorio `jw-finetune` (Fase 11).
- Eventual web UI para revisar manualmente bloques de baja confianza queda fuera de scope.

## Plan de implementación

Spec hijo plan: [`docs/superpowers/plans/2026-05-31-fase-36-vlm-ocr-plan.md`](../plans/2026-05-31-fase-36-vlm-ocr-plan.md) — 16 tareas TDD.

## Self-review

- ✅ Triple-target respetado: api / mlx / nvidia / cpu, cada uno con su provider.
- ✅ Naming: ClaudeVisionProvider es adapter sobre `anthropic` SDK, no modelo nuevo.
- ✅ No red en tests (FakeVLMProvider + lazy imports).
- ✅ en/es/pt soportados vía `language` arg + prompt explicit.
- ✅ Tesseract no se rompe — sólo se deprecia con migrate path.
- ✅ Ingesta directa al RAG con metadata por bloque.
- ✅ Boundaries claros vs Fase 37 (colpali multi-page) y Fase 11 (`jw-finetune`).

## Decisión de ejecución

Ejecutar plan en orden TDD task-by-task. Cada task = test rojo → impl → test verde → commit. PRs atómicos por task (o agrupados en sub-PRs de 3-4 tareas afines cuando convenga) hacia `feature/fase-36-vlm-ocr`.
