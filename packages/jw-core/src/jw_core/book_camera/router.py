"""Action router: produce SuggestedAction list per DetectedContent (Fase 71)."""

from __future__ import annotations

from jw_core.book_camera.models import (
    BibleVerseDetected,
    DetectedContent,
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


def _jwlibrary_deep_link(book_num: int, chapter: int, verse: int | None) -> str:
    """Best-effort jwlibrary:// deep link."""
    if verse is not None:
        return f"jwlibrary://bible/{book_num:02d}/{chapter:03d}/{verse:03d}"
    return f"jwlibrary://bible/{book_num:02d}/{chapter:03d}"


def suggested_actions_for(
    detected: DetectedContent,
    *,
    language: str = "es",
) -> list[SuggestedAction]:
    """Return the ordered list of suggested actions for a detected content."""

    actions: list[SuggestedAction] = []

    if isinstance(detected, BibleVerseDetected):
        ref_label = f"Bible reference book={detected.book_num} ch={detected.chapter}"
        actions.append(
            ReadAloudAction(text=ref_label, language_hint=language)
        )
        actions.append(
            OpenInJwLibraryAction(
                deep_link=_jwlibrary_deep_link(
                    detected.book_num,
                    detected.chapter,
                    detected.verse_start,
                )
            )
        )
        actions.append(OpenInWolAction(url=detected.wol_url))
        return actions

    if isinstance(detected, StudyQuestionDetected):
        actions.append(
            ShowAnswerAction(
                question=detected.text,
                suggested_topics=detected.suggested_topics,
            )
        )
        actions.append(
            ReadAloudAction(text=detected.text, language_hint=language)
        )
        return actions

    if isinstance(detected, WatchtowerParagraphDetected):
        actions.append(
            ReadAloudAction(
                text=detected.text, language_hint=language
            )
        )
        # No reliable WOL URL from a pub code alone; surface as plain
        # `open_in_jw_library` to let the app resolve via the MEPS catalog.
        actions.append(
            OpenInJwLibraryAction(
                deep_link=f"jwlibrary://publication/{detected.pub_code}"
            )
        )
        return actions

    if isinstance(detected, PlainTextDetected):
        actions.append(
            ReadAloudAction(text=detected.text, language_hint=language)
        )
        return actions

    # UnknownTextDetected
    if isinstance(detected, UnknownTextDetected) and detected.text:
        actions.append(
            ReadAloudAction(text=detected.text, language_hint=language)
        )
    return actions
