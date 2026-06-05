"""Port a Python del `BibleRef.fromWolUrl` que vive en jw-core-js.
Reusa el fixture cross-lang shared/ para garantizar parity con TS."""

from jw_core.models import BibleRef
from jw_core.parsers.wol_url import parse_wol_bible_url


def test_parse_wol_url_genesis_1_1_en():
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/1/1#study=discover&v=1:1:1")
    assert ref is not None
    assert ref.book_num == 1
    assert ref.chapter == 1
    assert ref.verse_start == 1
    assert ref.verse_end == 1


def test_parse_wol_url_john_3_16_en():
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/43/3#study=discover&v=43:3:16")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.chapter == 3
    assert ref.verse_start == 16


def test_parse_wol_url_es_pt_locales():
    ref_es = parse_wol_bible_url("/es/wol/b/r4/lp-s/nwt/1/1#study=discover&v=1:1:1")
    ref_pt = parse_wol_bible_url("/pt/wol/b/r5/lp-t/nwt/1/1#study=discover&v=1:1:1")
    assert ref_es is not None and ref_es.book_num == 1
    assert ref_pt is not None and ref_pt.book_num == 1


def test_parse_wol_url_no_verse_anchor():
    """Sin anchor v= solo capítulo se reconoce."""
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/1/1")
    assert ref is not None
    assert ref.book_num == 1 and ref.chapter == 1
    assert ref.verse_start is None


def test_parse_wol_url_non_bible_returns_none():
    """URLs no-bíblicas (publicaciones, daily-text) devuelven None."""
    assert parse_wol_bible_url("/en/wol/d/r1/lp-e/1200002342") is None
    assert parse_wol_bible_url("/en/wol/dt/r1/lp-e/2024/1/1") is None
    assert parse_wol_bible_url("") is None
    assert parse_wol_bible_url("not-a-url") is None


def test_biberef_from_wol_url_classmethod():
    """El classmethod en BibleRef delega al parser."""
    ref = BibleRef.from_wol_url("/en/wol/b/r1/lp-e/nwtsty/43/3#study=discover&v=43:3:16")
    assert ref is not None
    assert ref.book_canonical == "John"
