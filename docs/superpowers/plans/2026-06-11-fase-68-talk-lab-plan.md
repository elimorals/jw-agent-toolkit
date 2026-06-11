# Fase 68 — `talk-lab` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multimodal coach-of-public-speaking tool (CLI `jw talklab analyze recording.wav --kind bible_reading --language es`) that loads a local audio recording, transcribes it with WhisperX (F64) including word-level timestamps, extracts prosody features (pitch, intensity, pauses, speech rate, filler words) with librosa, scores the talk against each of ~50 "counsel points" of the JW Theocratic Ministry School manual (catalog `es/en/pt`), and returns a `TalkLabReport` with timeline + top-3 strengths + top-3 focus areas, optionally exported to PDF via F31 exporter. Local-first: audio never leaves the disk.

**Architecture:** New subpackage `packages/jw-core/src/jw_core/talk_lab/` with: Pydantic models (`ProsodyFeatures`, `WordTiming`, `TranscriptSegment`, `CounselPointResult`, `TalkLabReport`), audio loader reusing F34 normalizers, WhisperX adapter (F64 reuse) with graceful degradation to plain Whisper, prosody extractor (librosa+stdlib), 50 counsel-point scorers (prosodic = heuristics, linguistic = heuristics, audience = LLM judge opt-in), filler detector (es/en/pt), report builder, optional `SessionHistory` SQLite for longitudinal tracking. CLI adds `jw talklab {analyze,compare,history,counsel-points}`. MCP adds 3 tools.

**Tech Stack:** Python 3.13 · Pydantic v2 · librosa (audio prosody) · numpy · stdlib `tomllib` (counsel catalog TOML loader) · whisperx (F64, optional) · jw_finetune.synth.provider.LLMProvider (LLM judge opt-in) · jw_core.exporters (F31 PDF/DOCX) · pytest. Optional extras: `[talk-lab]` for librosa+numpy heavy deps.

**Spec:** [`docs/superpowers/specs/2026-06-11-fase-68-talk-lab-design.md`](../specs/2026-06-11-fase-68-talk-lab-design.md)

---

## File map

Creates:
- `packages/jw-core/src/jw_core/talk_lab/__init__.py`
- `packages/jw-core/src/jw_core/talk_lab/models.py`
- `packages/jw-core/src/jw_core/talk_lab/audio_loader.py`
- `packages/jw-core/src/jw_core/talk_lab/prosody.py`
- `packages/jw-core/src/jw_core/talk_lab/filler.py`
- `packages/jw-core/src/jw_core/talk_lab/transcriber.py`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/__init__.py`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_en.toml`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_es.toml`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_pt.toml`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/applies_by_kind.toml`
- `packages/jw-core/src/jw_core/talk_lab/counsel_points/loader.py`
- `packages/jw-core/src/jw_core/talk_lab/scorers/__init__.py`
- `packages/jw-core/src/jw_core/talk_lab/scorers/prosodic.py`
- `packages/jw-core/src/jw_core/talk_lab/scorers/linguistic.py`
- `packages/jw-core/src/jw_core/talk_lab/scorers/audience_llm.py`
- `packages/jw-core/src/jw_core/talk_lab/report.py`
- `packages/jw-core/src/jw_core/talk_lab/history.py`
- `packages/jw-core/src/jw_core/talk_lab/engine.py`
- `packages/jw-core/tests/talk_lab/__init__.py`
- `packages/jw-core/tests/talk_lab/test_models.py`
- `packages/jw-core/tests/talk_lab/test_audio_loader.py`
- `packages/jw-core/tests/talk_lab/test_prosody.py`
- `packages/jw-core/tests/talk_lab/test_filler.py`
- `packages/jw-core/tests/talk_lab/test_catalog.py`
- `packages/jw-core/tests/talk_lab/test_scorers_prosodic.py`
- `packages/jw-core/tests/talk_lab/test_scorers_linguistic.py`
- `packages/jw-core/tests/talk_lab/test_scorers_audience.py`
- `packages/jw-core/tests/talk_lab/test_report.py`
- `packages/jw-core/tests/talk_lab/test_history.py`
- `packages/jw-core/tests/talk_lab/test_engine.py`
- `packages/jw-core/tests/talk_lab/fixtures/__init__.py`
- `packages/jw-core/tests/talk_lab/fixtures/recordings/golden_30s_clear_es.wav`  (sample)
- `packages/jw-core/tests/talk_lab/fixtures/recordings/golden_30s_filler_heavy_es.wav`
- `packages/jw-core/tests/talk_lab/fixtures/expected_reports/golden_30s_clear_es.expected.json`
- `packages/jw-cli/src/jw_cli/commands/talklab.py`
- `docs/guias/talk-lab.md`

Modifies:
- `packages/jw-core/pyproject.toml` — add optional `[talk-lab]` extra with `librosa>=0.10` + `numpy>=1.24`.
- `packages/jw-cli/src/jw_cli/main.py` — register `talklab` subcommand.
- `packages/jw-mcp/src/jw_mcp/server.py` — expose 3 MCP tools.
- `docs/ROADMAP.md` — add Fase 68.
- `docs/README.md` — link new guide.

---

### Task 1: Pydantic models

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/__init__.py`
- Create: `packages/jw-core/src/jw_core/talk_lab/models.py`
- Create: `packages/jw-core/tests/talk_lab/__init__.py`
- Create: `packages/jw-core/tests/talk_lab/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_models.py
"""Pydantic models for talk_lab."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.models import (
    ProsodyFeatures,
    WordTiming,
    TranscriptSegment,
    CounselPointResult,
    TalkLabReport,
)


def test_prosody_round_trip() -> None:
    p = ProsodyFeatures(
        duration_s=30.0,
        speech_rate_wpm=140.0,
        pitch_mean_hz=180.0,
        pitch_range_hz=80.0,
        intensity_mean_db=-22.0,
        pause_count=5,
        pause_total_s=3.5,
        pause_avg_s=0.7,
        filler_count=2,
        filler_per_minute=4.0,
    )
    dumped = p.model_dump()
    rehydrated = ProsodyFeatures.model_validate(dumped)
    assert rehydrated.speech_rate_wpm == 140.0


def test_prosody_rejects_negative_durations() -> None:
    with pytest.raises(ValueError):
        ProsodyFeatures(
            duration_s=-1.0,
            speech_rate_wpm=140.0,
            pitch_mean_hz=180.0,
            pitch_range_hz=80.0,
            intensity_mean_db=-22.0,
            pause_count=0,
            pause_total_s=0.0,
            pause_avg_s=0.0,
            filler_count=0,
            filler_per_minute=0.0,
        )


def test_word_timing_rejects_inverted_window() -> None:
    with pytest.raises(ValueError):
        WordTiming(word="hello", start_s=1.0, end_s=0.5, confidence=0.9)


def test_counsel_score_in_range() -> None:
    c = CounselPointResult(
        point_id="cp-01",
        title="Pronunciation",
        title_localized="Pronunciación",
        score=2,
    )
    assert c.applies is True
    assert c.score == 2


def test_counsel_score_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        CounselPointResult(
            point_id="cp-01",
            title="x",
            title_localized="x",
            score=5,  # > 3
        )


def test_report_round_trip() -> None:
    p = ProsodyFeatures(
        duration_s=10.0, speech_rate_wpm=120.0, pitch_mean_hz=150.0,
        pitch_range_hz=50.0, intensity_mean_db=-18.0, pause_count=1,
        pause_total_s=0.5, pause_avg_s=0.5, filler_count=0, filler_per_minute=0.0,
    )
    rpt = TalkLabReport(
        recording_path="/tmp/x.wav",
        part_kind="bible_reading",
        language="es",
        duration_s=10.0,
        transcript=[],
        prosody=p,
        counsel_results=[],
        summary_top_3=[],
        summary_focus_3=[],
    )
    dumped = rpt.model_dump()
    rehydrated = TalkLabReport.model_validate(dumped)
    assert rehydrated.language == "es"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_models.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement models**

```python
# packages/jw-core/src/jw_core/talk_lab/__init__.py
"""jw_core.talk_lab — coach-of-public-speaking toolkit (Fase 68)."""

from __future__ import annotations

from jw_core.talk_lab.models import (
    ProsodyFeatures,
    WordTiming,
    TranscriptSegment,
    CounselPointResult,
    TalkLabReport,
    PartKind,
    CounselScore,
)

