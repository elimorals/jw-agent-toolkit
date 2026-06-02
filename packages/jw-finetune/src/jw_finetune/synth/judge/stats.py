"""Per-run accumulator for judge verdicts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from jw_finetune.synth.judge.models import QAScore


@dataclass
class JudgeStats:
    total: int = 0
    kept: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def record(self, score: QAScore) -> None:
        self.total += 1
        if score.kept:
            self.kept += 1
            return
        self.rejected += 1
        if score.reasons:
            primary = score.reasons[0].code
            self.rejection_reasons[primary] = (
                self.rejection_reasons.get(primary, 0) + 1
            )

    def format_summary(self) -> str:
        if self.total == 0:
            return (
                "Pairs generated: 0\nPairs kept:      0\nRejected:        0\n"
            )

        kept_pct = 100.0 * self.kept / self.total
        rej_pct = 100.0 * self.rejected / self.total

        lines = [
            "Extraction complete.",
            f"  Pairs generated: {self.total}",
            f"  Pairs kept:      {self.kept} ({kept_pct:.1f}%)",
            f"  Rejected:        {self.rejected} ({rej_pct:.1f}%)",
        ]
        if self.rejection_reasons:
            ordered = sorted(
                self.rejection_reasons.items(), key=lambda kv: -kv[1]
            )
            for code, n in ordered:
                lines.append(f"    {code}: {n}")
        return "\n".join(lines) + "\n"


def merge_counters(stats: JudgeStats, other: JudgeStats) -> JudgeStats:
    """Combine two stats accumulators (useful for parallel runs)."""

    merged = JudgeStats()
    merged.total = stats.total + other.total
    merged.kept = stats.kept + other.kept
    merged.rejected = stats.rejected + other.rejected
    combined: Counter[str] = Counter(stats.rejection_reasons) + Counter(
        other.rejection_reasons
    )
    merged.rejection_reasons = dict(combined)
    return merged
