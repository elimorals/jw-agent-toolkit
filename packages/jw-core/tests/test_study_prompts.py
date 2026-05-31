from __future__ import annotations

import pytest
from jw_core.data.study_prompts import (
    ANTICIPATION_TEMPLATES,
    render_template,
    scan_for_crisis,
)


def test_templates_cover_minimum_languages() -> None:
    for lang in ("es", "en", "pt"):
        assert lang in ANTICIPATION_TEMPLATES
        assert "fact" in ANTICIPATION_TEMPLATES[lang]
        assert "application" in ANTICIPATION_TEMPLATES[lang]
        assert "scripture" in ANTICIPATION_TEMPLATES[lang]


def test_render_fact_template_es() -> None:
    out = render_template("es", "fact", n=3)
    assert "3" in out
    assert "?" in out


def test_render_scripture_requires_ref() -> None:
    out = render_template("en", "scripture", n=2, ref="John 3:16")
    assert "John 3:16" in out
    assert "2" in out


def test_render_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        render_template("es", "does_not_exist", n=1)


def test_render_falls_back_to_english_for_unknown_lang() -> None:
    out = render_template("xx", "fact", n=1)
    assert "?" in out  # at least it rendered something usable


def test_scan_for_crisis_es_match() -> None:
    hits = scan_for_crisis("La hermana mencionó suicidio.", language="es")
    assert hits == ["suicidio"]


def test_scan_for_crisis_no_match() -> None:
    assert scan_for_crisis("Hablamos sobre el reino", language="es") == []


def test_scan_for_crisis_unknown_lang_falls_back_to_en() -> None:
    hits = scan_for_crisis("He felt abuse", language="xx")
    assert "abuse" in hits
