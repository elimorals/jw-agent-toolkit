"""Parse the Meeting Workbook EPUB (real production source).

Discovered live (May 2026): the workbook is NOT served at
`wol.jw.org/.../publication/mwb24.05`. The canonical source is the
**EPUB** distributed via `pub-media GETPUBMEDIALINKS?pub=mwb&issue=YYYYMM`.

Inside the EPUB:
  - doc[0..2] : cover + front matter (skip)
  - doc[3..10]: one document per week. Title is the date range
                (e.g. "MAY 6-12", "MAY 27–JUNE 2").
  - doc[11..] : navigation / extracted text (skip)

This module converts an `EpubDocument` (already parsed by
`jw_core.parsers.epub`) into a `WorkbookWeek`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from jw_core.models_meeting import (
    WorkbookAssignment,
    WorkbookSection,
    WorkbookWeek,
)
from jw_core.parsers.epub import Epub, EpubDocument, read_document_xhtml

# Localized labels for sections (subset from parsers/workbook.py — kept in
# sync deliberately so both parsers use the same vocabulary).
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
_DATE_RANGE_RE = re.compile(
    r"(\w+)\s+(\d{1,2})(?:\s*[-–—]\s*(?:(\w+)\s+)?(\d{1,2}))?",
    re.IGNORECASE,
)
_MONTHS_EN = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_MONTHS_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_MONTH_TABLES = {"en": _MONTHS_EN, "es": _MONTHS_ES, "pt": _MONTHS_PT}


def parse_week_from_epub_document(
    document: EpubDocument,
    *,
    year: int,
    pub_code: str = "",
    language: str = "en",
    source_url: str = "",
    epub_path: Path | str | None = None,
) -> WorkbookWeek:
    """Convert one EPUB document into a WorkbookWeek.

    When `epub_path` is provided we re-read the raw XHTML to recover
    section headings (h2/h3) the high-level EpubDocument parser drops.
    Without it we fall back to the paragraph-only heuristic.
    """
    week_of = _infer_monday(document.title, year=year, language=language)
    if epub_path is not None:
        sections = _split_sections_from_xhtml(
            epub_path, document.id, language=language,
        )
    else:
        sections = _split_sections(document.paragraphs, language=language)
    return WorkbookWeek(
        week_of=week_of,
        pub_code=pub_code,
        title=document.title,
        bible_reading=_extract_bible_reading(document.title, document.paragraphs),
        song_opening=_song_at(document.paragraphs, position="opening"),
        song_middle=_song_at(document.paragraphs, position="middle"),
        song_closing=_song_at(document.paragraphs, position="closing"),
        sections=sections,
        source_url=source_url,
        language=language,
    )


def _split_sections_from_xhtml(
    epub_path: Path | str,
    item_id: str,
    *,
    language: str,
) -> list[WorkbookSection]:
    """Walk the raw XHTML preserving heading order.

    Each `<h2>`/`<h3>` whose text matches a localized label opens a new
    `WorkbookSection`. Each `<h3>` (or `<p>` with `(N min)` marker) inside
    becomes a new `WorkbookAssignment` whose body collects the paragraphs
    that follow until the next assignment header.
    """
    xhtml = read_document_xhtml(epub_path, item_id)
    soup = BeautifulSoup(xhtml, "lxml-xml")
    labels = _SECTION_LABELS.get(language, _SECTION_LABELS["en"])

    sections: list[WorkbookSection] = []
    current_section: WorkbookSection | None = None
    current_assignment: WorkbookAssignment | None = None

    for element in soup.find_all(["h2", "h3", "h4", "p"]):
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        # Section header?
        section_match = _match_section(text, labels)
        if section_match is not None and element.name in ("h1", "h2", "h3"):
            if current_assignment is not None and current_section is not None:
                current_section.assignments.append(current_assignment)
                current_assignment = None
            current_section = WorkbookSection(
                name=section_match[0], heading=section_match[1], assignments=[]
            )
            sections.append(current_section)
            continue
        if current_section is None:
            continue
        # Assignment header? Either an explicit heading OR a `(N min)` paragraph.
        minutes = _MINUTES_RE.search(text)
        is_heading_element = element.name in ("h3", "h4")
        if minutes and (is_heading_element or current_assignment is None):
            if current_assignment is not None:
                current_section.assignments.append(current_assignment)
            current_assignment = _new_assignment(text, minutes)
            continue
        if is_heading_element:
            # A heading without a `(N min)` marker still opens a new assignment.
            if current_assignment is not None:
                current_section.assignments.append(current_assignment)
            current_assignment = WorkbookAssignment(title=text[:200], kind="talk")
            continue
        # Body content under current assignment.
        if current_assignment is not None:
            current_assignment.body = (
                f"{current_assignment.body}\n{text}".strip()
                if current_assignment.body
                else text
            )
    if current_assignment is not None and current_section is not None:
        current_section.assignments.append(current_assignment)
    return sections


def find_week_document(
    epub: Epub,
    *,
    target_date: date,
    language: str = "en",
) -> EpubDocument | None:
    """Pick the EPUB document whose date range contains `target_date`."""
    candidates: list[tuple[date, EpubDocument]] = []
    for doc in epub.documents:
        if not doc.paragraphs:
            continue  # cover / nav docs
        first_day = _first_day_from_title(doc.title, year=target_date.year, language=language)
        if first_day is None:
            continue
        candidates.append((first_day, doc))
    if not candidates:
        return None
    # Sort ascending — pick the latest whose first_day <= target_date.
    candidates.sort(key=lambda x: x[0])
    chosen = candidates[0][1]
    for first_day, doc in candidates:
        if first_day <= target_date:
            chosen = doc
    return chosen


def _first_day_from_title(title: str, *, year: int, language: str) -> date | None:
    """Parse 'MAY 6-12' / 'MAY 27–JUNE 2' / 'MAYO 6-12' → date(year, 5, 6)."""
    if not title:
        return None
    match = _DATE_RANGE_RE.search(title)
    if not match:
        return None
    months = _MONTH_TABLES.get(language, _MONTHS_EN)
    raw_month = match.group(1).lower()[:3]
    try:
        month = months.index(raw_month) + 1
    except ValueError:
        return None
    try:
        day = int(match.group(2))
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _infer_monday(title: str, *, year: int, language: str) -> str:
    d = _first_day_from_title(title, year=year, language=language)
    return d.isoformat() if d else ""


def _extract_bible_reading(title: str, paragraphs: list[str]) -> str:
    # The first paragraph in week documents is typically the Bible reading
    # in the format "BIBLE READING | <Books and chapters>".
    for p in paragraphs[:5]:
        upper = p.upper()
        if upper.startswith("BIBLE READING") or upper.startswith("LECTURA DE LA BIBLIA"):
            parts = re.split(r"[|·]", p, maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip()
            return p.strip()
    return title  # fallback


_SONG_RE = re.compile(r"(?:song|cantico|cántico|cântico|c[áa]ntico)\s+(\d{1,3})", re.IGNORECASE)


def _song_at(paragraphs: list[str], *, position: str) -> int | None:
    hits = []
    for p in paragraphs:
        for m in _SONG_RE.finditer(p):
            try:
                hits.append(int(m.group(1)))
            except ValueError:
                continue
    if not hits:
        return None
    if position == "opening":
        return hits[0]
    if position == "closing":
        return hits[-1]
    if len(hits) >= 3:
        return hits[len(hits) // 2]
    if len(hits) == 2:
        return hits[0]
    return None


def _split_sections(paragraphs: list[str], *, language: str) -> list[WorkbookSection]:
    """Walk paragraphs, group by section, then extract assignments per section."""
    labels = _SECTION_LABELS.get(language, _SECTION_LABELS["en"])
    sections: list[WorkbookSection] = []
    current_name = ""
    current_heading = ""
    current_assignments: list[WorkbookAssignment] = []
    current_assignment: WorkbookAssignment | None = None
    for paragraph in paragraphs:
        ptext = paragraph.strip()
        if not ptext:
            continue
        section_match = _match_section(ptext, labels)
        if section_match is not None:
            # Close previous section
            if current_assignment is not None:
                current_assignments.append(current_assignment)
                current_assignment = None
            if current_name:
                sections.append(
                    WorkbookSection(
                        name=current_name,
                        heading=current_heading,
                        assignments=current_assignments,
                    )
                )
            current_name, current_heading = section_match
            current_assignments = []
            continue

        if current_name:
            mm = _MINUTES_RE.search(ptext)
            if mm:
                if current_assignment is not None:
                    current_assignments.append(current_assignment)
                current_assignment = _new_assignment(ptext, mm)
            elif current_assignment is not None:
                current_assignment.body = (
                    f"{current_assignment.body}\n{ptext}".strip()
                    if current_assignment.body
                    else ptext
                )
    if current_assignment is not None:
        current_assignments.append(current_assignment)
    if current_name:
        sections.append(
            WorkbookSection(
                name=current_name,
                heading=current_heading,
                assignments=current_assignments,
            )
        )
    return sections


def _match_section(paragraph: str, labels: list[tuple[str, str]]) -> tuple[str, str] | None:
    lower = paragraph.lower()
    for name, needle in labels:
        if needle in lower:
            return name, paragraph
    return None


def _new_assignment(text: str, minutes_match: re.Match[str]) -> WorkbookAssignment:
    minutes = int(minutes_match.group(1))
    cleaned = _MINUTES_RE.sub("", text).strip(" .:-—–")
    lower = cleaned.lower()
    kind = "talk"
    for guess, needle in (
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
    ):
        if needle in lower:
            kind = guess
            break
    return WorkbookAssignment(
        title=cleaned[:200],
        minutes=minutes,
        kind=kind,
        body="",
    )