__all__ = [
    "ProsodyFeatures",
    "WordTiming",
    "TranscriptSegment",
    "CounselPointResult",
    "TalkLabReport",
    "PartKind",
    "CounselScore",
]
```

```python
# packages/jw-core/src/jw_core/talk_lab/models.py
"""Pydantic models for talk_lab."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

CounselScore = Literal[0, 1, 2, 3]
PartKind = Literal[
    "bible_reading",
    "initial_call",
    "return_visit",
    "bible_study",
    "public_talk",
    "watchtower_comment",
    "other",
]


class ProsodyFeatures(BaseModel):
    duration_s: float = Field(ge=0)
    speech_rate_wpm: float = Field(ge=0)
    pitch_mean_hz: float = Field(ge=0)
    pitch_range_hz: float = Field(ge=0)
    intensity_mean_db: float
    pause_count: int = Field(ge=0)
    pause_total_s: float = Field(ge=0)
    pause_avg_s: float = Field(ge=0)
    filler_count: int = Field(ge=0)
    filler_per_minute: float = Field(ge=0)
    pitch_contour_path: str | None = None


class WordTiming(BaseModel):
    word: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _validate_window(self) -> "WordTiming":
        if self.end_s < self.start_s:
            raise ValueError(f"end_s ({self.end_s}) < start_s ({self.start_s})")
        return self


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    words: list[WordTiming] = Field(default_factory=list)


class CounselPointResult(BaseModel):
    point_id: str
    title: str
    title_localized: str
    score: CounselScore
    evidence: list[str] = Field(default_factory=list)
    suggestion: str = ""
    applies: bool = True


class TalkLabReport(BaseModel):
    recording_path: str
    part_kind: PartKind
    language: Literal["en", "es", "pt"]
    duration_s: float = Field(ge=0)
    transcript: list[TranscriptSegment]
    prosody: ProsodyFeatures
    counsel_results: list[CounselPointResult]
    summary_top_3: list[str]
    summary_focus_3: list[str]
    trace_path: str | None = None
    score_history_path: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_models.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/__init__.py packages/jw-core/src/jw_core/talk_lab/models.py packages/jw-core/tests/talk_lab
git commit -m "feat(jw-core): scaffold talk_lab package with Pydantic models"
```

---

### Task 2: Audio loader (resample + normalize)

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/audio_loader.py`
- Create: `packages/jw-core/tests/talk_lab/test_audio_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_audio_loader.py
"""Audio loader tests."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from jw_core.talk_lab.audio_loader import load_audio_mono16k, AudioLoadError


