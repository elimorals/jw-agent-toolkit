"""Tests for ObsidianWikiWriter."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter, WriteOutsideNamespaceError


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def test_writer_rejects_path_outside_namespace(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    with pytest.raises(WriteOutsideNamespaceError):
        writer.write_page("../escape.md", body="x", frontmatter={})


def test_writer_creates_page_with_frontmatter(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.write_page(
        "verses/Juan_3_16.md",
        body="Texto del versículo.",
        frontmatter={"node_type": "Verse", "canonical_id": "verse:43:3:16"},
    )
    p = vault / "Second-Brain" / "verses" / "Juan_3_16.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "node_type: Verse" in text
    assert "Texto del versículo." in text


def test_writer_respects_human_edited_flag(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.write_page("verses/v.md", body="v1", frontmatter={"node_type": "Verse"})

    p = vault / "Second-Brain" / "verses" / "v.md"
    p.write_text(
        "---\nnode_type: Verse\nhuman_edited: true\n---\n\nHuman version.\n",
        encoding="utf-8",
    )

    writer.write_page("verses/v.md", body="agent v2", frontmatter={"node_type": "Verse"})
    out = p.read_text(encoding="utf-8")
    assert "Human version." in out
    assert "agent v2" not in out


def test_writer_appends_to_log(tmp_path: Path) -> None:
    vault = _make_vault(tmp_path)
    writer = ObsidianWikiWriter(vault_path=vault, namespace="Second-Brain")
    writer.append_log("compile", {"files": 3, "nodes_new": 12})
    log = (vault / "Second-Brain" / "log.md").read_text(encoding="utf-8")
    assert "compile" in log
    assert "files: 3" in log


def test_writer_rejects_vault_without_obsidian_marker(tmp_path: Path) -> None:
    vault = tmp_path / "no_marker"
    vault.mkdir()
    with pytest.raises(ValueError, match=".obsidian"):
        ObsidianWikiWriter(vault_path=vault)
