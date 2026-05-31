"""JW-specific data extractors that produce SFT pairs WITHOUT calling an LLM.

The toolkit already parses several JW publication formats into structures
that contain Q&A-shaped data natively:

  * Watchtower Study articles: each paragraph has its own study questions
    printed below it. The (text, questions) pairs are SFT-quality material
    written by WBTS itself — no synthesis needed.
  * NWT Study Notes: each note is aligned to a specific verse via the
    `jw_core.parsers.study_notes` algorithm. (verse, note) is exactly the
    verse-explainer task format.
  * Objection catalog: curated objection keys + topic/scripture anchors
    that ground real apologetics-style SFT pairs.
  * Workbook (Vida y Ministerio): timed assignments with structured cues —
    perfect for ministry-school SFT data.
  * JW Library backup: the user's own notes/highlights — gold for a
    personalized "study companion" preset.

This module CONVERTS those structures into `QAPair` records that flow
through the rest of the pipeline (formats → train) untouched. The synth
layer remains available for free-form chunks where genuine Q&A doesn't
exist.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from jw_finetune.data.formats import QAPair

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1.1 — Watchtower Study: real (text, question) pairs
# ---------------------------------------------------------------------------


def extract_watchtower_study_qa(
    html: str,
    *,
    pub_code: str,
    language: str = "es",
    source_url: str = "",
) -> Iterator[QAPair]:
    """Yield QAPair per (paragraph, question) from a Watchtower Study article.

    JW prints multiple questions per paragraph; we emit one QAPair per
    question, all sharing the same paragraph text as the answer. This is
    deliberate: the model learns to answer EACH question with the same
    canonical paragraph rather than averaging.
    """
    from jw_core.parsers.watchtower_study import parse_watchtower_study

    study = parse_watchtower_study(html)
    if not study or not study.paragraphs:
        logger.info("No paragraphs found in watchtower study (pub=%s)", pub_code)
        return

    for p in study.paragraphs:
        text = p.text.strip()
        if not text or not p.questions:
            continue
        for q in p.questions:
            question = q.strip()
            if not question:
                continue
            yield QAPair(
                question=question,
                answer=text,
                source_chunk_id=f"{pub_code}:par-{p.number}",
                language=language,
                metadata={
                    "pub_code": pub_code,
                    "kind": "watchtower",
                    "qa_style": "study-question",
                    "paragraph_number": str(p.number),
                    "source_url": source_url,
                    "scripture_refs": ",".join(p.scripture_refs),
                    "provenance": "extracted",  # not LLM-synthesized
                },
            )


def extract_watchtower_study_qa_from_file(
    path: Path | str,
    *,
    pub_code: str = "w",
    language: str = "es",
) -> list[QAPair]:
    """Convenience: read an HTML file from disk and extract Q&A pairs."""
    p = Path(path)
    return list(
        extract_watchtower_study_qa(
            p.read_text(encoding="utf-8"),
            pub_code=pub_code,
            language=language,
            source_url=str(p),
        )
    )


# ---------------------------------------------------------------------------
# 1.2 — NWT Study Notes → verse-explainer SFT
# ---------------------------------------------------------------------------


_BOOK_NAMES_ES: dict[int, str] = {
    1: "Génesis", 2: "Éxodo", 3: "Levítico", 4: "Números", 5: "Deuteronomio",
    6: "Josué", 7: "Jueces", 8: "Rut", 9: "1 Samuel", 10: "2 Samuel",
    11: "1 Reyes", 12: "2 Reyes", 13: "1 Crónicas", 14: "2 Crónicas",
    15: "Esdras", 16: "Nehemías", 17: "Ester", 18: "Job", 19: "Salmo",
    20: "Proverbios", 21: "Eclesiastés", 22: "Cantar de los Cantares",
    23: "Isaías", 24: "Jeremías", 25: "Lamentaciones", 26: "Ezequiel",
    27: "Daniel", 28: "Oseas", 29: "Joel", 30: "Amós", 31: "Abdías",
    32: "Jonás", 33: "Miqueas", 34: "Nahúm", 35: "Habacuc", 36: "Sofonías",
    37: "Hageo", 38: "Zacarías", 39: "Malaquías",
    40: "Mateo", 41: "Marcos", 42: "Lucas", 43: "Juan", 44: "Hechos",
    45: "Romanos", 46: "1 Corintios", 47: "2 Corintios", 48: "Gálatas",
    49: "Efesios", 50: "Filipenses", 51: "Colosenses",
    52: "1 Tesalonicenses", 53: "2 Tesalonicenses", 54: "1 Timoteo",
    55: "2 Timoteo", 56: "Tito", 57: "Filemón", 58: "Hebreos",
    59: "Santiago", 60: "1 Pedro", 61: "2 Pedro", 62: "1 Juan",
    63: "2 Juan", 64: "3 Juan", 65: "Judas", 66: "Apocalipsis",
}

_BOOK_NAMES_EN: dict[int, str] = {
    1: "Genesis", 2: "Exodus", 3: "Leviticus", 4: "Numbers", 5: "Deuteronomy",
    6: "Joshua", 7: "Judges", 8: "Ruth", 9: "1 Samuel", 10: "2 Samuel",
    11: "1 Kings", 12: "2 Kings", 13: "1 Chronicles", 14: "2 Chronicles",
    15: "Ezra", 16: "Nehemiah", 17: "Esther", 18: "Job", 19: "Psalm",
    20: "Proverbs", 21: "Ecclesiastes", 22: "Song of Solomon",
    23: "Isaiah", 24: "Jeremiah", 25: "Lamentations", 26: "Ezekiel",
    27: "Daniel", 28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadiah",
    32: "Jonah", 33: "Micah", 34: "Nahum", 35: "Habakkuk", 36: "Zephaniah",
    37: "Haggai", 38: "Zechariah", 39: "Malachi",
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John", 44: "Acts",
    45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians", 48: "Galatians",
    49: "Ephesians", 50: "Philippians", 51: "Colossians",
    52: "1 Thessalonians", 53: "2 Thessalonians", 54: "1 Timothy",
    55: "2 Timothy", 56: "Titus", 57: "Philemon", 58: "Hebrews",
    59: "James", 60: "1 Peter", 61: "2 Peter", 62: "1 John",
    63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation",
}


def _format_verse_ref(book_num: int, chapter: int, verse: int | None, language: str) -> str:
    book = _BOOK_NAMES_ES.get(book_num) if language.startswith("es") else _BOOK_NAMES_EN.get(book_num)
    if not book:
        book = f"Book {book_num}"
    if verse is None:
        return f"{book} {chapter}"
    return f"{book} {chapter}:{verse}"


def extract_study_notes_qa(
    html: str,
    *,
    book_num: int,
    chapter: int,
    language: str = "es",
    min_confidence: str = "headword",  # "headword" | "positional" | "any"
    source_url: str = "",
) -> Iterator[QAPair]:
    """Yield QAPair per study note from a NWT Study Edition chapter.

    Each note becomes:
        Q: "Explica {ref}, ¿qué significa '{headword}'?"
        A: "{body}"

    Notes with confidence below `min_confidence` are skipped — set
    `min_confidence='any'` to include positional-matched notes too.
    """
    from jw_core.parsers.study_notes import parse_study_notes

    notes = parse_study_notes(
        html, book_num=book_num, chapter=chapter, language=language
    )

    conf_rank = {"headword": 2, "positional": 1, "unmatched": 0, "any": 0}
    threshold = conf_rank.get(min_confidence, 2)

    for note in notes:
        if conf_rank.get(note.confidence, 0) < threshold:
            continue
        body = (note.body or "").strip()
        if not body:
            continue
        ref = _format_verse_ref(note.book_num, note.chapter, note.verse, language)
        headword = (note.headword or "").strip()
        if language.startswith("es"):
            question = (
                f"Explica {ref}: ¿qué significa «{headword}»?"
                if headword else f"Explica {ref}."
            )
        else:
            question = (
                f"Explain {ref}: what does “{headword}” mean?"
                if headword else f"Explain {ref}."
            )
        yield QAPair(
            question=question,
            answer=body,
            source_chunk_id=f"nwtsty:{book_num}:{chapter}:{note.verse or 0}",
            language=language,
            metadata={
                "pub_code": "nwtsty",
                "kind": "bible",
                "qa_style": "verse-explain",
                "book_num": str(book_num),
                "chapter": str(chapter),
                "verse": str(note.verse or ""),
                "headword": headword,
                "confidence": note.confidence,
                "source_url": source_url,
                "provenance": "extracted",
            },
        )


# ---------------------------------------------------------------------------
# 1.3 — Cross-reference enrichment for chunks
# ---------------------------------------------------------------------------


async def enrich_chunk_with_verses(
    chunk_text: str,
    *,
    language: str = "es",
    wol_client: Any | None = None,
    max_refs: int = 5,
) -> dict[str, str]:
    """Resolve all bible refs inside `chunk_text` to their verse text.

    Returns a dict mapping `"book c:v"` → verse text. The dict is meant to
    be merged into chunk metadata and rendered into the SFT prompt so the
    model sees the *resolved* verses alongside the chunk.

    Uses `jw_core.parsers.reference.parse_all_references` to find refs and
    `WOLClient.get_bible_chapter` to fetch the verse text.
    """
    from jw_core.parsers.reference import parse_all_references

    refs = parse_all_references(chunk_text)
    if not refs:
        return {}

    owned = False
    if wol_client is None:
        from jw_core.clients.wol import WOLClient
        wol_client = WOLClient()
        owned = True

    resolved: dict[str, str] = {}
    try:
        # Group by (book, chapter) so we only fetch each chapter once.
        seen_chapters: dict[tuple[int, int], str] = {}
        for ref in refs[:max_refs]:
            key = (ref.book_num, ref.chapter)
            try:
                if key not in seen_chapters:
                    _url, html = await wol_client.get_bible_chapter(
                        ref.book_num, ref.chapter, language=language
                    )
                    seen_chapters[key] = html
                # Extract verse-specific text — we use a minimal regex
                # since the structured verse parser lives in jw-core.
                verse_text = _extract_single_verse(
                    seen_chapters[key], ref.verse_start
                )
                if verse_text:
                    ref_key = _format_verse_ref(
                        ref.book_num, ref.chapter, ref.verse_start, language
                    )
                    resolved[ref_key] = verse_text
            except Exception as e:  # noqa: BLE001
                logger.debug("Failed to resolve ref %s: %s", ref.raw_match, e)
    finally:
        if owned:
            await wol_client.aclose()
    return resolved


def _extract_single_verse(html: str, verse_num: int | None) -> str:
    """Best-effort: pull a verse's text out of a WOL chapter HTML."""
    if verse_num is None or not html:
        return ""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # WOL marks each verse with a span class like 'vl' or an id 'v...'
    for sel in (
        f'span[id="v{verse_num}"]',
        f'[id*="-v{verse_num}-"]',
    ):
        el = soup.select_one(sel)
        if el is None:
            continue
        # The verse text often lives in the parent paragraph after the marker.
        parent = el.find_parent("p") or el.find_parent("span") or el
        text = parent.get_text(" ", strip=True)
        if text:
            return text
    return ""


