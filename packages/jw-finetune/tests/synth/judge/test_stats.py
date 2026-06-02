"""JudgeStats accumulator tests."""

from __future__ import annotations

from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.stats import JudgeStats


def test_stats_initial_state() -> None:
    s = JudgeStats()
    assert s.total == 0
    assert s.kept == 0
    assert s.rejected == 0
    assert s.rejection_reasons == {}


def _kept_score() -> QAScore:
    return QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        overall=8.0,
        kept=True,
    )


def _rejected_score(code: str = "no_jw_citation") -> QAScore:
    return QAScore(
        cites_jw_publication=False,
        has_minimum_substance=True,
        overall=3.0,
        kept=False,
        reasons=[RejectionReason(code=code)],  # type: ignore[arg-type]
    )


def test_stats_record_keeps_running_counts() -> None:
    s = JudgeStats()
    s.record(_kept_score())
    s.record(_kept_score())
    s.record(_rejected_score())
    assert s.total == 3
    assert s.kept == 2
    assert s.rejected == 1
    assert s.rejection_reasons["no_jw_citation"] == 1


def test_stats_record_groups_reasons() -> None:
    s = JudgeStats()
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("insufficient_substance"))
    assert s.rejection_reasons == {
        "no_jw_citation": 2,
        "insufficient_substance": 1,
    }


def test_stats_format_summary_human_readable() -> None:
    s = JudgeStats()
    for _ in range(7):
        s.record(_kept_score())
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("insufficient_substance"))
    summary = s.format_summary()
    assert "Pairs generated: 10" in summary
    assert "Pairs kept:      7 (70.0%)" in summary
    assert "Rejected:        3 (30.0%)" in summary
    assert "no_jw_citation:" in summary
    assert "2" in summary
    assert "insufficient_substance:" in summary


def test_stats_format_summary_zero_pairs() -> None:
    summary = JudgeStats().format_summary()
    assert "Pairs generated: 0" in summary
    assert "%" not in summary or "0.0%" in summary
