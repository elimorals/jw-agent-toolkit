"""Tests for jw_brain.server second_brain_* implementations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_brain.config import write_default_config
from jw_brain.server import (
    second_brain_compile,
    second_brain_lint,
    second_brain_query,
    second_brain_snapshot,
    second_brain_status,
)


def _bootstrap_brain(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    (brain / "raw" / "inbox").mkdir(parents=True)
    (brain / "raw" / "processed").mkdir(parents=True)
    (brain / "graph").mkdir(parents=True)
    (brain / "vault" / ".obsidian").mkdir(parents=True)
    write_default_config(brain, domain="tj")
    return brain


async def test_status_returns_structured_dict(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    out = await second_brain_status(str(brain))
    assert out["brain"] == str(brain)
    assert out["graph"]["n_nodes"] == 0
    assert out["raw"]["pending"] == 0


async def test_compile_dry_run_does_not_mutate(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    out = await second_brain_compile(str(brain), dry_run=True)
    assert out["dry_run"] is True
    status = await second_brain_status(str(brain))
    assert status["graph"]["n_nodes"] == 0


async def test_compile_processes_md_file(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    (brain / "raw" / "inbox" / "note.md").write_text("Juan 3:16", encoding="utf-8")
    out = await second_brain_compile(str(brain))
    assert out["n_files_processed"] == 1
    assert not (brain / "raw" / "inbox" / "note.md").exists()
    assert (brain / "raw" / "processed" / "note.md").exists()


async def test_query_returns_strategy(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    out = await second_brain_query(str(brain), "Explica Juan 3:16")
    assert out["strategy"] in {"wiki_first", "graph_first", "vector_fallback"}


async def test_lint_returns_orphan_count(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    out = await second_brain_lint(str(brain))
    assert out["orphan_count"] == 0


async def test_snapshot_creates_tarball(tmp_path: Path) -> None:
    brain = _bootstrap_brain(tmp_path)
    out = await second_brain_snapshot(str(brain), label="t1")
    snap = Path(out["snapshot"])
    assert snap.exists()
    assert snap.suffix == ".tar"
