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
