"""Audience scorers (LLM judge opt-in, heuristic fallback)."""

from __future__ import annotations

from typing import Protocol

from jw_core.talk_lab.models import CounselPointResult, TranscriptSegment


class LLMLike(Protocol):
    async def acomplete(self, prompt: str) -> str: ...


_WARMTH_WORDS = {
    "en": [
        "dear",
        "thank you",
        "friends",
        "brothers",
        "sisters",
        "appreciate",
        "welcome",
    ],
    "es": [
        "queridos",
        "gracias",
        "amigos",
        "hermanos",
        "hermanas",
        "aprecio",
        "bienvenidos",
    ],
    "pt": [
        "queridos",
        "obrigado",
        "amigos",
        "irmãos",
        "irmãs",
        "aprecio",
        "bem-vindos",
    ],
}

_TITLE_LOC = {
    "en": "Audience Warmth",
    "es": "Calidez hacia el auditorio",
    "pt": "Calor hacia o auditório",
}


def _heuristic_warmth(
    transcript: list[TranscriptSegment], language: str
) -> CounselPointResult:
    text = " ".join(s.text for s in transcript)
    words = _WARMTH_WORDS.get(language, _WARMTH_WORDS["en"])
    hits = sum(1 for w in words if w.lower() in text.lower())
    if hits >= 3:
        score, suggestion = 3, "Warmth is consistently expressed."
    elif hits == 2:
        score, suggestion = (
            2,
            "Some warmth shown; consider naming the audience explicitly.",
        )
    elif hits == 1:
        score, suggestion = (
            1,
            "Warmth is minimal; greet the audience and acknowledge them.",
        )
    else:
        score, suggestion = 0, "Warmth is missing; add a personal opener."
    return CounselPointResult(
        point_id="cp-06",
        title="Audience Warmth",
        title_localized=_TITLE_LOC.get(language, "Audience Warmth"),
        score=score,
        evidence=[f"{hits} warmth markers"],
        suggestion=suggestion,
    )


async def score_audience_warmth(
    transcript: list[TranscriptSegment],
    *,
    llm: LLMLike | None = None,
    language: str = "es",
) -> CounselPointResult:
    if llm is None:
        return _heuristic_warmth(transcript, language)

    text = " ".join(s.text for s in transcript)
    prompt = (
        f"Score the audience warmth of this talk from 0 to 3.\n"
        f"0 = cold; 3 = warm.\n"
        f"Talk: {text}\n"
        f"Respond with a single digit only."
    )
    raw = (await llm.acomplete(prompt)).strip()
    score = 0
    if raw and raw[0] in ("0", "1", "2", "3"):
        score = int(raw[0])
    return CounselPointResult(
        point_id="cp-06",
        title="Audience Warmth",
        title_localized=_TITLE_LOC.get(language, "Audience Warmth"),
        score=score,  # type: ignore[arg-type]
        evidence=[f"LLM judge: {raw!r}"],
    )
