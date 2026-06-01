"""End-to-end: spawn pytest in a subprocess against a tmp cookbook tree."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_pytest(cookbook_dir: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "pytest",
            f"--cookbook-dir={cookbook_dir}",
            str(cookbook_dir),
            "-q", "--no-header",
            *extra_args,
        ],
        capture_output=True, text=True,
    )


def test_passes_when_block_is_valid(tmp_path: Path) -> None:
    md = tmp_path / "01-recipe.md"
    md.write_text(
        "```python\n"
        "# test\n"
        "x = 1 + 1\n"
        "assert x == 2\n"
        "```\n",
        encoding="utf-8",
    )
    result = _run_pytest(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_fails_when_block_raises(tmp_path: Path) -> None:
    md = tmp_path / "02-failing.md"
    md.write_text(
        "```python\n"
        "# test\n"
        "assert False, 'on purpose'\n"
        "```\n",
        encoding="utf-8",
    )
    result = _run_pytest(tmp_path)
    assert result.returncode != 0
    assert "1 failed" in result.stdout


def test_skip_until_fase_marker_skips(tmp_path: Path) -> None:
    md = tmp_path / "03-future.md"
    md.write_text(
        "```python\n"
        "# test skip-until-fase=99\n"
        "from nonexistent import thing  # would fail if executed\n"
        "```\n",
        encoding="utf-8",
    )
    result = _run_pytest(tmp_path)
    assert "1 skipped" in result.stdout


def test_block_without_marker_is_ignored(tmp_path: Path) -> None:
    md = tmp_path / "04-noop.md"
    md.write_text(
        "```python\n"
        "print('would crash if executed: ' + 1)  # type error\n"
        "```\n",
        encoding="utf-8",
    )
    result = _run_pytest(tmp_path)
    # No tests collected, pytest exits with code 5 ("no tests collected")
    # but should not fail with the type error.
    assert "TypeError" not in result.stdout
