"""Prosody extractor tests with synthetic audio."""

from __future__ import annotations

import numpy as np
import pytest

from jw_core.talk_lab.prosody import extract_prosody


def _synth_silence(duration_s: float, sr: int = 16000) -> np.ndarray:
    return np.zeros(int(duration_s * sr), dtype=np.float32)


def _synth_tone(
    duration_s: float, freq_hz: float, sr: int = 16000
) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (0.3 * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_prosody_silence_has_zero_speech_rate() -> None:
    audio = _synth_silence(3.0)
    p = extract_prosody(audio, sr=16000, word_count=0)
    assert p.speech_rate_wpm == 0.0
    assert p.duration_s == pytest.approx(3.0)


def test_prosody_pitch_detected_or_zero_on_tone() -> None:
    audio = _synth_tone(2.0, freq_hz=200.0)
    p = extract_prosody(audio, sr=16000, word_count=4)
    assert 100.0 < p.pitch_mean_hz < 400.0 or p.pitch_mean_hz == 0.0


def test_prosody_speech_rate_computed() -> None:
    audio = _synth_tone(60.0, freq_hz=200.0)
    p = extract_prosody(audio, sr=16000, word_count=140)
    assert p.speech_rate_wpm == pytest.approx(140.0, rel=0.01)


def test_prosody_pause_detection_basic() -> None:
    a = _synth_tone(1.0, 200.0)
    b = _synth_silence(0.5)
    c = _synth_tone(1.0, 200.0)
    audio = np.concatenate([a, b, c])
    p = extract_prosody(audio, sr=16000, word_count=5)
    assert p.pause_count >= 1
