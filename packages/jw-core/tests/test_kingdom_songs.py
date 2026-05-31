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
