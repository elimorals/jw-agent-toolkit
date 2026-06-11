---
title: "Cámara para libros físicos (Fase 71)"
description: "Apunta a un libro físico y el toolkit OCR'iza, clasifica y sugiere acciones (read_aloud, open_in_jw_library, open_in_wol, show_answer). REST endpoints opt-in."
date: "2026-06-11"
---

# Cámara para libros físicos (Fase 71)

> Apunta la cámara a un libro físico, una página de Atalaya o una
> Biblia, y el toolkit clasifica lo que ve y sugiere acciones
> contextuales: leer en voz alta, abrir en JW Library, abrir en WOL,
> o mostrar respuesta. Pensado para hermanos mayores, recién
> interesados sin app, o niños aprendiendo a leer.

## Quick start

```bash
# Analizar con texto OCR ya extraído
jw book-camera analyze --ocr-text "Juan 3:16" --language es

# Analizar con imagen (requiere Tesseract)
jw book-camera analyze --image /tmp/page.jpg

# Listar tipos detectables
jw book-camera kinds
```

## CLI

| Comando                  | Descripción                              |
|--------------------------|------------------------------------------|
| `jw book-camera analyze` | Analiza una captura (imagen u OCR-text)  |
| `jw book-camera kinds`   | Lista los 5 tipos detectables            |

### Flags de `analyze`

| Flag                | Default | Efecto                                       |
|---------------------|---------|----------------------------------------------|
| `--image` / `-i`    | —       | Path a imagen capturada (se OCRea)           |
| `--ocr-text` / `-t` | —       | Bypass OCR: texto ya extraído                |
| `--language` / `-l` | `es`    | Idioma de OCR + TTS hint                     |

Al menos uno de `--image` o `--ocr-text` es obligatorio.

## MCP

| Tool                  | Descripción                              |
|-----------------------|------------------------------------------|
| `book_camera_analyze` | Devuelve `CameraFrameResult` dict        |

## Tipos detectables

| Kind                    | Descripción                                |
|-------------------------|--------------------------------------------|
| `bible_verse`           | Cita bíblica detectada por F1 parser       |
| `study_question`        | Pregunta de estudio (¿…? + hints)          |
| `watchtower_paragraph`  | Código de publicación + párrafo opcional   |
| `plain_text`            | Texto sin clasificar pero legible          |
| `unknown`               | Vacío / solo ruido                         |

## Acciones sugeridas

El router emite una lista ordenada de acciones por kind:

```
bible_verse        -> read_aloud, open_in_jw_library, open_in_wol
study_question     -> show_answer, read_aloud
watchtower_paragraph -> read_aloud, open_in_jw_library
plain_text         -> read_aloud
unknown            -> []
```

Los deep links son `jwlibrary://bible/{book:02d}/{ch:03d}/{verse:03d}`
para versículos y `jwlibrary://publication/{pub_code}` para revistas.

## Arquitectura

```
   captura
       │
       ▼
 ┌──────────────────────┐
 │ F70 preprocess + OCR │ (opt; bypass con --ocr-text)
 │  - PIL load          │
 │  - Tesseract + cleanup│
 └──────────┬───────────┘
            │ ocr_text
            ▼
 ┌──────────────────────┐
 │ classifier           │
 │  - parse_all_references (F1)
 │  - pub_code regex    │
 │  - question hints    │
 │  - plain/unknown     │
 └──────────┬───────────┘
            │ DetectedContent
            ▼
 ┌──────────────────────┐
 │ router               │
 │  - read_aloud        │
 │  - open_in_jw_library│
 │  - open_in_wol       │
 │  - show_answer       │
 └──────────┬───────────┘
            │ list[SuggestedAction]
            ▼
       CameraFrameResult
```

## Integración en F65 meta-orchestrator

Registrada como tool `book_camera.analyze`. El planner F65 puede
componer:

```json
{"steps": [
  {"id": "s1", "tool": "book_camera.analyze",
   "args": {"ocr_text": "Juan 3:16", "language": "es"}}
]}
```

## Dependencias opcionales

| Feature   | Dep            | Fallback                       |
|-----------|----------------|--------------------------------|
| OCR       | `pytesseract`  | `--ocr-text` manual            |
| Image     | `Pillow`       | requerido si `--image`         |

## Estado actual

- 5 tasks TDD. **30 tests passing** (4 models + 10 classifier + 9
  router/engine + 3 CLI + 1 MCP + 2 meta + 1 protocol delta).
- Pipeline async-friendly (síncrono internamente).
- 5 kinds + 4 actions discretas con Pydantic discriminated unions.
- CLI `jw book-camera {analyze,kinds}` + MCP tool.
- Meta tool `book_camera.analyze` en F65.

## Pendiente (futuro)

- App PWA / Capacitor en `apps/book-camera/` reutilizando F47
  jw-core-js (`parseReference` + `wolUrl` en TS).
- REST endpoints `POST /api/v1/book_camera/analyze` + `/tts` + `/rag_answer`
  para que la PWA hable con el backend MCP.
- VLM real-time on-device (Florence-2 base ONNX) para classify_content
  sobre frames live (no solo OCR).
- Lighthouse a11y ≥95 + botones ≥56dp.
- Wake word "Hermano IA" para uso manos libres.
- Streaming TTS con highlight word-by-word.
