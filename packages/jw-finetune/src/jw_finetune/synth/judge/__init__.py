"""jw_finetune.synth.judge — 3-stage Q&A quality filter.

Public API:
    from jw_finetune.synth.judge import (
        score_qa_pair, build_judge, Judge,
        QAScore, RejectionReason, JudgeMode, JudgeOverrides,
    )
"""

from __future__ import annotations

from jw_finetune.synth.judge.factories import build_judge
from jw_finetune.synth.judge.judge import Judge, score_qa_pair
from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.thresholds import (
    DEFAULT_CUTOFFS,
    JudgeMode,
    JudgeOverrides,
)

__all__ = [
    "DEFAULT_CUTOFFS",
    "Judge",
    "JudgeMode",
    "JudgeOverrides",
    "QAScore",
    "RejectionReason",
    "build_judge",
    "score_qa_pair",
]
