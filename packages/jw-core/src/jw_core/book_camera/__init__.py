"""jw_core.book_camera - live camera for physical JW publications (Fase 71).

Public API:
    from jw_core.book_camera import (
        DetectedKind, DetectedContent, SuggestedAction,
        CameraFrameResult,
        classify_content, analyze_capture,
    )
"""

from __future__ import annotations

from jw_core.book_camera.models import (
    BibleVerseDetected,
    CameraFrameResult,
    DetectedContent,
    DetectedKind,
    OpenInJwLibraryAction,
    OpenInWolAction,
    PlainTextDetected,
    ReadAloudAction,
    ShowAnswerAction,
    StudyQuestionDetected,
    SuggestedAction,
    UnknownTextDetected,
    WatchtowerParagraphDetected,
)

__all__ = [
    "BibleVerseDetected",
    "CameraFrameResult",
    "DetectedContent",
    "DetectedKind",
    "OpenInJwLibraryAction",
    "OpenInWolAction",
    "PlainTextDetected",
    "ReadAloudAction",
    "ShowAnswerAction",
    "StudyQuestionDetected",
    "SuggestedAction",
    "UnknownTextDetected",
    "WatchtowerParagraphDetected",
]
