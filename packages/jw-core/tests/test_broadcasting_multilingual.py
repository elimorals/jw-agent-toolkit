"""F54.8 — tests for the multilingual broadcasting ingest path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from jw_core.audio.broadcasting import (
    BroadcastingIndex,
    transcribe_and_index_audio,
)
from jw_core.audio.transcription import TranscriptionResult, TranscriptionSegment


class _FakeASRProvider:
    name = "fake-asr"

    def transcribe(self, path: Path, *, language: str | None = None, model_size: str = "auto"):  # type: ignore[no-untyped-def]
        # Simulate a provider that normalizes ISO-639-1 to its own scheme
        # (Omnilingual returns FLORES). The translate path uses whatever the
        # provider says — no second normalization happens in the helper.
        return TranscriptionResult(
            text="Allin Punchaw kachunchik. Juan 3:16 nin.",
            language="quy_Latn",
            duration=42.0,
            segments=[TranscriptionSegment(start=0.0, end=42.0, text="Allin Punchaw")],
        )


class _FakeTranslator:
    name = "fake-translator"
    is_commercial_safe = True

    def is_available(self) -> bool:
        return True

    def supports_language_pair(self, src: str, tgt: str) -> bool:
        return True

    def translate(self, text: str, *, source: str, target: str) -> str:
        return f"[{source}->{target}] {text}"


def test_transcribe_and_index_basic(tmp_path: Path) -> None:
    """Audio → transcript → indexed video. No translation."""
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"")
    index = BroadcastingIndex(tmp_path / "idx.db")
    try:
        with patch("jw_core.audio.transcription.get_asr_provider", return_value=_FakeASRProvider()):
            n = transcribe_and_index_audio(
                index, audio, video_id="vid-1", title="Asamblea Quechua", language="qu",
                source_url="https://tv.jw.org/video/vid-1",
            )
        assert n > 0
        results = index.search("Punchaw")
        assert any("Allin Punchaw" in r["text"] for r in results)
    finally:
        index.close()


def test_transcribe_and_index_with_translation(tmp_path: Path) -> None:
    """Translate to English at ingest time → indexed text is in English."""
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"")
    index = BroadcastingIndex(tmp_path / "idx.db")
    try:
        with (
            patch("jw_core.audio.transcription.get_asr_provider", return_value=_FakeASRProvider()),
            patch(
                "jw_core.translation_providers.get_translation_provider",
                return_value=_FakeTranslator(),
            ),
        ):
            transcribe_and_index_audio(
                index, audio, video_id="vid-2", title="Asamblea",
                language="qu", translate_to="en",
            )
        results = index.search("Allin")
        # Indexed text should carry the [src->tgt] marker from our fake translator.
        assert any("[quy_Latn->en]" in r["text"] for r in results)
        # The indexed language was overwritten with the target.
        assert all(r["language"] == "en" for r in results)
    finally:
        index.close()
