"""Audio loader tests."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from jw_core.talk_lab.audio_loader import AudioLoadError, load_audio_mono16k


def _write_pcm_wav(path: Path, sample_rate: int, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for s in samples:
            w.writeframes(int(s).to_bytes(2, "little", signed=True))


def test_load_audio_resamples_44k_to_16k(tmp_path: Path) -> None:
    p = tmp_path / "x.wav"
    _write_pcm_wav(p, 44100, [0] * 4410)
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
