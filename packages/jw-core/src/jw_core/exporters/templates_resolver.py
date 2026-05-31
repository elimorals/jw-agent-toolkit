"""Resolve Jinja2 templates, honoring user overrides at ~/.jw-agent-toolkit/templates/.

Lookup order:
    1. ~/.jw-agent-toolkit/templates/<name>  (user override)
    2. jw_core.templates.study_sheet.<name>  (packaged default)
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from jw_core.exporters.errors import ExportError
from jw_core.exporters.ir import StudySheet


def _packaged_dir() -> Path:
    return Path(__file__).parent.parent / "templates" / "study_sheet"


def _user_dir() -> Path:
    return Path.home() / ".jw-agent-toolkit" / "templates"


def list_builtin_templates() -> list[str]:
    """Return names of packaged Jinja2 templates."""
    return sorted(p.name for p in _packaged_dir().glob("*.html.j2"))


def resolve_template_path(name: str) -> Path:
    """Return the path of the template, user override wins. Raises if missing."""

    candidate = _user_dir() / name
    if candidate.exists():
        return candidate
    candidate = _packaged_dir() / name
    if candidate.exists():
        return candidate
    raise ExportError(f"Template {name!r} not found (looked in {_user_dir()} and {_packaged_dir()})")


def render_html(sheet: StudySheet, *, template_name: str = "plain.html.j2") -> str:
    """Render `sheet` to HTML using the given Jinja2 template."""

    path = resolve_template_path(template_name)
    env = Environment(
        loader=FileSystemLoader(path.parent),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(path.name)
    return template.render(sheet=sheet)
