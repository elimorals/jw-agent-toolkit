"""End-to-end test: render the agent template and verify all required files exist."""

from __future__ import annotations

from pathlib import Path

import pytest
from create_jw_agent.render import RenderContext, TargetExistsError, render_template


def _render_to(tmp_path: Path, name: str = "my-translator") -> Path:
    out = tmp_path / name
    ctx = RenderContext.build(name=name, type="agent", lang="en")
    render_template(template_type="agent", output_dir=out, ctx=ctx)
    return out


def test_agent_template_emits_pyproject(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    py = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "my-translator"' in py
    assert "jw_agent_toolkit.agents" in py
    assert "my_translator = \"my_translator.agent:my_translator\"" in py
    assert "pytest" in py
    assert "ruff" in py


def test_agent_template_emits_module_init(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    init = (out / "src" / "my_translator" / "__init__.py").read_text(encoding="utf-8")
    assert "from my_translator.agent import my_translator" in init
    assert "__version__" in init


def test_agent_template_emits_agent_stub(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    agent = (out / "src" / "my_translator" / "agent.py").read_text(encoding="utf-8")
    assert "async def my_translator(" in agent
    assert "wol.jw.org" in agent  # placeholder citation
    assert "100%" not in agent  # no scope reminder in code


def test_agent_template_emits_tests(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    test_file = (out / "tests" / "test_my_translator.py").read_text(encoding="utf-8")
    assert "async def test_smoke" in test_file
    assert "async def test_contract_shape" in test_file
    assert "async def test_citations_present" in test_file


def test_agent_template_emits_ci(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    ci = (out / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "uv python install 3.13" in ci
    assert "ruff check" in ci
    assert "pytest" in ci


def test_agent_template_emits_makefile(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    mk = (out / "Makefile").read_text(encoding="utf-8")
    assert "uv sync" in mk
    assert "uv run pytest" in mk


def test_agent_template_emits_readme(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "100%" in readme  # scope reminder in README
    assert "Jehovah's Witnesses" in readme


def test_agent_template_emits_gitignore(tmp_path: Path) -> None:
    out = _render_to(tmp_path)
    gi = (out / ".gitignore").read_text(encoding="utf-8")
    assert ".venv/" in gi
    assert "__pycache__/" in gi


def test_agent_template_rejects_existing_target(tmp_path: Path) -> None:
    out = tmp_path / "existing"
    out.mkdir()
    ctx = RenderContext.build(name="existing", type="agent", lang="en")
    with pytest.raises(TargetExistsError):
        render_template(template_type="agent", output_dir=out, ctx=ctx)


def test_agent_template_overwrite_flag(tmp_path: Path) -> None:
    out = tmp_path / "ow"
    out.mkdir()
    ctx = RenderContext.build(name="ow", type="agent", lang="en")
    render_template(template_type="agent", output_dir=out, ctx=ctx, overwrite=True)
    assert (out / "pyproject.toml").exists()
