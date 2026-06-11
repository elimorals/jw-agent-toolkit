# Fase 71 — `book-camera`: cámara en vivo para libros físicos

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (multimodal + accesibilidad)
> **Capa**: B — Multimodal
> **Depende de**: F7 OCR (Tesseract), F36 `vlm-ocr`, F1 parser referencias, F34 `audio-premium` (TTS), F47 `jw-core-js` (Capacitor móvil), F39 NLI
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: OCR de F7 + extension WOL F48 (ambos web/desktop, no cámara móvil)

## Motivación

Tres perfiles de usuario quedan fuera del flujo actual:

1. **Publicador mayor** que estudia con sus libros físicos de los 90s
   y no quiere/sabe usar la app digital.
2. **Recién interesado** que recibió un libro impreso pero no tiene
   JW Library instalada.
3. **Niño aprendiendo a leer** que quiere oír la página actual de
   "Aprende del Gran Maestro" en voz alta.

Ninguno tiene relación previa con el toolkit, y todos tienen un libro
físico abierto.

## Objetivos

1. PWA / app móvil simple: abre cámara → apunta al libro → reconoce
   página/texto/citas en tiempo real → ofrece acciones.
2. **Acciones contextuales** según contenido detectado:
   - Texto plano → "Leer en voz alta" (TTS F34).
   - Cita bíblica detectada → "Abrir en WOL" / "Ver notas estudio".
   - Pregunta de estudio → "Mostrar respuesta sugerida" (RAG).
   - Párrafo de Atalaya → "Resumen del párrafo".
3. **Offline-first**: VLM + OCR locales (Florence-2 small + Tesseract
   on-device).
4. **Accesibilidad alta**: botones grandes, contraste alto, font
   ajustable, voz lenta opt-in.
5. **Sin login**: zero friction, abrir y usar.

## No-objetivos (boundaries vinculantes)

- **No** indexa el contenido fotografiado. Cada uso es ephemeral —
  procesado in-memory, descartado.
- **No** sube imagen a cloud sin consentimiento explícito.
- **No** reemplaza JW Library. Es complemento para libros físicos.
- **No** soporta video continuo (battery drain) — captura en demanda
  o snapshot cada 2-3s.
- **No** vende suscripción. Free + open source.

## Decisión clave: ¿PWA vs app nativa?

### Opción A — App nativa (Capacitor iOS+Android)

**Pros**: Acceso completo a cámara, mejor performance, push notifs.
**Contras**: store submission, cycles de approval, 2 codebases.

### Opción B — PWA progresiva

**Pros**: Single codebase TS, instalable como app via `manifest.json`,
acceso a cámara via getUserMedia, offline via Service Worker.
**Contras**: Limitaciones de cámara nativa (sin focus manual fino).

### Opción C — Capacitor wrap de PWA

Lo mejor de ambos: PWA es source-of-truth, Capacitor empaqueta para
stores cuando sea necesario. Es lo que F47 jw-core-js ya prepara.

### Decisión: **Opción C** (Capacitor wrap de PWA)

Justificación:
1. F47 jw-core-js ya tiene el setup Capacitor.
2. Reduce mantenimiento.
3. Cero login = puede vivir como PWA web pura para usuarios sin
   instalación.

## Arquitectura

```
                      📷 cámara
                          │
                          ▼
             ┌──────────────────────────┐
             │ 1. Capture (PWA)         │
             │    Capacitor Camera API  │
             │    → JPEG in-memory      │
             └─────────────┬────────────┘
                           │
                           ▼
             ┌──────────────────────────┐
             │ 2. On-device pipeline    │
             │    - Tesseract OCR       │
             │    - parser refs         │
             │    - VLM caption opt     │
             └─────────────┬────────────┘
                           │
                           ▼
             ┌──────────────────────────┐
             │ 3. Action router         │
             │   if cita bíblica:       │
             │     → WOL deep link      │
             │   if texto plano:        │
             │     → TTS                │
             │   if pregunta:           │
             │     → RAG sobre answer   │
             └─────────────┬────────────┘
                           │
                           ▼
             ┌──────────────────────────┐
             │ 4. UI acciones grandes   │
             │    - Leer (TTS)          │
             │    - Abrir en JW Library │
             │    - Mostrar respuesta   │
             └──────────────────────────┘
```

