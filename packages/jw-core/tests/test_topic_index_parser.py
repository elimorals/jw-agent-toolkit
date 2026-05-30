"""Tests for the Watch Tower Publications Index subject-page parser.

Uses real fixtures captured from wol.jw.org (Trinity + Research Guide
landing). Fixtures are checked into the repo so tests run offline.
"""

from pathlib import Path

import pytest
from jw_core.parsers.topic_index import parse_subject_page

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def trinity_html() -> str:
    return (FIXTURES / "wt_pub_index_trinity.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def research_guide_html() -> str:
    return (FIXTURES / "wt_research_guide.html").read_text(encoding="utf-8")


# ── Trinity subject page ────────────────────────────────────────────────


def test_parse_trinity_returns_subject(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200275936")
    assert s is not None
    assert s.title.upper().startswith("TRINITY")
    assert s.docid == "1200275936"


def test_parse_trinity_has_see_also(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    assert s.see_also
    # 'Should You Believe in the Trinity?' or 'Triads' should appear.
    joined = " ".join(s.see_also).lower()
    assert "trinity" in joined or "triads" in joined


def test_parse_trinity_has_many_subheadings(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    assert len(s.subheadings) >= 30


def test_parse_trinity_top_level_subheading_present(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    su = [sh for sh in s.subheadings if sh.is_top_level]
    assert su
    # The first top-level subheading is "ancient non-Christian religions".
    headings = [sh.heading.lower() for sh in su]
    assert any("ancient" in h and "religions" in h for h in headings)


def test_parse_trinity_nested_subvalue_present(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    sv = [sh for sh in s.subheadings if not sh.is_top_level]
    assert sv
    # 'Babylon:' is a nested entry under 'ancient non-Christian religions'.
    assert any(sh.heading.lower() == "babylon" for sh in sv)


def test_parse_trinity_citations_split_correctly(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    # Find a known entry and verify its citations.
    babylon = next((sh for sh in s.subheadings if sh.heading.lower() == "babylon"), None)
    assert babylon is not None
    # Babylon: it-1 237, 974; w13 2/15 9; re 250; ...
    # Expect multiple publication citations.
    pub_cits = [c for c in babylon.citations if c.kind == "publication"]
    assert len(pub_cits) >= 3
    # All citations should have non-empty text.
    assert all(c.text for c in babylon.citations)


def test_parse_trinity_publication_citations_have_urls(trinity_html: str) -> None:
    """Phase 4.5: every publication citation should now have a /pc/ URL."""
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    pub_cits: list = []
    for sh in s.subheadings:
        pub_cits.extend(c for c in sh.citations if c.kind == "publication")
    assert pub_cits, "Expected publication citations across the Trinity page"
    # Sample: every publication citation should have a https://wol.jw.org/.../pc/... URL.
    assert all(c.url and "/pc/" in c.url for c in pub_cits)


def test_parse_trinity_first_pub_citation_well_formed(trinity_html: str) -> None:
    """The first publication code 'g05 4/22 7' should be a clickable URL."""
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    # Find the 'ancient' subheading
    target = next(sh for sh in s.subheadings if "ancient" in sh.heading.lower() and "religion" in sh.heading.lower())
    pub_cits = [c for c in target.citations if c.kind == "publication"]
    assert pub_cits
    # First publication code should be 'g05 4/22 7' (no trailing semicolon).
    assert pub_cits[0].text == "g05 4/22 7"
    assert pub_cits[0].url is not None
    assert pub_cits[0].url.startswith("https://wol.jw.org")


def test_parse_trinity_no_trailing_punctuation_in_citations(trinity_html: str) -> None:
    """Citations text must be clean (no trailing ';' or ',' from the list)."""
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    for sh in s.subheadings:
        for c in sh.citations:
            assert not c.text.endswith((";", ",", ".")), f"Citation text {c.text!r} has trailing punctuation"


def test_parse_trinity_bible_refs_have_urls(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    bible_cits: list = []
    for sh in s.subheadings:
        bible_cits.extend(c for c in sh.citations if c.kind == "bible")
    assert bible_cits, "Expected Bible refs as linked anchors in the Trinity page"
    # Every Bible cit should have a URL.
    assert all(c.url and c.url.startswith("https://wol.jw.org") for c in bible_cits)


def test_parse_total_citations_helper(trinity_html: str) -> None:
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    assert s.total_citations > 100  # Trinity is rich; expect lots of citations


# ── Phase 4.6: article-title-style subject pages ───────────────────────


@pytest.fixture(scope="module")
def religions_html() -> str:
    return (FIXTURES / "wt_pub_index_alt_1204387.html").read_text(encoding="utf-8")


def test_article_title_page_detected(religions_html: str) -> None:
    s = parse_subject_page(religions_html, source_url="x")
    assert s is not None
    assert s.style == "article_title"


def test_article_title_page_has_citations(religions_html: str) -> None:
    """Phase 4.6: previously returned 0 citations; should now return many."""
    s = parse_subject_page(religions_html, source_url="x")
    assert s is not None
    assert s.total_citations > 100


def test_article_title_page_citations_have_urls(religions_html: str) -> None:
    s = parse_subject_page(religions_html, source_url="x")
    assert s is not None
    for sh in s.subheadings[:30]:
        for c in sh.citations:
            assert c.url and c.url.startswith("https://wol.jw.org")


def test_article_title_splits_title_from_publication(religions_html: str) -> None:
    """The 'Timgad' entry should split into title + publication ref."""
    s = parse_subject_page(religions_html, source_url="x")
    assert s is not None
    timgad = next(
        (sh for sh in s.subheadings if "timgad" in sh.heading.lower()),
        None,
    )
    assert timgad is not None
    # Heading is the article title (no 'The Watchtower' suffix).
    assert "watchtower" not in timgad.heading.lower(), f"Heading should be title only; got: {timgad.heading!r}"
    # Citation text retains the publication reference.
    assert timgad.citations
    cit = timgad.citations[0]
    assert "watchtower" in cit.text.lower() or "12/1/2014" in cit.text


def test_trinity_page_remains_trinity_style(trinity_html: str) -> None:
    """Trinity is still classified as 'trinity' style (multi-anchor per p)."""
    s = parse_subject_page(trinity_html, source_url="x")
    assert s is not None
    assert s.style == "trinity"


# ── Research Guide landing page ─────────────────────────────────────────


def test_parse_research_guide_no_crash(research_guide_html: str) -> None:
    """The Research Guide landing is not a subject index per se, but the
    parser should still handle it without crashing — it may have few or no
    subheadings, which is fine."""
    s = parse_subject_page(research_guide_html, source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200277232")
    assert s is not None
    assert s.docid == "1200277232"


# ── Edge cases ─────────────────────────────────────────────────────────


def test_parse_nonsubject_page_returns_none() -> None:
    """An HTML page without <article id='article'> should return None."""
    assert parse_subject_page("<html><body><h1>nope</h1></body></html>") is None


def test_parse_citation_without_colon_uses_full_text() -> None:
    """A paragraph without a colon should treat the whole text as the heading."""
    html = """
    <html><body>
    <article id="article">
      <p class="su">simple heading without colon</p>
    </article>
    </body></html>
    """
    s = parse_subject_page(html)
    assert s is not None
    assert s.subheadings[0].heading == "simple heading without colon"
    assert s.subheadings[0].citations == []
