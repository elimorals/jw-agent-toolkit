"""Parser for Watch Tower Publications Index subject pages.

A subject page (e.g. /en/wol/d/r1/lp-e/1200275936 for 'Trinity') is a
structured list of subheadings and their citations:

  <p class="st">TRINITY</p>                 ← subject title
  <p class="sa">(See also …)</p>            ← see-also note
  <p class="su">ancient religions: <a href="/en/wol/pc/.../0">g05 4/22 7;</a>
                                   <a href="/en/wol/pc/.../3">ti 11-12;</a>
  </p>                                       ← top-level subheading
  <p class="sv">Assyria: <a href="/en/wol/pc/.../0">it-1 202;</a> ...</p>
  <p class="su">Catholic Church: ...</p>
  <p class="sv">admittedly not Biblical: ...</p>

Citation categorization (Phase 4.5)
-----------------------------------
Every citation in a subject page is rendered as an `<a>` element. They're
distinguished by URL path:

  /bc/  →  Bible cross-ref panel (`kind="bible"`)         class="b"
  /pc/  →  Publication citation panel (`kind="publication"`) no class
  /tc/  →  Table-of-contents (`kind="section"`)           class="it"
  /d/   →  Standalone document (`kind="document"`)        varies

Every TopicCitation now carries a `url` so the LLM can resolve it directly.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from jw_core.models import TopicCitation, TopicSubheading, TopicSubject

_WOL_BASE = "https://wol.jw.org"
_CITATION_SPLIT_RE = re.compile(r"\s*[;,]\s*")
_DOCID_FROM_URL_RE = re.compile(r"/d/[^/]+/[^/]+/(\d+)")
_TRAILING_PUNCT_RE = re.compile(r"[;,.\s]+$")

# Known JW publication-name markers used to split an article title from
# its citation suffix on article-title-style index pages. Order matters:
# longest first so 'Good News' doesn't pre-empt 'Good News About …'.
_PUB_MARKERS = [
    "The Watchtower (Study)",
    "The Watchtower",
    "Awake!",
    "God’s Friend",
    "God's Friend",
    "God’s Kingdom Rules!",
    "Pure Worship",
    "Good News",
    "Bible Teach",
    "Insight on the Scriptures",
    "Should You Believe in the Trinity?",
    "Reasoning From the Scriptures",
    "Our Christian Life and Ministry",
    "Examining the Scriptures Daily",
    "Yearbook of Jehovah’s Witnesses",
    "Yearbook of Jehovah's Witnesses",
]


def _split_article_title(text: str) -> tuple[str, str] | None:
    """Try to split an article-title-style entry into (title, publication_ref).

    Example: 'Timgad — A Buried City Reveals Its Secrets The Watchtower, 12/1/2014'
             → ('Timgad — A Buried City Reveals Its Secrets', 'The Watchtower, 12/1/2014')

    Returns None when no known publication marker is found.
    """
    cleaned = text.replace("​", "").strip()
    # Find the latest publication-name marker that has a citation-looking
    # suffix after it (comma + digit, ", lesson", ", chap.", ", Appendix").
    best_idx = -1
    for marker in _PUB_MARKERS:
        idx = cleaned.rfind(marker)
        if idx <= 0:
            continue
        # Validate: there must be a comma-something suffix within ~80 chars.
        tail = cleaned[idx + len(marker) :]
        if re.match(r",\s*(\d|lesson|chap\.|Appendix|p\.|Part)", tail) and idx > best_idx:
            best_idx = idx
    if best_idx < 0:
        return None
    title = cleaned[:best_idx].strip(" ​—-")
    pub = cleaned[best_idx:].strip()
    if not title or not pub:
        return None
    return title, pub


def _kind_from_href(href: str) -> str:
    """Classify a citation by its WOL URL path segment.

    Returns one of: 'bible', 'publication', 'section', 'document', 'other'.
    """
    if "/bc/" in href:
        return "bible"
    if "/pc/" in href:
        return "publication"
    if "/tc/" in href:
        return "section"
    if "/d/" in href:
        return "document"
    return "other"


def parse_subject_page(
    html: str,
    *,
    docid: str | None = None,
    source_url: str | None = None,
    language: str = "en",
) -> TopicSubject | None:
    """Parse a Watch Tower Publications Index subject page.

    Returns None if the page does not look like a subject index — e.g. if
    it's a generic article page or an error page. Inspect the result
    `subheadings` count to gauge coverage; an empty list means the page
    parsed but contained no recognizable entries.
    """
    soup = BeautifulSoup(html, "lxml")
    article = soup.find("article", id="article")
    if not article:
        return None

    if docid is None:
        docid = _extract_docid(article, source_url)

    title = _extract_title(article)
    see_also = _extract_see_also(article)
    subheadings = _extract_subheadings(article)
    style = _detect_style(subheadings)

    return TopicSubject(
        docid=docid or "",
        title=title,
        see_also=see_also,
        subheadings=subheadings,
        source_url=source_url or "",
        language=language,
        style=style,
    )


def _detect_style(subheadings: list[TopicSubheading]) -> str:
    """Decide whether the page is 'trinity'-style or 'article_title'-style.

    Heuristic: if at least 60% of subheadings have exactly one citation
    AND no semicolons in their heading text, it's article-title-style.
    """
    if not subheadings:
        return "trinity"
    one_cit = sum(1 for sh in subheadings if len(sh.citations) == 1 and ";" not in sh.heading)
    return "article_title" if one_cit / len(subheadings) >= 0.6 else "trinity"


# ── Internals ───────────────────────────────────────────────────────────


def _extract_docid(article: Tag, source_url: str | None) -> str:
    """Pull docid from `pub-docId-NNN` class on <article> or from the URL."""
    classes = article.get("class") or []
    for c in classes:
        if c.startswith("docId-") or c.startswith("pub-docId-"):
            return c.split("-")[-1]
    if source_url:
        m = _DOCID_FROM_URL_RE.search(source_url)
        if m:
            return m.group(1)
    return ""


def _extract_title(article: Tag) -> str:
    el = article.find("p", class_="st") or article.find("h1")
    if el:
        return el.get_text(" ", strip=True)
    return ""


def _extract_see_also(article: Tag) -> list[str]:
    """Pull '(See also X ; Y)' notes from class='sa' paragraphs."""
    out: list[str] = []
    for el in article.find_all("p", class_="sa"):
        text = el.get_text(" ", strip=True)
        # The text usually contains "(See also Foo ; Bar)" — strip parens
        # and the leading "See also" phrase, then split on `;`.
        text = re.sub(r"^\s*\(?\s*see\s+also\s*", "", text, flags=re.IGNORECASE)
        text = text.rstrip(")").strip()
        for part in re.split(r"\s*;\s*", text):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _extract_subheadings(article: Tag) -> list[TopicSubheading]:
    """Walk all <p class="su"> and <p class="sv"> paragraphs in order."""
    out: list[TopicSubheading] = []
    for p in article.find_all("p"):
        classes = set(p.get("class") or [])
        if "su" in classes:
            is_top_level = True
        elif "sv" in classes:
            is_top_level = False
        else:
            continue
        heading, citations = _parse_entry_paragraph(p)
        if heading or citations:
            out.append(
                TopicSubheading(
                    heading=heading,
                    citations=citations,
                    is_top_level=is_top_level,
                )
            )
    return out


def _parse_entry_paragraph(p: Tag) -> tuple[str, list[TopicCitation]]:
    """Extract headword + citations from one su/sv paragraph.

    Each `<a>` inside the paragraph becomes a TopicCitation whose `kind`
    is derived from the href's path segment:
      - `/bc/` → bible (also class='b')
      - `/pc/` → publication (no class)
      - `/tc/` → section (class='it')
      - `/d/`  → document

    Handles two layouts (Phase 4.6):

    Trinity-style (`<p>heading: <a>...; <a>...; <a>...</p>`):
        - heading = text before the first ':'
        - citations = every `<a>` in the paragraph
    Article-title-style (`<p><a>Article Title PubName, Date</a></p>`):
        - the single anchor wraps the whole reference
        - try to split into (article_title, publication_marker) using
          known JW publication name markers; if it splits, the heading is
          the article title and the publication name+date is the
          citation suffix
    """
    citations: list[TopicCitation] = []

    full_text = p.get_text(" ", strip=True)
    anchors = p.find_all("a")

    # Article-title-style detection: no colon + a single anchor whose text
    # makes up most of the paragraph.
    article_title_mode = (
        ":" not in full_text and len(anchors) == 1 and anchors[0].get_text(" ", strip=True).strip() == full_text.strip()
    )

    if article_title_mode:
        a = anchors[0]
        anchor_text = _TRAILING_PUNCT_RE.sub("", a.get_text(" ", strip=True)).strip()
        split = _split_article_title(anchor_text)
        if split:
            headword, pub_marker = split
        else:
            headword = anchor_text
            pub_marker = anchor_text
        href = a.get("href", "")
        kind = _kind_from_href(href)
        url = href if href.startswith("http") else f"{_WOL_BASE}{href}" if href else None
        citations.append(TopicCitation(text=pub_marker, kind=kind, url=url))
        return headword, citations

    # Trinity-style.
    if ":" in full_text:
        headword = full_text.split(":", 1)[0].strip()
    else:
        headword = full_text

    for a in anchors:
        text = _TRAILING_PUNCT_RE.sub("", a.get_text(" ", strip=True)).strip()
        if not text:
            continue
        href = a.get("href", "")
        kind = _kind_from_href(href)
        url = href if href.startswith("http") else f"{_WOL_BASE}{href}" if href else None
        citations.append(TopicCitation(text=text, kind=kind, url=url))

    return headword, citations
