from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_core.vision.vlm import StructuredBlock
from jw_core.vision.vlm_providers.fakes import FakeVLMProvider
from jw_rag.ingest_image import ingest_image


class _FakeStore:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, chunks) -> None:
        self.added.extend(chunks)


def _img(tmp_path: Path) -> Path:
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG")
    return p


def test_ingest_image_creates_one_chunk_per_block(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="header", text="Watchtower"),
            StructuredBlock(kind="paragraph", text="Jehová cuida"),
            StructuredBlock(kind="bible_ref", text="Juan 3:16"),
        ]
    )
    n = ingest_image(store, _img(tmp_path), language="es", provider=provider)
    assert n == 3
    assert len(store.added) == 3
    kinds = [c.metadata["kind"] for c in store.added]
    assert kinds == ["header", "paragraph", "bible_ref"]


def test_ingest_image_parses_bible_ref_metadata(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(canned_blocks=[StructuredBlock(kind="bible_ref", text="John 3:16")])
    ingest_image(store, _img(tmp_path), language="en", provider=provider)
    parsed = store.added[0].metadata.get("parsed_reference")
    assert parsed is not None
    assert parsed["chapter"] == 3
    assert parsed["verse_start"] == 16


def test_ingest_image_filters_low_confidence(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(
        canned_blocks=[
            StructuredBlock(kind="paragraph", text="strong", confidence=0.9),
            StructuredBlock(kind="paragraph", text="weak", confidence=0.1),
        ]
    )
    n = ingest_image(store, _img(tmp_path), language="en", provider=provider, min_confidence=0.3)
    assert n == 1
    assert store.added[0].text == "strong"


def test_ingest_image_source_id_is_stable(tmp_path: Path) -> None:
    store = _FakeStore()
    provider = FakeVLMProvider(canned_blocks=[StructuredBlock(kind="paragraph", text="t")])
    img = _img(tmp_path)
    ingest_image(store, img, language="en", provider=provider)
    sid = store.added[0].source_id
    assert sid.startswith("image:")
    assert sid.endswith(":0:paragraph")
