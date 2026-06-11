# Fase 68 — `talk-lab`: coach de oratoria multimodal

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (multimodal)
> **Capa**: B — Multimodal
> **Depende de**: F64 `asr-diarizacion` (WhisperX), F26 `partes-del-estudiante` (50 counsel points), F39 `nli-runtime`, F31 `exportador` (PDF report), F34 `audio-premium` (loader audio común)
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F26 `student_part_helper` (enumera los 50 puntos, no evalúa el discurso)

## Motivación

El folleto "Benefíciate de la Escuela del Ministerio Teocrático" (be)
y su versión moderna (ed-mwb) enumeran ~50 puntos de oratoria
("counsel points"): pronunciación clara, transiciones, énfasis,
contacto visual, uso de Escritura, etc.

Hoy:
- El instructor TJ los aplica manualmente en feedback verbal tras
  la parte del estudiante.
- F26 `student_part_helper` los enumera por kind (`bible_reading`,
  `initial_call`, `return_visit`, `bible_study`) en 3 idiomas.

Falta: **autoevaluación cuantitativa del audio grabado de tu propia
parte**, con métricas de prosodia + scoring por counsel point +
timeline + sugerencias accionables.

Es un caso de uso individual (uno graba su parte en casa y la analiza
antes de la reunión) o pedagógico (instructor analiza para dar
feedback más preciso).

## Objetivos

1. CLI `jw talklab analyze recording.wav --counsel-points all`
   produce `TalkLabReport`.
2. **Análisis de prosodia** sobre el audio: pitch tracking (librosa
   o pyworld), intensity envelope, pausas, palabras/min, ratio
   verbo/sustantivo, muletillas detectadas.
3. **Mapeo a counsel points**: para cada uno de los 50 puntos,
   un score 0-3 + evidencia (timestamp + métrica) + sugerencia.
4. **Timeline visual exportable** (SVG o Markdown ASCII).
5. **Privacidad estricta**: audio NUNCA sale del disco, scoring
   local-first, no telemetría.
6. **Solo autoevaluación**: nunca "rank a hermano X vs Y".

## No-objetivos (boundaries vinculantes)

- **No** sustituye al instructor de la Escuela. Es preparación.
- **No** compara a un hermano con otro. El reporte solo compara
  "tú contra ti anterior" si hay historial; cero scoring social.
- **No** se sube a cloud. El audio puede ser sensible (incluso si
  es el del usuario solo).
- **No** entrena modelos sobre el audio del usuario sin consent
  explícito (consent.txt F34 obligatorio).
- **No** evalúa contenido doctrinal — solo oratoria (los puntos
  son pedagógicos, no doctrinales). El reasoner F67 cubre lo
  doctrinal por separado.

## Decisión clave: ¿prosody local-first vs cloud STT premium?

### Opción A — Cloud STT (Deepgram/AssemblyAI con prosody features)

**Pros**: features prosódicas precisas out-of-the-box.
**Contras**: rompe local-first; coste por audio; latencia.

### Opción B — Stack 100% local: WhisperX + librosa/torchaudio

**Pros**:
- WhisperX F64 ya está integrado y diariza.
- librosa para pitch + energy + pause detection: 50 LOC.
- pyworld o crepe para pitch contour fino opt-in.
- Cero red, cero coste.

**Contras**:
- Calidad de pitch detection algo menor que cloud premium.

### Decisión: **Opción B** (local-first)

Justificación:
1. El proyecto es local-first por filosofía.
2. WhisperX F64 ya transcribe + diariza + word-level timestamps.
3. La precisión de pitch local es suficiente para evaluar oratoria
   (no es investigación fonética).
4. Cloud STT queda como provider opcional vía Plugin SDK F41 para
   quien quiera la opción premium.

## Arquitectura

