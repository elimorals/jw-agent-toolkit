from __future__ import annotations

import pytest
from jw_gen.i18n import REQUIRED_KEYS, get_message, list_logo_keywords, realism_suffix


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_all_languages_carry_required_keys(lang: str) -> None:
    for key in REQUIRED_KEYS:
        msg = get_message(key, lang=lang)  # type: ignore[arg-type]
        assert msg, f"{lang}: missing key {key}"


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_realism_suffix_localized(lang: str) -> None:
    suffix = realism_suffix(lang)  # type: ignore[arg-type]
    assert (
        "fotorrealista" in suffix
        or "photorealistic" in suffix
        or "não fotorrealista" in suffix
        or "fotorrealístico" in suffix
    )


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_logo_keywords_nonempty(lang: str) -> None:
    kws = list_logo_keywords(lang)  # type: ignore[arg-type]
    assert len(kws) >= 5
    for kw in kws:
        assert kw == kw.lower(), f"keyword not lowercased: {kw}"


def test_get_message_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        get_message("does.not.exist", lang="es")
