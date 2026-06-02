"""Tests for the lazy catalog registry."""

from __future__ import annotations

from jw_core.versification.models import VersificationMapping
from jw_core.versification.registry import catalog_version, load_catalog


def test_catalog_loads_and_is_non_empty() -> None:
    catalog = load_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) >= 25, "seed catalog should ship 25+ entries"


def test_catalog_entries_are_versification_mapping() -> None:
    catalog = load_catalog()
    for entry in catalog:
        assert isinstance(entry, VersificationMapping)
        assert {"en", "es", "pt"}.issubset(entry.explanation.keys())
        assert entry.source.strip()


def test_catalog_load_is_cached() -> None:
    a = load_catalog()
    b = load_catalog()
    assert a is b, "load_catalog must be lru_cache(1)"


def test_catalog_version_string() -> None:
    assert catalog_version() == "1.0"
