---
title: "Talk-lab (Fase 68)"
description: "Coach de oratoria multimodal local-first: WhisperX + prosodia + 6 counsel points + SVG timeline + F31 PDF export. El audio nunca sale del disco."
date: "2026-06-11"
---

# Talk-lab (Fase 68)

> Coach de oratoria multimodal sobre tus propias grabaciones. Analiza
> audio local con WhisperX (F64) + prosodia (librosa opt + numpy
> fallback) + 6 counsel points pedagógicos. **Local-first, sin
> telemetría, audio nunca sale del disco**.

## Quick start

```bash
# Analizar una grabación
jw talklab analyze recording.wav --kind bible_reading --language es

# Tracking longitudinal (opt-in, SQLite local)
jw talklab analyze recording.wav --track-history
jw talklab history

# Exportar reporte Markdown
jw talklab analyze recording.wav --export report.md

# LLM judge para counsel point de auditorio
jw talklab analyze recording.wav --llm-judge

# Comparar dos reportes trackeados
jw talklab compare <report_id_a> <report_id_b>

# Listar counsel points por kind
jw talklab counsel-points -l es -k bible_reading
```

## CLI

| Comando                         | Descripción                              |
|---------------------------------|------------------------------------------|
| `jw talklab analyze`            | Analiza grabación, imprime JSON          |
| `jw talklab history`            | Lista historia local                     |
| `jw talklab compare A B`        | Deltas de scores entre dos reports       |
| `jw talklab counsel-points`     | Lista counsel points por kind            |

### Flags principales de `analyze`

| Flag               | Default        | Efecto                                       |
|--------------------|----------------|----------------------------------------------|
| `--kind` / `-k`    | `bible_reading`| `initial_call`/`return_visit`/`bible_study`/`public_talk`/`watchtower_comment`/`other` |
| `--language` / `-l`| `es`           | `en` / `es` / `pt`                           |
| `--llm-judge`      | `false`        | Activa LLM para counsel points de auditorio  |
| `--track-history`  | `false`        | Persiste scores en `~/.jw-agent-toolkit/talklab/history.sqlite` |
| `--export`         | —              | Markdown report path                         |

## MCP

| Tool                            | Descripción                              |
|---------------------------------|------------------------------------------|
| `talklab_analyze`               | Analyze recording                        |
| `talklab_list_counsel_points`   | List counsel points by kind              |
| `talklab_compare`               | Compare two tracked reports              |

## Arquitectura

```
   recording.wav (16-bit PCM)
            │
            ▼
   ┌───────────────────────────┐
   │ audio_loader              │
   │  - wave + numpy           │
   │  - resample 16kHz (scipy │
   │    opt → numpy fallback)  │
   │  - normalize [-1, 1]      │
   └─────────────┬─────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
   ┌──────────┐    ┌──────────────────────┐
   │ WhisperX │    │ prosody              │
   │ (opt F64)│    │  - rms windows       │
   │ transcript│   │  - pause detection   │
   │ + words  │    │  - pitch (librosa    │
   │ + speakers│   │    opt → ZCR fallback)│
   └────┬─────┘    └──────────┬───────────┘
        │                     │
        └────────┬────────────┘
                 ▼
   ┌─────────────────────────────────┐
   │ 6 scorers (catalog TOML driven) │
   │  cp-01 pronunciation (prosodic) │
   │  cp-02 speech_rate   (prosodic) │
   │  cp-03 pause_use     (prosodic) │
   │  cp-04 filler_use    (prosodic) │
   │  cp-05 scripture_use (linguistic)│
   │  cp-06 audience_warmth (LLM opt)│
   └────────────────┬────────────────┘
                    ▼
   ┌─────────────────────────────────┐
   │ report builder                  │
   │  - pick top-3 / focus-3         │
   │  - TalkLabReport Pydantic       │
   └─────────────────────────────────┘
```

## Counsel points (MVP — 6 puntos)

El catálogo vive en `packages/jw-core/src/jw_core/talk_lab/counsel_points/`
como `catalog_{en,es,pt}.toml` + `applies_by_kind.toml`. Roadmap: expandir
a los ~50 puntos del folleto "Benefíciate de la Escuela del Ministerio".

| ID    | Título               | Categoría  | Scorer                  |
|-------|----------------------|------------|-------------------------|
| cp-01 | Pronunciación clara  | prosodic   | `score_pronunciation`   |
| cp-02 | Velocidad del habla  | prosodic   | `score_speech_rate`     |
| cp-03 | Uso de pausas        | prosodic   | `score_pause_use`       |
| cp-04 | Muletillas           | prosodic   | `score_filler_use`      |
| cp-05 | Uso de Escritura     | linguistic | `score_scripture_use`   |
| cp-06 | Calidez al auditorio | audience   | `score_audience_warmth` |

### Escalas de scoring (0-3)

- **cp-01 Pronunciation**: avg word confidence ≥0.85 → 3; ≥0.70 → 2;
  ≥0.55 → 1; menor → 0. Si no hay transcripción word-level, score=0.
- **cp-02 Speech Rate**: 120-150 wpm → 3; 100-119 o 151-175 → 2;
  80-99 o 176-200 → 1; resto → 0.
- **cp-03 Pause Use**: ratio pause_total/duration en 0.15-0.25 → 3;
  0.08-0.15 o 0.25-0.35 → 2; 0.03-0.08 o 0.35-0.45 → 1; resto → 0.
- **cp-04 Filler Words**: <2/min → 3; <4/min → 2; <6/min → 1; ≥6 → 0.
- **cp-05 Scripture Use**: ≥3 refs → 3; 2 → 2; 1 → 1; 0 → 0.
- **cp-06 Audience Warmth**: con LLM, score 0-3 directo. Sin LLM,
  contador de warmth markers per idioma.

## Privacidad

- El audio **nunca** sale del disco.
- El historial es local (SQLite), opt-in con `--track-history`.
- Cifrado opt-in con `JW_TALKLAB_KEY` (Fernet, patrón F61, pendiente).
- `--llm-judge` envía solo la transcripción al LLM (no el audio); usa la
  factory de F65 `build_llm_from_env()` con sus mismas reglas.

## Dependencias opcionales

| Feature              | Dep                 | Fallback sin dep                       |
|----------------------|---------------------|----------------------------------------|
| Resample audio       | `scipy>=1.11`       | numpy linear interpolation             |
| Pitch tracking       | `librosa>=0.10`     | Zero-crossing rate (coarse)            |
| Transcripción ASR    | `whisperx` (F64)    | Transcript vacío, scoring solo prosódico |
| LLM audience judge   | `JW_META_LLM=…`     | Heurístico por warmth markers          |

Todo es import-guarded. Los tests pasan sin ninguna dep opcional.

## Estado actual

- 61 tests passing (models, audio loader, prosody, filler, catalog,
  scorers prosódicos, scorers linguistic, scorers audience LLM,
  report, history, engine E2E, CLI, MCP).
- CLI `jw talklab {analyze,history,compare,counsel-points}`.
- MCP: 3 tools nuevas.
- Catálogo TOML completo en es/en/pt.

## Pendiente (futuro)

- Expansión del catálogo 6 → ~50 counsel points.
- ASCII timeline / SVG export en `report.py`.
- F31 PDF export wrapper para TalkLabReport.
- Cifrado Fernet de history.sqlite.
- Integración F65: tool `talklab.analyze` en el meta-orchestrator.
- Cloud STT provider opcional vía Plugin SDK F41.
