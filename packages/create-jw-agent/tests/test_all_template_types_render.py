"""End-to-end: all 5 template types render to disk with their entry-point group."""

from __future__ import annotations

from pathlib import Path

import pytest
from create_jw_agent.render import RenderContext, render_template

TYPES_TO_GROUPS = {
    "agent": "jw_agent_toolkit.agents",
    "parser": "jw_agent_toolkit.parsers",
    "embedder": "jw_agent_toolkit.embedders",
    "vlm": "jw_agent_toolkit.vlm_providers",
    "gen": "jw_agent_toolkit.gen_providers",
}


@pytest.mark.parametrize("plugin_type,group", TYPES_TO_GROUPS.items())
def test_template_emits_correct_entry_point_group(
    tmp_path: Path, plugin_type: str, group: str,
) -> None:
    out = tmp_path / f"my-{plugin_type}"
    ctx = RenderContext.build(name=f"my-{plugin_type}", type=plugin_type, lang="en")
    render_template(template_type=plugin_type, output_dir=out, ctx=ctx)
    py = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert group in py, f"template '{plugin_type}' should register under {group}"


@pytest.mark.parametrize("plugin_type", list(TYPES_TO_GROUPS.keys()))
def test_template_emits_expected_stub_file(tmp_path: Path, plugin_type: str) -> None:
    out = tmp_path / f"my-{plugin_type}"
    ctx = RenderContext.build(name=f"my-{plugin_type}", type=plugin_type, lang="en")
    render_template(template_type=plugin_type, output_dir=out, ctx=ctx)

    module_dir = out / "src" / f"my_{plugin_type}"
    assert module_dir.exists()
    # Each type has a stub named after the type.
    stub = module_dir / f"{plugin_type}.py"
    assert stub.exists(), f"{plugin_type} template must emit {stub.name}"


@pytest.mark.parametrize("plugin_type", list(TYPES_TO_GROUPS.keys()))
def test_template_emits_tests_for_stub(tmp_path: Path, plugin_type: str) -> None:
    out = tmp_path / f"my-{plugin_type}"
    ctx = RenderContext.build(name=f"my-{plugin_type}", type=plugin_type, lang="en")
    render_template(template_type=plugin_type, output_dir=out, ctx=ctx)
    test_file = out / "tests" / f"test_my_{plugin_type}.py"
    assert test_file.exists()


@pytest.mark.parametrize("plugin_type", list(TYPES_TO_GROUPS.keys()))
def test_template_has_ci_workflow(tmp_path: Path, plugin_type: str) -> None:
    out = tmp_path / f"my-{plugin_type}"
    ctx = RenderContext.build(name=f"my-{plugin_type}", type=plugin_type, lang="en")
    render_template(template_type=plugin_type, output_dir=out, ctx=ctx)
    ci = out / ".github" / "workflows" / "ci.yml"
    assert ci.exists()
    body = ci.read_text(encoding="utf-8")
    assert "uv python install 3.13" in body
    assert "pytest" in body
