"""Extract verse-keyed text from a WOL Bible chapter HTML page.

WOL renders each verse as `<span id="v{book:03}{chapter:03}{verse:03}" ...>`
with a `<sup class="vsNum">` prefix carrying the verse number. We strip the
sup and keep the trailing text. Anything else (footnote markers, cross-ref
boxes) is dropped.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from jw_core.concordance.indexer import NWTChapter

_VERSE_ID_RE = re.compile(r"^v(\d{2})(\d{3})(\d{3})$")


def nwt_chapter_from_html(
    html: str,
    *,
    language: str,
    book_num: int,
    chapter: int,
    url: str | None = None,
    book_name: str = "",
    publication: str = "nwt",
) -> NWTChapter:
    """Parse the chapter HTML and return an `NWTChapter` ready to index."""

    soup = BeautifulSoup(html, "lxml")
    verses: list[tuple[int, str]] = []
    for span in soup.find_all("span", id=_VERSE_ID_RE):
        # Drop the verse-number <sup>, footnote markers, and cross-ref links
        for junk in span.find_all(["sup", "a"], class_=["vsNum", "fn", "xref"]):
            junk.decompose()
        # Some content is wrapped in <p> children — keep the readable text.
        text = span.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        verse_num = int(span["id"][-3:])  # last 3 digits are the verse
        verses.append((verse_num, text))

    return NWTChapter(
        language=language,
        book_num=book_num,
        chapter=chapter,
        verses=verses,
        url=url,
        book_name=book_name,
        publication=publication,
    )
