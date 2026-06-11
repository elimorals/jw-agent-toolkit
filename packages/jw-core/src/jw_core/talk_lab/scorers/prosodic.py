"""Prosodic counsel-point scorers (purely heuristic, no LLM)."""

from __future__ import annotations

from jw_core.talk_lab.models import (
    CounselPointResult,
    ProsodyFeatures,
    TranscriptSegment,
)

_LOC_TITLES: dict[str, dict[str, str]] = {
    "cp-01": {
        "en": "Clear Pronunciation",
        "es": "Pronunciación clara",
        "pt": "Pronúncia clara",
    },
    "cp-02": {
        "en": "Speech Rate",
        "es": "Velocidad del habla",
        "pt": "Velocidade da fala",
    },
    "cp-03": {
        "en": "Use of Pauses",
        "es": "Uso de pausas",
        "pt": "Uso de pausas",
    },
    "cp-04": {
        "en": "Filler Words",
        "es": "Muletillas",
        "pt": "Vícios de linguagem",
    },
}


def _loc(point_id: str, language: str) -> str:
    return _LOC_TITLES.get(point_id, {}).get(
        language, _LOC_TITLES.get(point_id, {}).get("en", "")
    )


def score_pronunciation(
    features: ProsodyFeatures,
    transcript: list[TranscriptSegment],
    *,
    language: str = "en",
) -> CounselPointResult:
    confidences = [w.confidence for s in transcript for w in s.words]
    if not confidences:
        return CounselPointResult(
            point_id="cp-01",
            title="Clear Pronunciation",
            title_localized=_loc("cp-01", language),
            score=0,
            evidence=["no word-level transcript available"],
            suggestion=(
                "Re-run transcription with word-level timestamps "
                "enabled (WhisperX)."
            ),
        )
    avg_conf = sum(confidences) / len(confidences)
    if avg_conf >= 0.85:
        score, suggestion = 3, "Pronunciation is clear and confident."
    elif avg_conf >= 0.70:
        score, suggestion = (
            2,
            "Pronunciation is mostly clear; slow down on harder words.",
        )
    elif avg_conf >= 0.55:
        score, suggestion = (
            1,
            "Several words are unclear; record again in a quieter environment.",
        )
    else:
        score, suggestion = 0, "Pronunciation needs significant work."
    return CounselPointResult(
        point_id="cp-01",
        title="Clear Pronunciation",
        title_localized=_loc("cp-01", language),
        score=score,
        evidence=[f"avg word confidence: {avg_conf:.2f}"],
        suggestion=suggestion,
    )


def score_speech_rate(
    features: ProsodyFeatures, *, language: str = "en"
) -> CounselPointResult:
    wpm = features.speech_rate_wpm
    if 120 <= wpm <= 150:
        score, suggestion = 3, "Speech rate is in the ideal teaching range."
    elif 100 <= wpm < 120 or 150 < wpm <= 175:
        score, suggestion = (
            2,
            "Speech rate is acceptable; adjust slightly for clarity.",
        )
    elif 80 <= wpm < 100 or 175 < wpm <= 200:
        score, suggestion = (
            1,
            "Speech rate is off-target; slow down or speed up.",
        )
    else:
        score, suggestion = 0, "Speech rate is far from ideal."
    return CounselPointResult(
        point_id="cp-02",
        title="Speech Rate",
        title_localized=_loc("cp-02", language),
        score=score,
        evidence=[f"{wpm:.0f} wpm"],
        suggestion=suggestion,
    )


def score_pause_use(
    features: ProsodyFeatures, *, language: str = "en"
) -> CounselPointResult:
    if features.duration_s <= 0:
        return CounselPointResult(
            point_id="cp-03",
            title="Use of Pauses",
            title_localized=_loc("cp-03", language),
            score=0,
            evidence=["zero duration"],
        )
    pause_ratio = features.pause_total_s / features.duration_s
    if 0.15 <= pause_ratio <= 0.25:
        score, suggestion = 3, "Pauses are well placed; ideas land."
    elif 0.08 <= pause_ratio < 0.15 or 0.25 < pause_ratio <= 0.35:
        score, suggestion = 2, "Pauses are present; refine for emphasis."
    elif 0.03 <= pause_ratio < 0.08 or 0.35 < pause_ratio <= 0.45:
        score, suggestion = 1, "Pauses are too few or too many."
    else:
        score, suggestion = 0, "Pause use needs work."
    return CounselPointResult(
        point_id="cp-03",
        title="Use of Pauses",
        title_localized=_loc("cp-03", language),
        score=score,
        evidence=[f"pause ratio: {pause_ratio:.2f}"],
        suggestion=suggestion,
    )


def score_filler_use(
    features: ProsodyFeatures, *, language: str = "en"
) -> CounselPointResult:
    fpm = features.filler_per_minute
    if fpm < 2:
        score, suggestion = 3, "Filler words are minimal."
    elif fpm < 4:
        score, suggestion = 2, "Some filler words; aware of them."
    elif fpm < 6:
        score, suggestion = (
            1,
            "Filler words are noticeable; pause instead of filling.",
        )
    else:
        score, suggestion = (
            0,
            "Filler words are very frequent; deliberate practice needed.",
        )
    return CounselPointResult(
        point_id="cp-04",
        title="Filler Words",
        title_localized=_loc("cp-04", language),
        score=score,
        evidence=[f"{fpm:.1f} fillers/min"],
        suggestion=suggestion,
    )
