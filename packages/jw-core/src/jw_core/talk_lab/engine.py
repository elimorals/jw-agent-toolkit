"""End-to-end engine: load -> transcribe -> prosody -> score -> report."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from jw_core.talk_lab.audio_loader import load_audio_mono16k
from jw_core.talk_lab.counsel_points.loader import (
    applies_to,
    load_catalog,
)
from jw_core.talk_lab.filler import count_fillers
from jw_core.talk_lab.models import (
    CounselPointResult,
    PartKind,
    TalkLabReport,
    TranscriptSegment,
)
from jw_core.talk_lab.prosody import extract_prosody
from jw_core.talk_lab.report import build_report
from jw_core.talk_lab.scorers.audience_llm import score_audience_warmth
from jw_core.talk_lab.scorers.linguistic import score_scripture_use
from jw_core.talk_lab.scorers.prosodic import (
    score_filler_use,
    score_pause_use,
    score_pronunciation,
    score_speech_rate,
)
from jw_core.talk_lab.transcriber import transcribe

logger = logging.getLogger(__name__)


class TalkLabConfig(BaseModel):
    part_kind: PartKind
    language: str = "es"
    llm_judge: bool = False


async def analyze_recording(
    *,
    recording_path: str,
    config: TalkLabConfig,
) -> TalkLabReport:
    """Run the full talk-lab pipeline on a local recording."""

    audio, sr = load_audio_mono16k(recording_path)

    transcript: list[TranscriptSegment] = transcribe(
        audio, sr=sr, language=config.language
    )
    text = " ".join(s.text for s in transcript)
    if transcript:
        word_count = sum(
            len(s.words) if s.words else len(s.text.split())
            for s in transcript
        )
    else:
        word_count = 0
    filler_count = count_fillers(text, language=config.language)

    prosody = extract_prosody(
        audio, sr=sr, word_count=word_count, filler_count=filler_count
    )

    catalog = load_catalog(config.language)
    applicable = applies_to(config.part_kind)
    counsel_results: list[CounselPointResult] = []

    for point in catalog:
        if point.id not in applicable:
            counsel_results.append(
                CounselPointResult(
                    point_id=point.id,
                    title=point.title,
                    title_localized=point.title_localized,
                    score=0,
                    applies=False,
                )
            )
            continue

        if point.scorer == "score_pronunciation":
            r = score_pronunciation(
                prosody, transcript, language=config.language
            )
        elif point.scorer == "score_speech_rate":
            r = score_speech_rate(prosody, language=config.language)
        elif point.scorer == "score_pause_use":
            r = score_pause_use(prosody, language=config.language)
        elif point.scorer == "score_filler_use":
            r = score_filler_use(prosody, language=config.language)
        elif point.scorer == "score_scripture_use":
            r = score_scripture_use(transcript, language=config.language)
        elif point.scorer == "score_audience_warmth":
            llm = None
            if config.llm_judge:
                try:
                    from jw_agents.meta.llm_factory import (  # type: ignore
                        build_llm_from_env,
                    )

                    llm = build_llm_from_env()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "talk_lab: LLM judge requested but unavailable: %s",
                        exc,
                    )
            r = await score_audience_warmth(
                transcript, llm=llm, language=config.language
            )
        else:
            r = CounselPointResult(
                point_id=point.id,
                title=point.title,
                title_localized=point.title_localized,
                score=0,
                evidence=[f"unknown scorer: {point.scorer}"],
            )
        counsel_results.append(r)

    return build_report(
        recording_path=recording_path,
        part_kind=config.part_kind,
        language=config.language,
        transcript=transcript,
        prosody=prosody,
        counsel_results=counsel_results,
    )
