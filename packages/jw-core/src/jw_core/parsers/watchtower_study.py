"""Parser for the Watchtower Study article page.

URL pattern (WOL):
  /{iso}/wol/publication/{r}/{lp_tag}/w{YY}.{MM}/{study_index}

Each study article is a sequence of numbered paragraphs, where each paragraph
is followed by one or more study questions printed in italics. We extract:

  - title + theme scripture
  - paragraphs (number, text, questions, scripture refs)

Tolerant parser: if JW changes the markup the fields degrade to empty
rather than raising. Use `confidence` heuristics in callers if you need
to flag low-quality pages.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from jw_core.models_meeting import WatchtowerStudy, WatchtowerStudyParagraph

_PARAGRAPH_NUM_RE = re.compile(r"^\s*(\d{1,3})[.\)]\s+")


def parse_watchtower_study(
    html: str,
    *,
    pub_code: str = "",
    language: str = "en",
    source_url: str = "",
) -> WatchtowerStudy:
    soup = BeautifulSoup(html, "lxml")
    title = _extract_title(soup)
    theme_scripture = _extract_theme_scripture(soup)
    summary = _extract_summary(soup)
    study_number = _extract_study_number(soup)
    paragraphs = _extract_paragraphs(soup)
    return WatchtowerStudy(
        pub_code=pub_code,
        study_number=study_number,
        title=title,
        theme_scripture=theme_scripture,
        summary=summary,
        paragraphs=paragraphs,
        source_url=source_url,
        language=language,
    )


def _extract_title(soup: BeautifulSoup) -> str:
    for sel in ("h1", "article header h2", ".articleTitle"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return ""


def _extract_theme_scripture(soup: BeautifulSoup) -> str:
    for sel in (".themeScrp", ".themeScripture", "p.themeScripture", "p.themeScrp"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    # Fallback: a short italic blockquote near the top.
    blockquote = soup.find("blockquote")
    if blockquote and isinstance(blockquote, Tag):
        return blockquote.get_text(" ", strip=True)
    return ""


def _extract_summary(soup: BeautifulSoup) -> str:
    for sel in (".themeIntro", ".summary", "p.lead"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return ""


def _extract_study_number(soup: BeautifulSoup) -> int | None:
    el = soup.select_one(".studyArticleNumber") or soup.select_one(".articleNum")
    if el:
        m = re.search(r"\d+", el.get_text(" ", strip=True))
        if m:
            return int(m.group(0))
    return None


def _extract_paragraphs(soup: BeautifulSoup) -> list[WatchtowerStudyParagraph]:
    body = soup.find("article", id="article") or soup.find("article") or soup
    out: list[WatchtowerStudyParagraph] = []

    # WOL marks study paragraphs with `data-pid="N"` and class "qu" for
    # the question that follows. We walk the children in order.
    paragraphs: list[tuple[int, str, list[str]]] = []
    for p in body.find_all("p"):
        if not isinstance(p, Tag):
            continue
        pid = p.get("data-pid") or p.get("id", "").lstrip("p")
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        m = _PARAGRAPH_NUM_RE.match(text)
        if m:
            num = int(m.group(1))
            stripped = text[m.end() :]
            paragraphs.append((num, stripped, _pluck_scripture_refs(p)))
            continue
        if pid and pid.isdigit():
            paragraphs.append((int(pid), text, _pluck_scripture_refs(p)))

    # Questions are usually rendered as `<p class="qu">` separated from
    # their paragraphs. We attach each question to the nearest preceding
    # paragraph number.
    questions: list[tuple[int, str]] = []
    last_num = 0
    for el in body.find_all(["p", "div"]):
        if not isinstance(el, Tag):
            continue
        cls = el.get("class") or []
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        m = _PARAGRAPH_NUM_RE.match(text)
        if m:
            last_num = int(m.group(1))
        if any(c in cls for c in ("qu", "studyQuestion", "studyQu")):
            questions.append((last_num or 1, text))

    by_number: dict[int, WatchtowerStudyParagraph] = {}
    for num, text, refs in paragraphs:
        by_number[num] = WatchtowerStudyParagraph(number=num, text=text, scripture_refs=refs)
    for num, qtext in questions:
        if num in by_number:
            by_number[num].questions.append(qtext)

    out = [by_number[k] for k in sorted(by_number.keys())]
    return out


def _pluck_scripture_refs(tag: Tag) -> list[str]:
    refs: list[str] = []
    for a in tag.find_all("a", class_=lambda c: c and "b" in (c.split() if isinstance(c, str) else c)):
        text = a.get_text(" ", strip=True)
        if text and text not in refs:
            refs.append(text)
    return refs
