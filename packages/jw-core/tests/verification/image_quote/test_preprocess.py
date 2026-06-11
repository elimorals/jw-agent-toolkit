"""Image preprocess + OCR cleanup tests (Fase 70)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from jw_core.verification.image_quote.ocr_cleanup import (
    OCRUnavailableError,
    cleanup_ocr_text,
    ocr_image,
)
from jw_core.verification.image_quote.preprocess import (
    ImagePreprocessError,
    load_image,
)


def _write_test_jpeg(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    img = Image.new("RGB", size, color=(123, 200, 50))
    img.save(path, "JPEG", quality=80)


def test_load_image_returns_pil_and_metadata(tmp_path: Path) -> None:
    p = tmp_path / "x.jpg"
    _write_test_jpeg(p, (64, 32))
    img, meta = load_image(str(p))
    assert img.size == (64, 32)
    assert meta["format"] == "JPEG"
    assert len(meta["phash"]) == 16


def test_load_image_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ImagePreprocessError):
        load_image(str(tmp_path / "missing.jpg"))


def test_phash_is_stable_for_same_content(tmp_path: Path) -> None:
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_test_jpeg(a, (32, 32))
    _write_test_jpeg(b, (32, 32))  # identical content
    _, ma = load_image(str(a))
    _, mb = load_image(str(b))
    assert ma["phash"] == mb["phash"]


def test_cleanup_ocr_collapses_whitespace_and_joins_hyphens() -> None:
    raw = "Atalaya 2024:    compa-\nñero del   reino\n!@\n  Hello  "
    out = cleanup_ocr_text(raw)
    assert "compañero" in out
    assert "  " not in out  # collapsed
    assert "!@" not in out  # punctuation-only line dropped
    assert "Hello" in out


def test_cleanup_ocr_handles_empty_input() -> None:
    assert cleanup_ocr_text("") == ""


def test_ocr_image_raises_when_pytesseract_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pytesseract is not installed, OCRUnavailableError surfaces."""
    import sys

    monkeypatch.setitem(sys.modules, "pytesseract", None)
    img = Image.new("RGB", (8, 8), color="white")
    with pytest.raises(OCRUnavailableError):
        ocr_image(img)
