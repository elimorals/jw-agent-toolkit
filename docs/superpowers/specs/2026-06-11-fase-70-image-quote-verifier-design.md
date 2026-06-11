# Fase 70 — `image-quote-verifier`: defensa visual contra citas falsas

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (multimodal)
> **Capa**: B — Multimodal
> **Depende de**: F7 `multimodalidad-visual` (OCR), F9 `apocrypha_detector`, F36 `vlm-ocr`, F39 `nli-runtime`, RAG híbrido, F48 `wol-browser-ext` (deep link)
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F9 `apocrypha_detector` (solo texto pegado, sin imagen)

## Motivación

En redes sociales circulan capturas de pantalla y memes con
"supuestas citas de Testigos de Jehová" en 3 categorías:

- **Reales**: cita textual fiel, con o sin contexto correcto.
- **Distorsionadas**: cita real pero recortada / contexto alterado /
  títulos cambiados para parecer otra cosa.
- **Fabricadas**: inventadas con apariencia visual de publicación
  oficial (font, colors, layout) pero no existen.

`apocrypha_detector` (F9) cubre la versión texto-puro. Falta la
versión que parte de **una imagen** (screenshot, foto, meme).

## Objetivos

1. CLI `jw verify-image meme.jpg` produce `ImageQuoteVerdict`.
2. OCR + VLM analyzing layout para detectar "esto parece una
   publicación JW de los 80s" → hint para narrow search.
3. RAG sobre corpus oficial + NLI F39 entrega veredicto:
   `SUPPORTED` / `DISTORTED` / `FABRICATED` / `UNVERIFIABLE`.
4. Si `SUPPORTED`, devolver cita exacta con `wol_url` para comparación.
5. Si `DISTORTED`, mostrar diff entre cita en imagen y cita oficial.
6. Si `FABRICATED`, listar pistas (anachronismos visuales, vocabulario
   no canónico, etc.).