# ---------------------------------------------------------------------------
# 1.4 — JW Library backup → user-notes SFT
# ---------------------------------------------------------------------------


def discover_jw_library_publications(backup_path: Path | str) -> list[dict[str, str]]:
    """Return the list of publication codes referenced in a JW Library backup.

    Useful to auto-populate `Recipe.sources` without the user typing each
    JWPUB path. The toolkit knows where to map pub_codes → JWPUB files via
    `jw_library_backup.parse_jw_library_backup`.
    """
    from jw_core.parsers.jw_library_backup import parse_jw_library_backup

    backup = parse_jw_library_backup(backup_path)
    seen: set[str] = set()
    pubs: list[dict[str, str]] = []
    for note in backup.notes:
        if note.location is None:
            continue
        pub = getattr(note.location, "key_symbol", "") or ""
        if pub and pub not in seen:
            seen.add(pub)
            pubs.append({
                "pub_code": pub,
                "kind": "note-source",
            })
    for hl in backup.highlights:
        pub = getattr(hl.location, "key_symbol", "") or ""
        if pub and pub not in seen:
            seen.add(pub)
            pubs.append({"pub_code": pub, "kind": "highlight-source"})
    return pubs


def extract_user_notes_qa(
    backup_path: Path | str,
    *,
    language: str = "es",
    min_note_chars: int = 30,
) -> Iterator[QAPair]:
    """Convert user notes into SFT pairs: title → content.

    The user's own notes encode WHAT they care about. Fine-tuning on these
    yields a personalized study companion.
    """
    from jw_core.parsers.jw_library_backup import parse_jw_library_backup

    backup = parse_jw_library_backup(backup_path)
    for note in backup.notes:
        body = (note.content or "").strip()
        if len(body) < min_note_chars:
            continue
        title = (note.title or "").strip()
        loc = note.location
        loc_str = ""
        if loc is not None:
            book_num = getattr(loc, "book_number", None)
            chapter = getattr(loc, "chapter_number", None)
            verse = getattr(loc, "verse_number", None) or getattr(loc, "track_number", None)
            if book_num and chapter:
                loc_str = _format_verse_ref(book_num, chapter, verse, language)
        if language.startswith("es"):
            question = title or (
                f"¿Qué notas tomé sobre {loc_str}?" if loc_str else "Nota personal."
            )
        else:
            question = title or (
                f"What notes did I take on {loc_str}?" if loc_str else "Personal note."
            )
        yield QAPair(
            question=question,
            answer=body,
            source_chunk_id=f"user-note:{note.note_id}",
            language=language,
            metadata={
                "pub_code": "user-notes",
                "kind": "user-note",
                "qa_style": "personal-study",
                "note_guid": note.guid,
                "location_ref": loc_str,
                "provenance": "extracted",
            },
        )


