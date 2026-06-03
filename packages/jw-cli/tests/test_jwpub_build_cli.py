"""F54.4 — `jw jwpub build` CLI tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.jwpub import jwpub_app


def test_jwpub_build_round_trips(tmp_path: Path) -> None:
    """Build .jwpub from a folder of HTML, then inspect with jw jwpub inspect."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "chapter1.html").write_text("<html><body><p>Hello world</p></body></html>")
    (src / "chapter2.html").write_text("<html><body><p>Second chapter</p></body></html>")
    media_dir = src / "chapter1"
    media_dir.mkdir()
    (media_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    out = tmp_path / "ex22.jwpub"
    runner = CliRunner()
    result = runner.invoke(
        jwpub_app,
        [
            "build",
            str(src),
            "--out", str(out),
            "--symbol", "ex22",
            "--title", "Example",
            "--year", "2022",
            "--lang", "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()

    # Round-trip via the parser.
    from jw_core.parsers.jwpub import parse_jwpub

    parsed = parse_jwpub(out)
    assert parsed.symbol == "ex22"
    assert parsed.document_count == 2
    titles = {d.title for d in parsed.documents}
    assert titles == {"chapter1", "chapter2"}
    assert parsed.decrypted_text_available


def test_jwpub_build_empty_folder_fails(tmp_path: Path) -> None:
    """No HTML files → clear error, no output created."""
    out = tmp_path / "empty.jwpub"
    runner = CliRunner()
    result = runner.invoke(
        jwpub_app,
        ["build", str(tmp_path), "--out", str(out), "--symbol", "x", "--title", "x", "--year", "2025"],
    )
    assert result.exit_code != 0
    assert not out.exists()
