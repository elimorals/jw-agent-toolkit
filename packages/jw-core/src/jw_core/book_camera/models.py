"""Pydantic models for the book-camera flow (Fase 71)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DetectedKind = Literal[
    "bible_verse",
    "study_question",
    "watchtower_paragraph",
    "plain_text",
    "unknown",
]


class _DetectedBase(BaseModel):
    kind: DetectedKind


class BibleVerseDetected(_DetectedBase):
    kind: Literal["bible_verse"] = "bible_verse"
    book_num: int
    chapter: int
    verse_start: int | None = None
    verse_end: int | None = None
    detected_language: str = "unknown"
    wol_url: str


class StudyQuestionDetected(_DetectedBase):
    kind: Literal["study_question"] = "study_question"
    text: str
    suggested_topics: list[str] = Field(default_factory=list)


class WatchtowerParagraphDetected(_DetectedBase):
    kind: Literal["watchtower_paragraph"] = "watchtower_paragraph"
    pub_code: str
    paragraph_id: int | None = None
    text: str


class PlainTextDetected(_DetectedBase):
    kind: Literal["plain_text"] = "plain_text"
    text: str


class UnknownTextDetected(_DetectedBase):
    kind: Literal["unknown"] = "unknown"
    text: str = ""


DetectedContent = (
    BibleVerseDetected
    | StudyQuestionDetected
    | WatchtowerParagraphDetected
    | PlainTextDetected
    | UnknownTextDetected
)


# ---- Suggested actions --------------------------------------------------


class ReadAloudAction(BaseModel):
    kind: Literal["read_aloud"] = "read_aloud"
    language_hint: str = "es"
    text: str


class OpenInJwLibraryAction(BaseModel):
    kind: Literal["open_in_jw_library"] = "open_in_jw_library"
    deep_link: str


class OpenInWolAction(BaseModel):
    kind: Literal["open_in_wol"] = "open_in_wol"
    url: str


class ShowAnswerAction(BaseModel):
    kind: Literal["show_answer"] = "show_answer"
    question: str
    suggested_topics: list[str] = Field(default_factory=list)


SuggestedAction = (
    ReadAloudAction
    | OpenInJwLibraryAction
    | OpenInWolAction
    | ShowAnswerAction
)


class CameraFrameResult(BaseModel):
    captured_at: str
    ocr_text: str
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    detected: DetectedContent
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
