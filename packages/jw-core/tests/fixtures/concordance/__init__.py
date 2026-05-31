"""Builders for synthetic JWPUB/EPUB fixtures used by concordance tests.

We don't ship real JW publications in the repo (copyright). These
builders write structurally-valid minimal files we can index in tests.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def build_minimal_epub(path: Path, *, title: str, paragraphs: list[str]) -> Path:
    """Write a minimal but spec-compliant EPUB to `path`."""

    container = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="i">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="i">demo-1</dc:identifier>
  </metadata>
  <manifest>
    <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>"""

    body_paras = "\n".join(f'<p data-pid="{i}">{text}</p>' for i, text in enumerate(paragraphs))
    xhtml = f"""<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body>{body_paras}</body>
</html>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml", xhtml)
    return path