## Contratos de tipos

```typescript
// packages/jw-core-js/src/book_camera/types.ts

export type DetectedContent =
  | { kind: "bible_verse"; ref: BibleRef; wol_url: string }
  | { kind: "study_question"; text: string; suggested_answers: string[] }
  | { kind: "watchtower_paragraph"; pub_code: string; paragraph_id: number; summary: string }
  | { kind: "plain_text"; text: string }
  | { kind: "unknown"; text: string };

export interface CameraFrameResult {
  capturedAt: string;
  ocrText: string;
  ocrConfidence: number;
  detected: DetectedContent;
  suggestedActions: SuggestedAction[];
}

export type SuggestedAction =
  | { kind: "read_aloud"; languageTtsHint: string }
  | { kind: "open_in_jw_library"; deepLink: string }
  | { kind: "open_in_wol"; url: string }
  | { kind: "show_answer"; chunks: AnswerChunk[] }
  | { kind: "copy_to_clipboard"; text: string };

export interface AnswerChunk {
  text: string;
  citation_url: string;
  source_kind: string;
}
```

## Stack tecnológico

| Layer            | Tech                                             |
|------------------|--------------------------------------------------|
| Camera           | Capacitor Camera plugin / getUserMedia (web)     |
| OCR              | Tesseract.js (WASM, ~3MB, on-device)             |
| VLM (opt)        | ONNX runtime + Florence-2-base.onnx (~250MB)     |
| Reference parser | `@jw-agent-toolkit/core` F47 (`parseReference`)  |
| RAG              | Backend MCP `localhost:8765` cuando disponible   |
| TTS              | Web Speech API + fallback a F34 backend          |
| Routing          | Astro + React for PWA shell                      |
| Capacitor        | iOS + Android shell ya configurado en F47        |

## Endpoints REST nuevos

El backend MCP F10 expone (para uso desde PWA):

- `POST /api/v1/book_camera/analyze`
  body: `{image_b64: string, language: "es"|"en"|"pt"}`
  response: `CameraFrameResult`
- `POST /api/v1/book_camera/tts`
  body: `{text: string, language: string, voice_hint?: string}`
  response: `{audio_b64: string, mime: "audio/wav"}`
- `POST /api/v1/book_camera/rag_answer`
  body: `{question: string, language: string, top_k: number}`
  response: `{chunks: AnswerChunk[]}`

Si la PWA no puede llegar al backend (sin red, sin install), degrada
a OCR puro + Web Speech TTS sin RAG.

## UI / UX principios

```
   ┌────────────────────────────────────┐
   │ ┌─────────────────────────────────┐│
   │ │                                  ││
   │ │       📷 PREVIEW CÁMARA          ││
   │ │                                  ││
   │ │       (apuntar al libro)         ││
   │ │                                  ││
   │ └─────────────────────────────────┘│
   │                                    │
   │  Detectado: Juan 3:16              │ ← banner contextual
   │                                    │
   │  ┌──────────────┐  ┌─────────────┐ │
   │  │ 🔊 LEER       │  │ 📖 ABRIR    │ │ ← botones GRANDES
   │  │   EN VOZ ALTA │  │   EN JW LIB │ │
   │  └──────────────┘  └─────────────┘ │
   │                                    │
   │  ┌──────────────────────────────┐  │
   │  │ 🌐 VER EN WOL.JW.ORG          │  │
   │  └──────────────────────────────┘  │
   │                                    │
   └────────────────────────────────────┘
```

Principios:
- Botones de ≥56dp altura.
- Contraste ≥7:1.
- Font system default, escalable hasta 200%.
- Tap target ≥48×48dp.
- Animaciones suaves, opt-out via `prefers-reduced-motion`.
- Sin teclado: input por voz opcional via Web Speech.

## Detección de "qué tipo de contenido es"

Heurísticas + clasificador ligero:

