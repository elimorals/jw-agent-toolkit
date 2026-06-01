"""Route raw files to existing parsers (jw-core's formats) or plugins."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedRawFile:
    path: Path
    mime: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)


class ParserRouter:
    EXTENSION_MAP = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
        ".pdf": "pdf",
        ".epub": "epub",
        ".jwpub": "jwpub",
        ".html": "html",
        ".htm": "html",
    }

    def detect_route(self, path: Path) -> str | None:
        ext = path.suffix.lower()
        return self.EXTENSION_MAP.get(ext)

    def parse(self, path: Path) -> ParsedRawFile | None:
        route = self.detect_route(path)
        if route is None:
            return None
        if route in {"markdown", "text"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            mime, _ = mimetypes.guess_type(str(path))
            return ParsedRawFile(
                path=path,
                mime=mime or "text/plain",
                text=text,
                metadata={"source": "markdown"},
                chunks=[p for p in text.split("\n\n") if p.strip()],
            )
        if route == "html":
            try:
                from jw_core.parsers.article import parse_article
            except ImportError:
                return None
            html = path.read_text(encoding="utf-8", errors="replace")
            article = parse_article(html)
            return ParsedRawFile(
                path=path,
                mime="text/html",
                text="\n\n".join(article.paragraphs),
                metadata={"title": article.title, "source": "article"},
                chunks=list(article.paragraphs),
            )
        if route == "epub":
            try:
                from jw_core.parsers.epub import parse_epub
            except Exception:
                return None
            try:
                parsed = parse_epub(path)
                paragraphs = getattr(parsed, "paragraphs", [])
                return ParsedRawFile(
                    path=path,
                    mime="application/epub+zip",
                    text="\n\n".join(paragraphs[:200]),
                    metadata={"title": getattr(parsed, "title", path.stem)},
                    chunks=list(paragraphs[:200]),
                )
            except Exception:
                return None
        if route == "jwpub":
            try:
                from jw_core.parsers.jwpub import parse_jwpub
            except Exception:
                return None
            try:
                parsed = parse_jwpub(path)
                paragraphs = getattr(parsed, "paragraphs", [])
                return ParsedRawFile(
                    path=path,
                    mime="application/x-jwpub",
                    text="\n\n".join(paragraphs[:500]),
                    metadata={"pub_code": getattr(parsed, "pub_code", path.stem)},
                    chunks=list(paragraphs[:500]),
                )
            except Exception:
                return None
        return None
