"""meeting_helper agent — assistant for weekly meeting prep.

Given a meeting type and a date (or 'this week'), look up the relevant
material on wol.jw.org and return structured findings the user can use
to prepare comments, questions, or a brief outline.

Phase 7 scope: support the Watchtower study by accepting a reference (e.g.
the study article's URL or its Bible-based theme verse) and harvesting the
article + cross-references + suggested comments.

For 'this week' / date-driven discovery, Phase 7+ will integrate the meeting
workbook scraper. For now you pass the article URL or the theme reference.
"""

from __future__ import annotations

from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding


async def meeting_helper(
    input_text: str,
    *,
    language: str = "en",
    max_paragraphs: int = 8,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Build meeting-prep findings from an article URL or Bible reference.

    `input_text` can be:
      - A wol.jw.org URL (article or chapter).
      - A Bible reference ("Juan 3:16") — we resolve it then fetch the chapter.
    """
    result = AgentResult(query=input_text, agent_name="meeting_helper")
    result.metadata["language"] = language

    owned = False
    if wol is None:
        wol = WOLClient()
        owned = True

    try:
        if input_text.startswith("http"):
            url = input_text
            html = await wol.fetch(url)
        else:
            ref = parse_reference(input_text)
            if ref is None:
                result.warnings.append("Input must be a wol.jw.org URL or a Bible reference.")
                return result
            url, html = await wol.get_bible_chapter(ref.book_num, ref.chapter, language=language)
            result.metadata["resolved_reference"] = ref.display()
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    result.metadata["title"] = article.title

    for i, paragraph in enumerate(article.paragraphs[:max_paragraphs]):
        result.findings.append(
            Finding(
                summary=f"Paragraph {i + 1}",
                excerpt=paragraph,
                citation=Citation(
                    url=url,
                    title=article.title,
                    kind="article",
                    metadata={"paragraph_index": i + 1},
                ),
                metadata={"suggest_comment": _suggest_comment(paragraph, i)},
            )
        )

    if article.references:
        result.metadata["cross_references"] = article.references[:15]

    # A practical "questions to consider" block — derived heuristically from
    # the article structure. The LLM will refine these into natural language.
    result.metadata["prep_prompts"] = [
        "What is the main point of each paragraph?",
        "Which scripture references reinforce the lesson?",
        "Which paragraph would be best for a brief comment?",
        "Which application is most relevant to local circumstances?",
    ]
    return result


def _suggest_comment(paragraph: str, index: int) -> str:
    """Heuristic: short paragraphs early in the article are good for first comments."""
    length = len(paragraph)
    if index < 3 and 60 < length < 400:
        return "good for an early brief comment"
    if length > 400:
        return "rich content — pick one sentence to highlight"
    return ""
