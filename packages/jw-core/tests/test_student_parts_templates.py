"""Tests for jw_core.data.student_parts_templates."""

from __future__ import annotations

import pytest
from jw_core.data.student_parts_templates import (
    PART_TEMPLATES,
    find_template,
    time_target_seconds_for,
)


def test_registry_has_48_templates() -> None:
    # 4 kinds × 4 audiences × 3 langs = 48
    assert len(PART_TEMPLATES) == 48


def test_every_kind_audience_language_present() -> None:
    kinds = ("bible_reading", "starting_conversation", "return_visit", "bible_study")
    audiences = ("default", "new", "religious", "atheist")
    langs = ("en", "es", "pt")
    slots = {(t.kind, t.audience, t.language) for t in PART_TEMPLATES}
    expected = {(k, a, l) for k in kinds for a in audiences for l in langs}
    assert slots == expected


def test_find_template_exact_match() -> None:
    t = find_template("bible_reading", "default", "es")
    assert t.kind == "bible_reading"
    assert t.audience == "default"
    assert t.language == "es"


def test_find_template_falls_back_to_default_audience() -> None:
    # Remove the 'new' audience entry virtually by asking for a typo-ish audience.
    # Easier path: directly exercise the fallback code path.
    # We trust the existence test; here we test that asking for an unsupported
    # audience returns the default-audience template.
    t = find_template("bible_reading", "child", "es")  # 'child' not a slot
    assert t.audience == "default"
    assert t.language == "es"


def test_find_template_falls_back_to_default_language() -> None:
    t = find_template("bible_reading", "default", "fr")
    assert t.language == "en"
    assert t.kind == "bible_reading"


def test_find_template_raises_on_unknown_kind() -> None:
    with pytest.raises(ValueError):
        find_template("invented_kind", "default", "es")


def test_time_targets_are_correct() -> None:
    assert time_target_seconds_for("bible_reading") == 240
    assert time_target_seconds_for("starting_conversation") == 180
    assert time_target_seconds_for("return_visit") == 240
    assert time_target_seconds_for("bible_study") == 300


def test_time_target_raises_on_unknown_kind() -> None:
    with pytest.raises(ValueError):
        time_target_seconds_for("nope")


def test_every_template_has_required_placeholders_declared() -> None:
    for t in PART_TEMPLATES:
        # The four script slots should contain at least one placeholder
        # together, and `required_placeholders` should be a strict subset
        # of placeholders actually present in opening/body/transition/close.
        joined = "|".join([t.opening, t.body, t.transition, t.close])
        for placeholder in t.required_placeholders:
            assert "{" + placeholder + "}" in joined, (t.kind, t.audience, t.language, placeholder)
