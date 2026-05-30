"""Audio subsystem — TTS, transcription, JW Broadcasting indexing.

Public surface:
    from jw_core.audio import TTSProvider, get_tts_provider, transcribe_file
    from jw_core.audio.broadcasting import index_broadcasting_subtitles, search_index
"""

from jw_core.audio.tts import TTSProvider, get_tts_provider, list_tts_providers, synthesize_to_file

try:  # transcription is optional (requires faster-whisper)
    from jw_core.audio.transcription import transcribe_file
except ImportError:  # pragma: no cover - optional dep
    transcribe_file = None  # type: ignore[assignment]

__all__ = [
    "TTSProvider",
    "get_tts_provider",
    "list_tts_providers",
    "synthesize_to_file",
    "transcribe_file",
]
