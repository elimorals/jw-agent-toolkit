"""Tests for the NWT chapter HTML extractor."""

from __future__ import annotations

from jw_core.concordance.nwt_ingest import nwt_chapter_from_html

_HTML_FIXTURE = """
<div id="bibleText">
  <span id="v43003015" class="v">
    <sup class="vsNum">15</sup>
    Para que todo el que ejerce fe en él tenga vida eterna.
  </span>
  <span id="v43003016" class="v">
    <sup class="vsNum">16</sup>
    Porque tanto amó Dios al mundo que dio a su Hijo unigénito.
  </span>
</div>
"""


def test_nwt_chapter_from_html_extracts_verses() -> None:
    chapter = nwt_chapter_from_html(
        _HTML_FIXTURE,
        language="es",
        book_num=43,
        chapter=3,
        url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
        book_name="Juan",
    )
    assert chapter.book_num == 43
    assert chapter.chapter == 3
    assert len(chapter.verses) == 2
    assert chapter.verses[0][0] == 15
    assert "ejerce fe" in chapter.verses[0][1]
    assert chapter.source_id() == "nwt:es:43:3"


def test_nwt_chapter_from_html_handles_empty() -> None:
    chapter = nwt_chapter_from_html(
        "<div></div>",
        language="en",
        book_num=1,
        chapter=1,
    )
    assert chapter.verses == []