# ---------------------------------------------------------------------------
# 1.5 — Topic Index → terminology vocabulary
# ---------------------------------------------------------------------------


def build_terminology_set_from_topic_index(
    subjects: Iterable[Any],
    *,
    min_chars: int = 3,
    max_chars: int = 30,
) -> set[str]:
    """Mine the Watch Tower Publications Index for canonical JW terms.

    `subjects` is an iterable of `TopicSubject` objects (parsed from WOL
    subject pages via `jw_core.parsers.topic_index.parse_subject_page`).
    Each subject's main heading + subheading titles become candidate terms.

    Returns a lowercased set, deduplicated and filtered by length.
    """
    terms: set[str] = set()
    for subject in subjects:
        title = (getattr(subject, "title", "") or "").strip()
        if min_chars <= len(title) <= max_chars:
            terms.add(title.lower())
        for sub in getattr(subject, "subheadings", []) or []:
            sub_title = (getattr(sub, "title", "") or "").strip()
            if min_chars <= len(sub_title) <= max_chars:
                terms.add(sub_title.lower())
    return terms


# ---------------------------------------------------------------------------
# 1.6 — Objection catalog → SFT pairs (uses topic anchors for grounding)
# ---------------------------------------------------------------------------


def extract_objection_qa(
    *,
    language: str = "es",
    topic_resolver: Any | None = None,
    scripture_resolver: Any | None = None,
) -> list[QAPair]:
    """Convert the curated objection catalog into SFT pairs.

    For each objection in `jw_core.data.objections.CATALOG`:
      - Q = the localized objection label
      - A = the topic anchor list + scripture anchor list, formatted as a
        structured reply skeleton.

    The skeleton is intentionally simple: real prose comes from the user's
    later RAG context or from `apologetics` agent. We're teaching the model
    the *shape* of an objection reply — anchored, scripture-cited, calm.
    """
    from jw_core.data.objections import CATALOG

    out: list[QAPair] = []
    for obj in CATALOG:
        q = obj.label(language)
        if not q:
            continue
        a_parts: list[str] = []
        if obj.scripture_anchors:
            if language.startswith("es"):
                a_parts.append("Considere los siguientes textos:")
            else:
                a_parts.append("Consider the following scriptures:")
            for ref in obj.scripture_anchors:
                a_parts.append(f"  • {ref}")
        if obj.topic_anchors:
            if language.startswith("es"):
                a_parts.append("\nTemas relacionados en las publicaciones:")
            else:
                a_parts.append("\nRelated topics in the publications:")
            for t in obj.topic_anchors:
                a_parts.append(f"  • {t}")
        if not a_parts:
            continue
        a = "\n".join(a_parts)
        out.append(QAPair(
            question=q,
            answer=a,
            source_chunk_id=f"objection:{obj.key}",
            language=language,
            metadata={
                "pub_code": "objections-catalog",
                "kind": "objection",
                "qa_style": "objection-handling",
                "objection_key": obj.key,
                "category": obj.category,
                "provenance": "extracted",
            },
        ))
    return out


