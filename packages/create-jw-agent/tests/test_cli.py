"""End-to-end CLI tests for create-jw-agent."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from create_jw_agent.cli import app

runner = CliRunner()


def test_cli_help_shows_intro() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Typer pulls the docstring from `main()` when there's a single command.
    assert "jw-agent-toolkit plugin" in result.stdout
    assert "NAME" in result.stdout


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_invalid_name_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["jw-evil", "--type=agent", "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 2


def test_cli_invalid_type_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["my-thing", "--type=bogus", "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 2


def test_cli_invalid_license_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["my-thing", "--license=Evil-1.0", "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 2


def test_cli_generates_agent_project(tmp_path: Path) -> None:
    out = tmp_path / "my-agent-test"
    result = runner.invoke(
        app, ["my-agent-test", "--type=agent", "--output-dir", str(out), "--quiet"],
    )
    assert result.exit_code == 0, result.stdout
    assert (out / "pyproject.toml").exists()
    assert (out / "src" / "my_agent_test" / "agent.py").exists()


def test_cli_target_exists_exits_2(tmp_path: Path) -> None:
    out = tmp_path / "preexisting"
    out.mkdir()
    result = runner.invoke(
        app, ["preexisting", "--type=agent", "--output-dir", str(out)],
    )
    assert result.exit_code == 2


def test_cli_does_not_touch_network_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRITICAL no-network guarantee: without --check-pypi, httpx is never called.

    We monkeypatch httpx.get to raise; if the code calls it, the test fails.
    """

    import httpx

    def boom(*args, **kwargs):
        raise AssertionError("network call without --check-pypi!")

    monkeypatch.setattr(httpx, "get", boom)
    out = tmp_path / "offline-test"
    result = runner.invoke(
        app,
        ["offline-test", "--type=agent", "--output-dir", str(out), "--quiet"],
    )
    assert result.exit_code == 0


def test_cli_check_pypi_calls_httpx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When --check-pypi is set, httpx.get IS called (with a fake response)."""

    import httpx

    calls = []

    class _Resp:
        status_code = 404  # not taken

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        return _Resp()

    monkeypatch.setattr(httpx, "get", fake_get)
    out = tmp_path / "check-test"
    result = runner.invoke(
        app,
        [
            "check-test", "--type=agent",
            "--output-dir", str(out),
            "--check-pypi", "--quiet",
        ],
    )
    assert result.exit_code == 0
    assert any("check-test" in url for url in calls)


def test_cli_lang_es_emits_spanish_tagline(tmp_path: Path) -> None:
    out = tmp_path / "lang-es"
    result = runner.invoke(
        app, ["lang-es", "--type=agent", "--lang=es", "--output-dir", str(out)],
    )
    assert result.exit_code == 0
    assert "testigos de Jehov" in result.stdout
