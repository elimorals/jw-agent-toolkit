"""Linguistic counsel-point scorers (heuristic, no LLM)."""

from __future__ import annotations

from jw_core.parsers.reference import parse_all_references
from jw_core.talk_lab.models import CounselPointResult, TranscriptSegment

_TITLE_LOC = {
    "en": "Use of Scripture",
    "es": "Uso de la Escritura",
    "pt": "Uso da Escritura",
}


def score_scripture_use(
    transcript: list[TranscriptSegment],
    *,
    language: str = "es",
) -> CounselPointResult:
    text = " ".join(s.text for s in transcript)
    refs = parse_all_references(text) if text else []
    n = len(refs)
    if n >= 3:
        score, suggestion = (
            3,
            "Multiple Scriptures cited and connected to the points.",
        )
    elif n == 2:
        score, suggestion = (
            2,
            "Couple of Scriptures cited; tie them more explicitly to the points.",
        )
    elif n == 1:
        score, suggestion = (
            1,
            "One Scripture; consider adding a second to reinforce.",
        )
    else:
        score, suggestion = (
            0,
            "No Scriptures detected; add at least one to ground the teaching.",
        )
    return CounselPointResult(
        point_id="cp-05",
        title="Use of Scripture",
        title_localized=_TITLE_LOC.get(language, "Use of Scripture"),
        score=score,
        evidence=[f"{n} Scriptures parsed"],
        suggestion=suggestion,
    )
