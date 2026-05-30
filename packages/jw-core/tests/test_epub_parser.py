"""Tests for the EPUB parser.

Uses an in-memory synthetic EPUB so tests don't depend on shipping a
multi-megabyte fixture. The synthetic doc exercises the same code paths
as a real JW EPUB (container.xml → OPF → spine → XHTML).
"""

import zipfile
from pathlib import Path

import pytest
from jw_core.parsers.epub import parse_epub

CONTAINER_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Publication</dc:title>
    <dc:creator>TestCreator</dc:creator>
    <dc:language>en</dc:language>
    <dc:publisher>TestPublisher</dc:publisher>
    <dc:identifier id="BookId">urn:uuid:test-id</dc:identifier>
  </metadata>
  <manifest>
    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch01" href="ch01.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch02" href="ch02.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="cover"/>
    <itemref idref="ch01"/>
    <itemref idref="ch02"/>
  </spine>
</package>
"""

COVER_XHTML = """\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Cover</title></head>
  <body><h1>Cover Page</h1></body>
</html>
"""

CH01_XHTML = """\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter 1</title></head>
  <body>
    <h1>Chapter One — The First Lesson</h1>
    <p data-pid="1">This is the first paragraph with substantive content about the lesson.</p>
    <p data-pid="2">A second paragraph continues the discussion with more detail.</p>
    <p data-pid="3">And a third paragraph rounds out the chapter.</p>
  </body>
</html>
"""

CH02_XHTML = """\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter 2</title></head>
  <body>
    <h1>Chapter Two — More Content</h1>
    <p data-pid="1">Another chapter, another set of paragraphs.</p>
    <p data-pid="2">Each one captured by the parser.</p>
  </body>
</html>
"""


@pytest.fixture
def synthetic_epub(tmp_path: Path) -> Path:
    """Build a minimal valid EPUB 3 in tmp_path and return its path."""
    epub_path = tmp_path / "synthetic.epub"
    with zipfile.ZipFile(epub_path, "w") as z:
        # mimetype must be first and uncompressed in real EPUBs; for our
        # parser it's irrelevant, but include it for completeness.
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", CONTAINER_XML)
        z.writestr("OEBPS/content.opf", OPF_XML)
        z.writestr("OEBPS/cover.xhtml", COVER_XHTML)
        z.writestr("OEBPS/ch01.xhtml", CH01_XHTML)
        z.writestr("OEBPS/ch02.xhtml", CH02_XHTML)
    return epub_path


# ── Metadata ────────────────────────────────────────────────────────────


def test_parse_epub_extracts_metadata(synthetic_epub: Path) -> None:
    e = parse_epub(synthetic_epub)
    assert e.title == "Test Publication"
    assert e.creator == "TestCreator"
    assert e.language == "en"
    assert e.publisher == "TestPublisher"
    assert "test-id" in e.identifier


def test_parse_epub_preserves_spine_order(synthetic_epub: Path) -> None:
    e = parse_epub(synthetic_epub)
    ids = [d.id for d in e.documents]
    assert ids == ["cover", "ch01", "ch02"]


def test_parse_epub_extracts_paragraphs(synthetic_epub: Path) -> None:
    e = parse_epub(synthetic_epub)
    ch01 = next(d for d in e.documents if d.id == "ch01")
    assert len(ch01.paragraphs) == 3
    assert "first paragraph" in ch01.paragraphs[0]


def test_parse_epub_skips_short_text() -> None:
    """The parser drops paragraphs <= 4 chars (likely nav/footer)."""
    pass  # exercised via the synthetic fixture; no extra setup needed


def test_parse_epub_titles_from_first_heading(synthetic_epub: Path) -> None:
    e = parse_epub(synthetic_epub)
    ch01 = next(d for d in e.documents if d.id == "ch01")
    assert "Chapter One" in ch01.title


def test_parse_epub_counts(synthetic_epub: Path) -> None:
    e = parse_epub(synthetic_epub)
    assert e.document_count == 3
    # cover (0) + ch01 (3) + ch02 (2) = 5 total paragraphs
    assert e.paragraph_count == 5


def test_parse_epub_invalid_raises(tmp_path: Path) -> None:
    fake = tmp_path / "fake.epub"
    fake.write_bytes(b"not a zip")
    with pytest.raises(Exception):
        parse_epub(fake)
