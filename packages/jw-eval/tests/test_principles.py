"""Tests for jw_eval.principles — loader + violation detection."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_eval.principles import (
    BUILTIN_PRINCIPLES_DIR,
    DetectionRules,
    Principle,
    load_principles,
    load_principles_file,
    violations_for,
)


def test_builtin_principles_load() -> None:
    """All shipped YAML files parse without errors."""
    principles = load_principles()
    ids = {p.id for p in principles}
    assert "PF001-canon-only" in ids
    assert "PF002-cite-before-paraphrase" in ids
    assert "PF003-citation-required" in ids
    assert "PF010-no-impersonation" in ids
    assert "PF012-respect-conscience" in ids
    # Sorted iteration.
    assert [p.id for p in principles] == sorted(ids)


def test_principle_applies_global_when_empty() -> None:
    p = Principle(id="PF-test", severity="soft", applies_to=[], rationale="r")
    assert p.applies("any") is True
    assert p.applies(None) is True


def test_principle_applies_filters() -> None:
    p = Principle(id="PF-test", severity="hard", applies_to=["apologetics"], rationale="r")
    assert p.applies("apologetics") is True
    assert p.applies("verse_explainer") is False


def test_violations_for_forbidden_phrase_case_insensitive() -> None:
    p = Principle(
        id="PF-test",
        severity="hard",
        rationale="r",
        detect=DetectionRules(forbidden_phrases=["según los apócrifos"]),
    )
    hit = violations_for("Esto, Según LOS apócrifos, sería distinto.", [p])
    assert hit == [p]


def test_violations_for_regex() -> None:
    p = Principle(
        id="PF-test",
        severity="hard",
        rationale="r",
        detect=DetectionRules(forbidden_regex=[r"libro de tob(í|i)as"]),
    )
    assert violations_for("Mira el libro de Tobías hoy", [p]) == [p]
    assert violations_for("Otra cita distinta", [p]) == []


def test_violations_for_empty_text_returns_empty() -> None:
    p = Principle(
        id="PF-test",
        severity="hard",
        rationale="r",
        detect=DetectionRules(forbidden_phrases=["x"]),
    )
    assert violations_for("", [p]) == []


def test_invalid_regex_raises_at_construction() -> None:
    with pytest.raises(Exception):
        DetectionRules(forbidden_regex=["[unclosed"])


def test_load_file_supports_list_form(tmp_path: Path) -> None:
    yaml_path = tmp_path / "multi.yaml"
    yaml_path.write_text(
        """
principles:
  - id: A001
    severity: hard
    rationale: alpha
  - id: A002
    severity: soft
    rationale: beta
""",
        encoding="utf-8",
    )
    items = load_principles_file(yaml_path)
    assert [i.id for i in items] == ["A001", "A002"]


def test_user_override_replaces_builtin(tmp_path: Path) -> None:
    """A user YAML with the same id as a builtin should take precedence."""
    # Copy a builtin id but with different rationale, into a tmp root.
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        """
id: PF001-canon-only
severity: hard
rationale: user-override version
""",
        encoding="utf-8",
    )
    user_only = load_principles(tmp_path)
    matched = [p for p in user_only if p.id == "PF001-canon-only"]
    assert len(matched) == 1
    assert matched[0].rationale == "user-override version"


def test_builtin_dir_exists() -> None:
    assert BUILTIN_PRINCIPLES_DIR.exists()
    assert any(BUILTIN_PRINCIPLES_DIR.glob("*.yaml"))
