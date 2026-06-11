"""Counsel-point catalog loader tests."""

from __future__ import annotations

from jw_core.talk_lab.counsel_points.loader import (
    CounselPointDefinition,
    applies_to,
    load_catalog,
)


def test_load_catalog_es() -> None:
    points = load_catalog("es")
    assert any(p.id == "cp-01" for p in points)
    p1 = next(p for p in points if p.id == "cp-01")
    assert isinstance(p1, CounselPointDefinition)
    assert p1.title_localized != ""


def test_load_catalog_en_has_same_ids_as_es() -> None:
    es_ids = {p.id for p in load_catalog("es")}
    en_ids = {p.id for p in load_catalog("en")}
    pt_ids = {p.id for p in load_catalog("pt")}
    assert es_ids == en_ids == pt_ids


def test_applies_to_filters_by_kind() -> None:
    bible_reading_points = applies_to("bible_reading")
    assert "cp-01" in bible_reading_points
    assert "cp-06" not in bible_reading_points


def test_applies_to_unknown_kind_returns_empty() -> None:
    assert applies_to("nonexistent_kind") == frozenset()


def test_load_catalog_unknown_language_falls_back_to_en() -> None:
    fr = load_catalog("fr")
    en = load_catalog("en")
    assert [p.id for p in fr] == [p.id for p in en]