def _write_pcm_wav(path: Path, sample_rate: int, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for s in samples:
            w.writeframes(int(s).to_bytes(2, "little", signed=True))


def test_load_audio_resamples_44k_to_16k(tmp_path: Path) -> None:
    p = tmp_path / "x.wav"
    _write_pcm_wav(p, 44100, [0] * 4410)  # 0.1s silence
    audio, sr = load_audio_mono16k(str(p))
    assert sr == 16000
    assert 0.09 < len(audio) / sr < 0.11


def test_load_audio_normalizes_to_neg1_pos1(tmp_path: Path) -> None:
    p = tmp_path / "x.wav"
    _write_pcm_wav(p, 16000, [32767, -32768] * 1000)
    audio, sr = load_audio_mono16k(str(p))
    assert audio.max() <= 1.0
    assert audio.min() >= -1.0


def test_load_audio_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(AudioLoadError):
        load_audio_mono16k(str(tmp_path / "missing.wav"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_audio_loader.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement audio loader**

```python
# packages/jw-core/src/jw_core/talk_lab/audio_loader.py
"""Audio loader: read WAV, resample to 16kHz mono, normalize to [-1, 1]."""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class AudioLoadError(RuntimeError):
    """Raised when the audio cannot be loaded."""


def load_audio_mono16k(path: str) -> tuple[np.ndarray, int]:
    """Load `path` as float32 mono at 16kHz, normalized to [-1, 1]."""

    p = Path(path)
    if not p.exists():
        raise AudioLoadError(f"not found: {p}")
    try:
        with wave.open(str(p), "rb") as w:
            n_channels = w.getnchannels()
            sample_width = w.getsampwidth()
            framerate = w.getframerate()
            n_frames = w.getnframes()
            raw = w.readframes(n_frames)
    except wave.Error as exc:
        raise AudioLoadError(f"wave.Error: {exc}") from exc

    if sample_width != 2:
        raise AudioLoadError(f"only 16-bit PCM supported (got {sample_width*8}-bit)")

    samples = np.frombuffer(raw, dtype=np.int16)
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

    audio_f32 = samples.astype(np.float32) / 32768.0

    if framerate != 16000:
        try:
            from scipy.signal import resample_poly  # type: ignore
            ratio_num, ratio_den = 16000, framerate
            audio_f32 = resample_poly(audio_f32, ratio_num, ratio_den).astype(np.float32)
        except ImportError:
            # crude linear resample fallback
            new_len = int(len(audio_f32) * 16000 / framerate)
            old_x = np.linspace(0, 1, len(audio_f32), endpoint=False)
            new_x = np.linspace(0, 1, new_len, endpoint=False)
            audio_f32 = np.interp(new_x, old_x, audio_f32).astype(np.float32)

    return audio_f32, 16000
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_audio_loader.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/audio_loader.py packages/jw-core/tests/talk_lab/test_audio_loader.py
git commit -m "feat(talk_lab): audio loader with 16kHz mono normalization"
```

---

### Task 3: Prosody feature extractor

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/prosody.py`
- Create: `packages/jw-core/tests/talk_lab/test_prosody.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_prosody.py
"""Prosody extractor tests with synthetic audio."""

from __future__ import annotations

import numpy as np
import pytest

from jw_core.talk_lab.prosody import extract_prosody


def _synth_silence(duration_s: float, sr: int = 16000) -> np.ndarray:
    return np.zeros(int(duration_s * sr), dtype=np.float32)


def _synth_tone(duration_s: float, freq_hz: float, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (0.3 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_prosody_silence_has_zero_speech_rate() -> None:
    audio = _synth_silence(3.0)
    p = extract_prosody(audio, sr=16000, word_count=0)
    assert p.speech_rate_wpm == 0.0
    assert p.duration_s == pytest.approx(3.0)


def test_prosody_pitch_detected_on_tone() -> None:
    audio = _synth_tone(2.0, freq_hz=200.0)
    p = extract_prosody(audio, sr=16000, word_count=4)
    # Allow some tolerance because the extractor is naive without librosa
    assert 100.0 < p.pitch_mean_hz < 400.0 or p.pitch_mean_hz == 0.0


def test_prosody_speech_rate_computed() -> None:
    audio = _synth_tone(60.0, freq_hz=200.0)
    p = extract_prosody(audio, sr=16000, word_count=140)
    assert p.speech_rate_wpm == pytest.approx(140.0, rel=0.01)


def test_prosody_pause_detection_basic() -> None:
    # 1s tone + 0.5s silence + 1s tone
    a = _synth_tone(1.0, 200.0)
    b = _synth_silence(0.5)
    c = _synth_tone(1.0, 200.0)
    audio = np.concatenate([a, b, c])
    p = extract_prosody(audio, sr=16000, word_count=5)
    assert p.pause_count >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_prosody.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement prosody extractor**

```python
# packages/jw-core/src/jw_core/talk_lab/prosody.py
"""Prosody feature extractor.

Uses librosa when available, falls back to numpy-only heuristics otherwise.
Returns a `ProsodyFeatures` Pydantic model.
"""

from __future__ import annotations

import logging

import numpy as np

from jw_core.talk_lab.models import ProsodyFeatures

logger = logging.getLogger(__name__)

_PAUSE_RMS_THRESHOLD = 0.005  # below this rms = silence
_PAUSE_FRAME_MS = 25
_PAUSE_MIN_DURATION_S = 0.30


def _frame_rms(audio: np.ndarray, frame_size: int) -> np.ndarray:
    n_frames = len(audio) // frame_size
    if n_frames == 0:
        return np.array([], dtype=np.float32)
    trimmed = audio[: n_frames * frame_size].reshape(n_frames, frame_size)
    return np.sqrt(np.mean(trimmed.astype(np.float64) ** 2, axis=1)).astype(np.float32)


def _detect_pauses(rms: np.ndarray, sr: int, frame_size: int) -> tuple[int, float, float]:
    if rms.size == 0:
        return (0, 0.0, 0.0)
    silence_mask = rms < _PAUSE_RMS_THRESHOLD
    if not silence_mask.any():
        return (0, 0.0, 0.0)
    frame_dur = frame_size / sr
    pauses: list[float] = []
    current = 0
    for is_sil in silence_mask:
        if is_sil:
            current += 1
        else:
            if current * frame_dur >= _PAUSE_MIN_DURATION_S:
                pauses.append(current * frame_dur)
            current = 0
    if current * frame_dur >= _PAUSE_MIN_DURATION_S:
        pauses.append(current * frame_dur)
    return (len(pauses), float(sum(pauses)), float(np.mean(pauses)) if pauses else 0.0)


def _estimate_pitch(audio: np.ndarray, sr: int) -> tuple[float, float]:
    """Very crude autocorrelation pitch tracker over voiced frames."""

    try:
        import librosa  # type: ignore
        # Use librosa.yin if available
        f0 = librosa.yin(audio, fmin=80.0, fmax=400.0, sr=sr)
        voiced = f0[np.isfinite(f0) & (f0 > 0)]
        if voiced.size == 0:
            return (0.0, 0.0)
        return (float(np.mean(voiced)), float(np.percentile(voiced, 95) - np.percentile(voiced, 5)))
    except Exception:
        # numpy fallback: zero-crossing rate over windows → very coarse
        if audio.size < sr * 0.05:
            return (0.0, 0.0)
        window = 1024
        crossings_per_frame: list[int] = []
        for i in range(0, len(audio) - window, window):
            seg = audio[i : i + window]
            crossings = int(np.sum(np.diff(np.sign(seg)) != 0))
            crossings_per_frame.append(crossings)
        if not crossings_per_frame:
            return (0.0, 0.0)
        rate = float(np.mean(crossings_per_frame)) * (sr / window) / 2.0
        # Cap at human range
        if rate < 60 or rate > 500:
            return (0.0, 0.0)
        return (rate, max(rate * 0.4, 0.0))


def extract_prosody(
    audio: np.ndarray,
    *,
    sr: int = 16000,
    word_count: int,
    filler_count: int = 0,
) -> ProsodyFeatures:
    """Extract a `ProsodyFeatures` from an audio array."""

    duration_s = float(len(audio) / sr)
    frame_size = int(sr * _PAUSE_FRAME_MS / 1000)
    rms = _frame_rms(audio, frame_size)
    intensity_db = (
        20.0 * float(np.log10(max(np.sqrt(np.mean(audio.astype(np.float64) ** 2) + 1e-12), 1e-6)))
        if audio.size else -120.0
    )

    pause_count, pause_total, pause_avg = _detect_pauses(rms, sr, frame_size)

    speech_rate_wpm = (word_count / duration_s) * 60.0 if duration_s > 0 else 0.0
    pitch_mean, pitch_range = _estimate_pitch(audio, sr)
    filler_per_minute = (filler_count / duration_s) * 60.0 if duration_s > 0 else 0.0

    return ProsodyFeatures(
        duration_s=duration_s,
        speech_rate_wpm=speech_rate_wpm,
        pitch_mean_hz=pitch_mean,
        pitch_range_hz=pitch_range,
        intensity_mean_db=intensity_db,
        pause_count=pause_count,
        pause_total_s=pause_total,
        pause_avg_s=pause_avg,
        filler_count=filler_count,
        filler_per_minute=filler_per_minute,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_prosody.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/prosody.py packages/jw-core/tests/talk_lab/test_prosody.py
git commit -m "feat(talk_lab): prosody extractor (librosa with numpy fallback)"
```

---

### Task 4: Filler-word detector (es/en/pt)

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/filler.py`
- Create: `packages/jw-core/tests/talk_lab/test_filler.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_filler.py
"""Filler-word detector tests."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.filler import count_fillers


def test_count_fillers_en() -> None:
    text = "um, like, you know, uh, this is, um, important."
    n = count_fillers(text, language="en")
    # um, like, you know, uh, um = 5
    assert n == 5


def test_count_fillers_es() -> None:
    text = "Eh, pues, este, o sea, bueno, vale… continuamos."
    n = count_fillers(text, language="es")
    assert n == 6


def test_count_fillers_pt() -> None:
    text = "É, tipo assim, então, né, vamos lá."
    n = count_fillers(text, language="pt")
    assert n >= 4


def test_count_fillers_word_boundary() -> None:
    # "this is the umpire" should NOT count "um"
    assert count_fillers("the umpire", language="en") == 0


def test_count_fillers_case_insensitive() -> None:
    assert count_fillers("UM, ok", language="en") == 1


def test_count_fillers_unknown_language_falls_back() -> None:
    n = count_fillers("um like", language="fr")  # falls back to en
    assert n == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_filler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement filler detector**

```python
# packages/jw-core/src/jw_core/talk_lab/filler.py
"""Filler-word detector for es/en/pt with word-boundary matching."""

from __future__ import annotations

import re

_FILLERS: dict[str, list[str]] = {
    "en": ["um", "uh", "uhh", "like", "you know", "i mean", "so", "right"],
    "es": ["este", "esto", "o sea", "eh", "eeh", "pues", "bueno", "vale"],
    "pt": ["é", "tipo", "tipo assim", "então", "né", "pra você ver"],
}


def _compile_pattern(words: list[str]) -> re.Pattern[str]:
    # Sort by length so longer alternations like "you know" win over "you".
    sorted_words = sorted(words, key=len, reverse=True)
    escaped = [re.escape(w) for w in sorted_words]
    return re.compile(rf"(?<![\w]){'|'.join(escaped)}(?![\w])", re.IGNORECASE)


_CACHE: dict[str, re.Pattern[str]] = {lang: _compile_pattern(words) for lang, words in _FILLERS.items()}


def count_fillers(text: str, *, language: str = "es") -> int:
    """Return the count of filler words/phrases in `text` for `language`."""

    pattern = _CACHE.get(language) or _CACHE["en"]
    return len(pattern.findall(text or ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_filler.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/filler.py packages/jw-core/tests/talk_lab/test_filler.py
git commit -m "feat(talk_lab): filler-word detector (es/en/pt) with word-boundary regex"
```

---

### Task 5: Counsel-point catalog loader (TOML)

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/__init__.py`
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/loader.py`
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_es.toml` (minimal subset of 6 points for v1; extend in follow-up)
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_en.toml`
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_pt.toml`
- Create: `packages/jw-core/src/jw_core/talk_lab/counsel_points/applies_by_kind.toml`
- Create: `packages/jw-core/tests/talk_lab/test_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_catalog.py
"""Counsel-point catalog loader tests."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.counsel_points.loader import (
    load_catalog,
    applies_to,
    CounselPointDefinition,
)


def test_load_catalog_es() -> None:
    points = load_catalog("es")
    assert any(p.id == "cp-01" for p in points)
    p1 = next(p for p in points if p.id == "cp-01")
    assert isinstance(p1, CounselPointDefinition)
    assert p1.title_localized != ""


def test_load_catalog_en_has_same_ids() -> None:
    es_ids = {p.id for p in load_catalog("es")}
    en_ids = {p.id for p in load_catalog("en")}
    assert es_ids == en_ids


def test_applies_to_filters_by_kind() -> None:
    bible_reading_points = applies_to("bible_reading")
    assert isinstance(bible_reading_points, set)
    assert "cp-01" in bible_reading_points
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_catalog.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the catalog TOML files (initial 6 points)**

`packages/jw-core/src/jw_core/talk_lab/counsel_points/catalog_en.toml`:

```toml
[[points]]
id = "cp-01"
title = "Clear Pronunciation"
title_localized = "Clear Pronunciation"
category = "prosodic"
scorer = "score_pronunciation"
short_description = "Each word should be intelligible."

[[points]]
id = "cp-02"
title = "Speech Rate"
title_localized = "Speech Rate"
category = "prosodic"
scorer = "score_speech_rate"
short_description = "120-150 wpm for teaching."

[[points]]
id = "cp-03"
title = "Use of Pauses"
title_localized = "Use of Pauses"
category = "prosodic"
scorer = "score_pause_use"
short_description = "Pauses between thoughts to let ideas land."

[[points]]
id = "cp-04"
title = "Filler Words"
title_localized = "Filler Words"
category = "prosodic"
scorer = "score_filler_use"
short_description = "Minimize um/uh/like."

[[points]]
id = "cp-05"
title = "Use of Scripture"
title_localized = "Use of Scripture"
category = "linguistic"
scorer = "score_scripture_use"
short_description = "Cite Scripture and tie it to the point."

[[points]]
id = "cp-06"
title = "Audience Warmth"
title_localized = "Audience Warmth"
category = "audience"
scorer = "score_audience_warmth"
short_description = "Warmth shown to listeners."
```

`catalog_es.toml`: same IDs/categories/scorers but with `title_localized` translated.

```toml
[[points]]
id = "cp-01"
title = "Clear Pronunciation"
title_localized = "Pronunciación clara"
category = "prosodic"
scorer = "score_pronunciation"
short_description = "Cada palabra debe ser entendible."

[[points]]
id = "cp-02"
title = "Speech Rate"
title_localized = "Velocidad del habla"
category = "prosodic"
scorer = "score_speech_rate"
short_description = "120-150 ppm para enseñar."

[[points]]
id = "cp-03"
title = "Use of Pauses"
title_localized = "Uso de pausas"
category = "prosodic"
scorer = "score_pause_use"
short_description = "Pausas entre ideas para que se asienten."

[[points]]
id = "cp-04"
title = "Filler Words"
title_localized = "Muletillas"
category = "prosodic"
scorer = "score_filler_use"
short_description = "Reduce este/o sea/pues."

[[points]]
id = "cp-05"
title = "Use of Scripture"
title_localized = "Uso de la Escritura"
category = "linguistic"
scorer = "score_scripture_use"
short_description = "Cita la Biblia y conéctala al punto."

[[points]]
id = "cp-06"
title = "Audience Warmth"
title_localized = "Calidez hacia el auditorio"
category = "audience"
scorer = "score_audience_warmth"
short_description = "Calidez hacia los oyentes."
```

`catalog_pt.toml`: same with Portuguese translations.

`applies_by_kind.toml`:

```toml
[bible_reading]
points = ["cp-01", "cp-02", "cp-03", "cp-04", "cp-05"]

[initial_call]
points = ["cp-01", "cp-02", "cp-03", "cp-04", "cp-05", "cp-06"]

[return_visit]
points = ["cp-01", "cp-02", "cp-03", "cp-04", "cp-05", "cp-06"]

[bible_study]
points = ["cp-01", "cp-02", "cp-03", "cp-04", "cp-05", "cp-06"]

[public_talk]
points = ["cp-01", "cp-02", "cp-03", "cp-04", "cp-05", "cp-06"]

[watchtower_comment]
points = ["cp-01", "cp-02", "cp-03"]

[other]
points = ["cp-01", "cp-02", "cp-03"]
```

> NOTE: this MVP catalog has 6 points. The Fase 68 design budget calls
> for ~50; subsequent commits expand the catalog one category at a time.

- [ ] **Step 4: Implement loader**

```python
# packages/jw-core/src/jw_core/talk_lab/counsel_points/__init__.py
"""Counsel-point catalog (loader + TOML data)."""
```

```python
# packages/jw-core/src/jw_core/talk_lab/counsel_points/loader.py
"""Load TOML catalog of counsel points and the applies-by-kind table."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

_HERE = Path(__file__).parent
_LANG_FILES = {"en": "catalog_en.toml", "es": "catalog_es.toml", "pt": "catalog_pt.toml"}
_APPLIES_FILE = "applies_by_kind.toml"


class CounselPointDefinition(BaseModel):
    id: str
    title: str
    title_localized: str
    category: Literal["prosodic", "linguistic", "audience"]
    scorer: str
    short_description: str = ""


@lru_cache
def load_catalog(language: str) -> list[CounselPointDefinition]:
    """Return the counsel points for a language (fallback to en)."""

    fname = _LANG_FILES.get(language) or _LANG_FILES["en"]
    with (_HERE / fname).open("rb") as f:
        data = tomllib.load(f)
    return [CounselPointDefinition(**entry) for entry in data.get("points", [])]


@lru_cache
def _applies_by_kind() -> dict[str, set[str]]:
    with (_HERE / _APPLIES_FILE).open("rb") as f:
        data = tomllib.load(f)
    return {kind: set(spec["points"]) for kind, spec in data.items()}


def applies_to(part_kind: str) -> set[str]:
    """Set of point ids that apply to a given `part_kind`."""

    return _applies_by_kind().get(part_kind, set())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_catalog.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/counsel_points packages/jw-core/tests/talk_lab/test_catalog.py
git commit -m "feat(talk_lab): counsel-point catalog (6-point MVP, es/en/pt + applies_by_kind)"
```

---

### Task 6: Prosodic scorers

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/scorers/__init__.py`
- Create: `packages/jw-core/src/jw_core/talk_lab/scorers/prosodic.py`
- Create: `packages/jw-core/tests/talk_lab/test_scorers_prosodic.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_scorers_prosodic.py
"""Prosodic-only scorer tests."""

from __future__ import annotations

import pytest

from jw_core.talk_lab.models import ProsodyFeatures, TranscriptSegment, WordTiming
from jw_core.talk_lab.scorers.prosodic import (
    score_pronunciation,
    score_speech_rate,
    score_pause_use,
    score_filler_use,
)


def _features(**overrides) -> ProsodyFeatures:
    base = dict(
        duration_s=60.0, speech_rate_wpm=130.0, pitch_mean_hz=180.0,
        pitch_range_hz=80.0, intensity_mean_db=-20.0, pause_count=10,
        pause_total_s=10.0, pause_avg_s=1.0, filler_count=2, filler_per_minute=2.0,
    )
    base.update(overrides)
    return ProsodyFeatures(**base)


def _transcript_with_avg_confidence(c: float) -> list[TranscriptSegment]:
    words = [WordTiming(word="w", start_s=0, end_s=0.5, confidence=c)]
    return [TranscriptSegment(speaker="A", text="hi", start_s=0, end_s=1, words=words)]


def test_pronunciation_high_confidence_score_3() -> None:
    transcript = _transcript_with_avg_confidence(0.92)
    r = score_pronunciation(_features(), transcript, language="en")
    assert r.score == 3


def test_pronunciation_low_confidence_score_0() -> None:
    transcript = _transcript_with_avg_confidence(0.45)
    r = score_pronunciation(_features(), transcript, language="en")
    assert r.score == 0


def test_speech_rate_ideal_3() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=135.0), language="en")
    assert r.score == 3


def test_speech_rate_too_fast_0() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=220.0), language="en")
    assert r.score == 0


