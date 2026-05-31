"""Build the tiny PDF and EPUB fixtures for the rasterizer tests.

Run once: `uv run python packages/jw-rag/tests/visual/fixtures/build_fixtures.py`
"""

from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build_pdf() -> None:
    """Minimal 3-page PDF — pdf2image only needs valid PDF structure."""
    try:
        from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit("Install reportlab once to rebuild fixtures: uv pip install reportlab")
    out = HERE / "mini.pdf"
    c = Canvas(str(out))
    for i in range(3):
        c.drawString(100, 700, f"Page {i + 1}")
        c.showPage()
    c.save()
    print(f"wrote {out}")


def build_epub() -> None:
    out = HERE / "mini.epub"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        z.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Mini Visual Test</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="p1" href="p1.xhtml" media-type="application/xhtml+xml"/>
    <item id="p2" href="p2.xhtml" media-type="application/xhtml+xml"/>
    <item id="p3" href="p3.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="p1"/>
    <itemref idref="p2"/>
    <itemref idref="p3"/>
  </spine>
</package>""",
        )
        for i in (1, 2, 3):
            z.writestr(
                f"OEBPS/p{i}.xhtml",
                f"""<?xml version="1.0"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Page {i}</title></head>
  <body><h1>Page {i}</h1><p data-pid="{i}">Content {i}</p></body>
</html>""",
            )
    print(f"wrote {out}")


def build_jwpub_stub() -> None:
    """JWPUB stub: outer ZIP with empty manifest. Decryption tests skip this."""
    out = HERE / "mini.jwpub"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", '{"publication": {"symbol": "test", "year": 2026}}')
        z.writestr("contents", b"")
    print(f"wrote {out}")


if __name__ == "__main__":
    build_pdf()
    build_epub()
    build_jwpub_stub()
