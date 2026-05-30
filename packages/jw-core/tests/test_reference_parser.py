"""Tests for jw_core.parsers.reference.

Covers: English/Spanish/Portuguese names + abbreviations, verse ranges,
single-chapter books, multiple refs in one string, URL building per language.
"""

import pytest
from jw_core import parse_all_references, parse_reference
from jw_core.parsers.reference import ReferenceParser

# ── English ──────────────────────────────────────────────────────────────


def test_parse_english_full_name() -> None:
    ref = parse_reference("John 3:16")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.book_canonical == "John"
    assert ref.chapter == 3
    assert ref.verse_start == 16
    assert ref.verse_end is None
    assert ref.detected_language == "en"


def test_parse_english_abbreviation() -> None:
    ref = parse_reference("Heb 13:5")
    assert ref is not None
    assert ref.book_num == 58
    assert ref.chapter == 13
    assert ref.verse_start == 5


def test_parse_english_verse_range() -> None:
    ref = parse_reference("Romans 5:1-8")
    assert ref is not None
    assert ref.book_num == 45
    assert ref.verse_start == 1
    assert ref.verse_end == 8


def test_parse_english_chapter_only() -> None:
    ref = parse_reference("Psalm 23")
    assert ref is not None
    assert ref.book_num == 19
    assert ref.chapter == 23
    assert ref.verse_start is None


def test_parse_english_numbered_book() -> None:
    ref = parse_reference("1 Corinthians 13:4")
    assert ref is not None
    assert ref.book_num == 46
    assert ref.chapter == 13
    assert ref.verse_start == 4


def test_parse_english_compact_numbered() -> None:
    """'1Co 13' without space between digit and abbrev."""
    ref = parse_reference("1Co 13:4")
    assert ref is not None
    assert ref.book_num == 46


# ── Spanish ──────────────────────────────────────────────────────────────


def test_parse_spanish_full_name() -> None:
    ref = parse_reference("Juan 3:16")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.book_canonical == "John"
    assert ref.chapter == 3
    assert ref.verse_start == 16
    assert ref.detected_language == "es"


def test_parse_spanish_with_accent() -> None:
    """Accents in input must not break matching."""
    ref = parse_reference("Génesis 1:1")
    assert ref is not None
    assert ref.book_num == 1
    assert ref.chapter == 1
    assert ref.verse_start == 1


def test_parse_spanish_numbered_book() -> None:
    ref = parse_reference("1 Corintios 13:4-7")
    assert ref is not None
    assert ref.book_num == 46
    assert ref.chapter == 13
    assert ref.verse_start == 4
    assert ref.verse_end == 7
    assert ref.detected_language == "es"


def test_parse_spanish_abbreviation_apocalipsis() -> None:
    ref = parse_reference("Ap 21:4")
    assert ref is not None
    assert ref.book_num == 66
    assert ref.chapter == 21


def test_parse_spanish_hechos() -> None:
    """Spanish 'Hechos' (Acts) — different name from English."""
    ref = parse_reference("Hechos 2:38")
    assert ref is not None
    assert ref.book_num == 44


def test_parse_spanish_santiago() -> None:
    """Spanish 'Santiago' (James) — completely different name."""
    ref = parse_reference("Santiago 1:5")
    assert ref is not None
    assert ref.book_num == 59


# ── Portuguese ───────────────────────────────────────────────────────────


def test_parse_portuguese_full_name() -> None:
    ref = parse_reference("João 3:16")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.detected_language == "pt"


def test_parse_portuguese_numbered() -> None:
    """'1 João' is uniquely Portuguese (Spanish is 'Juan', different stem)."""
    ref = parse_reference("1 João 4:8")
    assert ref is not None
    assert ref.book_num == 62
    assert ref.detected_language == "pt"


def test_orthographic_collision_pt_es() -> None:
    """'Coríntios' (pt) and 'Corintios' (es) collide after accent stripping.

    Documented limitation: when a normalized form is registered under multiple
    languages, the first registration wins. A future enhancement could accept a
    `language_hint` to disambiguate. For now the book number is correct, only
    detected_language may be wrong on collisions.
    """
    ref = parse_reference("1 Coríntios 13:4")
    assert ref is not None
    assert ref.book_num == 46
    # detected_language is "es" (first registered) — acceptable since the
    # caller can override with their own language context.


# ── Multiple references ─────────────────────────────────────────────────