```
            recording.wav (16kHz mono recomendado)
                       │
                       ▼
          ┌────────────────────────────────────┐
          │ 1. Audio loader (F34 reuse)        │
          │    - resample to 16kHz mono        │
          │    - normalize -1.0..1.0           │
          └─────────────┬──────────────────────┘
                        │
              ┌─────────┴────────┐
              ▼                  ▼
   ┌──────────────────┐  ┌──────────────────────┐
   │ 2a. WhisperX F64 │  │ 2b. Prosody features │
   │   - transcript   │  │   - pitch (librosa)  │
   │   - word timing  │  │   - intensity        │
   │   - speakers     │  │   - pause durations  │
   └─────────┬────────┘  │   - speech rate      │
             │           │   - filler detection │
             │           └──────────┬───────────┘
             └────────┬─────────────┘
                      ▼
        ┌──────────────────────────────────────┐
        │ 3. Counsel point scorers              │
        │    50 evaluators (heuristic + LLM)    │
        │    each takes (transcript, prosody)   │
        │    each returns CounselScore          │
        └─────────────┬────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────────────┐
        │ 4. Report builder                     │
        │    - aggregate, sort, format          │
        │    - Markdown / PDF (F31) / SVG       │
        └──────────────────────────────────────┘
```

## Contratos de tipos

```python
# packages/jw-core/src/jw_core/talk_lab/models.py

from pydantic import BaseModel, Field
from typing import Literal

CounselScore = Literal[0, 1, 2, 3]   # 0=needs work, 3=excellent
PartKind = Literal[
    "bible_reading", "initial_call", "return_visit",
    "bible_study", "public_talk", "watchtower_comment", "other"
]

class ProsodyFeatures(BaseModel):
    duration_s: float
    speech_rate_wpm: float          # palabras por minuto
    pitch_mean_hz: float
    pitch_range_hz: float
    intensity_mean_db: float
    pause_count: int
    pause_total_s: float
    pause_avg_s: float
    filler_count: int               # eh / um / este / o sea
    filler_per_minute: float
    pitch_contour_path: str | None = None  # path al .npy o None

class WordTiming(BaseModel):
    word: str
    start_s: float
    end_s: float
    confidence: float

class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    start_s: float
    end_s: float
    words: list[WordTiming] = []

class CounselPointResult(BaseModel):
    point_id: str                    # "cp-01" .. "cp-50"
    title: str                       # "Pronunciación clara"
    title_localized: str
    score: CounselScore
    evidence: list[str] = []         # timestamps + observación
    suggestion: str = ""
    applies: bool = True             # si False, no se aplica a este kind

class TalkLabReport(BaseModel):
    recording_path: str
    part_kind: PartKind
    language: Literal["en", "es", "pt"]
    duration_s: float
    transcript: list[TranscriptSegment]
    prosody: ProsodyFeatures
    counsel_results: list[CounselPointResult]
    summary_top_3: list[str]         # 3 strengths
    summary_focus_3: list[str]       # 3 to work on
    trace_path: str | None = None
    score_history_path: str | None = None  # solo si user opt-in tracking
```

## API pública

```python
# packages/jw-core/src/jw_core/talk_lab/__init__.py

from jw_core.talk_lab.engine import analyze_recording, TalkLabConfig
from jw_core.talk_lab.models import (
    TalkLabReport,
    ProsodyFeatures,
    TranscriptSegment,
    CounselPointResult,
    PartKind,
    CounselScore,
)
from jw_core.talk_lab.history import SessionHistory, track_session

__all__ = [
    "analyze_recording",
    "TalkLabConfig",
    "TalkLabReport",
    "ProsodyFeatures",
    "TranscriptSegment",
    "CounselPointResult",
    "PartKind",
    "CounselScore",
    "SessionHistory",
    "track_session",
]
```

## CLI

```bash
# Análisis básico
jw talklab analyze recording.wav

# Especificar kind para activar counsel points relevantes
jw talklab analyze recording.wav --kind bible_reading --language es

# Exportar PDF
jw talklab analyze recording.wav --export report.pdf

# Opt-in tracking longitudinal (anónimo, local-only)
jw talklab analyze recording.wav --track-history

# Ver historial
jw talklab history

# Comparar 2 grabaciones tuyas
jw talklab compare recording_1.wav recording_2.wav

# Counsel points cubiertos
jw talklab counsel-points --kind bible_reading --language es
```

