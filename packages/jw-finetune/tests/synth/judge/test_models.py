"""Pydantic models for the synth judge."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.models import QAScore, RejectionReason


def test_rejection_reason_accepts_known_codes() -> None:
    r = RejectionReason(code="no_jw_citation", detail="missing URL")
    assert r.code == "no_jw_citation"
    assert r.detail == "missing URL"


def test_rejection_reason_rejects_unknown_code() -> None:
    with pytest.raises(ValueError):
        RejectionReason(code="totally_made_up", detail="x")  # type: ignore[arg-type]


def test_qa_score_minimal_kept_true() -> None:
    s = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        overall=7.5,
        kept=True,
    )
    assert s.kept is True
    assert s.nli_score is None
    assert s.nli_verdict is None
    assert s.pedagogical_quality is None
    assert s.reasons == []


def test_qa_score_with_full_signals() -> None:
    s = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        nli_score=0.92,
        nli_verdict="entails",
        pedagogical_quality=3,
        overall=9.4,
        kept=True,
    )
    assert s.nli_verdict == "entails"
    assert 0.0 <= s.nli_score <= 1.0


def test_qa_score_rejects_out_of_range_overall() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=False,
            has_minimum_substance=False,
            overall=12.0,
            kept=False,
        )


def test_qa_score_rejects_out_of_range_nli() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=True,
            has_minimum_substance=True,
            nli_score=1.5,
            nli_verdict="entails",
            overall=5.0,
            kept=True,
        )


def test_qa_score_rejects_out_of_range_pedagogical() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=True,
            has_minimum_substance=True,
            pedagogical_quality=5,
            overall=5.0,
            kept=True,
        )


def test_qa_score_carries_reasons_when_rejected() -> None:
    s = QAScore(
        cites_jw_publication=False,
        has_minimum_substance=True,
        overall=3.0,
        kept=False,
        reasons=[
            RejectionReason(code="no_jw_citation", detail="no URL"),
            RejectionReason(code="overall_below_threshold", detail="3.0 < 5.0"),
        ],
    )
    assert len(s.reasons) == 2
    assert s.reasons[0].code == "no_jw_citation"
