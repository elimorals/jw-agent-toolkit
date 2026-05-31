"""Tests for jw_core.songs — Kingdom Songs metadata registry."""

from __future__ import annotations

import pytest


def test_model_round_trip_minimum_fields() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="Christ's Self-Sacrificing Love",
        theme="Christ's self-sacrificing love as a pattern.",
        scriptures=["John 13:34-35"],
        language="en",
    )
    assert s.number == 5
    assert s.pub_symbol == "sjj"
    assert s.canonical_url == ""


def test_model_rejects_out_of_range_number() -> None:
    from jw_core.songs import KingdomSong

    with pytest.raises(ValueError):
        KingdomSong(number=999, title="x", theme="y", scriptures=[], language="en")


def test_song_lookup_error_is_lookup_error() -> None:
    from jw_core.songs import SongLookupError

    assert issubclass(SongLookupError, LookupError)


def test_resolved_scriptures_filters_unparseable() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="x",
        theme="y",
        scriptures=["Juan 13:34-35", "not-a-ref"],
        language="es",
    )
    refs = s.resolved_scriptures()
    assert len(refs) == 1
    assert refs[0].book_num == 43  # John


def test_get_registry_loads_three_languages() -> None:
    from jw_core.songs import get_registry

    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        assert len(reg.all()) >= 10, f"{lang} registry too small"


def test_get_registry_caches_per_language() -> None:
    from jw_core.songs import get_registry

    a = get_registry("en")
    b = get_registry("en")
    assert a is b


def test_lookup_returns_song() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    assert song.number == 5
    assert "amor" in song.title.lower() or "amor" in song.theme.lower()


def test_lookup_unknown_raises() -> None:
    from jw_core.songs import SongLookupError, get_registry

    reg = get_registry("en")
    with pytest.raises(SongLookupError):
        reg.lookup(999)


def test_unknown_language_returns_empty_registry() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("xx")
    assert reg.all() == []


def test_canonical_url_falls_back_to_finder_pattern() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    # Spanish wtlocale = "S".
    assert song.canonical_url == "https://www.jw.org/finder?wtlocale=S&pub=sjj"


def test_seed_integrity() -> None:
    """Invariants that protect the seed from accidentally storing lyrics."""

    from jw_core.songs import get_registry

    # Heuristic anti-lyrics tokens — flag obvious copy-paste from a lyric sheet.
    FORBIDDEN_TOKENS = [
        "verse 1", "estrofa", "estribillo", "refrão", "refrain",
        "chorus", "stanza", "©", "copyright watch tower",
    ]

    parallel_numbers: dict[str, set[int]] = {}
    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        nums = set()
        for s in reg.all():
            assert 1 <= s.number <= 200, f"{lang}/#{s.number}: out of 1..200"
            assert len(s.theme) <= 200, f"{lang}/#{s.number}: theme too long"
            assert len(s.title) <= 200, f"{lang}/#{s.number}: title too long"
            lower_blob = (s.title + " " + s.theme).lower()
            for tok in FORBIDDEN_TOKENS:
                assert tok not in lower_blob, (
                    f"{lang}/#{s.number}: forbidden token {tok!r}"
                )
            # Every scripture must parse cleanly.
            assert s.resolved_scriptures() or not s.scriptures, (
                f"{lang}/#{s.number}: scriptures {s.scriptures} all unparseable"
            )
            nums.add(s.number)
        parallel_numbers[lang] = nums

    # All three languages cover the same numbers (parallel coverage).
    assert parallel_numbers["en"] == parallel_numbers["es"] == parallel_numbers["pt"], (
        f"language coverage mismatch: {parallel_numbers}"
    )