## MCP tools

- `talklab_analyze(recording_path, part_kind, language="es") → TalkLabReport`
- `talklab_compare(report_a_id, report_b_id) → ComparisonReport`
- `talklab_list_counsel_points(part_kind=None, language="es") → list[CounselPoint]`

## Counsel point scorers

Los 50 puntos se organizan en 3 categorías:

| Categoría             | # puntos | Método de scoring                       |
|-----------------------|----------|-----------------------------------------|
| Prosódicos            | ~15      | Heurísticas puras sobre `ProsodyFeatures` |
| Lingüísticos          | ~20      | Heurísticas + LLM judge opt-in           |
| Audience engagement   | ~15      | LLM judge sobre transcript               |

### Ejemplos de scorers prosódicos puros (no LLM)

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/prosody.py

def score_pronunciation(features: ProsodyFeatures, transcript: list[TranscriptSegment]) -> CounselPointResult:
    """Counsel 01 — Clear Pronunciation.
    Basa el score en confidence promedio de Whisper + word-level timing
    coherente (sin words con duración <50ms ni >2s).
    """
    confidences = [w.confidence for s in transcript for w in s.words]
    avg_conf = sum(confidences) / max(len(confidences), 1)
    score: CounselScore
    if avg_conf >= 0.85: score = 3
    elif avg_conf >= 0.70: score = 2
    elif avg_conf >= 0.55: score = 1
    else: score = 0
    return CounselPointResult(
        point_id="cp-01",
        title="Clear Pronunciation",
        title_localized=_localize("cp-01", language),
        score=score,
        evidence=[f"Whisper avg confidence: {avg_conf:.2f}"],
        suggestion="Slow down on the words with lowest confidence: ..."
            if score < 2 else "Pronunciation is clear and confident."
    )

def score_speech_rate(features: ProsodyFeatures, ...) -> CounselPointResult:
    # 120-150 wpm = ideal for teaching
    # <100 = too slow, >180 = too fast
    ...

def score_pause_use(features: ProsodyFeatures, ...) -> CounselPointResult:
    # Pauses between thoughts; ratio pause_total_s / duration_s ~ 0.15-0.25 ideal
    ...

def score_filler_words(features: ProsodyFeatures, ...) -> CounselPointResult:
    # filler_per_minute <2 = excellent, 2-5 = ok, >5 = work needed
    ...
```

### Ejemplos de scorers híbridos (LLM judge opt-in)

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/llm_judge.py

def score_audience_warmth(transcript, llm_provider=None) -> CounselPointResult:
    """Counsel 22 — Warmth.
    Si no hay LLM, fallback: cuenta palabras de calidez ("amigos", "queridos",
    "thank you", etc.) en transcript.
    Con LLM: pide score 0-3.
    """
    if llm_provider is None:
        return _heuristic_warmth(transcript)
    return _llm_judge_warmth(transcript, llm_provider)
```

## Catálogo de los 50 counsel points

Vive en `packages/jw-core/src/jw_core/talk_lab/counsel_points/`:

- `catalog_en.toml` — 50 puntos en inglés
- `catalog_es.toml` — 50 puntos en español
- `catalog_pt.toml` — 50 puntos en portugués
- `applies_by_kind.toml` — mapa `part_kind → list[point_id]`

Estructura por punto:

```toml
[[points]]
id = "cp-01"
title = "Clear Pronunciation"
title_es = "Pronunciación clara"
title_pt = "Pronúncia clara"
category = "prosodic"
scorer = "score_pronunciation"
short_description = "Cada palabra debe ser entendible"
desc_es = "Cada palabra debe ser entendible..."
desc_pt = "..."
applies_to = ["bible_reading", "initial_call", "return_visit", "bible_study", "public_talk", "watchtower_comment"]
```

## Filler detection

`packages/jw-core/src/jw_core/talk_lab/filler.py`:

