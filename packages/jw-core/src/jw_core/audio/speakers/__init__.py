"""Speaker identification: voiceprints + name mapping for diarized ASR.

F64.7 — mapeo opt-in `speaker_id` → nombre real. La extracción del
embedding desde audio (whisperx + pyannote) se integra en F64.8 futuro;
esta capa es agnóstica al provider y trabaja sobre `np.ndarray`.
"""

from jw_core.audio.speakers.mapper import SpeakerNameMapper
from jw_core.audio.speakers.voiceprint_store import Voiceprint, VoiceprintStore

__all__ = ["SpeakerNameMapper", "Voiceprint", "VoiceprintStore"]
