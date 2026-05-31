from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from jw_agents.study_conductor import (
    AnticipationQuestion,
    LessonPrep,
    prepare_lesson,
)


@dataclass
class _FakeLesson:
    pub_code: str = "lff"
    chapter: int = 1
    language: str = "es"
    title: str = "¿Existe alguien que se preocupe por usted?"
    paragraphs: list[str] = field(
        default_factory=lambda: [
            "Jehová es un Padre amoroso (1 Pedro 5:7).",
            "Él se preocupa por usted más de lo que imagina.",
        ]
    )
    scripture_refs: dict[int, list[str]] = field(default_factory=lambda: {1: ["1 Pedro 5:7"], 2: []})
    source: str = "jwpub_local"
    citation_url: str = "https://wol.jw.org/es/wol/publication/r4/lp-s/lff/1"


def test_prepare_lesson_returns_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_agents.study_conductor.extract_lesson",
        lambda *a, **k: _FakeLesson(),
    )
    monkeypatch.setattr(
        "jw_agents.study_conductor._topic_hits",
        lambda *a, **k: ["Jehová", "Padre amoroso"],
    )
    result = prepare_lesson("lff", chapter=1, language="es")
    assert result.agent_name == "study_conductor"
    assert len(result.findings) >= 1

    lesson_finding = result.findings[0]
    assert lesson_finding.citation.url.startswith("https://wol.jw.org/")
    assert lesson_finding.metadata["source"] == "jwpub_chapter"
    prep = lesson_finding.metadata["payload"]
    assert isinstance(prep, LessonPrep)
    assert prep.pub_code == "lff"
    assert len(prep.questions) >= 2
    assert any("1 Pedro 5:7" in q.text for q in prep.questions)


def test_prepare_lesson_unknown_pub_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    from jw_core.study.lesson_extractor import LessonExtractionError

    def boom(*a: Any, **k: Any) -> Any:
        raise LessonExtractionError("nope")

    monkeypatch.setattr("jw_agents.study_conductor.extract_lesson", boom)
    result = prepare_lesson("nope", chapter=1, language="es")
    assert result.findings == []
    assert any("nope" in w for w in result.warnings)


def test_anticipation_question_dataclass() -> None:
    q = AnticipationQuestion(
        paragraph_index=1,
        text="hi",
        template_id="es.fact",
        related_verses=[],
    )
    assert q.paragraph_index == 1