7. Integración con extensión navegador F48 (right-click "verificar
   esta imagen").

## No-objetivos (boundaries vinculantes)

- **No** es apologética ofensiva contra ex-TJ. Es verificación neutra:
  decir "esto es real / esto es alterado / esto no existe" basado
  en evidencia.
- **No** sustituye juicio humano. El veredicto siempre incluye
  `confidence` y la cita original; el usuario decide presentación.
- **No** se usa para denunciar a personas. El output es sobre el
  meme/imagen, no sobre quien lo publicó.
- **No** indexa redes sociales. El usuario provee la imagen.

## Decisión clave: ¿OCR puro vs OCR + VLM análisis de layout?

### Opción A — Solo OCR (Tesseract / EasyOCR)

**Pros**: simple, rápido, cero modelos pesados.
**Contras**: pierde signal visual ("este meme aparenta ser Atalaya
1985 con font moderno" — anachronismo invisible al texto).

### Opción B — OCR + VLM análisis de layout y elementos visuales

**Pros**: detecta anachronismos visuales, layout inconsistente,
fonts wrong, logos modificados.
**Contras**: requiere VLM (mismo que F69).

### Decisión: **Opción B** (híbrido OCR + VLM)

Justificación:
1. F69 ya integra VLM via Plugin SDK F41 — reuso directo.
2. La capa visual detecta `FABRICATED` cases que OCR puro no puede.
3. VLM es opcional vía Plugin SDK F41 — sin él degrada a OCR puro
   con bandera de aviso.

## Arquitectura

```
                  meme.jpg / screenshot.png
                          │
                          ▼
              ┌────────────────────────┐
              │ 1. Image preprocess    │
              │    PIL load + EXIF rot │
              └───────────┬────────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       ┌────────┐   ┌──────────┐   ┌────────────┐
       │ 2a. OCR│   │ 2b. VLM  │   │ 2c. Image  │
       │ Tesser │   │ describe │   │ hash       │
       │ + clean│   │ layout   │   │ pHash      │
       └───┬────┘   └────┬─────┘   └─────┬──────┘
           │             │               │
           └─────────────┴───────────────┘
                        │
                        ▼
            ┌──────────────────────────┐
            │ 3. Quote extraction      │
            │    + visual fingerprint  │
            │    (era, format, logos)  │
            └────────────┬─────────────┘
                         │
                         ▼
            ┌──────────────────────────┐
            │ 4. RAG search            │
            │    BM25 + vector + RRF   │
            │    sobre corpus oficial  │
            └────────────┬─────────────┘
                         │
                         ▼
            ┌──────────────────────────┐
            │ 5. NLI F39 verify        │
            │    claim=quote_ocr       │
            │    premise=rag_top1      │
            └────────────┬─────────────┘
                         │
                         ▼
            ┌──────────────────────────┐
            │ 6. Verdict synthesis     │
            │    SUPPORTED / DISTORTED │
            │    FABRICATED / UNVERIF  │
            └──────────────────────────┘
```

## Contratos de tipos

```python
# packages/jw-core/src/jw_core/verification/image_quote/models.py

from pydantic import BaseModel, Field
from typing import Literal

Verdict = Literal["SUPPORTED", "DISTORTED", "FABRICATED", "UNVERIFIABLE"]

class VisualFingerprint(BaseModel):
    apparent_era: str | None = None        # "1980s", "2020s", etc.
    apparent_publication: str | None = None  # "Atalaya", "Despertad"
    layout_consistency: Literal["consistent", "inconsistent", "unknown"]
    visual_anomalies: list[str] = []        # ["wrong font", "logo modified"]
    image_phash: str
    image_format: str
    image_size: tuple[int, int]

class ExtractedQuote(BaseModel):
    raw_ocr_text: str
    cleaned_quote: str                      # cleanup post-OCR
    language_detected: Literal["en", "es", "pt", "fr", "de", "unknown"]
    has_attribution: bool                   # menciona pub específica?
    attribution_text: str = ""              # "Atalaya, abril 2024"

class MatchEvidence(BaseModel):
    source_url: str                         # wol.jw.org
    source_pub_code: str                    # "w24.04"
    source_text_original: str               # texto oficial
    nli_verdict: Literal["entails", "neutral", "contradicts"]
    nli_score: float
    diff_with_quote: str = ""               # markdown diff

class ImageQuoteVerdict(BaseModel):
    image_path: str
    verdict: Verdict
    confidence: float                       # 0..1
    extracted_quote: ExtractedQuote
    visual_fingerprint: VisualFingerprint
    matches: list[MatchEvidence] = []
    reasoning: str                          # 2-3 párrafos
    suggested_action: Literal[
        "share_with_correct_link",
        "share_corrected_version",
        "do_not_share",
        "discuss_with_elders",
    ]
```

## API pública

```python
# packages/jw-core/src/jw_core/verification/image_quote/__init__.py

from jw_core.verification.image_quote.engine import verify_image_quote
from jw_core.verification.image_quote.models import (
    ImageQuoteVerdict,
    Verdict,
    ExtractedQuote,
    VisualFingerprint,
    MatchEvidence,
)

__all__ = [
    "verify_image_quote",
    "ImageQuoteVerdict",
    "Verdict",
    "ExtractedQuote",
    "VisualFingerprint",
    "MatchEvidence",
]
```

## CLI

```bash
# Verificar imagen
jw verify-image /path/to/meme.jpg

# Con resumen breve
jw verify-image meme.jpg --brief

# Exportar reporte
jw verify-image meme.jpg --export report.md

# Modo batch (carpeta)
jw verify-image ./suspicious/*.jpg
```

## MCP tools

- `verify_image_quote(image_path, language="es") → ImageQuoteVerdict`
- `verify_image_quote_batch(paths, language="es") → list[ImageQuoteVerdict]`

## Wire-up extensión navegador (F48)

Right-click sobre cualquier imagen en wol.jw.org o redes sociales →
"Verificar esta imagen con jw-agent-toolkit":

```javascript
// apps/wol-browser-extension/src/content_script.ts
chrome.contextMenus.create({
  id: "verify-image",
  title: "Verificar esta imagen (jw-agent-toolkit)",
  contexts: ["image"],
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId === "verify-image" && info.srcUrl) {
    // POST a localhost:8765 endpoint nuevo
    const verdict = await fetch("http://localhost:8765/api/v1/verify_image", {
      method: "POST",
      body: JSON.stringify({image_url: info.srcUrl}),
    }).then(r => r.json());
    showVerdictOverlay(verdict);
  }
});
```

Endpoint REST nuevo en F10 infra REST API.

## Heurísticas para visual fingerprint

`packages/jw-core/src/jw_core/verification/image_quote/fingerprint.py`:

```python
def detect_apparent_era(vlm_description: str, ocr_text: str) -> str | None:
    """Detecta época aparente por elementos visuales."""
    # Logos, fonts, datos de copyright en footer
    # 1970s: serif heavy, fluffy clouds
    # 1980s: bold sans, primary colors
    # 1990s: pixelated logos
    # 2000s+: modern clean
    ...

def detect_visual_anomalies(vlm_description: str, ocr_text: str) -> list[str]:
    anomalies = []
    # font mismatch entre titular y body
    # logo no oficial (wrong proportions)
    # texto en color no canónico
    # gaps en layout sugieren composición artificial
    return anomalies
```

LLM helper para análisis: dado el caption VLM + OCR text, qué pistas
visuales hay de manipulación.

## Verdict synthesis

```python
def synthesize_verdict(
    quote: ExtractedQuote,
    matches: list[MatchEvidence],
    fingerprint: VisualFingerprint,
) -> tuple[Verdict, float, str]:
    if not matches:
        # No RAG hits + fingerprint anomalies → likely fabricated
        if fingerprint.visual_anomalies:
            return ("FABRICATED", 0.7, "No hay coincidencias en el corpus oficial...")
        return ("UNVERIFIABLE", 0.4, "No se encontró fuente en el corpus indexado...")

    top_match = matches[0]
    if top_match.nli_verdict == "entails" and top_match.nli_score > 0.85:
        if fingerprint.visual_anomalies:
            return ("DISTORTED", 0.8, "Texto coincide pero presentación visual altera...")
        return ("SUPPORTED", min(top_match.nli_score, 0.95), "Cita real, fuente: ...")

    if top_match.nli_verdict == "contradicts":
        return ("DISTORTED", 0.85, "Cita textualmente distinta a la fuente más cercana...")

    return ("UNVERIFIABLE", 0.3, "Coincidencia débil, no se puede determinar...")
```

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `VisualFingerprint` Pydantic round-trip                       | Unit        |
| Preprocess respeta EXIF rotation                              | Unit        |
| OCR cleanup quita ruidos comunes (artifacts, line breaks)     | Unit        |
| Image phash es estable a re-encoding JPEG                     | Unit        |
| Era detector: 1980s caption → "1980s"                         | Unit        |
| Anomaly detector: font mismatch flagged                       | Unit        |
| Verdict synth: NLI=entails + no anomalies → SUPPORTED         | Unit        |
| Verdict synth: NLI=entails + anomalies → DISTORTED            | Unit        |
| Verdict synth: no matches + anomalies → FABRICATED            | Unit        |
| Verdict synth: no matches + clean → UNVERIFIABLE              | Unit        |
| MCP `verify_image_quote` serializa bien                       | Integration |
| Extension F48 endpoint REST devuelve `ImageQuoteVerdict`      | Integration |
| Golden 50 imágenes (25 reales, 15 distorted, 10 fabricated)   | E2E         |

## Golden dataset

`tests/verification/image_quote/fixtures/golden/`:
- 25 imágenes con citas reales (Atalaya, Despertad, libros) anotadas con `wol_url`.
- 15 imágenes con citas distorsionadas (recortes, paráfrasis, contexto cambiado).
- 10 imágenes fabricadas (memes inventados con apariencia oficial).

Cada una con `expected_verdict.json`.

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| Falso positivo "FABRICATED" sobre cita real             | Confidence threshold; requiere visual anomaly clara |
| Falso negativo (cita falsa pasa como real)              | RAG sobre corpus actualizado; fallback UNVERIFIABLE |
| Imagen es legítima de ex-TJ con cita histórica vieja    | Indexar corpus histórico F62; mismo NLI            |
| OCR pierde texto por baja resolución                    | Warning explícito; downgrade a UNVERIFIABLE         |
| VLM provider no disponible                              | Degrada a OCR-only con bandera                      |
| Imagen contiene PII (caras, nombres)                    | No persist en disco salvo `--save-evidence` opt-in  |

## Métricas de éxito

- **Precisión**: ≥90% sobre golden de 50 imágenes en `SUPPORTED`
  y `FABRICATED` (las dos categorías extremas).
- **Recall sobre `DISTORTED`**: ≥75% (caso más difícil).
- **Tiempo**: <15s por imagen en MacBook M1 (sin VLM cloud).

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/verify_image.py`.
- MCP: 2 tools nuevas.
- F48 extension: context menu "verify image" + endpoint REST nuevo.
- F10 REST API: `POST /api/v1/verify_image` (binary upload o url).
- F65 meta-orchestrator: tool `verification.image_quote` registrada.

## Guía resultante

`docs/guias/image-quote-verifier.md` — quick start, los 4 veredictos,
flujo extension, ejemplos golden.
