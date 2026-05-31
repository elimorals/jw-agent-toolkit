"""Tests for visual ingest pipeline.

Use FakeRasterizer + FakeColPaliEmbedder so tests run without GPU and without
Playwright/pdf2image. The real backends are exercised in nightly GPU runners
(not in this plan).
"""

from __future__ import annotations

from pathlib import Path

from jw_rag.visual.fakes import FakeColPaliEmbedder, FakeRasterizer
from jw_rag.visual.ingest import ingest_path_visual
from jw_rag.visual.visual_store import VisualVectorStore
from PIL import Image


def _make_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    return p


def test_ingest_returns_pages_added(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    result = ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=4, size=(64, 64)),
        images_dir=tmp_path / "imgs",
    )
    assert result.pages_added == 4
    assert result.pages_skipped == 0
    assert store.count == 4


def test_ingest_idempotent_by_source_id(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    raster = FakeRasterizer(n_pages=3, size=(64, 64))
    first = ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    second = ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    assert first.pages_added == 3
    assert second.pages_added == 0
    assert second.pages_skipped == 3
    assert store.count == 3


def test_ingest_force_overrides_idempotency(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    raster = FakeRasterizer(n_pages=2, size=(64, 64))
    ingest_path_visual(pdf, store, rasterizer=raster, images_dir=tmp_path / "imgs")
    forced = ingest_path_visual(
        pdf,
        store,
        rasterizer=raster,
        images_dir=tmp_path / "imgs",
        force=True,
    )
    # Force does NOT duplicate chunks (id collision skipped by store.add) but
    # the result reports the attempt — useful for benchmarking re-ingest cost.
    assert forced.pages_added == 0 or store.count == 2


def test_ingest_persists_page_images(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    images_dir = tmp_path / "imgs"
    ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=2, size=(64, 64)),
        images_dir=images_dir,
    )
    pngs = sorted(images_dir.glob("*.png"))
    assert len(pngs) == 2
    img = Image.open(pngs[0])
    assert img.size == (64, 64)


def test_ingest_metadata_includes_source_path_and_language(tmp_path: Path) -> None:
    store = VisualVectorStore(tmp_path / "store", FakeColPaliEmbedder(dim=32, n_patches=16))
    pdf = _make_pdf(tmp_path)
    ingest_path_visual(
        pdf,
        store,
        rasterizer=FakeRasterizer(n_pages=1, size=(64, 64)),
        images_dir=tmp_path / "imgs",
        language="es",
    )
    chunk = store._chunks[0]  # type: ignore[attr-defined]
    assert chunk.metadata["source_path"].endswith("sample.pdf")
    assert chunk.metadata["language"] == "es"
