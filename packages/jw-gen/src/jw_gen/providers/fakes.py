"""Deterministic fake providers used by every offline test.

Image fake → PNG 512x512 with prompt text rasterized, color seeded by
sha256(prompt).
Audio fake → 3-second WAV mono 22050 Hz with single tone whose freq is
derived from sha256(prompt).
Video fake → 2-second GIF built from 3 frames of FakeImageProvider.

All fakes have target='cpu' and is_available() → True. cost_estimate() is zero.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from jw_gen.models import CostHint, GenerationRequest


def _seed(prompt: str) -> int:
    return int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)


class FakeImageProvider:
    name = "fake"
    kind = "image"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.01)

    def generate(self, request: GenerationRequest) -> Path:
        seed = _seed(request.prompt)
        r = (seed >> 16) & 0xFF
        g = (seed >> 8) & 0xFF
        b = seed & 0xFF
        img = Image.new("RGB", (512, 512), color=(r, g, b))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 16)
        except Exception:  # noqa: BLE001
            font = ImageFont.load_default()
        wrapped = "\n".join(request.prompt[i : i + 32] for i in range(0, len(request.prompt), 32))
        draw.text((10, 10), wrapped, fill=(255, 255, 255), font=font)
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_image_{digest}.png"
        img.save(out, format="PNG")
        return out


class FakeAudioProvider:
    name = "fake"
    kind = "audio"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.01)

    def generate(self, request: GenerationRequest) -> Path:
        seed = _seed(request.prompt)
        freq = 200 + (seed % 600)  # 200–800 Hz
        sample_rate = 22050
        duration_s = 3.0
        n = int(sample_rate * duration_s)
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_audio_{digest}.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            for i in range(n):
                v = int(32767 * 0.4 * math.sin(2 * math.pi * freq * (i / sample_rate)))
                w.writeframes(struct.pack("<h", v))
        return out


class FakeVideoProvider:
    name = "fake"
    kind = "video"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.05)

    def generate(self, request: GenerationRequest) -> Path:
        # Multi-frame GIF as cheap portable "video" fake. Real videos go
        # through Veo3/Kling/Runway. Fake only proves contract.
        img_provider = FakeImageProvider(work_dir=self.work_dir)
        frame = Image.open(img_provider.generate(request))
        frames = [frame.copy() for _ in range(3)]
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_video_{digest}.gif"
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=600, loop=0)
        return out
