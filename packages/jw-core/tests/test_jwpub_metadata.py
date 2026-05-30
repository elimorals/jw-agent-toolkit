"""Tests for the JWPUB metadata-only parser.

We build a synthetic JWPUB (outer ZIP + inner ZIP + SQLite with Document
rows but encrypted-looking Content blobs) so the test runs offline.
"""

import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest
from jw_core.parsers.jwpub import JwpubError, parse_jwpub_metadata


def _build_synthetic_jwpub(dst: Path) -> None:
    """Build a minimal JWPUB-shaped file at `dst`."""
    # 1. Build the inner SQLite DB.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE Document (
                DocumentId INTEGER, MepsDocumentId INTEGER, PublicationId INTEGER,
                MepsLanguageIndex INTEGER, Class TEXT, Type INTEGER,
                SectionNumber INTEGER, ChapterNumber INTEGER,
                Title TEXT, TitleRich TEXT, TocTitle TEXT, TocTitleRich TEXT,
                ContextTitle TEXT, ContextTitleRich TEXT,
                FeatureTitle TEXT, FeatureTitleRich TEXT,
                Subtitle TEXT, SubtitleRich TEXT,
                FeatureSubtitle TEXT, FeatureSubtitleRich TEXT,
                Content BLOB,
                FirstFootnoteId INTEGER, LastFootnoteId INTEGER,
                FirstBibleCitationId INTEGER, LastBibleCitationId INTEGER,
                ParagraphCount INTEGER, HasMediaLinks INTEGER, HasLinks INTEGER,
                FirstPageNumber INTEGER, LastPageNumber INTEGER,
                ContentLength INTEGER, PreferredPresentation INTEGER
            )
            """
        )
        rows = [
            (
                0,
                100,
                1,
                0,
                "18",
                0,
                0,
                None,
                "Title Page",
                None,
                "Title Page",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                b"\x01\x02\x03\x04",
                None,
                None,
                None,
                None,
                5,
                0,
                0,
                1,
                2,
                100,
                None,
            ),
            (
                1,
                101,
                1,
                0,
                "11",
                0,
                0,
                1,
                "Chapter 1",
                None,
                "Chapter 1",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                b"\x05\x06\x07\x08",
                None,
                None,
                None,
                None,
                20,
                0,
                0,
                3,
                10,
                500,
                None,
            ),
            (
                2,
                102,
                1,
                0,
                "11",
                0,
                0,
                2,
                "Chapter 2",
                None,
                "Chapter 2",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                b"\x09\x0a\x0b\x0c",
                None,
                None,
                None,
                None,
                15,
                0,
                0,
                11,
                18,
                380,
                None,
            ),
        ]
        conn.executemany("INSERT INTO Document VALUES (" + ",".join("?" * 32) + ")", rows)
        conn.commit()
        conn.close()
        db_bytes = db_path.read_bytes()
    finally:
        db_path.unlink(missing_ok=True)

    # 2. Wrap in inner ZIP ("contents").
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as inner:
        inner.writestr("test_E.db", db_bytes)
    inner_bytes = inner_buf.getvalue()

    # 3. Wrap in outer ZIP (the actual .jwpub file).
    manifest = {
        "hash": "abc123",
        "contentFormat": "z-a",
        "publication": {
            "title": "Test Publication",
            "shortTitle": "Test",
            "symbol": "test",
            "language": 0,
            "publicationType": "Brochure",
            "year": 2024,
            "schemaVersion": 8,
        },
    }
    with zipfile.ZipFile(dst, "w") as outer:
        outer.writestr("manifest.json", json.dumps(manifest))
        outer.writestr("contents", inner_bytes)


@pytest.fixture
def synthetic_jwpub(tmp_path: Path) -> Path:
    pub = tmp_path / "test_E.jwpub"
    _build_synthetic_jwpub(pub)
    return pub


def test_parse_jwpub_metadata_basic(synthetic_jwpub: Path) -> None:
    m = parse_jwpub_metadata(synthetic_jwpub)
    assert m.title == "Test Publication"
    assert m.symbol == "test"
    assert m.publication_type == "Brochure"
    assert m.year == 2024
    assert m.manifest_hash == "abc123"


def test_parse_jwpub_metadata_documents(synthetic_jwpub: Path) -> None:
    m = parse_jwpub_metadata(synthetic_jwpub)
    assert m.document_count == 3
    assert len(m.documents) == 3
    assert m.documents[1].title == "Chapter 1"
    assert m.documents[1].chapter_number == 1
    assert m.documents[1].paragraph_count == 20
    assert m.documents[1].content_length == 500


def test_parse_jwpub_metadata_reports_no_text(synthetic_jwpub: Path) -> None:
    """parse_jwpub_metadata (no decryption flag) always reports False."""
    m = parse_jwpub_metadata(synthetic_jwpub)
    assert m.decrypted_text_available is False


# ── Phase 5.5: decryption (synthetic + live) ────────────────────────────


def test_compute_key_iv_known_publication() -> None:
    """Trinity brochure: lang=0, symbol='ti', year=1989 → known key/iv."""
    from jw_core.parsers.jwpub import _compute_key_iv

    key, iv = _compute_key_iv(0, "ti", 1989, 0)
    # These were verified against the actual ti_E.jwpub blob during dev.
    assert key.hex() == "84d116c26a45e6bff27bf8c4ae44202d"
    assert iv.hex() == "a9e6c7f8cd56171bd645ab5ce61c9b0d"


def test_compute_key_iv_with_issue_number() -> None:
    """When issue_tag_number != 0, it's appended to the pub string."""
    from jw_core.parsers.jwpub import _compute_key_iv

    k1, _ = _compute_key_iv(0, "w", 2024, 0)
    k2, _ = _compute_key_iv(0, "w", 2024, 4)
    # Different issue → different key (proves the issue is part of the input)
    assert k1 != k2


def test_parse_jwpub_live_ti_brochure() -> None:
    """End-to-end decryption against the Trinity brochure on disk."""
    from jw_core.parsers.jwpub import parse_jwpub

    pub_path = Path("data/jwpub_test/ti_E.jwpub")
    if not pub_path.exists():
        pytest.skip(f"{pub_path} not downloaded; run scripts/download_jwpub.py")
    pub = parse_jwpub(pub_path)
    assert pub.decrypted_text_available is True
    assert pub.title == "Should You Believe in the Trinity?"
    # First document is the title page — its decrypted text should be
    # the page-number/title block, not raw ciphertext bytes.
    doc0 = pub.documents[0]
    assert "<p" in doc0.text  # XHTML
    assert doc0.content_length == len(doc0.text)  # declared == actual
    # Foreword (doc 2) is real prose — should mention "people" early.
    foreword = pub.documents[2]
    assert "people" in foreword.text.lower()
    # Paragraphs should be populated for non-trivial documents.
    has_paragraphs = sum(1 for d in pub.documents if d.paragraphs)
    assert has_paragraphs >= 5


def test_parse_jwpub_invalid_file_raises(tmp_path: Path) -> None:
    fake = tmp_path / "fake.jwpub"
    fake.write_bytes(b"not a jwpub")
    with pytest.raises(JwpubError):
        parse_jwpub_metadata(fake)
