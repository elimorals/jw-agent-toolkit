"""Parser for wol.jw.org article HTML.

Extracts clean structured data from the article-style pages WOL serves:
title, ordered paragraphs, and Bible cross-references.

WOL marks the main article with `<article id="article">` (or similar) and
paragraphs as `<p id="pN" data-pid="N">`. Inline highlight `<span>` tags are
stripped to get clean text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag


@dataclass
class Article:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


def parse_article(html: str) -> Article:
    """Parse a wol.jw.org article page."""
    soup = BeautifulSoup(html, "lxml")
    title = _extract_title(soup)
    paragraphs = _extract_paragraphs(soup)
    references = _extract_references(soup)
    return Article(title=title, paragraphs=paragraphs, references=references)


def _extract_title(soup: BeautifulSoup) -> str:
    for selector in ("h1", "header h1", ".pubName"):
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        return title_tag.get_text(strip=True)
    return ""


def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:
    article = soup.find("article", id="article") or soup.find("article") or soup
    out: list[str] = []
    for p in article.find_all("p"):
        # Skip footer/navigation paragraphs without a data-pid.
        if not p.get("data-pid") and not p.get("id", "").startswith("p"):
            continue
        text = p.get_text(" ", strip=True)
        if text:
            out.append(text)
    return out


def _extract_references(soup: BeautifulSoup) -> list[str]:
    """Collect scripture cross-references linked inside the article."""
    refs: set[str] = set()
    for a in soup.find_all("a", class_=lambda c: c and "b" in c.split()):
        text = a.get_text(strip=True)
        if text:
            refs.add(text)
    return sorted(refs)
