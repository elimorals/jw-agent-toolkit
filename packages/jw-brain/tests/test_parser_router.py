"""Tests for parser router."""

from __future__ import annotations

from pathlib import Path

from jw_brain.compiler.parser_router import ParsedRawFile, ParserRouter


def test_router_detects_markdown(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("# Hello\n\nWorld.", encoding="utf-8")
    router = ParserRouter()
    parsed = router.parse(f)
    assert isinstance(parsed, ParsedRawFile)
    assert "Hello" in parsed.text
    assert parsed.mime == "text/markdown"


def test_router_returns_none_for_unknown(tmp_path: Path) -> None:
    f = tmp_path / "bin.xyz"
    f.write_bytes(b"\x00\x01\x02")
    router = ParserRouter()
    assert router.parse(f) is None


def test_router_routes_jwpub_to_jw_core(tmp_path: Path) -> None:
    f = tmp_path / "sample.jwpub"
    f.write_bytes(b"PK\x03\x04stub")
    router = ParserRouter()
    routing = router.detect_route(f)
    assert routing == "jwpub"


def test_router_markdown_produces_chunks(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("first.\n\nsecond.\n\nthird.", encoding="utf-8")
    parsed = ParserRouter().parse(f)
    assert parsed is not None
    assert len(parsed.chunks) == 3
