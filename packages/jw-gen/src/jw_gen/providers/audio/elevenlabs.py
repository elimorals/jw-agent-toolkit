"""ElevenLabs TTS adapter — thin. Voice clone gated by `safety.refuse_voice_cloning_without_double_optin`."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class ElevenLabsProvider:
    name = "elevenlabs"
    kind = "audio"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("ELEVENLABS_API_KEY"):
            return False
        if sys.modules.get("elevenlabs", "missing") is None:
            return False
        try:
            importlib.import_module("elevenlabs")
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:
        chars = len(request.prompt)
        return CostHint(usd=chars * 0.00003, time_s=2.0, notes="ElevenLabs TTS")

    def generate(self, request: GenerationRequest) -> Path:
        from elevenlabs import ElevenLabs  # type: ignore[import-not-found]

        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        audio = client.text_to_speech.convert(
            voice_id=str(request.extra.get("voice_id", "EXAVITQu4vr4xnSDxMaL")),
            output_format="mp3_44100_128",
            text=request.prompt,
        )
        digest = abs(hash(request.prompt)) & 0xFFFFFF
        out = self.work_dir / f"elevenlabs_{digest:06x}.mp3"
        with out.open("wb") as f:
            for chunk in audio:
                f.write(chunk)
        return out
