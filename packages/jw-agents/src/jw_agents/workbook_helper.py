"""workbook_helper agent — discover the weekly Workbook + Watchtower Study.

LIVE-VERIFIED FLOW (May 2026):

  1. The Meeting Workbook is published as `mwb_E_YYYYMM.epub` via the
     pub-media GETPUBMEDIALINKS endpoint (`pub=mwb&issue=YYYYMM`). The
     WOL URL pattern `/.../publication/mwb24.05` returns 404 — we don't use it.
  2. The Watchtower Study Edition is published as `w_E_YYYYMM.epub`
     (`pub=w&issue=YYYYMM`). The first 5-6 documents after the cover/TOC
     are the study articles.

Both EPUBs are cached on disk at `~/.jw-agent-toolkit/epubs/` (override
`JW_EPUB_CACHE`). The agent re-downloads only when the cached file is
missing or older than 30 days.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

from jw_core.clients.pub_media import PubMediaClient, PubMediaError
from jw_core.clients.wol import WOLClient
from jw_core.models_meeting import (
    CommentSuggestion,
    WatchtowerStudy,
    WatchtowerStudyParagraph,
    WorkbookWeek,
)
from jw_core.parsers.epub import parse_epub
from jw_core.parsers.workbook_epub import find_week_document, parse_week_from_epub_document

from jw_agents.base import AgentResult, Citation, Finding

logger = logging.getLogger(__name__)

_LANG_TO_JW = {
    "en": "E",
    "es": "S",
    "pt": "T",
    "fr": "F",
    "de": "X",
    "it": "I",
    "ru": "U",
    "ja": "J",
    "ko": "KO",
    "zh": "CHS",
}

_COMMENT_INTROS: dict[str, dict[str, str]] = {
    "en": {
        "main_point": "The key thought here is that",
        "practical_application": "I appreciated how this applies practically:",
        "scripture_link": "What stood out was how this links to",
        "personal_experience": "This made me think of a personal experience —",
    },
    "es": {
        "main_point": "El punto principal aquí es que",
        "practical_application": "Me llamó la atención cómo aplica esto:",
        "scripture_link": "Lo que destacó fue cómo se conecta con",
        "personal_experience": "Esto me hizo pensar en una experiencia personal:",
    },
    "pt": {
        "main_point": "O ponto principal aqui é que",
        "practical_application": "O que me chamou a atenção foi a aplicação prática:",
        "scripture_link": "O que se destacou foi a ligação com",
        "personal_experience": "Isso me lembrou de uma experiência pessoal:",
    },
}


def _epub_cache_dir() -> Path:
    raw = os.getenv("JW_EPUB_CACHE", "~/.jw-agent-toolkit/epubs/")
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _is_stale(path: Path, *, max_age_days: int = 30) -> bool:
    if not path.exists():
        return True
    import time

    return (time.time() - path.stat().st_mtime) > max_age_days * 86400


async def _download_epub(
    pub: PubMediaClient,
    *,
    pub_code: str,
    issue: int,
    language: str,
    cache_dir: Path,
) -> Path | None:
    """Ensure the EPUB for (pub, issue, language) is on disk and return its path."""
    jw_code = _LANG_TO_JW.get(language, language.upper())
    filename = f"{pub_code}_{jw_code}_{issue:06d}.epub"
    dest = cache_dir / filename
    if not _is_stale(dest):
        return dest
    try:
        publication = await pub.get_publication(pub_code, issue=issue, language=jw_code, file_format="EPUB")
    except PubMediaError as e:
        logger.warning("pub_media miss for %s/%s: %s", pub_code, issue, e)
        return None
    files = publication.files_by_format("EPUB")
    if not files:
        logger.warning("No EPUB available for %s issue=%s lang=%s", pub_code, issue, jw_code)
        return None
    await pub.download(files[0], dest)
    return dest


async def workbook_helper(
    target_date: str | date | None = None,
    *,
    language: str = "en",
    include_watchtower: bool = True,
    include_comments: bool = True,
    comments_per_paragraph: int = 1,
    wol: WOLClient | None = None,
    pub: PubMediaClient | None = None,
) -> AgentResult:
    """Discover the week's workbook + WT study from a date (LIVE pipeline)."""
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    monday = target_date - timedelta(days=target_date.weekday())

    result = AgentResult(query=monday.isoformat(), agent_name="workbook_helper")
    result.metadata.update(
        {
            "language": language,
            "week_of": monday.isoformat(),
            "pipeline": "epub",
        }
    )

    owned_pub = pub is None
    pub = pub or PubMediaClient()
    cache_dir = _epub_cache_dir()

    try:
        # Workbook: bimonthly issue (Jan-Feb → 01, Mar-Apr → 03, ...).
        mwb_issue = _bimonthly_issue(monday)
        result.metadata["workbook_issue"] = mwb_issue
        mwb_path = await _download_epub(pub, pub_code="mwb", issue=mwb_issue, language=language, cache_dir=cache_dir)
        if mwb_path is None:
            result.warnings.append(f"Workbook EPUB not available for {mwb_issue}")
        else:
            week = _parse_workbook_for_date(mwb_path, target_date=monday, language=language)
            if week is None:
                result.warnings.append(f"No week document matches {monday.isoformat()} in {mwb_path.name}")
            else:
                _emit_workbook_findings(result, week, source_path=mwb_path)

        # Watchtower: monthly issue, studied two months after print.
        if include_watchtower:
            wt_issue = _watchtower_issue(monday)
            result.metadata["watchtower_issue"] = wt_issue
            wt_path = await _download_epub(pub, pub_code="w", issue=wt_issue, language=language, cache_dir=cache_dir)
            if wt_path is None:
                result.warnings.append(f"Watchtower EPUB not available for {wt_issue}")
            else:
                studies = _parse_watchtower(wt_path, language=language, pub_code=f"w{wt_issue}")
                for s in studies:
                    _emit_watchtower_findings(
                        result,
                        s,
                        include_comments=include_comments,
                        comments_per_paragraph=comments_per_paragraph,
                        language=language,
                    )
    finally:
        if owned_pub:
            await pub.aclose()

    return result


