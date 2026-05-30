"""verse_explainer agent — resolve a reference, fetch the chapter, extract
the target verse and the surrounding context, collect cross-references.

Input:  "Juan 3:16" (or any string with a Bible ref)
Steps:
  1. parse_reference(text)
  2. WOLClient.get_bible_chapter(book, chapter)
  3. parse_article(html) → paragraphs + references
  4. Build Findings with the verse-adjacent paragraphs as evidence

Output: AgentResult with findings ordered by relevance.
"""

from __future__ import annotations

from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_reference
from jw_core.parsers.study_notes import (
    parse_cross_references,
    parse_study_notes,
    study_notes_for_verse,
)
from jw_core.parsers.verse import parse_verses

from jw_agents.base import AgentResult, Citation, Finding


async def verse_explainer(
    text: str,
    *,
    language: str = "en",
    wol: WOLClient | None = None,
    max_paragraphs: int = 5,
    include_study_notes: bool = True,
    include_cross_refs: bool = True,
) -> AgentResult:
    """Explain a verse with Phase 3 enrichment: verse text + study notes + cross-refs.

    Phase 3 upgrade: instead of returning the first N article paragraphs, we
    pin findings to the actual target verse and pull in the nwtsty study
    notes mapped to it. Cross-references stay attached to verse anchors so
    the LLM can chain to `get_cross_references` if needed.
    """
    result = AgentResult(query=text, agent_name="verse_explainer")
    ref = parse_reference(text)
    if ref is None:
        result.warnings.append(f"No Bible reference detected in {text!r}")
        return result

    canonical_url = ref.wol_url(lang=language)
    result.metadata.update(
        {
            "book_num": ref.book_num,
            "book_canonical": ref.book_canonical,
            "chapter": ref.chapter,
            "verse_start": ref.verse_start,
            "verse_end": ref.verse_end,
            "detected_language": ref.detected_language,
            "canonical_url": canonical_url,
        }
    )

    owned = False
    if wol is None:
        wol = WOLClient()
        owned = True
    try:
        chapter_url, html = await wol.get_bible_chapter(ref.book_num, ref.chapter, language=language)
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    result.metadata["chapter_title"] = article.title

    # Phase 3: pull verse text + study notes for the target verse range.
    target_start = ref.verse_start or 1
    target_end = ref.verse_end or target_start
    all_verses = parse_verses(html, book_num=ref.book_num, chapter=ref.chapter, language=language)

    if ref.has_verse:
        target_verses = [v for v in all_verses if target_start <= v.verse <= target_end]
        if not target_verses:
            result.warnings.append(f"Verse {target_start}-{target_end} not found in chapter HTML")
        for v in target_verses:
            result.findings.append(
                Finding(
                    summary=f"{ref.book_canonical} {v.chapter}:{v.verse}",
                    excerpt=v.text,
                    citation=Citation(
                        url=v.wol_url(),
                        title=f"{ref.book_canonical} {v.chapter}:{v.verse}",
                        kind="verse",
                        metadata={"book_num": v.book_num, "chapter": v.chapter, "verse": v.verse},
                    ),
                    metadata={"kind": "target_verse"},
                )
            )
    else:
        # No specific verse — return the first N paragraphs as before.
        for i, paragraph in enumerate(article.paragraphs[:max_paragraphs]):
            result.findings.append(
                Finding(
                    summary=f"Paragraph {i + 1} of {article.title}",
                    excerpt=paragraph,
                    citation=Citation(
                        url=canonical_url if i == 0 else chapter_url,
                        title=article.title,
                        kind="chapter",
                        metadata={"paragraph_index": i + 1},
                    ),
                    metadata={"paragraph_index": i + 1},
                )
            )

    # Study notes for the target verse(s).
    if include_study_notes:
        notes = parse_study_notes(html, book_num=ref.book_num, chapter=ref.chapter, language=language)
        relevant: list = []
        if ref.has_verse:
            for vnum in range(target_start, target_end + 1):
                relevant.extend(study_notes_for_verse(notes, vnum))
        else:
            relevant = notes[:5]
        for note in relevant:
            result.findings.append(
                Finding(
                    summary=f"Study note: {note.headword}",
                    excerpt=note.body,
                    citation=Citation(
                        url=canonical_url,
                        title=f"{note.headword} — study note ({ref.book_canonical} {ref.chapter}:{note.verse or '?'})",
                        kind="study_note",
                        metadata={
                            "verse": note.verse,
                            "headword": note.headword,
                            "inline_refs": note.inline_refs,
                        },
                    ),
                    metadata={"kind": "study_note", "verse": note.verse},
                )
            )

    # Cross-reference markers for the target verse(s).
    if include_cross_refs:
        xrefs = parse_cross_references(html, book_num=ref.book_num, chapter=ref.chapter, language=language)
        if ref.has_verse:
            xrefs = [x for x in xrefs if target_start <= x.verse <= target_end]
        for x in xrefs[:10]:
            result.findings.append(
                Finding(
                    summary=f"Cross-reference marker at {ref.book_canonical} {x.chapter}:{x.verse}",
                    excerpt="",
                    citation=Citation(
                        url=x.full_url(),
                        title=f"Cross-ref panel for {ref.book_canonical} {x.chapter}:{x.verse}",
                        kind="cross_ref",
                        metadata={"verse": x.verse, "marker": x.marker},
                    ),
                    metadata={"kind": "cross_ref", "verse": x.verse},
                )
            )

    return result
