"""Tests for the Caudal jw / Caleb-and-Sophia catalog (Gap 11)."""

from __future__ import annotations

from jw_core.family.caudal_jw import (
    CAUDAL_LESSONS,
    list_caudal_lessons,
    pick_caudal_by_topic,
)


def test_catalog_has_ten_lessons() -> None:
    assert len(CAUDAL_LESSONS) >= 10


def test_each_lesson_has_video_key_or_scripture() -> None:
    for c in CAUDAL_LESSONS:
        assert c.bjf_video_key or c.scripture_anchors


def test_list_localized() -> None:
    items_es = list_caudal_lessons("es")
    items_en = list_caudal_lessons("en")
    assert {i["key"] for i in items_es} == {i["key"] for i in items_en}
    obey = next(i for i in items_es if i["key"] == "obey_parents")
    assert obey["title"] == "Obedece a tus padres"


def test_filter_by_age_band() -> None:
    middle = list_caudal_lessons(age_band="middle")
    assert middle
    assert all(c["age_band"] == "middle" for c in middle)


def test_pick_by_topic_case_insensitive() -> None:
    lesson = pick_caudal_by_topic("OBEDIENCE")
    assert lesson is not None
    assert lesson["key"] == "obey_parents"
