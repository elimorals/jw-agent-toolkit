"""Parser for the Meeting Workbook (`mwb`) weekly page.

JW publishes the workbook online at:

  wol.jw.org/{iso}/wol/publication/{r}/{lp_tag}/mwb{YY}.{MM}/{week_index}

The page is server-rendered HTML with a known structure: three top
sections marked by `<h2>` (or `<div class="section">`) followed by the
assignments as `<p>` paragraphs with a leading bullet and a duration.

We do tolerant parsing — when JW changes the layout we degrade to plain
paragraphs preserving the assignment text.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup, Tag

from jw_core.models_meeting import (
    WORKBOOK_SECTIONS,
    WorkbookAssignment,
    WorkbookSection,
    WorkbookWeek,
)

# Localized section labels we recognise. Add new languages as we expand.
_SECTION_LABELS: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("treasures", "treasures from"),
        ("apply_yourself", "apply yourself"),
        ("living_as_christians", "living as christians"),
    ],
    "es": [
        ("treasures", "tesoros de la"),
        ("apply_yourself", "seamos mejores"),
        ("living_as_christians", "nuestra vida cristiana"),
    ],
    "pt": [
        ("treasures", "tesouros da palavra"),
        ("apply_yourself", "faça seu melhor"),
        ("living_as_christians", "nossa vida cristã"),
    ],
}

_MINUTES_RE = re.compile(r"\(\s*(\d{1,2})\s*(?:min|mins|m|minutos?|min\.)\s*\)", re.IGNORECASE)
_SONG_RE = re.compile(r"(?:song|cant[ai]co|c[áa]ntico)\s+(\d{1,3})", re.IGNORECASE)
_BIBLE_READING_RE = re.compile(
    r"bible reading|lectura de la biblia|leitura da bíblia",
    re.IGNORECASE,
)


def parse_workbook_week(
    html: str,
    *,
    pub_code: str = "",
    week_of: str = "",
    language: str = "en",
    source_url: str = "",
) -> WorkbookWeek:
    """Parse a single workbook week page into structured assignments.

    All inputs except `html` are best-effort hints; if the page contains
    a header that exposes the publication code or date we prefer it.
    """
    soup = BeautifulSoup(html, "lxml")
    title = _extract_title(soup)
    bible_reading = _extract_bible_reading(soup, title)
    songs = _extract_songs(soup)
    sections = _extract_sections(soup, language=language)

    return WorkbookWeek(
        week_of=week_of or _heuristic_week_of(soup),
        pub_code=pub_code,
        title=title,
        bible_reading=bible_reading,
        song_opening=songs.get("opening"),
        song_middle=songs.get("middle"),
        song_closing=songs.get("closing"),
        sections=sections,
        source_url=source_url,
        language=language,
    )


def _extract_title(soup: BeautifulSoup) -> str:
    for sel in ("h1", "header h2", ".groupTOC h2"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    return ""


def _extract_bible_reading(soup: BeautifulSoup, title: str) -> str:
    # The headline of each workbook week IS the Bible reading
    # (e.g. "PROVERBS 1-3" / "PROVERBIOS 1 A 3").
    if title and any(c.isdigit() for c in title):
        return title
    for h in soup.find_all(["h1", "h2", "h3"]):
        text = h.get_text(" ", strip=True)
        if _BIBLE_READING_RE.search(text):
            sibling = h.find_next("p")
            if sibling and isinstance(sibling, Tag):
                return sibling.get_text(" ", strip=True)
    return ""


def _extract_songs(soup: BeautifulSoup) -> dict[str, int]:
    """Look for `Song N` mentions; assume 3 total → opening/middle/closing.

    Fallback: any number prefixed with the localized "Song" word.
    """
    hits: list[int] = []
    for el in soup.find_all(["p", "h3", "h4", "strong"]):
        text = el.get_text(" ", strip=True)
        for m in _SONG_RE.finditer(text):
            try:
                hits.append(int(m.group(1)))
            except ValueError:
                continue
    out: dict[str, int] = {}
    if hits:
        out["opening"] = hits[0]
    if len(hits) >= 2:
        out["middle"] = hits[len(hits) // 2]
    if len(hits) >= 2:
        out["closing"] = hits[-1]
    return out


def _heuristic_week_of(soup: BeautifulSoup) -> str:
    """Try to find a printed date range; return ISO Monday of that range."""
    for el in soup.find_all(["h2", "h3", "p"]):
        text = el.get_text(" ", strip=True)
        m = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+(\w+)", text)
        if m:
            day = int(m.group(1))
            month_name = m.group(3).lower()
            try:
                month = _MONTHS.index(month_name[:3]) + 1
            except ValueError:
                continue
            year = date.today().year
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            # Snap back to Monday.
            return (d - timedelta(days=d.weekday())).isoformat()
    return ""


_MONTHS = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


def _extract_sections(soup: BeautifulSoup, *, language: str) -> list[WorkbookSection]:
    labels = _SECTION_LABELS.get(language, _SECTION_LABELS["en"])
    sections: list[WorkbookSection] = []
    body = soup.find("article") or soup.find("main") or soup

    # JW workbook pages mark each section with an `<h2>` heading whose text
    # matches one of the localized labels.
    section_headers: list[tuple[Tag, str, str]] = []
    for h in body.find_all(["h2", "h3"]):
        normalized = h.get_text(" ", strip=True).lower()
        for name, label in labels:
            if label in normalized:
                section_headers.append((h, name, h.get_text(" ", strip=True)))
                break

    if not section_headers:
        return _fallback_sections(body, language=language)

    # Pair each header with the next; everything between them belongs
    # to that section.
    for i, (header, name, heading) in enumerate(section_headers):
        end = section_headers[i + 1][0] if i + 1 < len(section_headers) else None
        block_tags = _between(header, end)
        assignments = _extract_assignments(block_tags)
        sections.append(WorkbookSection(name=name, heading=heading, assignments=assignments))

    return sections


def _fallback_sections(body: Tag, *, language: str) -> list[WorkbookSection]:
    """When the header heuristic fails, attribute everything to a single
    flat 'treasures' bucket so downstream code still has something to use."""
    paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p") if p.get_text(strip=True)]
    if not paragraphs:
        return []
    assignments = [
        WorkbookAssignment(
            title=para[:80],
            body=para,
            kind="talk",
        )
        for para in paragraphs[:12]
    ]
    return [WorkbookSection(name="treasures", heading="(parsed in fallback mode)", assignments=assignments)]


def _between(start: Tag, end: Tag | None) -> list[Tag]:
    """Collect siblings strictly between two tags."""
    out: list[Tag] = []
    cur = start.find_next_sibling()
    while cur is not None and cur is not end:
        if isinstance(cur, Tag):
            out.append(cur)
        cur = cur.find_next_sibling()
    return out


def _extract_assignments(block_tags: list[Tag]) -> list[WorkbookAssignment]:
    assignments: list[WorkbookAssignment] = []
    current: WorkbookAssignment | None = None
    for tag in block_tags:
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name in {"h3", "h4", "strong"} or _looks_like_assignment_header(text):
            if current is not None:
                assignments.append(current)
            current = _new_assignment_from_header(text, tag)
        elif current is not None:
            # Append body text.
            current.body = (current.body + "\n" + text).strip() if current.body else text
            current.references.extend(_pluck_refs(tag))
        else:
            # Stray paragraph without a header — accept it as one-shot.
            assignments.append(_new_assignment_from_header(text, tag))
    if current is not None:
        assignments.append(current)
    return assignments


def _looks_like_assignment_header(text: str) -> bool:
    return bool(_MINUTES_RE.search(text))


_KIND_HINTS = (
    ("video", "video"),
    ("video", "vídeo"),
    ("song", "song"),
    ("song", "cántico"),
    ("song", "cantico"),
    ("song", "cântico"),
    ("study", "study"),
    ("study", "estudio"),
    ("study", "estudo"),
    ("bible_reading", "bible reading"),
    ("bible_reading", "lectura de la biblia"),
    ("bible_reading", "leitura"),
    ("demonstration", "demonstration"),
    ("demonstration", "demostración"),
    ("demonstration", "demonstração"),
)


def _new_assignment_from_header(text: str, tag: Tag) -> WorkbookAssignment:
    minutes_match = _MINUTES_RE.search(text)
    minutes = int(minutes_match.group(1)) if minutes_match else None
    cleaned = _MINUTES_RE.sub("", text).strip(" .:—-—–")
    lower = cleaned.lower()
    kind = "talk"
    for guess, needle in _KIND_HINTS:
        if needle in lower:
            kind = guess
            break
    return WorkbookAssignment(
        title=cleaned[:200],
        minutes=minutes,
        kind=kind,
        body="",
        references=_pluck_refs(tag),
        cue=_pluck_cue(text),
    )


def _pluck_refs(tag: Tag) -> list[str]:
    refs: list[str] = []
    for a in tag.find_all("a"):
        text = a.get_text(" ", strip=True)
        if text and len(text) < 50:
            refs.append(text)
    return refs


_CUE_RE = re.compile(r"\bth\s+(?:study\s+)?\d+\b", re.IGNORECASE)


def _pluck_cue(text: str) -> str:
    m = _CUE_RE.search(text)
    return m.group(0) if m else ""


# ── Workbook code helpers ────────────────────────────────────────────────


def workbook_pub_code_for_date(d: date) -> str:
    """Return the workbook publication code that covers month `d`.

    JW issues the workbook bimonthly (Jan-Feb, Mar-Apr, ...) — the code uses
    the first month of the pair, two-digit year:

        date(2026, 3, 15) → "mwb26.03"

    Edge cases: even months snap back one month (April → March issue, etc.).
    """
    year_two = d.year % 100
    month = d.month if d.month % 2 == 1 else d.month - 1
    return f"mwb{year_two:02d}.{month:02d}"


def watchtower_study_pub_code_for_date(d: date) -> str:
    """Return the Watchtower Study publication code for the study issue
    that the congregation is studying on date `d`.

    JW prints the study edition two months before the study week. So when
    you're studying in May 2026 the issue is `w26.03`.
    """
    delta_months = 2
    month = d.month - delta_months
    year = d.year
    while month < 1:
        month += 12
        year -= 1
    year_two = year % 100
    return f"w{year_two:02d}.{month:02d}"
