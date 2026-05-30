"""EPUB (.epub) parser.

EPUB is the open-standard alternative to JWPUB. JW publishes most of its
recent material as both formats; EPUB content is unencrypted XHTML and
fully usable for indexing/RAG.

Structure (EPUB 3):
    META-INF/container.xml      → points at the OPF file
    {opf_path}                  → manifest + spine (XML)
    OEBPS/*.xhtml               → actual content
    OEBPS/css/*.css             → styling (ignored for text extraction)
    OEBPS/images/*.jpg          → images (ignored)
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup
from defusedxml.ElementTree import fromstring as xml_fromstring

from jw_core.models import Epub, EpubDocument

# Namespaces commonly used in EPUB OPF / container.
_NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def read_document_xhtml(epub_path: Path | str, item_id: str) -> str:
    """Return the raw XHTML for one document inside the EPUB.

    Useful when the caller wants to traverse the DOM with their own
    selectors (e.g. extract section headings + paragraphs in order).
    """
    p = Path(epub_path)
    with zipfile.ZipFile(p) as z:
        opf_path = _find_opf_path(z)
        if not opf_path:
            raise ValueError(f"{p}: no OPF file")
        opf_xml = z.read(opf_path).decode("utf-8")
        _, manifest, _ = _parse_opf(opf_xml)
        href = manifest.get(item_id)
        if not href:
            raise KeyError(f"item_id {item_id!r} not in manifest")
        opf_dir = "/".join(opf_path.split("/")[:-1])
        full_path = f"{opf_dir}/{href}" if opf_dir else href
        return z.read(full_path).decode("utf-8", errors="replace")


def parse_epub(path: Path | str) -> Epub:
    """Open an EPUB file and parse its manifest + spine + content."""
    epub_path = Path(path)
    with zipfile.ZipFile(epub_path) as z:
        opf_path = _find_opf_path(z)
        if not opf_path:
            raise ValueError(f"{epub_path}: no OPF file referenced from container.xml")

        opf_xml = z.read(opf_path).decode("utf-8")
        metadata, manifest, spine = _parse_opf(opf_xml)

        opf_dir = "/".join(opf_path.split("/")[:-1])
        documents: list[EpubDocument] = []
        for idx, item_id in enumerate(spine):
            href = manifest.get(item_id)
            if not href:
                continue
            full_path = f"{opf_dir}/{href}" if opf_dir else href
            try:
                xhtml = z.read(full_path).decode("utf-8", errors="replace")
            except KeyError:
                continue
            doc = _parse_xhtml(item_id, full_path, idx, xhtml)
            documents.append(doc)

    return Epub(
        title=metadata.get("title", ""),
        creator=metadata.get("creator", ""),
        language=metadata.get("language", ""),
        publisher=metadata.get("publisher", ""),
        identifier=metadata.get("identifier", ""),
        documents=documents,
        source_path=str(epub_path),
    )


# ── Internals ───────────────────────────────────────────────────────────


def _find_opf_path(zf: zipfile.ZipFile) -> str | None:
    """Read META-INF/container.xml and return the OPF rootfile path."""
    try:
        container_xml = zf.read("META-INF/container.xml").decode("utf-8")
    except KeyError:
        return None
    # Simple regex (avoids namespace headaches and we only need one attribute).
    m = re.search(r'full-path="([^"]+)"', container_xml)
    return m.group(1) if m else None


def _parse_opf(opf_xml: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Return (metadata dict, manifest id→href dict, spine item ID list)."""
    root = xml_fromstring(opf_xml)

    metadata: dict[str, str] = {}
    md_el = root.find(f"{{{_NS['opf']}}}metadata")
    if md_el is not None:
        for tag, key in (
            ("title", "title"),
            ("creator", "creator"),
            ("language", "language"),
            ("publisher", "publisher"),
            ("identifier", "identifier"),
        ):
            child = md_el.find(f"{{{_NS['dc']}}}{tag}")
            if child is not None and child.text:
                metadata[key] = child.text.strip()

    manifest: dict[str, str] = {}
    mf_el = root.find(f"{{{_NS['opf']}}}manifest")
    if mf_el is not None:
        for item in mf_el.findall(f"{{{_NS['opf']}}}item"):
            item_id = item.get("id")
            href = item.get("href")
            if item_id and href:
                manifest[item_id] = href

    spine_ids: list[str] = []
    sp_el = root.find(f"{{{_NS['opf']}}}spine")
    if sp_el is not None:
        for ref in sp_el.findall(f"{{{_NS['opf']}}}itemref"):
            idref = ref.get("idref")
            if idref:
                spine_ids.append(idref)

    return metadata, manifest, spine_ids


def _parse_xhtml(item_id: str, href: str, spine_index: int, xhtml: str) -> EpubDocument:
    """Extract title + paragraphs from one XHTML spine document."""
    # XHTML is XML; lxml-xml avoids BeautifulSoup's XMLParsedAsHTMLWarning.
    soup = BeautifulSoup(xhtml, "lxml-xml")
    title_el = soup.find(["h1", "h2", "h3"]) or soup.find("title")
    title = title_el.get_text(" ", strip=True) if title_el else ""

    paragraphs: list[str] = []
    # JW publications use <p data-pid="N"> for content paragraphs. Fall back
    # to all <p> tags if none have data-pid.
    candidates = soup.find_all("p", attrs={"data-pid": True}) or soup.find_all("p")
    for p in candidates:
        text = p.get_text(" ", strip=True)
        # Drop nav / footer lines that are very short.
        if text and len(text) > 4:
            paragraphs.append(text)

    return EpubDocument(
        id=item_id,
        title=title,
        href=href,
        paragraphs=paragraphs,
        spine_index=spine_index,
    )
