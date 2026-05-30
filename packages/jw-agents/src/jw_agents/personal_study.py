"""personal_study agent — daily reading + notes + flashcards orchestration.

Composes:
  - ReadingPlanTracker: tells you what to read today.
  - WOLClient.get_bible_chapter: pulls the actual text.
  - PersonalNoteStore: surfaces your notes for the verses you're reading.
  - FlashcardDeck: shows cards due today.

Returns a single AgentResult so the calling LLM (Claude Desktop) can
build a daily study session.
"""

from __future__ import annotations

from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.study.flashcards import FlashcardDeck
from jw_core.study.personal_notes import PersonalNoteStore
from jw_core.study.reading_plan import READING_PLANS, ReadingPlanTracker

from jw_agents.base import AgentResult, Citation, Finding


async def personal_study(
    plan_key: str = "whole_bible_year",
    *,
    language: str = "en",
    include_notes: bool = True,
    include_due_cards: bool = True,
    max_chapters: int = 3,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Produce today's study agenda."""
    result = AgentResult(query=plan_key, agent_name="personal_study")
    result.metadata["language"] = language
    plan = READING_PLANS.get(plan_key)
    if plan is None:
        result.warnings.append(f"Unknown plan {plan_key!r}")
        return result

    with ReadingPlanTracker() as tracker:
        status = tracker.status(plan_key)
        result.metadata["plan_status"] = status
        upcoming = tracker.upcoming(plan_key, count=1)
    today = upcoming[0] if upcoming else None
    if today is None:
        result.warnings.append(f"Plan {plan_key!r} completed!")
        return result

    chapters = today["chapters"][:max_chapters]
    result.metadata["today"] = {"day": today["day"], "label": today["label"], "chapters": chapters}

    owned = wol is None
    wol = wol or WOLClient()
    try:
        for book_num, chapter in chapters:
            try:
                url, html = await wol.get_bible_chapter(book_num, chapter, language=language)
            except Exception as e:
                result.warnings.append(f"Fetch {book_num}:{chapter} failed: {e}")
                continue
            article = parse_article(html)
            top_para = article.paragraphs[0] if article.paragraphs else ""
            result.findings.append(
                Finding(
                    summary=f"Read {book_num}:{chapter} — {article.title or ''}",
                    excerpt=top_para,
                    citation=Citation(url=url, title=article.title, kind="chapter"),
                    metadata={"source": "reading_plan", "book_num": book_num, "chapter": chapter},
                )
            )

            if include_notes:
                with PersonalNoteStore() as notes:
                    for note in notes.for_anchor(book_num, chapter):
                        result.findings.append(
                            Finding(
                                summary=f"Note: {note.title or note.anchor()}",
                                excerpt=note.body,
                                citation=Citation(url=url, title=note.title, kind="personal_note"),
                                metadata={
                                    "source": "personal_note",
                                    "note_id": note.note_id,
                                    "tags": note.tags,
                                },
                            )
                        )
    finally:
        if owned:
            await wol.aclose()

    if include_due_cards:
        with FlashcardDeck() as deck:
            due = deck.due_today()
            result.metadata["due_cards"] = len(due)
            for card in due[:10]:
                result.findings.append(
                    Finding(
                        summary=f"Card due: {card.front}",
                        excerpt=card.back,
                        citation=Citation(url="", title=card.front, kind="flashcard"),
                        metadata={"source": "flashcard", "card_id": card.card_id, "due": card.due_iso},
                    )
                )

    return result