```typescript
function classifyContent(ocrText: string, vlmDescription?: string): DetectedContent {
  // 1. Bible reference detected?
  const refs = parseAllReferences(ocrText);
  if (refs.length > 0) {
    return {
      kind: "bible_verse",
      ref: refs[0],
      wol_url: wolUrl(refs[0]),
    };
  }

  // 2. Study question pattern?
  if (/^[¿?].+[?]/.test(ocrText.trim()) || ocrText.includes("párrafo")) {
    return {
      kind: "study_question",
      text: ocrText,
      suggested_answers: [],   // populated by backend RAG call
    };
  }

  // 3. Watchtower paragraph pattern?
  // Detección por footer "w24.04 página 5 párr. 12" o similar
  const pubMatch = ocrText.match(/(w|g)\d{2}[.\-]\d{2}.*p[áa]rr[.\s]?\s*(\d+)/i);
  if (pubMatch) {
    return {
      kind: "watchtower_paragraph",
      pub_code: pubMatch[1] + pubMatch[2],
      paragraph_id: parseInt(pubMatch[2]),
      summary: "",  // populated by RAG
    };
  }

  // 4. Default
  return {kind: "plain_text", text: ocrText};
}
```

## TTS flow

1. Detect content → "Leer" tap.
2. Si online + backend disponible → `POST /tts` con voice F34 premium.
3. Si offline → Web Speech API native.
4. Streaming audio playback (no blocking).
5. Highlight current word (sync con timestamps si backend).

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `DetectedContent` type narrowing TypeScript                   | Unit        |
| Tesseract OCR sobre fixture JPEG produce texto                | Integration |
| `classifyContent` ranks bible ref highest                     | Unit        |
| `classifyContent` detecta pregunta de estudio                 | Unit        |
| `classifyContent` detecta pub code w24.04                     | Unit        |
| OCR confidence threshold filtra basura                        | Unit        |
| Backend `/analyze` endpoint round-trip                        | Integration |
| Backend `/tts` produce audio playable                         | Integration |
| Backend `/rag_answer` devuelve chunks con citation_url        | Integration |
| Offline degradation: sin backend, OCR puro + Web Speech       | E2E         |
| PWA install manifest válido                                   | Manual      |
| Accesibilidad: lighthouse score ≥95                           | Audit       |
| Capacitor build iOS + Android sin errores                     | E2E (slow)  |

## Fixtures golden

`tests/book_camera/fixtures/`:
- `bible_open_juan3.jpg` — libro Biblia abierto en Juan 3
- `awake_g23_open.jpg` — Despertad página 5
- `kids_book_lesson.jpg` — Aprende del Gran Maestro lección
- `low_light_blurry.jpg` — caso difícil
- `partial_visible.jpg` — texto parcial

Cada uno con `expected_detection.json`.

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| Cámara mala / poca luz                                  | Auto-enhance + retry; mensaje claro de mejora       |
| Idioma del libro distinto al UI                         | Auto-detect language + ofrecer switch               |
| OCR falla sobre texto curvado / pagina arrugada         | Reintento + tip "aplanar libro"                     |
| Privacy: cámara siempre activa                          | Solo capture on-tap; preview ≠ capture              |
| PWA install confuso                                     | UI siempre funcional sin install                    |
| TTS calidad pobre en Web Speech                         | Opt-in backend premium                              |
| Niño usa solo sin supervisión                           | Sin login; pero backend puede tener parental gate   |
| Battery drain                                           | Power profile; capture solo on-tap                  |

## Métricas de éxito

- **Accuracy reconocimiento**: ≥85% sobre golden de 20 fotos.
- **Tiempo a primera acción**: <3s desde tap a banner contextual
  (en M1 / iPhone 13).
- **Lighthouse**: ≥95 accesibilidad.
- **Adopción**: ≥1000 instalaciones PWA en primer trimestre post-launch.

## Wire-up

- App PWA: `apps/book-camera/` nuevo subdir bajo `apps/`.
- Backend REST: `packages/jw-mcp/src/jw_mcp/rest/book_camera.py` con
  3 endpoints.
- Capacitor: reusa setup de F47 jw-core-js.
- jw-core-js: añade módulo `book_camera/` para clasificación.

## Guía resultante

`docs/guias/book-camera.md` — install PWA, setup backend (opcional),
casos de uso, accesibilidad.
