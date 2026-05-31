from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredBlock, StructuredPage
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider

FIXTURES = Path(__file__).parent / "fixtures" / "vlm"


def test_fake_is_always_available() -> None:
    assert FakeVLMProvider().is_available() is True


def test_fake_loads_golden_when_matching_filename() -> None:
    provider = FakeVLMProvider()
    page = provider.extract_structured(FIXTURES / "wt_2024_page_es.png", language="es")
    assert page.provider_name == "fake"
    assert page.target == "cpu"
    assert page.language_detected == "es"
    assert any(b.kind == "bible_ref" for b in page.blocks)
    assert "Jehová" in page.text_only()


def test_fake_falls_back_to_canned_block_for_unknown_image(tmp_path: Path) -> None:
    bogus = tmp_path / "unknown.png"
    bogus.write_bytes(b"\x89PNG\r\n\x1a\n")
    page = FakeVLMProvider().extract_structured(bogus, language="en")
    assert len(page.blocks) == 1
    assert page.blocks[0].kind == "paragraph"
    assert page.raw_text_fallback


def test_fake_accepts_bytes_input() -> None:
    page = FakeVLMProvider().extract_structured(b"\x89PNG\r\n\x1a\n", language="en")
    assert isinstance(page, StructuredPage)


def test_fake_custom_blocks_override() -> None:
    custom = [StructuredBlock(kind="header", text="custom")]
    page = FakeVLMProvider(canned_blocks=custom).extract_structured(b"x")
    assert page.blocks == custom


def test_fake_cost_is_zero() -> None:
    hint = FakeVLMProvider().cost_estimate(b"x")
    assert hint.cents_estimate == 0.0
    assert hint.network is False
