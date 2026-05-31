"""Veo 3 (Gemini video generation) provider — thin."""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class Veo3Provider:
    name = "veo3"
    kind = "video"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(
            os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache")
        )
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("GEMINI_API_KEY"):
            return False
        if sys.modules.get("google.genai", "missing") is None:
            return False
        try:
            importlib.import_module("google.genai")
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:
        seconds = float(request.duration_s or 6.0)
        return CostHint(
            usd=seconds * 0.50,
            time_s=60.0,
            notes="Veo 3 — long-running operation",
        )

    def generate(self, request: GenerationRequest) -> Path:
        from google import genai  # type: ignore[import-not-found]

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        op = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=request.prompt,
        )
        # Poll until done. Cap at 5 min wall-clock.
        deadline = time.time() + 300
        while not op.done and time.time() < deadline:
            time.sleep(5)
            op = client.operations.get(op)
        if not op.done:
            raise RuntimeError("Veo3 generation timed out after 5 minutes")
        digest = abs(hash(request.prompt)) & 0xFFFFFF
        out = self.work_dir / f"veo3_{digest:06x}.mp4"
        client.files.download(
            file=op.response.generated_videos[0].video, destination=str(out)
        )
        return out
