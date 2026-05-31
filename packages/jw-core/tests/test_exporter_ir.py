"""Tests for jw_core.exporters.ir — the StudySheet IR and AgentResult conversion."""

from __future__ import annotations

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet


def _sample_result() -> AgentResult:
    return AgentResult(
        query="Es la Trinidad bíblica?",
        agent_name="apologetics",
        findings=[
            Finding(
                summary="La Biblia presenta a Jehová como el único Dios verdadero.",
                citation=Citation(
                    url="https://wol.jw.org/es/wol/d/r4/lp-s/1101989140",
                    title="¿Qué enseña la Biblia sobre la Trinidad?",
                    kind="article",
                    metadata={"source": "topic_index"},
                ),
                excerpt="Jehová es uno solo (Deuteronomio 6:4).",
                metadata={"source": "topic_index"},
            ),
            Finding(
                summary="Jesús siempre se distinguió de su Padre.",
                citation=Citation(
                    url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/14",
                    title="Juan 14:28",
                    kind="verse",
                ),
            ),
        ],
        warnings=["Cobertura parcial en idiomas LSN."],
        metadata={"language": "es"},
    )


def test_studysheet_construct_directly() -> None:
    sheet = StudySheet(
        title="Demo",
        sections=[StudySection(heading="Punto 1", body="Contenido.")],
    )
    assert sheet.title == "Demo"
    assert len(sheet.sections) == 1
    assert sheet.language == "es"


def test_citation_ir_defaults() -> None:
    cite = CitationIR(url="https://wol.jw.org/x")
    assert cite.title == ""
    assert cite.kind == ""
    assert cite.short_label == ""


def test_from_agent_result_minimal() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert sheet.title == "Es la Trinidad bíblica?"
    assert "apologetics" in sheet.subtitle.lower() or "apologé" in sheet.subtitle.lower()
    assert sheet.language == "es"
    assert len(sheet.sections) == 2


def test_from_agent_result_explicit_title_wins() -> None:
    sheet = StudySheet.from_agent_result(_sample_result(), title="Mi título")
    assert sheet.title == "Mi título"


def test_from_agent_result_truncates_long_title() -> None:
    long_q = "Por qué " + "muy largo " * 50
    sheet = StudySheet.from_agent_result(
        AgentResult(query=long_q, agent_name="apologetics")
    )
    assert len(sheet.title) <= 80


def test_from_agent_result_warnings_become_footer() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert "Cobertura parcial" in sheet.footer_note
    assert "Advertencias" in sheet.footer_note


def test_from_agent_result_no_citations_when_disabled() -> None:
    sheet = StudySheet.from_agent_result(_sample_result(), include_citations=False)
    assert all(section.citations == [] for section in sheet.sections)


def test_from_agent_result_keeps_excerpt() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    assert sheet.sections[0].excerpt.startswith("Jehová es uno solo")


def test_from_agent_result_empty_findings() -> None:
    empty = AgentResult(query="vacío", agent_name="apologetics", findings=[])
    sheet = StudySheet.from_agent_result(empty)
    assert len(sheet.sections) == 1
    assert "sin resultados" in sheet.sections[0].heading.lower()


def test_from_agent_result_accepts_dict() -> None:
    """`from_agent_result` must accept the dict form (AgentResult.to_dict())."""
    raw = _sample_result().to_dict()
    sheet = StudySheet.from_agent_result(raw)
    assert sheet.title == "Es la Trinidad bíblica?"
    assert len(sheet.sections) == 2


def test_citation_short_label_is_built() -> None:
    sheet = StudySheet.from_agent_result(_sample_result())
    labels = [c.short_label for s in sheet.sections for c in s.citations]
    assert any(labels)  # at least one non-empty short label
