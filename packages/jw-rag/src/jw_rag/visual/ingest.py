"""Visual ingest pipeline.

`ingest_path_visual(path, store, ...)` is the single entry point. It:
  1. Computes `source_id = sha256(file_bytes)[:32]`.
  2. If `source_id in store.source_ids()` and not `force`: returns
     `IngestResult(pages_skipped=N)` where N is best-effort.
  3. Rasterizes pages via `rasterize_any(path, rasterizer=...)`.
  4. For each page: saves the PNG to `images_dir/<source_id>_p{NNN}.png`,
     builds a `VisualChunk`, and appends to a batch.
  5. Calls `store.add(batch)` once at the end (cheaper than per-page).
  6. Calls `store.save()` so partial work survives crashes.

Idempotency is the contract that lets users re-run the CLI safely. `force=True`
is for development iteration (e.g. tweaking max_patches).
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from PIL import Image

from jw_rag.visual.models import IngestResult, VisualChunk
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any
from jw_rag.visual.visual_store import VisualVectorStore


def _source_id_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:32]


def ingest_path_visual(
    path: Path,
    store: VisualVectorStore,
    *,
    rasterizer: PageRasterizer | None = None,
    images_dir: Path | None = None,
    language: str = "",
    force: bool = False,
    dpi: int = 200,
) -> IngestResult:
    """Rasterize → embed → store every page of `path`.

    Args:
        path: PDF / EPUB / JWPUB file.
        store: target VisualVectorStore (already constructed with the right
               embedder).
        rasterizer: optional custom PageRasterizer (tests pass FakeRasterizer).
        images_dir: where to save page PNGs for later render. Defaults to
                    `store.path / "images"`.
        language: ISO code stored in chunk metadata for filtering.
        force: re-ingest even if `source_id` is already present.
        dpi: rasterization DPI for PDF/JWPUB.
    """
    start = time.monotonic()
    source_id = _source_id_of(path)
    images_dir = images_dir or (store.path / "images")
    images_dir.mkdir(parents=True, exist_ok=True)

    if not force and source_id in store.source_ids():
        existing = sum(1 for c in store._chunks if c.source_id == source_id)  # type: ignore[attr-defined]
        return IngestResult(
            pages_added=0,
            pages_skipped=existing,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    pairs: list[tuple[VisualChunk, Image.Image]] = []
    for page_idx, image in rasterize_any(path, rasterizer=rasterizer, dpi=dpi):
        png_path = images_dir / f"{source_id}_p{page_idx:03d}.png"
        image.save(png_path, format="PNG")
        chunk = VisualChunk(
            id=f"{source_id}#p{page_idx + 1}",
            source_id=source_id,
            page_number=page_idx + 1,
            image_path=png_path,
            metadata={
                "source_path": str(path),
                "language": language,
                "dpi": dpi,
            },
        )
        pairs.append((chunk, image))

    before = store.count
    store.add(pairs)
    added = store.count - before
    store.save()
    return IngestResult(
        pages_added=added,
        pages_skipped=len(pairs) - added,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


# Convenience aliases for spec parity. All three are the same function;
# extension-based dispatch happens inside `rasterize_any`.


def ingest_pdf_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)


def ingest_epub_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)


def ingest_jwpub_visual(path: Path, store: VisualVectorStore, **kw) -> IngestResult:
    return ingest_path_visual(path, store, **kw)
