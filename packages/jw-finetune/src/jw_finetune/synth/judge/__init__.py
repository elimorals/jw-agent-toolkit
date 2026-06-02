"""jw_finetune.synth.judge — 3-stage Q&A quality filter (Fase 44).

The public surface grows as later tasks land. After T1 only the Pydantic
models are exported; T3 will add JudgeMode + cutoffs, T7 will add Judge +
score_qa_pair, T8 will add build_judge.
"""

from __future__ import annotations

from jw_finetune.synth.judge.models import QAScore, RejectionReason

__all__ = ["QAScore", "RejectionReason"]
