"""conversation_assistant agent — answer common objections with citations.

Pipeline:
  1. Match the incoming text against the canonical objection catalog.
  2. For each `topic_anchor`, query the Watch Tower Publications Index
     and surface its top subheadings.
  3. For each `scripture_anchor`, fetch the verse text + study notes.
  4. Combine into an `AgentResult` ordered by authority.

This is the door-to-door / informal-witness companion: structured,
verifiable, and language-aware. The agent answers the OBJECTION, not
the person — the LLM uses the result to craft a respectful reply.
"""

from __future__ import annotations

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.wol import WOLClient
from jw_core.data.objections import Objection, find_objection
from jw_core.parsers.reference import parse_reference
from jw_core.parsers.study_notes import parse_study_notes, study_notes_for_verse
from jw_core.parsers.verse import get_verse

from jw_agents.base import AgentResult, Citation, Finding

_LANG_MAP = {"E": "en", "S": "es", "T": "pt"}


async def conversation_assistant(
    text: str,
    *,
    language: str = "E",
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    max_subheadings: int = 6,
) -> AgentResult:
    """Match `text` to a known objection and harvest authoritative answers."""
    result = AgentResult(query=text, agent_name="conversation_assistant")
    iso = _LANG_MAP.get(language.upper(), language.lower())
    result.metadata["language"] = language

    objection = find_objection(text, language=iso)
    if objection is None:
        result.warnings.append("No matching objection in catalog. Falling back to free apologetics.")
        result.metadata["matched_objection"] = None
    else:
        result.metadata["matched_objection"] = objection.key
        result.metadata["matched_label"] = objection.label(iso)
        result.findings.append(
            Finding(
                summary=f"Matched objection: {objection.label(iso)}",
                excerpt=objection.label("en"),
                citation=Citation(
                    url="",
                    title=objection.key,
                    kind="objection",
                    metadata={
                        "category": objection.category,
                        "topic_anchors": objection.topic_anchors,
                        "scripture_anchors": objection.scripture_anchors,
                    },
                ),
                metadata={"source": "objection_catalog"},
            )
        )

    owned_topic = topic is None
    owned_cdn = cdn is None
    owned_wol = wol is None
    topic = topic or TopicIndexClient(cdn=cdn, wol=wol)
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()

    try:
        if objection is not None:
            await _surface_topic_anchors(result, objection, topic, language, iso, max_subheadings=max_subheadings)
            await _surface_scripture_anchors(result, objection, wol, iso)
    finally:
        if owned_topic:
            await topic.aclose()
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    return result


async def _surface_topic_anchors(
    result: AgentResult,
    objection: Objection,
    topic: TopicIndexClient,
    language: str,
    iso: str,
    *,
    max_subheadings: int,
) -> None:
    for anchor in objection.topic_anchors:
        try:
            results = await topic.search_subjects(anchor, language=language, limit=1)
        except Exception as e:
            result.warnings.append(f"Topic anchor {anchor!r} failed: {e}")
            continue
        if not results:
            continue
        docid = results[0].get("docid")
        if not docid:
            continue
        try:
            subject = await topic.get_subject_page(docid, language=iso)
        except Exception as e:
            result.warnings.append(f"Subject {anchor!r} fetch failed: {e}")
            continue
        for sh in subject.subheadings[:max_subheadings]:
            result.findings.append(
                Finding(
                    summary=f"{subject.title} → {sh.heading}",
                    excerpt="; ".join(c.text for c in sh.citations[:6]),
                    citation=Citation(
                        url=subject.source_url,
                        title=f"{subject.title}: {sh.heading}",
                        kind="topic_subheading",
                    ),
                    metadata={
                        "source": "topic_index_entry",
                        "anchor": anchor,
                        "bible_refs": [c.text for c in sh.citations if c.kind == "bible"],
                    },
                )
            )


async def _surface_scripture_anchors(
    result: AgentResult,
    objection: Objection,
    wol: WOLClient,
    iso: str,
) -> None:
    for ref_text in objection.scripture_anchors:
        ref = parse_reference(ref_text)
        if ref is None:
            continue
        try:
            url, html = await wol.get_bible_chapter(ref.book_num, ref.chapter, language=iso)
        except Exception as e:
            result.warnings.append(f"Could not fetch {ref_text}: {e}")
            continue
        verse = (
            get_verse(html, ref.book_num, ref.chapter, ref.verse_start, language=iso)
            if ref.verse_start
            else None
        )
        result.findings.append(
            Finding(
                summary=f"Scripture anchor: {ref.display()}",
                excerpt=verse.text if verse else "",
                citation=Citation(
                    url=verse.wol_url() if verse else url,
                    title=ref.display(),
                    kind="verse",
                ),
                metadata={"source": "verse_text"},
            )
        )
        if ref.verse_start:
            for note in study_notes_for_verse(
                parse_study_notes(html, book_num=ref.book_num, chapter=ref.chapter, language=iso),
                ref.verse_start,
            )[:2]:
                result.findings.append(
                    Finding(
                        summary=f"Study note: {note.headword}",
                        excerpt=note.body,
                        citation=Citation(
                            url=url,
                            title=note.headword,
                            kind="study_note",
                        ),
                        metadata={"source": "study_note"},
                    )
                )
