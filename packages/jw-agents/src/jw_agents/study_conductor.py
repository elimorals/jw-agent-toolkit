"""study_conductor — procedural agent for preparing study-book lessons.

VISION rule: "No sustituir la palabra de los ancianos". This agent
generates **preparation material for the conductor** (the brother doing
the personal study), NOT a script to read aloud.

Pipeline:
    1. extract_lesson(pub, chapter, lang)  — load content (JWPUB or WOL).
    2. generate_anticipation_questions(...) — templated questions.
    3. topic_index hits for the chapter title — supporting subjects.
    4. wrap as AgentResult with stable source ordering (Fase 22 L1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from jw_core.data.study_prompts import render_template
from jw_core.study.lesson_extractor import (
    LessonContent,
    LessonExtractionError,
    extract_lesson,
)

from jw_agents.base import AgentResult, Citation, Finding

AGENT_NAME = "study_conductor"


@dataclass(frozen=True)
class AnticipationQuestion:
    paragraph_index: int
    text: str
    template_id: str
    related_verses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LessonPrep:
    pub_code: str
    chapter: int
    language: str
    title: str
    summary: str
    questions: list[AnticipationQuestion]
    key_verses: list[str]
    supporting_topics: list[str]
    source: Literal["jwpub_local", "wol_fallback"]


def prepare_lesson(pub_code: str, chapter: int, language: str = "es") -> AgentResult:
    query = f"prepare_lesson({pub_code!r}, ch={chapter}, lang={language!r})"
    warnings: list[str] = []
    findings: list[Finding] = []

    try:
        content = extract_lesson(pub_code, chapter, language)
    except LessonExtractionError as e:
        return AgentResult(
            query=query,
            agent_name=AGENT_NAME,
            findings=[],
            warnings=[str(e)],
        )

    if content.source == "wol_fallback":
        warnings.append("JWPUB local no encontrado: usando WOL como fallback.")

    questions = _generate_anticipation_questions(content)
    key_verses = sorted({r for refs in content.scripture_refs.values() for r in refs})
    topics = _topic_hits(content.title, language)

    prep = LessonPrep(
        pub_code=content.pub_code,
        chapter=content.chapter,
        language=content.language,
        title=content.title,
        summary=_make_summary(content),
        questions=questions,
        key_verses=key_verses,
        supporting_topics=topics,
        source=content.source,
    )

    # Primary finding: the lesson itself (highest-priority source).
    findings.append(
        Finding(
            summary=f"Lección {content.chapter} — {content.title}",
            excerpt=prep.summary,
            citation=Citation(
                url=content.citation_url,
                title=content.title,
                kind="chapter",
            ),
            metadata={
                "source": "jwpub_chapter" if content.source == "jwpub_local" else "wol_chapter",
                "payload": prep,
            },
        )
    )

    # Secondary findings: topic_index subjects (lower priority).
    for subject in topics:
        findings.append(
            Finding(
                summary=f"Tema relacionado: {subject}",
                excerpt="",
                citation=Citation(url=content.citation_url, title=subject, kind="topic"),
                metadata={"source": "topic_index"},
            )
        )

    return AgentResult(
        query=query,
        agent_name=AGENT_NAME,
        findings=findings,
        warnings=warnings,
        metadata={"pub_code": pub_code, "chapter": chapter, "language": language},
    )


def _generate_anticipation_questions(content: LessonContent) -> list[AnticipationQuestion]:
    """Two questions per paragraph (fact + application); +scripture when refs exist."""

    out: list[AnticipationQuestion] = []
    for idx, _para in enumerate(content.paragraphs, start=1):
        out.append(
            AnticipationQuestion(
                paragraph_index=idx,
                text=render_template(content.language, "fact", n=idx),
                template_id=f"{content.language}.fact",
                related_verses=[],
            )
        )
        out.append(
            AnticipationQuestion(
                paragraph_index=idx,
                text=render_template(content.language, "application", n=idx),
                template_id=f"{content.language}.application",
                related_verses=[],
            )
        )
        refs = content.scripture_refs.get(idx, [])
        for ref in refs:
            out.append(
                AnticipationQuestion(
                    paragraph_index=idx,
                    text=render_template(content.language, "scripture", n=idx, ref=ref),
                    template_id=f"{content.language}.scripture",
                    related_verses=[ref],
                )
            )
    return out


def _make_summary(content: LessonContent) -> str:
    # First paragraph clipped; deterministic, no LLM.
    if not content.paragraphs:
        return content.title
    first = content.paragraphs[0]
    return (first[:320] + "…") if len(first) > 320 else first


def _topic_hits(title: str, language: str) -> list[str]:
    """Up to 3 supporting subjects from topic_index. Best-effort, no raise."""

    try:
        from jw_core.clients.factory import build_clients

        suite = build_clients()
        results = suite.topic_index.search(title, language=language)
        return [r.title for r in (results or [])[:3]]
    except Exception:
        return []
