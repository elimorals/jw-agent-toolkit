"""Pydantic models for talk_lab (Fase 68)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

CounselScore = Literal[0, 1, 2, 3]
PartKind = Literal[
    "bible_reading",
    "initial_call",
    "return_visit",
    "bible_study",
    "public_talk",
    "watchtower_comment",
    "other",
]


class ProsodyFeatures(BaseModel):
    duration_s: float = Field(ge=0)
    speech_rate_wpm: float = Field(ge=0)
    pitch_mean_hz: float = Field(ge=0)
    pitch_range_hz: float = Field(ge=0)
    intensity_mean_db: float
    pause_count: int = Field(ge=0)
    pause_total_s: float = Field(ge=0)
    pause_avg_s: float = Field(ge=0)
    filler_count: int = Field(ge=0)
    filler_per_minute: float = Field(ge=0)
    pitch_contour_path: str | None = None


class WordTiming(BaseModel):
    word: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _validate_window(self) -> "WordTiming":
        if self.end_s < self.start_s:
            raise ValueError(
                f"end_s ({self.end_s}) < start_s ({self.start_s})"
            )
        return self


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    words: list[WordTiming] = Field(default_factory=list)


class CounselPointResult(BaseModel):
    point_id: str
    title: str
    title_localized: str
    score: CounselScore
    evidence: list[str] = Field(default_factory=list)
    suggestion: str = ""
    applies: bool = True


class TalkLabReport(BaseModel):
    recording_path: str
    part_kind: PartKind
    language: Literal["en", "es", "pt"]
    duration_s: float = Field(ge=0)
    transcript: list[TranscriptSegment]
    prosody: ProsodyFeatures
    counsel_results: list[CounselPointResult]
    summary_top_3: list[str]
    summary_focus_3: list[str]
    trace_path: str | None = None
    score_history_path: str | None = None
