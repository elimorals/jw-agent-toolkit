"""Tests for jw_core.ministry.field_report and related field_service modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1 — vocabulary
# ---------------------------------------------------------------------------


def test_default_tags_present() -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert "street" in DEFAULT_TAGS
    assert "return_visit" in DEFAULT_TAGS
    assert "bible_study" in DEFAULT_TAGS
    tags = load_tags(override_path=None)
    assert set(DEFAULT_TAGS).issubset(tags)


def test_override_adds_local_tag(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": ["hospital"], "remove": []}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "hospital" in tags
    assert "street" in tags  # defaults survive


def test_override_can_remove(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": [], "remove": ["letter"]}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "letter" not in tags
    assert "street" in tags


def test_override_missing_file_returns_defaults(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert set(load_tags(override_path=tmp_path / "nope.json")) == set(DEFAULT_TAGS)
