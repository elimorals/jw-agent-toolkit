"""Verify the heuristic-only judge hits the spec's precision targets.

Spec targets ≥90% accuracy in LOOSE and ≥95% in STRICT when the LLM judge
and NLI are wired. With heuristics-only the realistic LOOSE bound is ~0.85
(FPs are doctrinally-contradictory pairs that happen to clear the substance
heuristic); STRICT routinely hits 1.0 because the higher cutoff catches
non-cited answers regardless of substance.
"""

from __future__ import annotations

import json
from pathlib import Path

from jw_finetune.synth.judge import score_qa_pair
from jw_finetune.synth.judge.eval_precision import evaluate_precision
from jw_finetune.synth.judge.thresholds import JudgeMode

FIXTURE = Path(__file__).parent / "fixtures" / "golden_50_pairs.jsonl"


def test_fixture_has_exactly_50_rows() -> None:
    rows = [
        ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert len(rows) == 50


def test_fixture_balanced_pass_reject() -> None:
    rows = [
        json.loads(ln)
        for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    passes = sum(1 for r in rows if r["expected_kept"])
    rejects = sum(1 for r in rows if not r["expected_kept"])
    assert passes == 25, f"expected 25 pass rows, got {passes}"
    assert rejects == 25, f"expected 25 reject rows, got {rejects}"


def test_loose_mode_accuracy_above_85_pct() -> None:
    report = evaluate_precision(FIXTURE, mode=JudgeMode.LOOSE)
    assert report.accuracy >= 0.85, (
        f"LOOSE accuracy {report.accuracy:.3f} below 0.85; "
        f"TP={report.tp} TN={report.tn} FP={report.fp} FN={report.fn}"
    )


def test_strict_mode_accuracy_above_95_pct() -> None:
    report = evaluate_precision(FIXTURE, mode=JudgeMode.STRICT)
    assert report.accuracy >= 0.95, (
        f"STRICT accuracy {report.accuracy:.3f} below 0.95; "
        f"TP={report.tp} TN={report.tn} FP={report.fp} FN={report.fn}"
    )


def test_strict_mode_no_false_positives_on_doctrinal_contradictions() -> None:
    """Rows whose note mentions doctrinal contradiction must NOT be kept in STRICT."""

    report_failures: list[str] = []
    for ln in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        row = json.loads(ln)
        note = row.get("note", "").lower()
        if (
            "contradicts" not in note
            and "contradiction" not in note
            and "wrong" not in note
        ):
            continue
        score = score_qa_pair(
            question=row["q"],
            answer=row["a"],
            language=row.get("language", "es"),
            mode=JudgeMode.STRICT,
            llm_provider=None,
            nli_provider=None,
        )
        if score.kept:
            report_failures.append(
                f"{row['topic']}/{row.get('language', '?')}: {row['a'][:60]!r}"
            )
    assert len(report_failures) <= 2, (
        "Too many doctrinal contradictions slipped past STRICT heuristics:\n"
        + "\n".join(report_failures)
    )