def test_parse_multiple_refs() -> None:
    refs = parse_all_references("Juan 3:16 y también Romanos 5:8")
    assert len(refs) == 2
    assert refs[0].book_num == 43
    assert refs[1].book_num == 45


def test_parse_multiple_mixed_languages() -> None:
    refs = parse_all_references("Compare John 3:16 with Juan 3:16")
    assert len(refs) == 2
    assert refs[0].book_num == refs[1].book_num == 43
    assert {r.detected_language for r in refs} == {"en", "es"}


# ── Edge cases ──────────────────────────────────────────────────────────


def test_parse_no_match_returns_none() -> None:
    assert parse_reference("hello world") is None
    assert parse_all_references("nothing biblical here") == []


def test_parse_em_dash_in_range() -> None:
    """Some refs use em-dash or en-dash instead of hyphen."""
    ref = parse_reference("Juan 3:16—18")
    assert ref is not None
    assert ref.verse_start == 16
    assert ref.verse_end == 18


def test_parse_period_as_chapter_verse_separator() -> None:
    """Some traditions write 'Jn 3.16' instead of 'Jn 3:16'."""
    ref = parse_reference("Jn 3.16")
    assert ref is not None
    assert ref.chapter == 3
    assert ref.verse_start == 16


def test_parse_longest_match_wins() -> None:
    """'1 Juan' must not be split into '1' + 'Juan'."""
    ref = parse_reference("1 Juan 4:8")
    assert ref is not None
    assert ref.book_num == 62  # 1 John, not John


# ── URL building ────────────────────────────────────────────────────────


def test_wol_url_english() -> None:
    ref = parse_reference("John 3:16")
    assert ref is not None
    url = ref.wol_url(lang="en")
    assert "wol.jw.org/en/wol/b/r1/lp-e/nwtsty/43/3" in url
    assert "v=43:3:16" in url


def test_wol_url_spanish_uses_r4_and_nwt() -> None:
    """Spanish wol URLs use the r4 resource and the nwt edition (not nwtsty)."""
    ref = parse_reference("Juan 3:16")
    assert ref is not None
    url = ref.wol_url(lang="es")
    assert "wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3" in url


def test_wol_url_portuguese_uses_r5_and_nwt() -> None:
    ref = parse_reference("João 3:16")
    assert ref is not None
    url = ref.wol_url(lang="pt")
    assert "wol.jw.org/pt/wol/b/r5/lp-t/nwt/43/3" in url


def test_wol_url_override_pub() -> None:
    """Callers can force a different Bible edition (e.g. Rbi8 for Spanish Ref Bible)."""
    ref = parse_reference("Juan 3:16")
    assert ref is not None
    url = ref.wol_url(lang="es", pub="Rbi8")
    assert "/Rbi8/43/3" in url


def test_wol_url_chapter_only_no_verse_anchor() -> None:
    ref = parse_reference("Salmo 23")
    assert ref is not None
    url = ref.wol_url(lang="es")
    assert "19/23" in url
    assert "#study" not in url


# ── Display ─────────────────────────────────────────────────────────────


def test_display_with_range() -> None:
    ref = parse_reference("1 Corintios 13:4-7")
    assert ref is not None
    assert ref.display() == "1 Corinthians 13:4-7"


def test_display_chapter_only() -> None:
    ref = parse_reference("Psalm 23")
    assert ref is not None
    assert ref.display() == "Psalms 23"


# ── Parser internals / coverage ─────────────────────────────────────────


def test_singleton_returns_same_instance() -> None:
    from jw_core.parsers.reference import _singleton

    assert _singleton() is _singleton()


def test_all_66_books_indexed() -> None:
    p = ReferenceParser()
    book_nums = {entry[0] for entry in p._index.values()}
    assert book_nums == set(range(1, 67))


@pytest.mark.parametrize(
    "ref_str,expected_book",
    [
        ("Ge 1:1", 1),
        ("Ex 20:3", 2),
        ("Sl 23:1", 19),
        ("Pr 3:5", 20),
        ("Mt 24:14", 40),
        ("Mr 13:32", 41),
        ("Lu 21:1", 42),
        ("Ro 12:2", 45),
        ("Flp 4:13", 50),
        ("1Te 4:16", 52),
        ("2Pe 3:13", 61),
    ],
)
def test_spanish_abbreviation_roundtrip(ref_str: str, expected_book: int) -> None:
    ref = parse_reference(ref_str)
    assert ref is not None, f"Failed to parse: {ref_str!r}"
    assert ref.book_num == expected_book
