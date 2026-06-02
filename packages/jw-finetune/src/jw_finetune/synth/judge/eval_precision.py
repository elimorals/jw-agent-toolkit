"""Run the judge over a golden fixture and report precision.

Usage:
    uv run python -m jw_finetune.synth.judge.eval_precision \
        --fixture packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl \
        --mode loose
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from jw_finetune.synth.judge.judge import score_qa_pair
from jw_finetune.synth.judge.thresholds import JudgeMode


@dataclass
class PrecisionReport:
    total: int
    tp: int
    tn: int
    fp: int
    fn: int

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.tp + self.tn) / self.total

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0


def _load_fixture(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fp:
        for ln in fp:
            ln = ln.strip()
            if not ln:
                continue
            yield json.loads(ln)


def evaluate_precision(
    fixture_path: Path,
    *,
    mode: JudgeMode = JudgeMode.LOOSE,
) -> PrecisionReport:
    report = PrecisionReport(total=0, tp=0, tn=0, fp=0, fn=0)
    for row in _load_fixture(fixture_path):
        score = score_qa_pair(
            question=row["q"],
            answer=row["a"],
            language=row.get("language", "es"),
            mode=mode,
            llm_provider=None,
            nli_provider=None,
        )
        expected = bool(row["expected_kept"])
        predicted = bool(score.kept)
        report.total += 1
        if expected and predicted:
            report.tp += 1
        elif (not expected) and (not predicted):
            report.tn += 1
        elif (not expected) and predicted:
            report.fp += 1
        else:
            report.fn += 1
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fixture",
        type=Path,
        default=Path(
            "packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl"
        ),
    )
    ap.add_argument(
        "--mode", default="loose", choices=["off", "loose", "strict"]
    )
    args = ap.parse_args()

    report = evaluate_precision(args.fixture, mode=JudgeMode(args.mode))
    print(f"Total:     {report.total}")
    print(f"TP / TN:   {report.tp} / {report.tn}")
    print(f"FP / FN:   {report.fp} / {report.fn}")
    print(f"Accuracy:  {report.accuracy:.3f}")
    print(f"Precision: {report.precision:.3f}")
    print(f"Recall:    {report.recall:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
