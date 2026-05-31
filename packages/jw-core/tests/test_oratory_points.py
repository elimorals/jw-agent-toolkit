"""Tests for jw_core.data.oratory_points registry."""

from __future__ import annotations

from datetime import date

import pytest

from jw_core.data.oratory_points import (
    ORATORY_POINTS,
    OratoryPoint,
    brief,
    get_point,
    key_phrase,
    point_of_the_month,
    points_applicable_to,
)


def test_registry_has_50_points() -> None:
    assert len(ORATORY_POINTS) == 50


def test_points_are_numbered_1_to_50_uniquely() -> None:
    numbers = sorted(p.number for p in ORATORY_POINTS)
    assert numbers == list(range(1, 51))


def test_brief_paraphrases_under_300_chars() -> None:
    for p in ORATORY_POINTS:
        assert len(p.brief_en) <= 300, p.number
        assert len(p.brief_es) <= 300, p.number
        assert len(p.brief_pt) <= 300, p.number


def test_key_phrases_under_120_chars() -> None:
    for p in ORATORY_POINTS:
        assert len(p.key_phrase_en) <= 120
        assert len(p.key_phrase_es) <= 120
        assert len(p.key_phrase_pt) <= 120


def test_get_point_returns_canonical() -> None:
    p = get_point(1)
    assert p.number == 1


def test_get_point_raises_on_unknown() -> None:
    with pytest.raises(ValueError):
        get_point(0)
    with pytest.raises(ValueError):
        get_point(51)


def test_point_of_the_month_is_deterministic() -> None:
    # Month 1 → point 1 in our canonical mapping.
    p = point_of_the_month(date(2026, 1, 15))
    assert p.number == 1
    # Month 7 → point 25.
    assert point_of_the_month(date(2026, 7, 1)).number == 25
    # Month 12 → point 45.
    assert point_of_the_month(date(2026, 12, 31)).number == 45


def test_points_applicable_to_filters_by_kind() -> None:
    applicable = points_applicable_to("bible_reading")
    assert all("bible_reading" in p.applies_to for p in applicable)
    assert len(applicable) >= 10  # plenty of advice for reading aloud


def test_points_applicable_to_unknown_kind_returns_empty() -> None:
    assert points_applicable_to("nonsense") == []


def test_key_phrase_helper_picks_language() -> None:
    p = get_point(1)
    assert key_phrase(p, "en") == p.key_phrase_en
    assert key_phrase(p, "es") == p.key_phrase_es
    assert key_phrase(p, "pt") == p.key_phrase_pt
    # Unknown language falls back to en.
    assert key_phrase(p, "xx") == p.key_phrase_en


def test_brief_helper_picks_language() -> None:
    p = get_point(1)
    assert brief(p, "es") == p.brief_es
    assert brief(p, "xx") == p.brief_en
