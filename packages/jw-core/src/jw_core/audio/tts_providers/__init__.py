"""Premium TTS providers (opt-in).

All providers extend jw_core.audio.tts.TTSProvider. SDK imports are LAZY:
`is_available()` must not touch the network and must not raise.
"""

from jw_core.audio.tts_providers.fakes import (
    FakeElevenLabsTTS,
    FakeF5TTS,
    FakeKokoroTTS,
    FakeXTTSv2,
)

__all__ = [
    "FakeElevenLabsTTS",
    "FakeF5TTS",
    "FakeKokoroTTS",
    "FakeXTTSv2",
]
