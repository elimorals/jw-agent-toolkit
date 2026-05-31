from __future__ import annotations


def test_lookup_song_returns_metadata() -> None:
    from jw_mcp.server import lookup_song

    out = lookup_song(number=5, language="es")
    assert out["number"] == 5
    assert "amor" in out["title"].lower() or "amor" in out["theme"].lower()
    assert isinstance(out["scriptures"], list)
    assert isinstance(out["scriptures_resolved"], list)
    assert out["canonical_url"].startswith("https://www.jw.org/")


def test_lookup_song_unknown_returns_error_dict() -> None:
    from jw_mcp.server import lookup_song

    out = lookup_song(number=999, language="en")
    assert "error" in out
    assert "999" in out["error"]