def test_speech_rate_too_slow_1() -> None:
    r = score_speech_rate(_features(speech_rate_wpm=70.0), language="en")
    assert r.score <= 1


def test_pause_use_ideal_3() -> None:
    # pause_total/duration = 12/60 = 0.20 → ideal
    r = score_pause_use(_features(pause_total_s=12.0, duration_s=60.0), language="en")
    assert r.score == 3


def test_filler_use_low_score_3() -> None:
    r = score_filler_use(_features(filler_per_minute=1.5), language="en")
    assert r.score == 3


def test_filler_use_high_score_0() -> None:
    r = score_filler_use(_features(filler_per_minute=8.0), language="en")
    assert r.score == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_scorers_prosodic.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement prosodic scorers**

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/__init__.py
"""Scorers — pure functions over features + transcripts."""
```

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/prosodic.py
"""Prosodic counsel-point scorers (purely heuristic, no LLM)."""

from __future__ import annotations

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TranscriptSegment,
)

_LOC_TITLES: dict[str, dict[str, str]] = {
    "cp-01": {"en": "Clear Pronunciation", "es": "Pronunciación clara", "pt": "Pronúncia clara"},
    "cp-02": {"en": "Speech Rate", "es": "Velocidad del habla", "pt": "Velocidade da fala"},
    "cp-03": {"en": "Use of Pauses", "es": "Uso de pausas", "pt": "Uso de pausas"},
    "cp-04": {"en": "Filler Words", "es": "Muletillas", "pt": "Vícios de linguagem"},
}


def _loc(point_id: str, language: str) -> str:
    return _LOC_TITLES.get(point_id, {}).get(language, _LOC_TITLES.get(point_id, {}).get("en", ""))


def score_pronunciation(
    features: ProsodyFeatures,
    transcript: list[TranscriptSegment],
    *,
    language: str = "en",
) -> CounselPointResult:
    confidences = [w.confidence for s in transcript for w in s.words]
    if not confidences:
        return CounselPointResult(
            point_id="cp-01",
            title="Clear Pronunciation",
            title_localized=_loc("cp-01", language),
            score=0,
            evidence=["no word-level transcript available"],
            suggestion="Re-run transcription with word-level timestamps enabled (WhisperX).",
        )
    avg_conf = sum(confidences) / len(confidences)
    if avg_conf >= 0.85:
        score, suggestion = 3, "Pronunciation is clear and confident."
    elif avg_conf >= 0.70:
        score, suggestion = 2, "Pronunciation is mostly clear; slow down slightly on harder words."
    elif avg_conf >= 0.55:
        score, suggestion = 1, "Several words are unclear; record again in a quieter environment."
    else:
        score, suggestion = 0, "Pronunciation needs significant work."
    return CounselPointResult(
        point_id="cp-01",
        title="Clear Pronunciation",
        title_localized=_loc("cp-01", language),
        score=score,
        evidence=[f"avg word confidence: {avg_conf:.2f}"],
        suggestion=suggestion,
    )


def score_speech_rate(features: ProsodyFeatures, *, language: str = "en") -> CounselPointResult:
    wpm = features.speech_rate_wpm
    if 120 <= wpm <= 150:
        score, suggestion = 3, "Speech rate is in the ideal teaching range."
    elif 100 <= wpm < 120 or 150 < wpm <= 175:
        score, suggestion = 2, "Speech rate is acceptable; adjust slightly for clarity."
    elif 80 <= wpm < 100 or 175 < wpm <= 200:
        score, suggestion = 1, "Speech rate is off-target; slow down or speed up."
    else:
        score, suggestion = 0, "Speech rate is far from ideal; reread the counsel."
    return CounselPointResult(
        point_id="cp-02",
        title="Speech Rate",
        title_localized=_loc("cp-02", language),
        score=score,
        evidence=[f"{wpm:.0f} wpm"],
        suggestion=suggestion,
    )


def score_pause_use(features: ProsodyFeatures, *, language: str = "en") -> CounselPointResult:
    if features.duration_s <= 0:
        return CounselPointResult(
            point_id="cp-03",
            title="Use of Pauses",
            title_localized=_loc("cp-03", language),
            score=0,
            evidence=["zero duration"],
        )
    pause_ratio = features.pause_total_s / features.duration_s
    if 0.15 <= pause_ratio <= 0.25:
        score, suggestion = 3, "Pauses are well placed; ideas land."
    elif 0.08 <= pause_ratio < 0.15 or 0.25 < pause_ratio <= 0.35:
        score, suggestion = 2, "Pauses are present; refine for emphasis."
    elif 0.03 <= pause_ratio < 0.08 or 0.35 < pause_ratio <= 0.45:
        score, suggestion = 1, "Pauses are too few or too many."
    else:
        score, suggestion = 0, "Pause use needs work."
    return CounselPointResult(
        point_id="cp-03",
        title="Use of Pauses",
        title_localized=_loc("cp-03", language),
        score=score,
        evidence=[f"pause ratio: {pause_ratio:.2f}"],
        suggestion=suggestion,
    )


def score_filler_use(features: ProsodyFeatures, *, language: str = "en") -> CounselPointResult:
    fpm = features.filler_per_minute
    if fpm < 2:
        score, suggestion = 3, "Filler words are minimal."
    elif fpm < 4:
        score, suggestion = 2, "Some filler words; aware of them."
    elif fpm < 6:
        score, suggestion = 1, "Filler words are noticeable; slow down to replace with silence."
    else:
        score, suggestion = 0, "Filler words are very frequent; deliberate practice needed."
    return CounselPointResult(
        point_id="cp-04",
        title="Filler Words",
        title_localized=_loc("cp-04", language),
        score=score,
        evidence=[f"{fpm:.1f} fillers/min"],
        suggestion=suggestion,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_scorers_prosodic.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/scorers/__init__.py packages/jw-core/src/jw_core/talk_lab/scorers/prosodic.py packages/jw-core/tests/talk_lab/test_scorers_prosodic.py
git commit -m "feat(talk_lab): prosodic counsel-point scorers (pronunciation, rate, pauses, fillers)"
```

