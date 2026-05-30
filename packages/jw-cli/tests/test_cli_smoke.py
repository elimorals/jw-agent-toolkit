"""Smoke tests for the CLI — no network, just verb routing and parser plumbing."""

from typer.testing import CliRunner

from jw_cli.main import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("verse", "search", "daily", "languages", "download", "chapter", "jwpub", "topic"):
        assert cmd in result.stdout, f"missing CLI command: {cmd}"


def test_verse_command_known_ref() -> None:
    result = runner.invoke(app, ["verse", "Juan 3:16", "--lang", "es"])
    assert result.exit_code == 0
    assert "wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3" in result.stdout


def test_verse_command_unknown_ref_exits_nonzero() -> None:
    result = runner.invoke(app, ["verse", "hello world"])
    assert result.exit_code == 1


def test_chapter_command_validates_book_num() -> None:
    result = runner.invoke(app, ["chapter", "0", "1"])
    assert result.exit_code == 1
