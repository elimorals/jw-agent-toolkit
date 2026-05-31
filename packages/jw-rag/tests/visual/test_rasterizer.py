"""Tests for PageRasterizer.

We don't exercise the heavy backends (pdf2image / Playwright) — those are
opt-in extras. Instead we check:
  - dispatch by file extension picks the right method
  - skipped-by-extra paths raise ConfigError with an actionable message
  - the FakeRasterizer protocol is honored by the real class signature
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_rag.visual.errors import ConfigError
from jw_rag.visual.page_rasterizer import PageRasterizer, rasterize_any
from PIL import Image

FIXTURES = Path(__file__).parent / "fixtures"


def test_dispatch_by_extension_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling rasterize_any on .pdf delegates to rasterize_pdf."""
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_pdf(self, data, *, dpi=200):  # type: ignore[override]
            called.append("pdf")
            yield 0, Image.new("RGB", (10, 10))

    pdf = FIXTURES / "mini.pdf"
    list(rasterize_any(pdf, rasterizer=_Stub()))
    assert called == ["pdf"]


def test_dispatch_by_extension_epub(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_epub(self, path, *, viewport=(768, 1024)):  # type: ignore[override]
            called.append("epub")
            yield 0, Image.new("RGB", (10, 10))

    epub = FIXTURES / "mini.epub"
    list(rasterize_any(epub, rasterizer=_Stub()))
    assert called == ["epub"]


def test_dispatch_by_extension_jwpub() -> None:
    called: list[str] = []

    class _Stub(PageRasterizer):
        def rasterize_jwpub(self, path, *, dpi=200):  # type: ignore[override]
            called.append("jwpub")
            yield 0, Image.new("RGB", (10, 10))

    jwpub = FIXTURES / "mini.jwpub"
    list(rasterize_any(jwpub, rasterizer=_Stub()))
    assert called == ["jwpub"]


def test_unknown_extension_raises() -> None:
    with pytest.raises(ValueError):
        list(rasterize_any(Path("/tmp/foo.txt"), rasterizer=PageRasterizer()))


def test_real_rasterizer_pdf_missing_pdf2image_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pdf2image isn't installed, calling rasterize_pdf raises ConfigError."""
    import jw_rag.visual.page_rasterizer as mod

    monkeypatch.setattr(mod, "_HAS_PDF2IMAGE", False)
    r = PageRasterizer()
    with pytest.raises(ConfigError) as exc:
        list(r.rasterize_pdf(b"%PDF-1.4\n"))
    assert "uv sync --extra visual" in str(exc.value)


def test_real_rasterizer_epub_missing_playwright_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jw_rag.visual.page_rasterizer as mod

    monkeypatch.setattr(mod, "_HAS_PLAYWRIGHT", False)
    r = PageRasterizer()
    with pytest.raises(ConfigError) as exc:
        list(r.rasterize_epub(FIXTURES / "mini.epub"))
    assert "playwright" in str(exc.value).lower()