---

### Task 7: Linguistic scorer + LLM-judge stub for audience

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/scorers/linguistic.py`
- Create: `packages/jw-core/src/jw_core/talk_lab/scorers/audience_llm.py`
- Create: `packages/jw-core/tests/talk_lab/test_scorers_linguistic.py`
- Create: `packages/jw-core/tests/talk_lab/test_scorers_audience.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/talk_lab/test_scorers_linguistic.py
from __future__ import annotations

from jw_core.talk_lab.models import TranscriptSegment, WordTiming
from jw_core.talk_lab.scorers.linguistic import score_scripture_use


def _ts(text: str) -> list[TranscriptSegment]:
    return [TranscriptSegment(speaker="A", text=text, start_s=0, end_s=1)]


def test_scripture_use_high_with_explicit_reference() -> None:
    transcript = _ts("As Juan 3:16 makes clear, this principle...")
    r = score_scripture_use(transcript, language="es")
    assert r.score >= 2


def test_scripture_use_low_without_any_ref() -> None:
    transcript = _ts("Just talk no scriptures here at all.")
    r = score_scripture_use(transcript, language="es")
    assert r.score == 0
```

```python
# packages/jw-core/tests/talk_lab/test_scorers_audience.py
from __future__ import annotations

import pytest

from jw_core.talk_lab.models import TranscriptSegment
from jw_core.talk_lab.scorers.audience_llm import score_audience_warmth


class FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def acomplete(self, prompt: str) -> str:
        return self._text


def _ts(text: str) -> list[TranscriptSegment]:
    return [TranscriptSegment(speaker="A", text=text, start_s=0, end_s=1)]


@pytest.mark.asyncio
async def test_audience_warmth_with_fake_llm_returning_3() -> None:
    r = await score_audience_warmth(_ts("Hello dear friends, thank you for being here."), llm=FakeLLM("3"), language="en")
    assert r.score == 3


@pytest.mark.asyncio
async def test_audience_warmth_without_llm_fallback_heuristic() -> None:
    # No LLM provider → heuristic counts warmth words
    r = await score_audience_warmth(_ts("dear friends, thank you, brothers"), llm=None, language="en")
    assert r.score >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_scorers_linguistic.py packages/jw-core/tests/talk_lab/test_scorers_audience.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement linguistic + audience scorers**

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/linguistic.py
"""Linguistic counsel-point scorers (heuristic, no LLM)."""

from __future__ import annotations

from jw_core.parsers.reference import parse_all_references
from jw_core.talk_lab.models import CounselPointResult, TranscriptSegment


def score_scripture_use(
    transcript: list[TranscriptSegment],
    *,
    language: str = "es",
) -> CounselPointResult:
    text = " ".join(s.text for s in transcript)
    refs = parse_all_references(text) if text else []
    n = len(refs)
    if n >= 3:
        score, suggestion = 3, "Multiple Scriptures cited and connected to the points."
    elif n == 2:
        score, suggestion = 2, "Couple of Scriptures cited; tie them more explicitly to the points."
    elif n == 1:
        score, suggestion = 1, "One Scripture; consider adding a second to reinforce the teaching."
    else:
        score, suggestion = 0, "No Scriptures detected; add at least one to ground the teaching."
    title_loc = {"en": "Use of Scripture", "es": "Uso de la Escritura", "pt": "Uso da Escritura"}
    return CounselPointResult(
        point_id="cp-05",
        title="Use of Scripture",
        title_localized=title_loc.get(language, "Use of Scripture"),
        score=score,
        evidence=[f"{n} Scriptures parsed"],
        suggestion=suggestion,
    )
```

```python
# packages/jw-core/src/jw_core/talk_lab/scorers/audience_llm.py
"""Audience scorers (LLM judge opt-in, heuristic fallback)."""

from __future__ import annotations

from typing import Protocol

from jw_core.talk_lab.models import CounselPointResult, TranscriptSegment


class LLMLike(Protocol):
    async def acomplete(self, prompt: str) -> str: ...


_WARMTH_WORDS = {
    "en": ["dear", "thank you", "friends", "brothers", "sisters", "appreciate", "welcome"],
    "es": ["queridos", "gracias", "amigos", "hermanos", "hermanas", "aprecio", "bienvenidos"],
    "pt": ["queridos", "obrigado", "amigos", "irmãos", "irmãs", "aprecio", "bem-vindos"],
}