def _bimonthly_issue(d: date) -> int:
    month = d.month if d.month % 2 == 1 else d.month - 1
    return d.year * 100 + month


def _watchtower_issue(d: date) -> int:
    month = d.month - 2
    year = d.year
    while month < 1:
        month += 12
        year -= 1
    return year * 100 + month


def _parse_workbook_for_date(
    epub_path: Path,
    *,
    target_date: date,
    language: str,
) -> WorkbookWeek | None:
    epub = parse_epub(epub_path)
    doc = find_week_document(epub, target_date=target_date, language=language)
    if doc is None:
        return None
    return parse_week_from_epub_document(
        doc,
        year=target_date.year,
        epub_path=epub_path,
        pub_code=epub.title,
        language=language,
        source_url=str(epub_path),
    )


def _parse_watchtower(
    epub_path: Path,
    *,
    language: str,
    pub_code: str,
) -> list[WatchtowerStudy]:
    """Extract study articles from a WT EPUB.

    Heuristic: skip cover/TOC/page-nav/extracted docs. Keep documents with
    title that does NOT start with 'Cover', 'Table of Contents',
    'Page Navigation', or 'Extracted Text'.
    """
    epub = parse_epub(epub_path)
    out: list[WatchtowerStudy] = []
    study_idx = 0
    for doc in epub.documents:
        if not doc.paragraphs:
            continue
        title = (doc.title or "").strip()
        if not title:
            continue
        if title.lower().startswith(
            ("cover", "table of contents", "page navigation", "extracted text", "study edition", "indice", "índice")
        ):
            continue
        study_idx += 1
        paragraphs = [
            WatchtowerStudyParagraph(number=i + 1, text=p, scripture_refs=[]) for i, p in enumerate(doc.paragraphs)
        ]
        out.append(
            WatchtowerStudy(
                pub_code=pub_code,
                study_number=study_idx,
                title=title,
                theme_scripture="",
                summary=doc.paragraphs[0] if doc.paragraphs else "",
                paragraphs=paragraphs,
                source_url=str(epub_path),
                language=language,
            )
        )
    return out


# ── Comment synthesis ───────────────────────────────────────────────────


