"""Tests for the symlink-safe path resolution used in /api/run/{id}."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_safe_run_dir_rejects_dotdot(tmp_path: Path) -> None:
    from jw_finetune.monitor.studio import _safe_run_dir
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "../etc")
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "..")


def test_safe_run_dir_rejects_slash(tmp_path: Path) -> None:
    from jw_finetune.monitor.studio import _safe_run_dir
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "subdir/file")
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "/absolute")


def test_safe_run_dir_rejects_empty(tmp_path: Path) -> None:
    from jw_finetune.monitor.studio import _safe_run_dir
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "")
    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "   ")


def test_safe_run_dir_accepts_real_run(tmp_path: Path) -> None:
    from jw_finetune.monitor.studio import _safe_run_dir
    workspace = tmp_path / "workspace"
    run = workspace / "run-20260530-120000"
    run.mkdir(parents=True)
    resolved = _safe_run_dir(workspace, "run-20260530-120000")
    assert resolved.is_dir()
    assert resolved.name == "run-20260530-120000"


def test_safe_run_dir_rejects_symlink_outside(tmp_path: Path) -> None:
    """A symlink inside the workspace that points outside must be rejected."""
    from jw_finetune.monitor.studio import _safe_run_dir
    if os.name == "nt":
        pytest.skip("symlink test requires POSIX")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sym = workspace / "evil"
    sym.symlink_to(outside)

    with pytest.raises(ValueError):
        _safe_run_dir(workspace, "evil")


def test_safe_run_dir_accepts_symlink_inside(tmp_path: Path) -> None:
    """A symlink inside the workspace pointing to ANOTHER place inside the workspace is OK."""
    from jw_finetune.monitor.studio import _safe_run_dir
    if os.name == "nt":
        pytest.skip("symlink test requires POSIX")
    workspace = tmp_path / "workspace"
    real_run = workspace / "real"
    real_run.mkdir(parents=True)
    alias = workspace / "alias"
    alias.symlink_to(real_run)
    resolved = _safe_run_dir(workspace, "alias")
    assert resolved.is_dir()


def test_safe_run_dir_missing_raises_not_found(tmp_path: Path) -> None:
    from jw_finetune.monitor.studio import _safe_run_dir
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(FileNotFoundError):
        _safe_run_dir(workspace, "nonexistent-run")