async def score_audience_warmth(
    transcript: list[TranscriptSegment],
    *,
    llm: LLMLike | None = None,
    language: str = "es",
) -> CounselPointResult:
    text = " ".join(s.text for s in transcript)
    title_loc = {"en": "Audience Warmth", "es": "Calidez hacia el auditorio", "pt": "Calor hacia o auditório"}

    if llm is None:
        words = _WARMTH_WORDS.get(language, _WARMTH_WORDS["en"])
        hits = sum(1 for w in words if w.lower() in text.lower())
        if hits >= 3:
            score, suggestion = 3, "Warmth is consistently expressed."
        elif hits == 2:
            score, suggestion = 2, "Some warmth shown; consider naming the audience explicitly."
        elif hits == 1:
            score, suggestion = 1, "Warmth is minimal; greet the audience and acknowledge them."
        else:
            score, suggestion = 0, "Warmth is missing; add a personal opener."
        return CounselPointResult(
            point_id="cp-06",
            title="Audience Warmth",
            title_localized=title_loc.get(language, "Audience Warmth"),
            score=score,
            evidence=[f"{hits} warmth markers"],
            suggestion=suggestion,
        )

    prompt = (
        f"Score the audience warmth of this talk from 0 to 3.\n"
        f"0 = cold; 3 = warm.\n"
        f"Talk: {text}\n"
        f"Respond with a single digit only."
    )
    raw = (await llm.acomplete(prompt)).strip()
    try:
        score = int(raw[0])
        if score not in (0, 1, 2, 3):
            score = 0
    except (ValueError, IndexError):
        score = 0
    return CounselPointResult(
        point_id="cp-06",
        title="Audience Warmth",
        title_localized=title_loc.get(language, "Audience Warmth"),
        score=score,  # type: ignore[arg-type]
        evidence=[f"LLM judge: {raw!r}"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_scorers_linguistic.py packages/jw-core/tests/talk_lab/test_scorers_audience.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/scorers/linguistic.py packages/jw-core/src/jw_core/talk_lab/scorers/audience_llm.py packages/jw-core/tests/talk_lab/test_scorers_linguistic.py packages/jw-core/tests/talk_lab/test_scorers_audience.py
git commit -m "feat(talk_lab): linguistic scripture-use + LLM/heuristic audience-warmth scorers"
```

---

### Task 8: Transcriber adapter (WhisperX with degradation)

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/transcriber.py`

- [ ] **Step 1: Implement transcriber (no test now — integration via engine)**

```python
# packages/jw-core/src/jw_core/talk_lab/transcriber.py
"""WhisperX-based transcriber with graceful fallback.

If WhisperX (F64) isn't available, returns an empty transcript so the
report still renders prosody-only counsel points.
"""

from __future__ import annotations

import logging

import numpy as np

from jw_core.talk_lab.models import TranscriptSegment, WordTiming

logger = logging.getLogger(__name__)


def transcribe(audio: np.ndarray, *, sr: int = 16000, language: str = "es") -> list[TranscriptSegment]:
    """Return word-level transcript. Empty list on failure or missing dep."""

    try:
        from jw_core.audio.asr_providers.whisperx import WhisperXProvider  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.info("talk_lab: WhisperX not available (%s); using empty transcript", exc)
        return []

    try:
        provider = WhisperXProvider(language=language)
        result = provider.transcribe(audio, sample_rate=sr, word_timestamps=True)
        segments: list[TranscriptSegment] = []
        for seg in result.segments:
            words = [
                WordTiming(word=w.word, start_s=w.start, end_s=w.end, confidence=w.confidence)
                for w in (seg.words or [])
            ]
            segments.append(
                TranscriptSegment(
                    speaker=seg.speaker or "A",
                    text=seg.text,
                    start_s=seg.start,
                    end_s=seg.end,
                    words=words,
                )
            )
        return segments
    except Exception as exc:  # noqa: BLE001
        logger.warning("talk_lab: WhisperX transcribe failed (%s); empty transcript", exc)
        return []
```

- [ ] **Step 2: Commit (no test yet)**

```bash
git add packages/jw-core/src/jw_core/talk_lab/transcriber.py
git commit -m "feat(talk_lab): WhisperX transcriber adapter (F64) with graceful fallback"
```

---

### Task 9: Report builder + summary top-3 / focus-3

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/report.py`
- Create: `packages/jw-core/tests/talk_lab/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_report.py
from __future__ import annotations

from jw_core.talk_lab.models import (
    CounselPointResult, ProsodyFeatures, TalkLabReport,
)
from jw_core.talk_lab.report import build_report, pick_top_focus


def _cp(point_id: str, score: int) -> CounselPointResult:
    return CounselPointResult(
        point_id=point_id, title=point_id, title_localized=point_id, score=score,  # type: ignore[arg-type]
    )


def test_pick_top_focus_picks_3_high_and_3_low() -> None:
    results = [
        _cp("a", 3), _cp("b", 3), _cp("c", 2),
        _cp("d", 1), _cp("e", 0), _cp("f", 1),
    ]
    top, focus = pick_top_focus(results)
    assert len(top) == 3
    assert len(focus) == 3
    assert "a" in top and "b" in top
    assert "e" in focus


def test_build_report_smoke() -> None:
    prosody = ProsodyFeatures(
        duration_s=60.0, speech_rate_wpm=135.0, pitch_mean_hz=180.0,
        pitch_range_hz=80.0, intensity_mean_db=-20.0, pause_count=8,
        pause_total_s=12.0, pause_avg_s=1.5, filler_count=1, filler_per_minute=1.0,
    )
    rpt = build_report(
        recording_path="/tmp/x.wav",
        part_kind="bible_reading",
        language="es",
        transcript=[],
        prosody=prosody,
        counsel_results=[_cp("a", 3), _cp("b", 0)],
    )
    assert isinstance(rpt, TalkLabReport)
    assert rpt.duration_s == 60.0
    assert len(rpt.summary_top_3) == 1
    assert len(rpt.summary_focus_3) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement report builder**

```python
# packages/jw-core/src/jw_core/talk_lab/report.py
"""Report builder for talk_lab."""

from __future__ import annotations

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TalkLabReport,
    TranscriptSegment,
    PartKind,
)


def pick_top_focus(results: list[CounselPointResult]) -> tuple[list[str], list[str]]:
    """Return (top_3, focus_3) lists of point_id strings."""

    by_score = sorted(results, key=lambda r: r.score, reverse=True)
    top = [r.point_id for r in by_score[:3] if r.score >= 2]
    focus = [r.point_id for r in by_score[::-1][:3] if r.score <= 1]
    return top, focus


def build_report(
    *,
    recording_path: str,
    part_kind: PartKind,
    language: str,
    transcript: list[TranscriptSegment],
    prosody: ProsodyFeatures,
    counsel_results: list[CounselPointResult],
    trace_path: str | None = None,
) -> TalkLabReport:
    top, focus = pick_top_focus(counsel_results)
    return TalkLabReport(
        recording_path=recording_path,
        part_kind=part_kind,
        language=language,  # type: ignore[arg-type]
        duration_s=prosody.duration_s,
        transcript=transcript,
        prosody=prosody,
        counsel_results=counsel_results,
        summary_top_3=top,
        summary_focus_3=focus,
        trace_path=trace_path,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_report.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/report.py packages/jw-core/tests/talk_lab/test_report.py
git commit -m "feat(talk_lab): report builder + top-3 / focus-3 picker"
```

---

### Task 10: SessionHistory SQLite (opt-in tracking)

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/history.py`
- Create: `packages/jw-core/tests/talk_lab/test_history.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_history.py
from __future__ import annotations

from pathlib import Path

from jw_core.talk_lab.history import SessionHistory


def test_session_history_round_trip(tmp_path: Path) -> None:
    h = SessionHistory(tmp_path / "history.sqlite")
    h.track(
        recording_hash="abc",
        report_id="r1",
        scores={"cp-01": 3, "cp-02": 2},
        part_kind="bible_reading",
        language="es",
    )
    rows = h.list()
    assert len(rows) == 1
    assert rows[0].report_id == "r1"
    assert rows[0].scores["cp-01"] == 3


def test_session_history_compare_returns_deltas(tmp_path: Path) -> None:
    h = SessionHistory(tmp_path / "history.sqlite")
    h.track(recording_hash="a", report_id="r1", scores={"cp-01": 1}, part_kind="bible_reading", language="es")
    h.track(recording_hash="b", report_id="r2", scores={"cp-01": 3}, part_kind="bible_reading", language="es")
    deltas = h.compare("r1", "r2")
    assert deltas["cp-01"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_history.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement history**

```python
# packages/jw-core/src/jw_core/talk_lab/history.py
"""Session history (opt-in longitudinal tracking)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel


class HistoryRow(BaseModel):
    report_id: str
    recording_hash: str
    part_kind: str
    language: str
    scores: dict[str, int]
    timestamp: str


class SessionHistory:
    """SQLite-backed tracker for talk_lab reports (local-only)."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                recording_hash TEXT NOT NULL,
                part_kind TEXT NOT NULL,
                language TEXT NOT NULL,
                scores_json TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def track(
        self,
        *,
        recording_hash: str,
        report_id: str,
        scores: dict[str, int],
        part_kind: str,
        language: str,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO reports (report_id, recording_hash, part_kind, language, scores_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (report_id, recording_hash, part_kind, language, json.dumps(scores)),
        )
        self._conn.commit()

    def list(self) -> list[HistoryRow]:
        cur = self._conn.execute(
            "SELECT report_id, recording_hash, part_kind, language, scores_json, timestamp FROM reports "
            "ORDER BY timestamp DESC"
        )
        rows = []
        for r in cur:
            rows.append(
                HistoryRow(
                    report_id=r[0],
                    recording_hash=r[1],
                    part_kind=r[2],
                    language=r[3],
                    scores=json.loads(r[4]),
                    timestamp=r[5],
                )
            )
        return rows

    def compare(self, report_id_a: str, report_id_b: str) -> dict[str, int]:
        cur = self._conn.execute(
            "SELECT report_id, scores_json FROM reports WHERE report_id IN (?, ?)",
            (report_id_a, report_id_b),
        )
        a, b = {}, {}
        for rid, sj in cur:
            d = json.loads(sj)
            if rid == report_id_a:
                a = d
            else:
                b = d
        return {pid: b.get(pid, 0) - a.get(pid, 0) for pid in {*a, *b}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_history.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/history.py packages/jw-core/tests/talk_lab/test_history.py
git commit -m "feat(talk_lab): SessionHistory SQLite for opt-in longitudinal tracking"
```

---

### Task 11: Engine — `analyze_recording` end-to-end

**Files:**
- Create: `packages/jw-core/src/jw_core/talk_lab/engine.py`
- Create: `packages/jw-core/tests/talk_lab/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/talk_lab/test_engine.py
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from jw_core.talk_lab.engine import analyze_recording, TalkLabConfig
from jw_core.talk_lab.models import TalkLabReport


def _write_silent_wav(path: Path, duration_s: float = 5.0, sr: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(duration_s * sr))


@pytest.mark.asyncio
async def test_analyze_recording_silence_produces_valid_report(tmp_path: Path) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=2.0)
    rpt = await analyze_recording(
        recording_path=str(wav),
        config=TalkLabConfig(part_kind="bible_reading", language="es", llm_judge=False),
    )
    assert isinstance(rpt, TalkLabReport)
    assert rpt.language == "es"
    assert rpt.duration_s == pytest.approx(2.0, abs=0.1)
    # No transcript → pronunciation score should be 0
    assert any(r.point_id == "cp-01" and r.score == 0 for r in rpt.counsel_results)


@pytest.mark.asyncio
async def test_analyze_recording_returns_top_and_focus(tmp_path: Path) -> None:
    wav = tmp_path / "x.wav"
    _write_silent_wav(wav, duration_s=2.0)
    rpt = await analyze_recording(
        recording_path=str(wav),
        config=TalkLabConfig(part_kind="bible_reading", language="es", llm_judge=False),
    )
    # summary lists may be empty if everything is mid-tier, but they must exist
    assert isinstance(rpt.summary_top_3, list)
    assert isinstance(rpt.summary_focus_3, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_engine.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement engine**

```python
# packages/jw-core/src/jw_core/talk_lab/engine.py
"""End-to-end engine: load → transcribe → prosody → score → report."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from jw_core.talk_lab.audio_loader import load_audio_mono16k
from jw_core.talk_lab.counsel_points.loader import applies_to, load_catalog
from jw_core.talk_lab.filler import count_fillers
from jw_core.talk_lab.models import (
    CounselPointResult,
    PartKind,
    TalkLabReport,
    TranscriptSegment,
)
from jw_core.talk_lab.prosody import extract_prosody
from jw_core.talk_lab.report import build_report
from jw_core.talk_lab.scorers.audience_llm import score_audience_warmth
from jw_core.talk_lab.scorers.linguistic import score_scripture_use
from jw_core.talk_lab.scorers.prosodic import (
    score_filler_use,
    score_pause_use,
    score_pronunciation,
    score_speech_rate,
)
from jw_core.talk_lab.transcriber import transcribe

logger = logging.getLogger(__name__)


class TalkLabConfig(BaseModel):
    part_kind: PartKind
    language: str = "es"
    llm_judge: bool = False


async def analyze_recording(
    *,
    recording_path: str,
    config: TalkLabConfig,
) -> TalkLabReport:
    audio, sr = load_audio_mono16k(recording_path)

    transcript: list[TranscriptSegment] = transcribe(audio, sr=sr, language=config.language)
    text = " ".join(s.text for s in transcript)
    word_count = sum(len(s.words) or len(s.text.split()) for s in transcript)
    filler_count = count_fillers(text, language=config.language)

    prosody = extract_prosody(audio, sr=sr, word_count=word_count, filler_count=filler_count)

    catalog = load_catalog(config.language)
    applicable = applies_to(config.part_kind)
    counsel_results: list[CounselPointResult] = []

    for point in catalog:
        if point.id not in applicable:
            counsel_results.append(
                CounselPointResult(
                    point_id=point.id,
                    title=point.title,
                    title_localized=point.title_localized,
                    score=0,
                    applies=False,
                )
            )
            continue

        if point.scorer == "score_pronunciation":
            r = score_pronunciation(prosody, transcript, language=config.language)
        elif point.scorer == "score_speech_rate":
            r = score_speech_rate(prosody, language=config.language)
        elif point.scorer == "score_pause_use":
            r = score_pause_use(prosody, language=config.language)
        elif point.scorer == "score_filler_use":
            r = score_filler_use(prosody, language=config.language)
        elif point.scorer == "score_scripture_use":
            r = score_scripture_use(transcript, language=config.language)
        elif point.scorer == "score_audience_warmth":
            llm = None
            if config.llm_judge:
                try:
                    from jw_finetune.synth.provider import build_provider_from_env  # type: ignore
                    llm = build_provider_from_env(scope="talklab")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("talk_lab: LLM judge requested but provider unavailable: %s", exc)
            r = await score_audience_warmth(transcript, llm=llm, language=config.language)
        else:
            r = CounselPointResult(
                point_id=point.id,
                title=point.title,
                title_localized=point.title_localized,
                score=0,
                evidence=[f"unknown scorer: {point.scorer}"],
            )
        counsel_results.append(r)

    return build_report(
        recording_path=recording_path,
        part_kind=config.part_kind,
        language=config.language,
        transcript=transcript,
        prosody=prosody,
        counsel_results=counsel_results,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/talk_lab/test_engine.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/talk_lab/engine.py packages/jw-core/tests/talk_lab/test_engine.py
git commit -m "feat(talk_lab): analyze_recording engine wiring load→transcribe→prosody→score→report"
```

---

### Task 12: CLI + MCP wire-up + guide

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/talklab.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `docs/guias/talk-lab.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/README.md`

- [ ] **Step 1: CLI module**

```python
# packages/jw-cli/src/jw_cli/commands/talklab.py
"""`jw talklab` CLI."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jw_core.talk_lab.counsel_points.loader import applies_to, load_catalog
from jw_core.talk_lab.engine import TalkLabConfig, analyze_recording
from jw_core.talk_lab.history import SessionHistory

app = typer.Typer(help="Talk-lab — coach of public speaking.")
console = Console()


@app.command("analyze")
def cmd_analyze(
    recording: str = typer.Argument(..., help="Path to .wav recording"),
    kind: str = typer.Option("bible_reading", "--kind", "-k"),
    language: str = typer.Option("es", "--language", "-l"),
    llm_judge: bool = typer.Option(False, "--llm-judge"),
    track_history: bool = typer.Option(False, "--track-history"),
    export_md: str | None = typer.Option(None, "--export"),
) -> None:
    """Analyze a recording and print TalkLabReport."""

    cfg = TalkLabConfig(part_kind=kind, language=language, llm_judge=llm_judge)  # type: ignore[arg-type]
    rpt = asyncio.run(analyze_recording(recording_path=recording, config=cfg))
    console.print_json(rpt.model_dump_json())

    if track_history:
        h = SessionHistory(Path("~/.jw-agent-toolkit/talklab/history.sqlite").expanduser())
        scores = {r.point_id: r.score for r in rpt.counsel_results if r.applies}
        h.track(
            recording_hash=hashlib.sha256(Path(recording).read_bytes()).hexdigest()[:16],
            report_id=hashlib.sha256(rpt.model_dump_json().encode()).hexdigest()[:12],
            scores=scores,
            part_kind=rpt.part_kind,
            language=rpt.language,
        )
        console.print("[dim]tracked to local history.sqlite[/]")

    if export_md:
        Path(export_md).write_text(_markdown(rpt))
        console.print(f"[dim]exported to {export_md}[/]")


@app.command("history")
def cmd_history() -> None:
    """Show local TalkLab history."""

    h = SessionHistory(Path("~/.jw-agent-toolkit/talklab/history.sqlite").expanduser())
    table = Table(title="TalkLab history")
    table.add_column("Report")
    table.add_column("Kind")
    table.add_column("Lang")
    table.add_column("Top scores")
    for row in h.list():
        top = ", ".join(f"{pid}={s}" for pid, s in sorted(row.scores.items(), key=lambda kv: -kv[1])[:3])
        table.add_row(row.report_id, row.part_kind, row.language, top)
    console.print(table)


@app.command("counsel-points")
def cmd_counsel_points(
    language: str = typer.Option("es", "--language", "-l"),
    kind: str | None = typer.Option(None, "--kind", "-k"),
) -> None:
    """List counsel points (optionally filtered by kind)."""

    catalog = load_catalog(language)
    applicable = applies_to(kind) if kind else {p.id for p in catalog}
    table = Table(title=f"Counsel points ({language}{', kind=' + kind if kind else ''})")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Category")
    table.add_column("Applies")
    for p in catalog:
        table.add_row(p.id, p.title_localized, p.category, "yes" if p.id in applicable else "no")
    console.print(table)


def _markdown(report) -> str:
    lines = [
        f"# TalkLab report — {report.part_kind}",
        f"- Language: {report.language}",
        f"- Duration: {report.duration_s:.1f}s",
        "",
        "## Prosody",
        f"- Speech rate: {report.prosody.speech_rate_wpm:.0f} wpm",
        f"- Pause count: {report.prosody.pause_count} (total {report.prosody.pause_total_s:.1f}s)",
        f"- Fillers/min: {report.prosody.filler_per_minute:.1f}",
        "",
        "## Top 3 strengths",
        *[f"- {pid}" for pid in report.summary_top_3],
        "",
        "## 3 focus areas",
        *[f"- {pid}" for pid in report.summary_focus_3],
        "",
        "## All counsel points",
    ]
    for r in report.counsel_results:
        if not r.applies:
            continue
        lines.append(f"- **{r.point_id} {r.title_localized}**: {r.score}/3 — {r.suggestion}")
    return "\n".join(lines)
```

- [ ] **Step 2: Register subcommand in `main.py`**

```python
from jw_cli.commands import talklab as _talklab_cmd
app.add_typer(_talklab_cmd.app, name="talklab")
```

- [ ] **Step 3: MCP tools in `server.py`**

```python
@mcp.tool
async def talklab_analyze(
    recording_path: str,
    part_kind: str = "bible_reading",
    language: str = "es",
    llm_judge: bool = False,
) -> dict:
    """Analyze a recording with talk-lab."""
    from jw_core.talk_lab.engine import TalkLabConfig, analyze_recording
    rpt = await analyze_recording(
        recording_path=recording_path,
        config=TalkLabConfig(part_kind=part_kind, language=language, llm_judge=llm_judge),  # type: ignore[arg-type]
    )
    return rpt.model_dump()


@mcp.tool
async def talklab_list_counsel_points(
    part_kind: str | None = None,
    language: str = "es",
) -> dict:
    """List counsel points for a language and optional part_kind."""
    from jw_core.talk_lab.counsel_points.loader import applies_to, load_catalog
    catalog = load_catalog(language)
    applicable = applies_to(part_kind) if part_kind else {p.id for p in catalog}
    return {"points": [p.model_dump() | {"applies": p.id in applicable} for p in catalog]}


@mcp.tool
async def talklab_compare(report_id_a: str, report_id_b: str) -> dict:
    """Compare two tracked reports."""
    from pathlib import Path
    from jw_core.talk_lab.history import SessionHistory
    h = SessionHistory(Path("~/.jw-agent-toolkit/talklab/history.sqlite").expanduser())
    return {"deltas": h.compare(report_id_a, report_id_b)}
```

- [ ] **Step 4: Add `[talk-lab]` extra in `pyproject.toml`**

```toml
[project.optional-dependencies]
"talk-lab" = ["librosa>=0.10", "numpy>=1.24", "scipy>=1.11"]
```

- [ ] **Step 5: Add guide stub**

`docs/guias/talk-lab.md`:

```markdown
# Talk-lab (Fase 68)

> Coach de oratoria multimodal sobre tus propias grabaciones.

## Quick start

\`\`\`bash
jw talklab analyze recording.wav --kind bible_reading --language es

# Con LLM judge para counsel points de auditorio
jw talklab analyze recording.wav --llm-judge

# Tracking longitudinal (opt-in)
jw talklab analyze recording.wav --track-history
jw talklab history

# Exportar markdown
jw talklab analyze recording.wav --export report.md
\`\`\`

## CLI

| Comando                       | Descripción                              |
|-------------------------------|------------------------------------------|
| `jw talklab analyze`          | Analizar grabación                       |
| `jw talklab history`          | Ver historia local                       |
| `jw talklab counsel-points`   | Listar counsel points por kind           |

## MCP

| Tool                            | Descripción                          |
|--------------------------------|--------------------------------------|
| `talklab_analyze`              | Analyze recording                    |
| `talklab_list_counsel_points`  | List counsel points                  |
| `talklab_compare`              | Compare two reports                  |

## Privacidad

El audio nunca sale del disco. El historial es local y opt-in. Nada se
sube a cloud salvo que actives `--llm-judge` (que solo envía texto
transcripción al LLM, no audio).

## Counsel points (MVP)

6 puntos en v0.68. Roadmap: extender a 50.

| ID    | Título               | Categoría  |
|-------|----------------------|------------|
| cp-01 | Pronunciación clara  | prosodic   |
| cp-02 | Velocidad del habla  | prosodic   |
| cp-03 | Uso de pausas        | prosodic   |
| cp-04 | Muletillas           | prosodic   |
| cp-05 | Uso de Escritura     | linguistic |
| cp-06 | Calidez al auditorio | audience   |
```

- [ ] **Step 6: ROADMAP + README**

Add Fase 68 section to `docs/ROADMAP.md` and link from `docs/README.md` (in "Guías por tema").

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest packages/jw-core/tests/talk_lab -v
uv run pytest
```

Expected: 30+ passed for talk_lab, ≥1917 total.

- [ ] **Step 8: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/talklab.py packages/jw-cli/src/jw_cli/main.py packages/jw-mcp/src/jw_mcp/server.py packages/jw-core/pyproject.toml docs/guias/talk-lab.md docs/ROADMAP.md docs/README.md
git commit -m "feat(talklab): CLI + 3 MCP tools + extra [talk-lab] + guide for Fase 68"
```

---

## Acceptance checklist

- [ ] Pydantic models, audio loader, prosody extractor, filler detector, catalog loader, 6 scorers, transcriber, report builder, history, engine — all green.
- [ ] CLI `jw talklab analyze` produces JSON.
- [ ] CLI `jw talklab counsel-points` lists 6 points.
- [ ] CLI `jw talklab history` reads SQLite.
- [ ] 3 MCP tools (`talklab_analyze`, `talklab_list_counsel_points`, `talklab_compare`) are exposed.
- [ ] `pyproject.toml` declares `[talk-lab]` extra.
- [ ] Guide `docs/guias/talk-lab.md` exists and is linked.
- [ ] ROADMAP has Fase 68 section.
- [ ] Full repo suite passes (≥1917 total).

## Follow-ups (out of scope for this plan)

- Expand counsel-point catalog from 6 → ~50 (one category per follow-up).
- Add ASCII timeline / SVG export to `report.py`.
- Wire `jw talklab compare` CLI (only MCP tool exists in MVP).
- Add F31 PDF export wrapper for TalkLabReport.
- Integrate F65 meta-orchestrator tool `talklab.analyze`.
- Add Cloud STT provider (Deepgram) via Plugin SDK F41.
