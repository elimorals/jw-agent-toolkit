"""Rasterize JWPUB / EPUB / PDF documents to page-level PIL images.

Three backends, all optional and behind lazy imports:
  - PDF   → pdf2image (poppler under the hood)
  - EPUB  → Playwright headless Chromium at a fixed viewport
  - JWPUB → decrypt via jw_core.parsers.jwpub.parse_jwpub, then render each
            decrypted XHTML document through Playwright

The class methods are coroutines-like generators that yield (page_index, PIL).
This lets the ingest pipeline embed pages incrementally instead of buffering
hundreds of images in memory.

`rasterize_any(path, rasterizer=...)` is the dispatcher used by ingest:
extension-based routing to the right method. Tests inject FakeRasterizer here.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from PIL import Image

from jw_rag.visual.errors import ConfigError

try:
    import pdf2image  # type: ignore[import-not-found]

    _HAS_PDF2IMAGE = True
except ImportError:
    _HAS_PDF2IMAGE = False

try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


_INSTALL_HINT = "Install with: uv sync --extra visual (NVIDIA) or --extra visual-mlx (Apple Silicon)."


class PageRasterizer:
    """Backend-aware page rasterizer for PDF/EPUB/JWPUB."""

    def rasterize_pdf(self, data: bytes, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:
        if not _HAS_PDF2IMAGE:
            raise ConfigError(f"pdf2image not installed. {_INSTALL_HINT}")
        # pdf2image accepts bytes via `convert_from_bytes`.
        for i, img in enumerate(pdf2image.convert_from_bytes(data, dpi=dpi)):
            yield i, img.convert("RGB")

    def rasterize_epub(
        self, path: Path, *, viewport: tuple[int, int] = (768, 1024)
    ) -> Iterator[tuple[int, Image.Image]]:
        if not _HAS_PLAYWRIGHT:
            raise ConfigError(f"playwright not installed. {_INSTALL_HINT}")
        from jw_core.parsers.epub import parse_epub, read_document_xhtml

        epub = parse_epub(path)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
            try:
                for idx, doc in enumerate(epub.documents):
                    try:
                        xhtml = read_document_xhtml(path, doc.id)
                    except (KeyError, ValueError):
                        continue
                    page = context.new_page()
                    page.set_content(xhtml, wait_until="load")
                    png = page.screenshot(full_page=True, type="png")
                    page.close()
                    img = Image.open(_bytes_io(png)).convert("RGB")
                    yield idx, img
            finally:
                context.close()
                browser.close()

    def rasterize_jwpub(self, path: Path, *, dpi: int = 200) -> Iterator[tuple[int, Image.Image]]:  # noqa: ARG002
        if not _HAS_PLAYWRIGHT:
            raise ConfigError(f"playwright not installed (needed for JWPUB rendering). {_INSTALL_HINT}")
        from jw_core.parsers.jwpub import parse_jwpub

        meta = parse_jwpub(path)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 768, "height": 1024})
            try:
                for idx, doc in enumerate(meta.documents):
                    if not doc.text:
                        continue
                    page = context.new_page()
                    page.set_content(doc.text, wait_until="load")
                    png = page.screenshot(full_page=True, type="png")
                    page.close()
                    img = Image.open(_bytes_io(png)).convert("RGB")
                    yield idx, img
            finally:
                context.close()
                browser.close()


def _bytes_io(data: bytes):
    from io import BytesIO

    return BytesIO(data)


def rasterize_any(
    path: Path,
    *,
    rasterizer: PageRasterizer | None = None,
    dpi: int = 200,
) -> Iterator[tuple[int, Image.Image]]:
    """Dispatch to the right backend by file extension.

    `rasterizer` is injectable so tests can pass FakeRasterizer.
    """
    rasterizer = rasterizer or PageRasterizer()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        data = path.read_bytes()
        yield from rasterizer.rasterize_pdf(data, dpi=dpi)
    elif suffix == ".epub":
        yield from rasterizer.rasterize_epub(path)
    elif suffix == ".jwpub":
        yield from rasterizer.rasterize_jwpub(path, dpi=dpi)
    else:
        raise ValueError(f"Unsupported extension {suffix!r}: expected .pdf|.epub|.jwpub")
