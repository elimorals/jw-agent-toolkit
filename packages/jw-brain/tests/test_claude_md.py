"""Tests for CLAUDE.md autogen."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_brain.cli import brain_app
from jw_brain.schema.builtins import tj_edge_specs, tj_node_specs
from jw_brain.wiki.claude_md import render_claude_md, write_claude_md

runner = CliRunner()


def test_render_includes_domain_name() -> None:
    body = render_claude_md(domain_name="tj", nodes=tj_node_specs(), edges=tj_edge_specs())
    assert "(domain: tj)" in body


def test_render_lists_all_node_types() -> None:
    body = render_claude_md(domain_name="tj", nodes=tj_node_specs(), edges=tj_edge_specs())
    for name in ("Verse", "Topic", "Publication", "Concept", "Person", "Place"):
        assert f"**{name}**" in body


def test_render_marks_sensitive_edge_type() -> None:
    body = render_claude_md(domain_name="tj", nodes=tj_node_specs(), edges=tj_edge_specs())
    # CONTRADICTS is sensitive=True in builtin TJ.
    assert "CONTRADICTS" in body
    assert "sensitive" in body


def test_render_handles_empty_domain() -> None:
    body = render_claude_md(domain_name="empty", nodes=[], edges=[])
    assert "(none)" in body


def test_render_supports_plugin_duck_typed_specs() -> None:
    """Plugin domains (finance fixture) ship their own spec dataclasses."""

    class _N:
        name = "Transaction"
        canonical_id_pattern = "tx:{date}:{amount}"
        properties = {"date": str, "amount": float}

    class _E:
        name = "PAID_TO"
        sources = ("Transaction",)
        targets = ("Vendor",)
        sensitive = False

    body = render_claude_md(domain_name="finance", nodes=[_N()], edges=[_E()])
    assert "Transaction" in body
    assert "PAID_TO" in body


def test_write_claude_md_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "vault" / "Second-Brain" / "CLAUDE.md"
    write_claude_md(
        target_path=target,
        domain_name="tj",
        nodes=tj_node_specs(),
        edges=tj_edge_specs(),
    )
    assert target.exists()
    assert "Second Brain" in target.read_text(encoding="utf-8")


def test_cli_init_writes_claude_md(tmp_path: Path) -> None:
    """End-to-end: `jw brain init` writes a domain-specific CLAUDE.md."""

    brain = tmp_path / "test-brain"
    result = runner.invoke(brain_app, ["init", "--brain", str(brain), "--domain", "tj"])
    assert result.exit_code == 0
    claude = brain / "vault" / "Second-Brain" / "CLAUDE.md"
    assert claude.exists()
    body = claude.read_text(encoding="utf-8")
    assert "(domain: tj)" in body
    assert "**Verse**" in body