```python
_FILLERS = {
    "en": {"um", "uh", "uhh", "like", "you know", "i mean", "so", "right"},
    "es": {"este", "esto", "o sea", "eh", "eeh", "pues", "bueno", "vale"},
    "pt": {"é", "tipo", "tipo assim", "então", "né", "pra você ver"},
}

def detect_fillers(transcript: list[TranscriptSegment], language: str) -> int:
    ...
```

## Tracking longitudinal (opt-in)

Si `--track-history`, el `TalkLabReport` se guarda en
`~/.jw-agent-toolkit/talklab/history.sqlite` con `(report_id,
recording_hash, timestamp, scores_json)`. Permite `jw talklab compare`
y `jw talklab history` para ver evolución.

Cero metadata identificable. Cero export remoto. Cifrado opt-in con
`JW_TALKLAB_KEY` (Fernet, patrón F61).

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `ProsodyFeatures` Pydantic round-trip                         | Unit        |
| Catalog 50 points carga desde TOML                            | Unit        |
| `applies_by_kind` tiene mapping para 7 kinds                  | Unit        |
| Filler detector cuenta correctamente en es/en/pt              | Unit        |
| Speech rate scorer: 130 wpm → score 3                         | Unit        |
| Speech rate scorer: 220 wpm → score 0                         | Unit        |
| Pronunciation scorer respeta avg confidence                   | Unit        |
| Pause scorer detecta gaps >300ms                              | Unit        |
| Audio loader resample 44kHz → 16kHz                           | Unit        |
| Integration WhisperX devuelve TranscriptSegment[]             | Integration |
| LLM judge fallback heurístico si no provider                  | Unit        |
| `analyze_recording` golden 30s clip produce report válido     | E2E         |
| Report Markdown contiene todos los 50 counsel results         | Integration |
| Export PDF via F31 funciona                                   | Integration |
| Tracking history se guarda + recuperación funciona            | Integration |
| MCP `talklab_analyze` devuelve serializable                   | Integration |
| CLI `jw talklab compare` reporta deltas correctos             | E2E         |

## Golden fixtures

`tests/talk_lab/fixtures/recordings/`:
- `golden_30s_clear_es.wav` — bible reading 30s, score 3 en pronunciación
- `golden_30s_filler_heavy_es.wav` — score 1 en filler use
- `golden_60s_too_fast_en.wav` — speech rate >200 wpm

Cada uno con `expected_report.json` que sirve como ground truth.

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| WhisperX requiere HF token (diarización)                | Diarización opcional; fallback a Whisper plano      |
| Pitch detection da NaN en silencios                     | Filtrado pre-análisis; ventanas con energy > floor  |
| Audio del usuario es sensible                           | NUNCA upload; deletes opcional tras análisis        |
| LLM judge es caro si se usa para 35 counsel points      | Default: solo prosódicos; LLM opt-in con `--llm-judge` |
| Scoring se siente "punitivo"                            | Output siempre con `summary_top_3` antes de `summary_focus_3` |
| User compara su score con otros                         | NO hay leaderboard; comparación solo "tú vs tú"     |
| Idioma no soportado                                     | Fallback a en con warning; lista clara de soportados |

## Métricas de éxito

- **Correlación humana**: en blind eval, score automático correlaciona
  ≥0.7 con score de instructor humano sobre 20 grabaciones.
- **Coste**: análisis offline <60s para clip de 5 min en MacBook M1.
- **Adopción**: usuarios usan `jw talklab` ≥1 vez por semana en mes 2.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/talklab.py` — `jw talklab {analyze,compare,history,counsel-points}`.
- MCP: 3 tools nuevas.
- F31 exporter: handler nuevo `TalkLabReport → StudySheet → PDF`.
- F65 meta-orchestrator: tool `talklab.analyze` registrada.

## Guía resultante

`docs/guias/talk-lab.md` — quick start, los 50 counsel points,
interpretación de prosodia, tracking longitudinal, integración con
F26 student parts.
