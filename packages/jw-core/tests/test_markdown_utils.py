"""Tests for jw_core.integrations.markdown (Phase 20)."""

from __future__ import annotations

import pytest
from jw_core.integrations.markdown import (
    ConversionStats,
    convert_jw_links_in_text,
    convert_jwpub_bible_url,
    convert_jwpub_publication_url,
    linkify_markdown,
    parse_jwlibrary_url,
    render_markdown_link,
    render_verse_block,
)
from jw_core.parsers.reference import parse_reference

# ── parse_jwlibrary_url ─────────────────────────────────────────────────


def test_parse_single_verse() -> None:
    ref = parse_jwlibrary_url("jwlibrary:///finder?bible=43003016&wtlocale=S")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.chapter == 3
    assert ref.verse_start == 16
    assert ref.verse_end is None
    assert ref.detected_language == "es"
    assert ref.book_canonical == "John"


def test_parse_verse_range_same_chapter() -> None:
    ref = parse_jwlibrary_url("jwlibrary:///finder?bible=45008028-45008030")
    assert ref is not None
    assert ref.book_num == 45
    assert ref.verse_start == 28
    assert ref.verse_end == 30


def test_parse_no_wtlocale_defaults_to_en() -> None:
    ref = parse_jwlibrary_url("jwlibrary:///finder?bible=01001001")
    assert ref is not None
    assert ref.detected_language == "en"


def test_parse_publication_url_returns_none() -> None:
    # docid URLs are publications, not Bible refs — out of scope here.
    assert parse_jwlibrary_url("jwlibrary:///finder?docid=1102021201") is None


def test_parse_garbage_returns_none() -> None:
    assert parse_jwlibrary_url("https://example.com") is None
    assert parse_jwlibrary_url("") is None
    assert parse_jwlibrary_url("jwlibrary:///finder?bible=BAD") is None


# ── convert_jwpub_bible_url ─────────────────────────────────────────────


def test_convert_jwpub_bible_single() -> None:
    out = convert_jwpub_bible_url("jwpub://b/43:3:16-43:3:16")
    assert out == "jwlibrary:///finder?bible=43003016"


def test_convert_jwpub_bible_range() -> None:
    out = convert_jwpub_bible_url("jwpub://b/45:8:28-45:8:30")
    assert out == "jwlibrary:///finder?bible=45008028-45008030"


def test_convert_jwpub_bible_multichapter() -> None:
    out = convert_jwpub_bible_url("jwpub://b/40:3:1-40:4:11")
    assert out == "jwlibrary:///finder?bible=40003001-40004011"


def test_convert_jwpub_bible_with_locale_override() -> None:
    out = convert_jwpub_bible_url("jwpub://b/43:3:16-43:3:18", wtlocale="S")
    assert out == "jwlibrary:///finder?bible=43003016-43003018&wtlocale=S"


def test_convert_jwpub_bible_invalid() -> None:
    assert convert_jwpub_bible_url("https://example.com") is None


# ── convert_jwpub_publication_url ───────────────────────────────────────


def test_convert_jwpub_publication_full() -> None:
    out = convert_jwpub_publication_url("jwpub://p/E:1102021201/2")
    assert out == "jwlibrary:///finder?wtlocale=E&docid=1102021201&par=2"


def test_convert_jwpub_publication_no_paragraph() -> None:
    out = convert_jwpub_publication_url("jwpub://p/S:1102021201")
    assert out == "jwlibrary:///finder?wtlocale=S&docid=1102021201"


def test_convert_jwpub_publication_locale_override() -> None:
    # User wants the same docid but in a different language.
    out = convert_jwpub_publication_url("jwpub://p/E:1102021201/2", wtlocale="S")
    assert out == "jwlibrary:///finder?wtlocale=S&docid=1102021201&par=2"


# ── render_markdown_link ────────────────────────────────────────────────


def test_render_link_uses_detected_language_label() -> None:
    ref = parse_reference("Juan 3:16")
    link = render_markdown_link(ref)
    assert link == "[Juan 3:16](jwlibrary:///finder?bible=43003016&wtlocale=S)"


def test_render_link_short_form() -> None:
    ref = parse_reference("Juan 3:16")
    link = render_markdown_link(ref, length="short")
    assert "[Jn 3:16]" in link


def test_render_link_explicit_language_override() -> None:
    ref = parse_reference("Juan 3:16")
    link = render_markdown_link(ref, language="en", length="long")
    assert link.startswith("[John 3:16]")
    assert "wtlocale=E" in link


def test_render_link_custom_text() -> None:
    ref = parse_reference("Juan 3:16")
    link = render_markdown_link(ref, text="el versículo más conocido")
    assert link.startswith("[el versículo más conocido]")


def test_render_link_range() -> None:
    ref = parse_reference("Romanos 8:28-30")
    link = render_markdown_link(ref, language="es")
    assert link == "[Rom. 8:28-30](jwlibrary:///finder?bible=45008028-45008030&wtlocale=S)"


# ── linkify_markdown ────────────────────────────────────────────────────


def test_linkify_single_reference() -> None:
    r = linkify_markdown("Lee Juan 3:16 hoy.", language="es")
    assert r.converted == 1
    assert "[Juan 3:16](jwlibrary://" in r.text


