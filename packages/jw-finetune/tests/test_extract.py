"""Tests for ParagraphRecord extraction from JWPUB / EPUB."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_finetune.data.extract import (
    _derive_pub_code_from_title,
    _infer_kind_from_pub_code,
    extract_from_epub,
    extract_from_jwpub,
)


def test_kind_inference_watchtower() -> None:
    assert _infer_kind_from_pub_code("w24") == "watchtower"
    assert _infer_kind_from_pub_code("wp23") == "watchtower"
    assert _infer_kind_from_pub_code("ws24") == "watchtower"


def test_kind_inference_awake() -> None:
    assert _infer_kind_from_pub_code("g") == "awake"
    assert _infer_kind_from_pub_code("g23") == "awake"


def test_kind_inference_book() -> None:
    assert _infer_kind_from_pub_code("lff") == "book"
    assert _infer_kind_from_pub_code("jy") == "book"
    assert _infer_kind_from_pub_code("sjj") == "book"
    assert _infer_kind_from_pub_code("rr") == "book"


def test_kind_inference_bible() -> None:
    assert _infer_kind_from_pub_code("nwt") == "bible"


def test_kind_inference_unknown() -> None:
    assert _infer_kind_from_pub_code("foo") == "other"
    assert _infer_kind_from_pub_code("") == "other"


def test_derive_pub_code_es() -> None:
    assert _derive_pub_code_from_title("Atalaya — Edición de Estudio 2024") == "w"
    assert _derive_pub_code_from_title("¡Despertad! 2024") == "g"
    assert _derive_pub_code_from_title("Libro de algo") == "book"
    assert _derive_pub_code_from_title("") == "unknown"


def test_extract_from_jwpub_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(extract_from_jwpub(tmp_path / "missing.jwpub", language_hint="es"))


def test_extract_from_epub_missing_file_raises(tmp_path: Path) -> None:
    """parse_epub should raise on missing/invalid file; we want that surfaced."""
    fake = tmp_path / "missing.epub"
    fake.write_text("not a real epub")
    with pytest.raises(Exception):
        list(extract_from_epub(fake, language_hint="es"))
