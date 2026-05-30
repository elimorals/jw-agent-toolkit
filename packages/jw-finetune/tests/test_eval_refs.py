"""Tests for citation-accuracy and terminology evaluators."""

from __future__ import annotations

from jw_finetune.eval.doctrinal import score_terminology
from jw_finetune.eval.refs import score_citation_accuracy


def test_citation_accuracy_all_valid() -> None:
    answers = [
        "Como dice Mateo 24:14, esto es una señal importante.",
        "Hechos 1:8 menciona la obra de testificación mundial.",
    ]
    assert score_citation_accuracy(answers, expect_at_least=1) == 1.0


def test_citation_accuracy_partial() -> None:
    answers = [
        "Mateo 24:14 lo dice claramente.",
        "Sin referencia bíblica aquí.",
    ]
    s = score_citation_accuracy(answers, expect_at_least=1)
    assert 0.0 < s < 1.0
    assert abs(s - 0.5) < 1e-9


def test_citation_accuracy_empty_zero() -> None:
    assert score_citation_accuracy([]) == 0.0


def test_citation_accuracy_threshold() -> None:
    answers = ["Solo una cita: Mateo 24:14"]
    assert score_citation_accuracy(answers, expect_at_least=1) == 1.0
    assert score_citation_accuracy(answers, expect_at_least=2) == 0.0


def test_doctrinal_terminology_es() -> None:
    answers = [
        "Jehová es el Soberano del universo.",
        "El Reino de Dios es el gobierno celestial.",
    ]
    assert score_terminology(answers, language="es") > 0.5


def test_doctrinal_terminology_unknown_language_zero() -> None:
    assert score_terminology(["any text"], language="xx") == 0.0


def test_doctrinal_terminology_empty_zero() -> None:
    assert score_terminology([], language="es") == 0.0


def test_doctrinal_terminology_en() -> None:
    answers = [
        "Jehovah's witnesses preach the Kingdom good news worldwide.",
        "No JW vocabulary at all in this sentence.",
    ]
    score = score_terminology(answers, language="en")
    assert 0.0 < score < 1.0
