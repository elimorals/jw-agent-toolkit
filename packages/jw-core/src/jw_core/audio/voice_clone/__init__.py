"""jw_core.audio.voice_clone - consented family-voice TTS (Fase 76).

Public API:
    from jw_core.audio.voice_clone import (
        ConsentRecord, License, Provider, TrainingSample,
        VoiceProfile, TrainResult,
        synthesize_with_voice, list_voices, get_voice,
        delete_voice, revoke_consent,
    )
"""

from __future__ import annotations

from jw_core.audio.voice_clone.models import (
    ConsentRecord,
    License,
    Provider,
    TrainingSample,
    TrainResult,
    VoiceProfile,
)

__all__ = [
    "ConsentRecord",
    "License",
    "Provider",
    "TrainResult",
    "TrainingSample",
    "VoiceProfile",
]
