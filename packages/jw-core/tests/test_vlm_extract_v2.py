from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import (
    StructuredBlock,
    extract_bible_reference_from_image_v2,
)
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider


def test_v2_returns_structured_page_dict(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="bible_ref", text="Juan 3:16", lang_hint="es")
        ]
    )
    out = extract_bible_reference_from_image_v2(img, language="es", provider=provider)
    assert "structured_page" in out
    assert "reference" in out
    assert "text" in out
    assert out["language_hint"] == "es"
    ref = out["reference"]
    assert ref is not None
    assert ref["book_num"] == 43  # John
    assert ref["chapter"] == 3
    assert ref["verse_start"] == 16


def test_v2_text_is_raw_fallback(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="paragraph", text="Hello world")]
    )
    out = extract_bible_reference_from_image_v2(img, language="en", provider=provider)
    assert "Hello world" in out["text"]


def test_v2_no_reference_returns_none(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    provider = FakeVLMProvider(
        canned_blocks=[StructuredBlock(kind="paragraph", text="no scripture here")]
    )
    out = extract_bible_reference_from_image_v2(img, language="en", provider=provider)
    assert out["reference"] is None