# ---------------------------------------------------------------------------
# 1.7 — Workbook (Vida y Ministerio) → ministry-school SFT
# ---------------------------------------------------------------------------


def extract_workbook_qa(
    weeks: Iterable[Any],
    *,
    language: str = "es",
) -> Iterator[QAPair]:
    """Convert workbook weeks into SFT pairs.

    Each timed assignment becomes a Q&A where:
      - Q describes the assignment shape ("Prepara una conversación de 3 min...")
      - A is the workbook's own descriptive paragraph (`assignment.body`).

    `weeks` is an iterable of `WorkbookWeek` models (from
    `jw_core.parsers.workbook` or `workbook_epub`).
    """
    SECTION_LABELS_ES = {
        "treasures": "Tesoros de la Biblia",
        "apply_yourself": "Sea mejor ministro",
        "living_as_christians": "Nuestra vida cristiana",
    }
    SECTION_LABELS_EN = {
        "treasures": "Treasures From God's Word",
        "apply_yourself": "Apply Yourself to the Field Ministry",
        "living_as_christians": "Living as Christians",
    }
    labels = SECTION_LABELS_ES if language.startswith("es") else SECTION_LABELS_EN

    for week in weeks:
        pub_code = getattr(week, "pub_code", "mwb")
        week_of = getattr(week, "week_of", "")
        for section in getattr(week, "sections", []) or []:
            section_label = labels.get(section.name, section.heading or section.name)
            for assn in section.assignments or []:
                body = (assn.body or "").strip()
                title = (assn.title or "").strip()
                if not body or not title:
                    continue
                minutes = f"({assn.minutes} min)" if assn.minutes else ""
                if language.startswith("es"):
                    q = (
                        f"En la sección «{section_label}» del programa de la reunión, "
                        f"¿cómo prepararías «{title}» {minutes}?"
                    )
                else:
                    q = (
                        f"In the «{section_label}» section of the meeting, "
                        f"how would you prepare «{title}» {minutes}?"
                    )
                refs = ",".join(assn.references) if assn.references else ""
                yield QAPair(
                    question=q.strip(),
                    answer=body,
                    source_chunk_id=f"{pub_code}:{week_of}:{section.name}:{title[:30]}",
                    language=language,
                    metadata={
                        "pub_code": pub_code,
                        "kind": "workbook",
                        "qa_style": "ministry-school",
                        "section": section.name,
                        "week_of": week_of,
                        "assignment_kind": assn.kind,
                        "minutes": str(assn.minutes or ""),
                        "scripture_refs": refs,
                        "cue": assn.cue,
                        "provenance": "extracted",
                    },
                )
