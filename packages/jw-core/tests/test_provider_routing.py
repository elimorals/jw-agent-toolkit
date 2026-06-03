"""F54.1 — tests for ASR + translation provider routers.

Verifies the auto-selection logic without needing the real models loaded.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from jw_core.audio.transcription import (
    DEFAULT_ASR_CHAIN,
    TranscriptionError,
    get_asr_provider,
    list_asr_providers,
)
from jw_core.translation_providers import (
    TranslationError,
    get_translation_provider,
    list_translation_providers,
)


# ── ASR router ──────────────────────────────────────────────────────────


def test_asr_chain_lists_all_three() -> None:
    """The chain must mention all three modern providers in priority order."""
    assert DEFAULT_ASR_CHAIN == ["deepgram", "whisper-turbo", "omnilingual"]


def test_list_asr_providers_includes_omnilingual() -> None:
    """`list_asr_providers` enumerates the registry, no matter availability."""
    names = {p["name"] for p in list_asr_providers()}
    assert "omnilingual" in names
    assert "deepgram" in names


def test_asr_explicit_name_unknown_raises() -> None:
    with pytest.raises(TranscriptionError, match="Unknown ASR provider"):
        get_asr_provider("not-a-real-provider")


def test_asr_explicit_omnilingual_when_unavailable_raises() -> None:
    """Asking explicitly for Omnilingual without the venv must fail loudly."""
    with patch(
        "jw_core.audio.asr_providers.omnilingual.OmnilingualProvider.is_available",
        return_value=False,
    ):
        with pytest.raises(TranscriptionError, match="not available"):
            get_asr_provider("omnilingual")


def test_asr_routes_low_resource_lang_to_omnilingual() -> None:
    """Quechua isn't in Deepgram's list → router prefers Omnilingual."""
    with (
        patch(
            "jw_core.audio.asr_providers.omnilingual.OmnilingualProvider.is_available",
            return_value=True,
        ),
        patch(
            "jw_core.audio.asr_providers.deepgram.DeepgramProvider.is_available",
            return_value=True,
        ),
    ):
        provider = get_asr_provider(language="qu")
    assert provider.name == "omnilingual"


def test_asr_routes_english_to_deepgram_when_available() -> None:
    """English is in Deepgram's list → router picks it (latency win)."""
    with (
        patch(
            "jw_core.audio.asr_providers.omnilingual.OmnilingualProvider.is_available",
            return_value=True,
        ),
        patch(
            "jw_core.audio.asr_providers.deepgram.DeepgramProvider.is_available",
            return_value=True,
        ),
    ):
        provider = get_asr_provider(language="en")
    assert provider.name == "deepgram"


def test_asr_no_provider_available_raises() -> None:
    with (
        patch(
            "jw_core.audio.asr_providers.deepgram.DeepgramProvider.is_available",
            return_value=False,
        ),
        patch(
            "jw_core.audio.asr_providers.whisper_turbo.WhisperTurboProvider.is_available",
            return_value=False,
        ),
        patch(
            "jw_core.audio.asr_providers.omnilingual.OmnilingualProvider.is_available",
            return_value=False,
        ),
    ):
        with pytest.raises(TranscriptionError, match="No ASR provider available"):
            get_asr_provider()


def test_asr_env_var_picks_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_ASR_PROVIDER", "omnilingual")
    with patch(
        "jw_core.audio.asr_providers.omnilingual.OmnilingualProvider.is_available",
        return_value=True,
    ):
        provider = get_asr_provider()
    assert provider.name == "omnilingual"


# ── Translation router ─────────────────────────────────────────────────


def test_translation_list_includes_nllb() -> None:
    names = {p["name"] for p in list_translation_providers()}
    assert "nllb-200" in names


def test_translation_marks_nllb_as_non_commercial() -> None:
    nllb_entry = next(p for p in list_translation_providers() if p["name"] == "nllb-200")
    assert nllb_entry["commercial_safe"] is False


def test_translation_explicit_unknown_raises() -> None:
    with pytest.raises(TranslationError, match="Unknown translation provider"):
        get_translation_provider("not-a-real-translator")


def test_translation_commercial_filter_blocks_nllb() -> None:
    """When commercial=True, NLLB (CC-BY-NC) must be excluded → no provider available."""
    with patch(
        "jw_core.translation_providers.nllb.NLLBProvider.is_available",
        return_value=True,
    ):
        with pytest.raises(TranslationError, match="No translation provider"):
            get_translation_provider(commercial=True)


def test_translation_explicit_nllb_with_commercial_raises() -> None:
    with patch(
        "jw_core.translation_providers.nllb.NLLBProvider.is_available",
        return_value=True,
    ):
        with pytest.raises(TranslationError, match="non-commercial"):
            get_translation_provider("nllb-200", commercial=True)


def test_translation_default_picks_nllb_when_available() -> None:
    with patch(
        "jw_core.translation_providers.nllb.NLLBProvider.is_available",
        return_value=True,
    ):
        provider = get_translation_provider(source="en", target="es")
    assert provider.name == "nllb-200"


def test_translation_no_provider_available_raises() -> None:
    with patch(
        "jw_core.translation_providers.nllb.NLLBProvider.is_available",
        return_value=False,
    ):
        with pytest.raises(TranslationError, match="No translation provider"):
            get_translation_provider()
