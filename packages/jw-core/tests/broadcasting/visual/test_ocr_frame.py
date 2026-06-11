"""OCR enrichment of visual frames (Fase 69 post-MVP)."""

from __future__ import annotations

import pytest

from jw_core.broadcasting.visual.models import VisualFrame
from jw_core.broadcasting.visual.ocr_frame import enrich_frames_with_ocr


def _frame(thumb: str | None = "/tmp/x.png", ocr: str = "") -> VisualFrame:
    return VisualFrame(
        video_id="vid",
        timestamp_s=1.0,
        caption="caption",
        ocr_text=ocr,
        embedding_id=0,
        thumb_path=thumb,
    )


def test_enrich_populates_empty_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod

    monkeypatch.setattr(mod, "ocr_image", lambda *a, **kw: "Hello world")
    out = enrich_frames_with_ocr([_frame()], language="en")
    assert len(out) == 1
    assert out[0].ocr_text == "Hello world"


def test_enrich_skips_when_ocr_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod

    monkeypatch.setattr(
        mod, "ocr_image", lambda *a, **kw: pytest.fail("should not run")
    )
    out = enrich_frames_with_ocr(
        [_frame(ocr="already here")], language="en"
    )
    assert out[0].ocr_text == "already here"


def test_enrich_overwrite_reruns_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod

    monkeypatch.setattr(mod, "ocr_image", lambda *a, **kw: "fresh")
    out = enrich_frames_with_ocr(
        [_frame(ocr="old")], language="en", overwrite=True
    )
    assert out[0].ocr_text == "fresh"


def test_enrich_skips_when_no_thumb_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod

    monkeypatch.setattr(
        mod, "ocr_image", lambda *a, **kw: pytest.fail("should not run")
    )
    out = enrich_frames_with_ocr([_frame(thumb=None)], language="en")
    assert out[0].ocr_text == ""


def test_language_routing_uses_tesseract_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod

    seen: dict[str, str] = {}

    def fake_ocr(path, *, language):
        seen["lang"] = language
        return "ok"

    monkeypatch.setattr(mod, "ocr_image", fake_ocr)
    enrich_frames_with_ocr([_frame()], language="es")
    assert seen["lang"] == "spa"


def test_propagates_ocr_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jw_core.broadcasting.visual import ocr_frame as mod
    from jw_core.vision.ocr import OCRError

    def boom(*a, **kw):
        raise OCRError("no tesseract")

    monkeypatch.setattr(mod, "ocr_image", boom)
    with pytest.raises(OCRError):
        enrich_frames_with_ocr([_frame()], language="en")
