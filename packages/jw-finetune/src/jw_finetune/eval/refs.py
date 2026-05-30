"""Citation-accuracy evaluator: do model answers include valid bible refs?"""

from __future__ import annotations

from collections.abc import Iterable

from jw_finetune.synth.validators import count_bible_refs


def score_citation_accuracy(
    answers: Iterable[str],
    *,
    expect_at_least: int = 1,
) -> float:
    """Fraction of answers containing at least `expect_at_least` bible refs.

    Returns 0.0 for an empty input. Values are in [0, 1].
    """
    answers_list = list(answers)
    if not answers_list:
        return 0.0
    hits = sum(1 for a in answers_list if count_bible_refs(a) >= expect_at_least)
    return hits / len(answers_list)