def test_linkify_handles_accents_correctly() -> None:
    # The parser normalizes accents; offset mapping must restore them.
    r = linkify_markdown("Génesis 1:1 dice...", language="es")
    assert r.converted == 1
    assert "[Génesis 1:1](" in r.text  # accent preserved


def test_linkify_skips_existing_markdown_links() -> None:
    r = linkify_markdown(
        "[Juan 3:16](jwlibrary:///finder?bible=43003016) y nada más.",
        language="es",
    )
    assert r.converted == 0
    assert r.skipped_already_linked == 1


def test_linkify_skips_existing_non_jwlibrary_links() -> None:
    # If user already linked it to anything else, leave it alone.
    r = linkify_markdown(
        "[Juan 3:16](https://example.com/john-3) y nada más.",
        language="es",
    )
    assert r.converted == 0


def test_linkify_ignores_inline_code() -> None:
    r = linkify_markdown(
        "Esto `Juan 3:16` está en código.",
        language="es",
    )
    assert r.converted == 0


def test_linkify_ignores_fenced_code() -> None:
    text = "Antes\n```\nNo tocar Mateo 5:3\n```\nDespués Juan 1:1."
    r = linkify_markdown(text, language="es")
    assert r.converted == 1
    assert "No tocar Mateo 5:3" in r.text
    assert "[Juan 1:1]" in r.text


def test_linkify_multiple_references_in_one_line() -> None:
    r = linkify_markdown(
        "Compara Génesis 1:1 con Apocalipsis 21:1.",
        language="es",
    )
    assert r.converted == 2


def test_linkify_empty_input() -> None:
    r = linkify_markdown("", language="es")
    assert r.converted == 0
    assert r.text == ""


def test_linkify_no_references() -> None:
    r = linkify_markdown("Texto sin referencias bíblicas.", language="es")
    assert r.converted == 0
    assert r.text == "Texto sin referencias bíblicas."


def test_linkify_result_to_dict() -> None:
    r = linkify_markdown("Juan 3:16", language="es")
    d = r.to_dict()
    assert d["converted"] == 1
    assert "text" in d


# ── convert_jw_links_in_text ────────────────────────────────────────────


def test_convert_jw_links_bible_and_publication() -> None:
    text = "Vid [Mat 5:1](jwpub://b/40:5:1-40:5:1) y [WT](jwpub://p/E:1102021201/2)."
    out = convert_jw_links_in_text(text)
    assert out.bible_converted == 1
    assert out.publication_converted == 1
    assert "jwpub://" not in out.text
    assert "[Mat 5:1](jwlibrary:///finder?bible=40005001)" in out.text


def test_convert_jw_links_bible_only_filter() -> None:
    text = "[A](jwpub://b/40:5:1-40:5:1) [B](jwpub://p/E:123)"
    out = convert_jw_links_in_text(text, kind="bible")
    assert out.bible_converted == 1
    assert out.publication_converted == 0
    assert "jwpub://p/" in out.text  # not touched


def test_convert_jw_links_publication_only_filter() -> None:
    text = "[A](jwpub://b/40:5:1-40:5:1) [B](jwpub://p/E:123)"
    out = convert_jw_links_in_text(text, kind="publication")
    assert out.publication_converted == 1
    assert "jwpub://b/" in out.text  # not touched


def test_convert_jw_links_skips_other_links() -> None:
    text = "[Web](https://example.com)"
    out = convert_jw_links_in_text(text)
    assert out.bible_converted == 0
    assert out.publication_converted == 0
    assert out.untouched == 1


def test_convert_jw_links_idempotent() -> None:
    # Already-converted text should pass through unchanged.
    text = "[J](jwlibrary:///finder?bible=43003016)"
    out = convert_jw_links_in_text(text)
    assert out.text == text


def test_conversion_stats_to_dict() -> None:
    stats = ConversionStats(text="x", bible_converted=2, publication_converted=1)
    d = stats.to_dict()
    assert d["total_converted"] == 3


# ── render_verse_block ──────────────────────────────────────────────────


def test_render_callout_with_body() -> None:
    ref = parse_reference("Juan 3:16")
    out = render_verse_block(ref, "Porque tanto amó Dios al mundo.", template="callout")
    assert out.startswith("> [!quote] [Juan 3:16](")
    assert out.endswith("> Porque tanto amó Dios al mundo.")


def test_render_callout_collapsed() -> None:
    ref = parse_reference("Juan 3:16")
    out = render_verse_block(ref, "abc", template="callout-collapsed")
    assert "[!quote]-" in out


def test_render_blockquote() -> None:
    ref = parse_reference("Juan 3:16")
    out = render_verse_block(ref, "abc", template="blockquote")
    assert out.startswith("> [")
    assert "\n>\n> abc" in out


def test_render_link_template_no_body() -> None:
    ref = parse_reference("Juan 3:16")
    out = render_verse_block(ref, template="link")
    # Just the link when there's no verse text.
    assert out.startswith("[Juan 3:16](")
    assert ">" not in out


def test_render_plain() -> None:
    ref = parse_reference("Juan 3:16")
    out = render_verse_block(ref, "Hello", template="plain")
    assert "(jwlibrary://" not in out
    assert "Hello" in out


def test_render_unknown_template_raises() -> None:
    ref = parse_reference("Juan 3:16")
    with pytest.raises(ValueError):
        render_verse_block(ref, "x", template="weird-template")  # type: ignore[arg-type]