def _emit_workbook_findings(result: AgentResult, week: WorkbookWeek, *, source_path: Path) -> None:
    result.findings.append(
        Finding(
            summary=f"Workbook week of {week.week_of}",
            excerpt=week.title or week.bible_reading,
            citation=Citation(
                url=f"file://{source_path}",
                title=week.title,
                kind="workbook_week",
                metadata={
                    "bible_reading": week.bible_reading,
                    "assignment_count": week.assignment_count,
                    "songs": {
                        "opening": week.song_opening,
                        "middle": week.song_middle,
                        "closing": week.song_closing,
                    },
                },
            ),
            metadata={"source": "workbook_week"},
        )
    )
    for section in week.sections:
        for assignment in section.assignments:
            result.findings.append(
                Finding(
                    summary=f"{section.heading or section.name}: {assignment.title}",
                    excerpt=assignment.body,
                    citation=Citation(
                        url=f"file://{source_path}",
                        title=assignment.title,
                        kind="workbook_assignment",
                        metadata={
                            "section": section.name,
                            "minutes": assignment.minutes,
                            "kind": assignment.kind,
                        },
                    ),
                    metadata={"source": "workbook_assignment"},
                )
            )


def _emit_watchtower_findings(
    result: AgentResult,
    study: WatchtowerStudy,
    *,
    include_comments: bool,
    comments_per_paragraph: int,
    language: str,
) -> None:
    result.findings.append(
        Finding(
            summary=f"Watchtower Study — {study.title}",
            excerpt=study.summary,
            citation=Citation(
                url=study.source_url,
                title=study.title,
                kind="watchtower_study",
                metadata={
                    "study_number": study.study_number,
                    "paragraph_count": study.paragraph_count,
                },
            ),
            metadata={"source": "watchtower_study"},
        )
    )
    for para in study.paragraphs:
        result.findings.append(
            Finding(
                summary=f"Paragraph {para.number}",
                excerpt=para.text,
                citation=Citation(
                    url=study.source_url,
                    title=f"{study.title} ¶{para.number}",
                    kind="watchtower_paragraph",
                    metadata={"paragraph_number": para.number},
                ),
                metadata={"source": "watchtower_paragraph"},
            )
        )
        if include_comments:
            for comment in synthesize_comments(
                para,
                study=study,
                language=language,
                max_comments=comments_per_paragraph,
            ):
                result.findings.append(
                    Finding(
                        summary=f"Suggested comment (¶{para.number}, {comment.angle})",
                        excerpt=comment.script,
                        citation=Citation(
                            url=comment.source_url,
                            title=f"Comment for ¶{para.number}",
                            kind="comment_suggestion",
                            metadata={"angle": comment.angle, "duration_seconds": comment.duration_seconds},
                        ),
                        metadata={"source": "comment_suggestion"},
                    )
                )


def synthesize_comments(
    paragraph: WatchtowerStudyParagraph,
    *,
    study: WatchtowerStudy,
    language: str = "en",
    max_comments: int = 1,
) -> list[CommentSuggestion]:
    intros = _COMMENT_INTROS.get(language, _COMMENT_INTROS["en"])
    sentences = _split_sentences(paragraph.text)
    main_point = sentences[0] if sentences else paragraph.text[:200]
    suggestions: list[CommentSuggestion] = [
        CommentSuggestion(
            paragraph_number=paragraph.number,
            duration_seconds=25,
            angle="main_point",
            script=f"{intros['main_point']} {main_point}",
            scripture_refs=paragraph.scripture_refs[:1],
            source_url=study.source_url,
        )
    ]
    if max_comments >= 2 and paragraph.scripture_refs:
        suggestions.append(
            CommentSuggestion(
                paragraph_number=paragraph.number,
                duration_seconds=20,
                angle="scripture_link",
                script=(
                    f"{intros['scripture_link']} {paragraph.scripture_refs[0]}. "
                    f"{sentences[1] if len(sentences) > 1 else ''}"
                ).strip(),
                scripture_refs=paragraph.scripture_refs[:2],
                source_url=study.source_url,
            )
        )
    if max_comments >= 3:
        suggestions.append(
            CommentSuggestion(
                paragraph_number=paragraph.number,
                duration_seconds=30,
                angle="practical_application",
                script=f"{intros['practical_application']} {sentences[-1] if sentences else paragraph.text[:200]}",
                source_url=study.source_url,
            )
        )
    return suggestions[:max_comments]


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?" and len(buf.strip()) > 30:
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
