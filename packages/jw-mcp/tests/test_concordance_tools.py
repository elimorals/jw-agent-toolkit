"""Tests for the concordance MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_mcp.tools.concordance import concordance_build_index_tool, concordance_search_tool

from tests.fixtures.concordance import build_minimal_epub  # type: ignore[import-not-found]


def test_build_index_tool_returns_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "x.epub",
        title="Demo",
        paragraphs=["one line", "another"],
    )
    out = concordance_build_index_tool(paths=[str(epub)], language="en")
    assert out["inserted"] == 2
    assert "error" not in out


def test_search_tool_returns_hits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    epub = build_minimal_epub(
        tmp_path / "x.epub",
        title="Demo",
        paragraphs=["the kingdom of God is at hand"],
    )
    concordance_build_index_tool(paths=[str(epub)], language="en")
    hits = concordance_search_tool(query='"kingdom of God"', language="en", max_results=10)
    assert hits["hits"]
    assert hits["hits"][0]["ref"]


def test_search_tool_rejects_regex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_CONCORDANCE_DB", str(tmp_path / "c.db"))
    out = concordance_search_tool(query=r"\bx\b")
    assert "error" in out
