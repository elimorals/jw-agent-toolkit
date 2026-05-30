"""CLI subprocess tests — invoke `jw ...` as a real binary.

These differ from `test_cli_smoke.py` (which uses Typer's in-process
CliRunner) by actually fork+exec a Python subprocess. That catches
problems CliRunner can't see:

  - Missing `__main__.py` / entry-point misconfiguration
  - Imports that succeed in pytest but break at install time
  - stdout/stderr handling under a real terminal-less environment
  - Exit codes propagating through Typer correctly

These tests don't hit the network (verse / topic-style commands that
require WOL are excluded).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Use `uv run jw` instead of `python -m jw_cli` so the venv resolves
# correctly. `uv run` does its own environment resolution which avoids
# the macOS iCloud `UF_HIDDEN` flag problem on .pth files — provided we
# strip that flag right before invocation (uv itself re-applies it on
# every sync; we never quite win permanently).
_UV = shutil.which("uv")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PTH_DIR = _REPO_ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

_pytestmark_skip_no_uv = pytest.mark.skipif(
    _UV is None,
    reason="`uv` binary not on PATH; cannot run CLI subprocess tests.",
)
pytestmark = _pytestmark_skip_no_uv


def _ensure_pth_visible() -> None:
    """Strip macOS UF_HIDDEN from all .pth files in the venv.

    Idempotent and cheap (~milliseconds). Called before every subprocess.
    """
    if sys.platform != "darwin":
        return
    pth_files = list(_PTH_DIR.glob("*.pth"))
    if pth_files:
        subprocess.run(
            ["chflags", "nohidden", *map(str, pth_files)],
            check=False,
            capture_output=True,
        )


def _run(*args: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Run `uv run --no-sync jw ARGS...` and return the completed process.

    Retries once if the subprocess fails with `No module named 'jw_cli'`
    after re-applying chflags — that error means iCloud re-marked the
    .pth files as hidden during the gap between our chflags call and
    the subprocess start.
    """
    assert _UV is not None
    for attempt in range(2):
        _ensure_pth_visible()
        result = subprocess.run(
            [_UV, "run", "--no-sync", "jw", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=_REPO_ROOT,
        )
        if "No module named 'jw_cli'" not in result.stderr:
            return result
        if attempt == 0:
            # Race with iCloud UF_HIDDEN marking — retry once.
            continue
    return result


# ── Help + global flags ────────────────────────────────────────────────


def test_help_lists_every_command() -> None:
    """`jw --help` exits 0 and mentions every subcommand."""
    result = _run("--help")
    assert result.returncode == 0
    for cmd in ("verse", "search", "daily", "languages", "download", "chapter", "jwpub", "topic"):
        assert cmd in result.stdout, f"missing CLI command in help: {cmd}"


def test_subcommand_help_documents_args() -> None:
    """Every subcommand should respond to --help."""
    for cmd in ("verse", "search", "daily", "chapter", "jwpub", "topic"):
        result = _run(cmd, "--help")
        assert result.returncode == 0, (
            f"`jw {cmd} --help` failed: exit={result.returncode}, stderr={result.stderr[:200]}"
        )


# ── `jw verse` — pure-parser, no network ───────────────────────────────


def test_verse_command_with_valid_reference() -> None:
    """`jw verse 'Juan 3:16'` prints the canonical URL with exit 0."""
    result = _run("verse", "Juan 3:16", "--lang", "es")
    assert result.returncode == 0
    assert "wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3" in result.stdout
    assert "v=43:3:16" in result.stdout


def test_verse_command_english_default_lang() -> None:
    result = _run("verse", "John 3:16")
    assert result.returncode == 0
    # Default lang is 'es' per the verse command's default.
    # Just verify SOME wol URL appears.
    assert "wol.jw.org" in result.stdout


def test_verse_command_unknown_ref_exits_nonzero() -> None:
    result = _run("verse", "gibberish-not-a-ref")
    assert result.returncode == 1
    # Error message should mention no reference detected.
    combined = result.stdout + result.stderr
    assert "No Bible reference" in combined or "no Bible reference" in combined.lower()


def test_verse_command_with_range() -> None:
    result = _run("verse", "1 Co 13:4-7")
    assert result.returncode == 0
    assert "/46/13" in result.stdout  # 1 Corinthians is book 46


# ── `jw chapter` — argument validation, no network if invalid ─────────


def test_chapter_command_rejects_invalid_book_num() -> None:
    """book_num=0 should fail validation before any network call."""
    result = _run("chapter", "0", "1")
    assert result.returncode == 1
    assert "1..66" in result.stdout or "1..66" in result.stderr


def test_chapter_command_rejects_book_num_67() -> None:
    result = _run("chapter", "67", "1")
    assert result.returncode == 1


# ── `jw jwpub` — uses fixture if present, skips cleanly otherwise ──────


def test_jwpub_command_lists_toc_when_file_present() -> None:
    pub_path = Path("data/jwpub_test/ti_E.jwpub")
    if not pub_path.exists():
        return  # silent skip — no fixture in this env
    result = _run("jwpub", str(pub_path), "--max", "3", timeout=60.0)
    assert result.returncode == 0
    assert "Trinity" in result.stdout or "TRINITY" in result.stdout


def test_jwpub_command_rejects_missing_file() -> None:
    """When `path` doesn't exist, Typer's `exists=True` should reject it."""
    result = _run("jwpub", "/nonexistent/path/to/file.jwpub")
    assert result.returncode != 0


# ── Unknown command ────────────────────────────────────────────────────


def test_unknown_command_exits_nonzero() -> None:
    result = _run("totally-not-a-command")
    assert result.returncode != 0
