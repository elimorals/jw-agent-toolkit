"""Tests for the template resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_core.exporters.errors import ExportError
from jw_core.exporters.templates_resolver import (
    list_builtin_templates,
    render_html,
    resolve_template_path,
)
from jw_core.exporters.ir import StudySection, StudySheet


def _sheet() -> StudySheet:
    return StudySheet(
        title="T",
        sections=[StudySection(heading="h", body="b")],
    )


def test_list_builtin_templates_includes_two() -> None:
    names = list_builtin_templates()
    assert "plain.html.j2" in names
    assert "study-sheet.html.j2" in names


def test_resolve_builtin_template() -> None:
    p = resolve_template_path("plain.html.j2")
    assert p.exists()
    assert p.name == "plain.html.j2"


def test_resolve_user_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_dir = tmp_path / ".jw-agent-toolkit" / "templates"
    user_dir.mkdir(parents=True)
    user_tpl = user_dir / "plain.html.j2"
    user_tpl.write_text("<html>USER</html>", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_template_path("plain.html.j2")
    # User override wins
    assert p == user_tpl


def test_resolve_missing_raises() -> None:
    with pytest.raises(ExportError):
        resolve_template_path("does-not-exist.html.j2")


def test_render_html_contains_title_and_body() -> None:
    html = render_html(_sheet(), template_name="plain.html.j2")
    assert "T" in html
    assert "<html" in html.lower()


def test_render_html_escapes_html_in_body() -> None:
    sheet = StudySheet(
        title="T",
        sections=[StudySection(heading="h", body="<script>alert(1)</script>")],
    )
    html = render_html(sheet, template_name="plain.html.j2")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
