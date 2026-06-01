"""Tests for renderer (uses inline minimal template fixture)."""

from __future__ import annotations

from pathlib import Path

import pytest

from create_jw_agent.render import RenderContext, _interpolate_filename


def test_render_context_build_produces_module_name() -> None:
    ctx = RenderContext.build(name="my-translator", type="agent", lang="es")
    assert ctx.name == "my-translator"
    assert ctx.module == "my_translator"
    assert ctx.type == "agent"
    assert ctx.lang == "es"


def test_interpolate_filename_replaces_placeholders() -> None:
    ctx = RenderContext.build(name="my-translator", type="agent")
    assert _interpolate_filename("src/{{module}}/__init__.py", ctx) == "src/my_translator/__init__.py"
    assert _interpolate_filename("tests/test_{{module}}.py", ctx) == "tests/test_my_translator.py"


def test_interpolate_filename_leaves_unknown_placeholders() -> None:
    ctx = RenderContext.build(name="x", type="agent")
    assert _interpolate_filename("{{unknown}}/file.txt", ctx) == "{{unknown}}/file.txt"


def test_render_context_default_jw_core_version() -> None:
    ctx = RenderContext.build(name="x", type="agent")
    assert "jw-core" not in ctx.jw_core_version  # just version spec, no name
    assert ctx.jw_core_version.startswith(">=")
