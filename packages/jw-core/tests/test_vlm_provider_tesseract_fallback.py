from __future__ import annotations

import warnings
from pathlib import Path

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.tesseract_fallback import TesseractFallbackProvider


def test_emits_deprecation_warning(tmp_path: Path, monkeypatch) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    def fake_ocr(image_path, *, language="eng"):  # noqa: ARG001
        return "Some OCR text"

    monkeypatch.setattr(
        "jw_core.vision.vlm_providers.tesseract_fallback.ocr_image", fake_ocr
    )
    # also force _probe to return True so is_available reports True even if
    # pytesseract isn't installed.
    monkeypatch.setattr(
        "jw_core.vision.vlm_providers.tesseract_fallback._probe", lambda: True
    )
    p = TesseractFallbackProvider()
    assert p.is_available()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        page = p.extract_structured(img, language="en")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "tesseract_fallback"
    assert page.target == "cpu"
    assert page.blocks[0].kind == "paragraph"
    assert "Some OCR text" in page.blocks[0].text


def test_unavailable_when_pytesseract_missing(monkeypatch) -> None:
    def boom():
        raise ImportError("no module")

    monkeypatch.setattr(
        "jw_core.vision.vlm_providers.tesseract_fallback._probe", boom
    )
    assert TesseractFallbackProvider().is_available() is False


def test_migrate_to_vlm_helper_returns_callable(monkeypatch, tmp_path: Path) -> None:
    from jw_core.vision.ocr import migrate_to_vlm

    out = migrate_to_vlm()  # returns a callable usable in place of ocr_image
    assert callable(out)


def test_deprecated_extract_bible_reference_warns(monkeypatch, tmp_path: Path) -> None:
    from jw_core.vision import ocr as ocr_mod

    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    monkeypatch.setattr(
        "jw_core.vision.ocr.ocr_image", lambda *a, **k: "x"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ocr_mod.extract_bible_reference_from_image(img, language="en")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
