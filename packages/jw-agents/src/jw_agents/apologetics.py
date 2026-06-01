"""apologetics agent — answer doctrinal questions with verified citations.

Combines:
  - CDN search (find authoritative jw.org sources for the question)
  - WOL fetch (pull the actual article text)
  - parse_reference (extract Bible refs from the question for direct lookup)
  - Optional RAG (if a VectorStore is provided, hybrid-search local corpus)

The result is structured so the calling LLM can synthesize an answer where
every claim is backed by a citation URL.
"""

from __future__ import annotations

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient, TopicIndexError
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_all_references
from jw_core.parsers.study_notes import parse_study_notes, study_notes_for_verse
from jw_core.parsers.verse import get_verse
from jw_core.provenance.propagation import stamp_finding_text

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.research_topic import _flatten_search, _wol_url_from


async def apologetics(
    question: str,
    *,
    language: str = "E",
    rag_store: object | None = None,
    rag_top_k: int = 5,
    web_top_k: int = 3,
    topic_top_k: int = 1,
    topic_subheadings_limit: int = 8,
    use_topic_index: bool = True,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    topic: TopicIndexClient | None = None,
) -> AgentResult:
    """Answer a doctrinal question with citations only from jw.org sources.

    Pipeline (Phase 4 upgrade):
      0. Phase 4: query the Watch Tower Publications Index for the question
         topic — this is the authoritative JW subject map. Take the top
         matching subject(s) and surface its top subheadings + citations.
      1. Parse any Bible refs in the question, fetch verse text + study notes
         for each (Phase 3 enrichment).
      2. Run a CDN search and fetch the top K articles for the question.
      3. Optionally do a RAG hybrid_search on a local store.

    All findings carry `metadata['source']` so the calling LLM can rank
    them by authority (topic_index > question_refs > verse_text > study_note
    > cdn_search > rag).
    """
    result = AgentResult(query=question, agent_name="apologetics")
    result.metadata["language"] = language

    iso = _iso_for(language)

    # 0. Phase 4: Topic Index — authoritative JW subject mapping.
    if use_topic_index:
        owned_topic = topic is None
        topic_client = topic or TopicIndexClient(cdn=cdn, wol=wol)
        try:
            try:
                subjects = await topic_client.search_subjects(question, language=language, limit=topic_top_k)
            except TopicIndexError as e:
                result.warnings.append(f"Topic index search failed: {e}")
                subjects = []
            for s in subjects[:topic_top_k]:
                docid = s.get("docid") or ""
                if not docid:
                    # Surface as a low-fidelity finding so the LLM still
                    # knows the topic index returned something.
                    if s.get("wol_url"):
                        result.findings.append(
                            Finding(
                                summary=f"Topic candidate (no docid resolved): {s.get('title', '')}",
                                excerpt=s.get("snippet", ""),
                                citation=Citation(
                                    url=s["wol_url"],
                                    title=s.get("title", ""),
                                    kind="topic_candidate",
                                ),
                                metadata={"source": "topic_index_candidate"},
                            )
                        )
                    continue
                try:
                    subject = await topic_client.get_subject_page(docid, language=iso)
                except TopicIndexError as e:
                    result.warnings.append(f"Could not fetch subject {docid}: {e}")
                    continue
                # Add a "subject anchor" finding so the LLM knows this came
                # from the official index.
                result.findings.append(
                    Finding(
                        summary=f"Topic index: {subject.title}",
                        excerpt=f"Subject from the Watch Tower Publications Index. "
                        f"{subject.total_citations} citations across "
                        f"{len(subject.subheadings)} subheadings.",
                        citation=Citation(
                            url=subject.source_url,
                            title=subject.title,
                            kind="topic_subject",
                            metadata={"docid": subject.docid, "see_also": subject.see_also},
                        ),
                        metadata={"source": "topic_index", "docid": subject.docid},
                    )
                )
                # Surface the top subheadings as individual findings so the
                # LLM has both the structure and the citation text.
                for sh in subject.subheadings[:topic_subheadings_limit]:
                    citation_summary = "; ".join(c.text for c in sh.citations[:8])
                    result.findings.append(
                        Finding(
                            summary=f"{subject.title} — {sh.heading}",
                            excerpt=citation_summary or "(no citations in entry)",
                            citation=Citation(
                                url=subject.source_url,
                                title=f"{subject.title}: {sh.heading}",
                                kind="topic_subheading",
                                metadata={
                                    "is_top_level": sh.is_top_level,
                                    "bible_refs": [c.model_dump() for c in sh.citations if c.kind == "bible"],
                                    "publication_codes": [c.text for c in sh.citations if c.kind == "publication"],
                                },
                            ),
                            metadata={"source": "topic_index_entry"},
                        )
                    )
        finally:
            if owned_topic:
                await topic_client.aclose()

    # 1. Bible refs in the question — for each, pull the verse text + any
    #    nwtsty study notes mapped to it.
    explicit_refs = parse_all_references(question)

    # Set up clients (may be needed for ref enrichment too).
    owned_cdn = False
    owned_wol = False
    if cdn is None:
        cdn = CDNClient()
        owned_cdn = True
    if wol is None:
        wol = WOLClient()
        owned_wol = True

    # 1a. For each explicit ref, attempt to fetch the verse text + study notes.
    for ref in explicit_refs:
        ref_url = ref.wol_url(lang=iso)
        # Always add the bare citation first so it's there even if the fetch fails.
        result.findings.append(
            Finding(
                summary=f"User cited {ref.display()}",
                excerpt="",
                citation=Citation(
                    url=ref_url,
                    title=ref.display(),
                    kind="verse",
                    metadata={
                        "book_num": ref.book_num,
                        "chapter": ref.chapter,
                        "verse_start": ref.verse_start,
                        "verse_end": ref.verse_end,
                    },
                ),
                metadata={"source": "question_refs"},
            )
        )
        # Try to enrich with actual verse text and study notes.
        try:
            _, html = await wol.get_bible_chapter(ref.book_num, ref.chapter, language=iso)
        except Exception as e:
            result.warnings.append(f"Could not fetch {ref.display()}: {e}")
            continue
        if ref.has_verse:
            v = get_verse(html, ref.book_num, ref.chapter, ref.verse_start, language=iso)
            if v:
                result.findings.append(
                    Finding(
                        summary=f"Verse text: {ref.display()}",
                        excerpt=v.text,
                        citation=Citation(
                            url=v.wol_url(),
                            title=ref.display(),
                            kind="verse",
                            metadata={"book_num": v.book_num, "chapter": v.chapter, "verse": v.verse},
                        ),
                        metadata={"source": "verse_text"},
                    )
                )
            # Study notes for that verse.
            notes = parse_study_notes(html, book_num=ref.book_num, chapter=ref.chapter, language=iso)
            for note in study_notes_for_verse(notes, ref.verse_start):
                result.findings.append(
                    Finding(
                        summary=f"Study note: {note.headword}",
                        excerpt=note.body,
                        citation=Citation(
                            url=ref_url,
                            title=note.headword,
                            kind="study_note",
                            metadata={"verse": note.verse, "headword": note.headword, "inline_refs": note.inline_refs},
                        ),
                        metadata={"source": "study_note"},
                    )
                )

    # 2. CDN search + article fetch.
    try:
        try:
            data = await cdn.search(question, filter_type="all", language=language, limit=web_top_k * 2)
            items = _flatten_search(data, limit=web_top_k)
        except Exception as e:
            result.warnings.append(f"Search failed: {e}")
            items = []
        for item in items:
            url = _wol_url_from(item)
            if not url:
                continue
            try:
                html = await wol.fetch(url)
            except Exception as e:
                result.warnings.append(f"Fetch {url} failed: {e}")
                continue
            article = parse_article(html)
            top_para = article.paragraphs[0] if article.paragraphs else ""
            result.findings.append(
                Finding(
                    summary=f"Article: {article.title or item.get('title', '')}",
                    excerpt=top_para,
                    citation=Citation(
                        url=url,
                        title=article.title or item.get("title", ""),
                        kind="article",
                    ),
                    metadata={"source": "cdn_search"},
                )
            )
    finally:
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    # 3. Optional RAG hybrid search.
    if rag_store is not None and hasattr(rag_store, "hybrid_search"):
        try:
            hits = rag_store.hybrid_search(question, top_k=rag_top_k)
        except Exception as e:
            result.warnings.append(f"RAG search failed: {e}")
            hits = []
        for hit in hits:
            result.findings.append(
                Finding(
                    summary=hit.chunk.metadata.get("title", "Local corpus hit"),
                    excerpt=hit.chunk.text,
                    citation=Citation(
                        url=hit.chunk.metadata.get("source_url", ""),
                        title=hit.chunk.metadata.get("title", ""),
                        kind=hit.chunk.metadata.get("kind", "rag_chunk"),
                        metadata=hit.chunk.metadata,
                    ),
                    metadata={"source": "rag", "rrf_score": hit.score},
                )
            )

    for f in result.findings:
        stamp_finding_text(f)
    return result


def _iso_for(jw_or_iso: str) -> str:
    """Loose helper: turn a JW code like 'E' into ISO 'en', or pass through."""
    mapping = {"E": "en", "S": "es", "T": "pt"}
    return mapping.get(jw_or_iso.upper(), jw_or_iso.lower())
