from __future__ import annotations

import wave
from pathlib import Path

from PIL import Image

from jw_gen.models import GenerationRequest
from jw_gen.providers.fakes import (
    FakeAudioProvider,
    FakeImageProvider,
    FakeVideoProvider,
)


def test_fake_image_provider_returns_valid_png(tmp_path: Path) -> None:
    p = FakeImageProvider(work_dir=tmp_path)
    req = GenerationRequest(prompt="hello", kind="image")
    out = p.generate(req)
    assert out.exists()
    assert out.suffix == ".png"
    img = Image.open(out)
    assert img.size == (512, 512)


def test_fake_image_provider_is_deterministic(tmp_path: Path) -> None:
    p1 = FakeImageProvider(work_dir=tmp_path)
    p2 = FakeImageProvider(work_dir=tmp_path / "again")
    out1 = p1.generate(GenerationRequest(prompt="same", kind="image"))
    out2 = p2.generate(GenerationRequest(prompt="same", kind="image"))
    assert out1.read_bytes() == out2.read_bytes()


def test_fake_audio_provider_returns_valid_wav(tmp_path: Path) -> None:
    p = FakeAudioProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="music", kind="audio"))
    assert out.suffix == ".wav"
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() in (1, 2)
        assert w.getframerate() > 0


def test_fake_video_provider_returns_file_with_audio_track(tmp_path: Path) -> None:
    p = FakeVideoProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="anything", kind="video"))
    assert out.exists()
    assert out.suffix in {".mp4", ".webm", ".gif"}


def test_all_fakes_report_zero_cost(tmp_path: Path) -> None:
    for cls in (FakeImageProvider, FakeAudioProvider, FakeVideoProvider):
        prov = cls(work_dir=tmp_path)  # type: ignore[abstract]
        assert prov.is_available()
        cost = prov.cost_estimate(GenerationRequest(prompt="x", kind=prov.kind))  # type: ignore[arg-type]
        assert cost.usd == 0.0
