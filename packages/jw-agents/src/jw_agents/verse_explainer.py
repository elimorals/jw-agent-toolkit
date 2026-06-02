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
from jw_core.provenance.propagation import stamp_finding_text

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.tracing import AgentTracer, get_active_tracer


async def verse_explainer(
    text: str,
    *,
    language: str = "en",
    wol: WOLClient | None = None,
    cdn: object | None = None,  # noqa: ARG001
    max_paragraphs: int = 5,
    include_study_notes: bool = True,
    include_cross_refs: bool = True,
    trace: AgentTracer | None = None,
) -> AgentResult:
    """Explain a verse with Phase 3 enrichment: verse text + study notes + cross-refs.

    Phase 3 upgrade: instead of returning the first N article paragraphs, we
    pin findings to the actual target verse and pull in the nwtsty study
    notes mapped to it. Cross-references stay attached to verse anchors so
    the LLM can chain to `get_cross_references` if needed.
    """
    tr = trace if trace is not None else get_active_tracer()
    result = AgentResult(query=text, agent_name="verse_explainer")
    result.metadata["trace_id"] = str(tr.trace_id)
    ref = parse_reference(text)
    if ref is None:
        result.warnings.append(f"No Bible reference detected in {text!r}")
        tr.warn(f"no Bible reference detected in {text!r}")
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
    with tr.step("verse_fetch", input_digest={"ref": ref.display()}) as step:
        kept_count = 0
        try:
            chapter_url, html = await wol.get_bible_chapter(
                ref.book_num, ref.chapter, language=language
            )
        finally:
            if owned:
                await wol.aclose()

        article = parse_article(html)
        result.metadata["chapter_title"] = article.title

        target_start = ref.verse_start or 1
        target_end = ref.verse_end or target_start
        all_verses = parse_verses(
            html, book_num=ref.book_num, chapter=ref.chapter, language=language
        )

        if ref.has_verse:
            target_verses = [
                v for v in all_verses if target_start <= v.verse <= target_end
            ]
            if not target_verses:
                result.warnings.append(
                    f"Verse {target_start}-{target_end} not found in chapter HTML"
                )
                tr.warn(
                    f"verses {target_start}-{target_end} not found",
                    step="verse_fetch",
                )
            for v in target_verses:
                verse_url = v.wol_url()
                result.findings.append(
                    Finding(
                        summary=f"{ref.book_canonical} {v.chapter}:{v.verse}",
                        excerpt=v.text,
                        citation=Citation(
                            url=verse_url,
                            title=f"{ref.book_canonical} {v.chapter}:{v.verse}",
                            kind="verse",
                            metadata={
                                "book_num": v.book_num,
                                "chapter": v.chapter,
                                "verse": v.verse,
                            },
                        ),
                        metadata={"kind": "target_verse"},
                    )
                )
                tr.kept(
                    source="verse_text",
                    citation_url=verse_url,
                    reason="verse hit",
                )
                kept_count += 1
        else:
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
                tr.kept(
                    source="chapter",
                    citation_url=canonical_url if i == 0 else chapter_url,
                    reason=f"paragraph {i + 1}",
                )
                kept_count += 1

        if include_study_notes:
            notes = parse_study_notes(
                html,
                book_num=ref.book_num,
                chapter=ref.chapter,
                language=language,
            )
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
                            title=(
                                f"{note.headword} — study note "
                                f"({ref.book_canonical} {ref.chapter}:{note.verse or '?'})"
                            ),
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
                tr.kept(
                    source="study_note",
                    citation_url=canonical_url,
                    reason=note.headword,
                )
                kept_count += 1

        if include_cross_refs:
            xrefs = parse_cross_references(
                html,
                book_num=ref.book_num,
                chapter=ref.chapter,
                language=language,
            )
            if ref.has_verse:
                xrefs = [x for x in xrefs if target_start <= x.verse <= target_end]
            for x in xrefs[:10]:
                xref_url = x.full_url()
                result.findings.append(
                    Finding(
                        summary=(
                            f"Cross-reference marker at "
                            f"{ref.book_canonical} {x.chapter}:{x.verse}"
                        ),
                        excerpt="",
                        citation=Citation(
                            url=xref_url,
                            title=(
                                f"Cross-ref panel for "
                                f"{ref.book_canonical} {x.chapter}:{x.verse}"
                            ),
                            kind="cross_ref",
                            metadata={"verse": x.verse, "marker": x.marker},
                        ),
                        metadata={"kind": "cross_ref", "verse": x.verse},
                    )
                )
                tr.kept(
                    source="cross_ref",
                    citation_url=xref_url,
                    reason=f"v.{x.verse}",
                )
                kept_count += 1
        step.note_kept(kept_count)

    for f in result.findings:
        stamp_finding_text(f)
    return result
