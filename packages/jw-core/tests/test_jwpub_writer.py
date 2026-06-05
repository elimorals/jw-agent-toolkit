"""F49 — round-trip tests for the JWPUB writer.

Verify that `JwpubBuilder` produces a `.jwpub` that:
  1. Opens with `parse_jwpub_metadata` and reports the expected metadata.
  2. Opens with `parse_jwpub` and decrypts back to the exact content we wrote.
  3. Includes media in the inner ZIP.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_core.jwpub_crypto import compute_key_iv, decrypt_blob, encrypt_blob
from jw_core.parsers.jwpub import parse_jwpub, parse_jwpub_metadata
from jw_core.writers.jwpub import JwpubBuilder


def test_crypto_round_trip() -> None:
    """encrypt_blob → decrypt_blob is the identity for valid content."""
    key, iv = compute_key_iv(0, "ex22", 2022)
    content = "<html><body><p data-pid='1'>Hola mundo</p></body></html>"
    blob = encrypt_blob(content, key, iv)
    back = decrypt_blob(blob, key, iv)
    assert back == content


def test_builder_metadata(tmp_path: Path) -> None:
    """Built `.jwpub` exposes the expected publication metadata."""
    builder = JwpubBuilder(
        symbol="ex22",
        title="Example Publication",
        year=2022,
        meps_language_index=0,
    )
    builder.add_document(title="Chapter 1", content="<html><body><p>One</p></body></html>")
    out = builder.build(tmp_path / "ex22.jwpub")

    meta = parse_jwpub_metadata(out)
    assert meta.symbol == "ex22"
    assert meta.title == "Example Publication"
    assert meta.year == 2022
    assert meta.language_index == 0
    assert meta.document_count == 1
    assert meta.schema_version == 8


def test_builder_decrypts_back_to_original(tmp_path: Path) -> None:
    """Documents written via the builder must decrypt to the exact same text."""
    docs = [
        ("Doc A", "<html><body><p data-pid='1'>Alpha content here.</p></body></html>"),
        ("Doc B", "<html><body><p data-pid='2'>Beta content slightly longer.</p></body></html>"),
    ]
    builder = JwpubBuilder(symbol="rt23", title="Round-Trip", year=2023, meps_language_index=0)
    for title, content in docs:
        builder.add_document(title=title, content=content)
    out = builder.build(tmp_path / "rt23.jwpub")

    parsed = parse_jwpub(out)
    assert parsed.decrypted_text_available
    assert len(parsed.documents) == 2
    for doc, (expected_title, expected_content) in zip(parsed.documents, docs, strict=True):
        assert doc.title == expected_title
        # The decrypted blob is the full XHTML we wrote in.
        assert doc.text == expected_content


def test_builder_bundles_media(tmp_path: Path) -> None:
    """Media files registered via add_media end up in the inner ZIP."""
    img_path = tmp_path / "cover.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")  # JPEG magic; content doesn't matter

    builder = JwpubBuilder(symbol="im24", title="Image Pub", year=2024, meps_language_index=0)
    builder.add_document(title="Cover Doc", content="<html><body><p>see image</p></body></html>", media=[img_path])
    out = builder.build(tmp_path / "im24.jwpub")

    import zipfile

    with zipfile.ZipFile(out) as outer:
        with outer.open("contents") as f:
            inner_bytes = f.read()
    with zipfile.ZipFile(__import__("io").BytesIO(inner_bytes)) as inner:
        names = inner.namelist()
    assert "cover.jpg" in names
    assert "im24.db" in names


def test_builder_handles_issue_tag_number(tmp_path: Path) -> None:
    """Issue-tagged publications (e.g. Watchtower) must derive the right key."""
    builder = JwpubBuilder(
        symbol="w22",
        title="The Watchtower (2022, no. 6)",
        year=2022,
        meps_language_index=1,
        issue_tag_number=20220600,
    )
    builder.add_document(title="Article 1", content="<html><body><p>watchtower body</p></body></html>")
    out = builder.build(tmp_path / "w22.jwpub")

    parsed = parse_jwpub(out)
    assert parsed.decrypted_text_available
    assert parsed.documents[0].text.endswith("watchtower body</p></body></html>")


@pytest.mark.parametrize("content_length", [10, 100, 1000, 10_000])
def test_builder_handles_various_content_sizes(tmp_path: Path, content_length: int) -> None:
    """Padding/encryption must handle inputs from tiny to large.

    The PKCS7 padding (16 - len % 16) is the boundary-sensitive part —
    parameterizing across sizes guards against an off-by-one when the
    deflated size happens to be a multiple of 16.
    """
    payload = "<html><body><p>" + ("x" * content_length) + "</p></body></html>"
    builder = JwpubBuilder(symbol=f"sz{content_length}", title="size test", year=2025, meps_language_index=0)
    builder.add_document(title="doc", content=payload)
    out = builder.build(tmp_path / f"sz{content_length}.jwpub")

    parsed = parse_jwpub(out)
    assert parsed.documents[0].text == payload
