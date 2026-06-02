"""apologetics agent — answer doctrinal questions with verified citations.

Combines:
  - Topic Index (Phase 4) — authoritative subject mapping
  - Bible-ref enrichment (verse text + study notes)
  - CDN search + article fetch
  - Optional RAG hybrid search on a local store

Every per-source decision (kept / dropped / warning) is mirrored to the
active AgentTracer (Fase 43). Without `--trace` the tracer is a no-op and
the agent runs at the same cost as before.
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
from jw_agents.tracing import AgentTracer, get_active_tracer


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
    trace: AgentTracer | None = None,
) -> AgentResult:
    """Answer a doctrinal question with citations only from jw.org sources.

    Pipeline (Phase 4 upgrade, Phase 43 instrumented):
      0. Topic Index — authoritative JW subject mapping.
      1. Parse any Bible refs in the question, fetch verse text + study notes.
      2. CDN search + article fetch.
      3. Optional RAG hybrid_search on a local store.

    All findings carry `metadata['source']` so the calling LLM can rank
    them by authority (topic_index > question_refs > verse_text > study_note
    > cdn_search > rag).
    """

    tr = trace if trace is not None else get_active_tracer()

    result = AgentResult(query=question, agent_name="apologetics")
    result.metadata["language"] = language
    result.metadata["trace_id"] = str(tr.trace_id)

    iso = _iso_for(language)

    # 0. Topic Index.
    if use_topic_index:
        owned_topic = topic is None
        topic_client = topic or TopicIndexClient(cdn=cdn, wol=wol)
        with tr.step(
            "topic_index_lookup", input_digest={"q_len": len(question)}
        ) as step:
            kept_count = 0
            dropped_count = 0
            try:
                try:
                    subjects = await topic_client.search_subjects(
                        question, language=language, limit=topic_top_k
                    )
                except TopicIndexError as e:
                    result.warnings.append(f"Topic index search failed: {e}")
                    tr.warn(
                        f"topic search failed: {e}", step="topic_index_lookup"
                    )
                    subjects = []
                step.note_hits(len(subjects))
                for s in subjects[:topic_top_k]:
                    docid = s.get("docid") or ""
                    if not docid:
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
                            tr.kept(
                                source="topic_index_candidate",
                                citation_url=s["wol_url"],
                                reason="no_docid_but_url",
                            )
                            kept_count += 1
                        else:
                            tr.dropped(
                                source="topic_index",
                                reason="no_docid",
                                citation_url=s.get("wol_url"),
                            )
                            dropped_count += 1
                        continue
                    try:
                        subject = await topic_client.get_subject_page(
                            docid, language=iso
                        )
                    except TopicIndexError as e:
                        result.warnings.append(
                            f"Could not fetch subject {docid}: {e}"
                        )
                        tr.warn(f"subject fetch failed for {docid}: {e}")
                        dropped_count += 1
                        continue
                    result.findings.append(
                        Finding(
                            summary=f"Topic index: {subject.title}",
                            excerpt=(
                                "Subject from the Watch Tower Publications Index. "
                                f"{subject.total_citations} citations across "
                                f"{len(subject.subheadings)} subheadings."
                            ),
                            citation=Citation(
                                url=subject.source_url,
                                title=subject.title,
                                kind="topic_subject",
                                metadata={
                                    "docid": subject.docid,
                                    "see_also": subject.see_also,
                                },
                            ),
                            metadata={
                                "source": "topic_index",
                                "docid": subject.docid,
                            },
                        )
                    )
                    tr.kept(
                        source="topic_index",
                        citation_url=subject.source_url,
                        reason="primary subject match",
                    )
                    kept_count += 1
                    for sh in subject.subheadings[:topic_subheadings_limit]:
                        citation_summary = "; ".join(
                            c.text for c in sh.citations[:8]
                        )
                        result.findings.append(
                            Finding(
                                summary=f"{subject.title} — {sh.heading}",
                                excerpt=citation_summary
                                or "(no citations in entry)",
                                citation=Citation(
                                    url=subject.source_url,
                                    title=f"{subject.title}: {sh.heading}",
                                    kind="topic_subheading",
                                    metadata={
                                        "is_top_level": sh.is_top_level,
                                        "bible_refs": [
                                            c.model_dump()
                                            for c in sh.citations
                                            if c.kind == "bible"
                                        ],
                                        "publication_codes": [
                                            c.text
                                            for c in sh.citations
                                            if c.kind == "publication"
                                        ],
                                    },
                                ),
                                metadata={"source": "topic_index_entry"},
                            )
                        )
                        tr.kept(
                            source="topic_index_entry",
                            citation_url=subject.source_url,
                            reason=f"subheading: {sh.heading}",
                        )
                        kept_count += 1
            finally:
                if owned_topic:
                    await topic_client.aclose()
                step.note_kept(kept_count)
                step.note_dropped(dropped_count)

    # 1. Bible refs.
    explicit_refs = parse_all_references(question)

    owned_cdn = False
    owned_wol = False
    if cdn is None:
        cdn = CDNClient()
        owned_cdn = True
    if wol is None:
        wol = WOLClient()
        owned_wol = True

    if explicit_refs:
        with tr.step(
            "bible_ref_enrichment", input_digest={"refs": len(explicit_refs)}
        ) as step:
            kept_count = 0
            for ref in explicit_refs:
                ref_url = ref.wol_url(lang=iso)
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
                tr.kept(
                    source="question_refs",
                    citation_url=ref_url,
                    reason="cited by user",
                )
                kept_count += 1
                try:
                    _, html = await wol.get_bible_chapter(
                        ref.book_num, ref.chapter, language=iso
                    )
                except Exception as e:
                    result.warnings.append(
                        f"Could not fetch {ref.display()}: {e}"
                    )
                    tr.warn(f"chapter fetch failed for {ref.display()}: {e}")
                    continue
                if ref.has_verse:
                    v = get_verse(
                        html,
                        ref.book_num,
                        ref.chapter,
                        ref.verse_start,
                        language=iso,
                    )
                    if v:
                        result.findings.append(
                            Finding(
                                summary=f"Verse text: {ref.display()}",
                                excerpt=v.text,
                                citation=Citation(
                                    url=v.wol_url(),
                                    title=ref.display(),
                                    kind="verse",
                                    metadata={
                                        "book_num": v.book_num,
                                        "chapter": v.chapter,
                                        "verse": v.verse,
                                    },
                                ),
                                metadata={"source": "verse_text"},
                            )
                        )
                        tr.kept(
                            source="verse_text",
                            citation_url=v.wol_url(),
                            reason="verse hit",
                        )
                        kept_count += 1
                    notes = parse_study_notes(
                        html,
                        book_num=ref.book_num,
                        chapter=ref.chapter,
                        language=iso,
                    )
                    for note in study_notes_for_verse(notes, ref.verse_start):
                        result.findings.append(
                            Finding(
                                summary=f"Study note: {note.headword}",
                                excerpt=note.body,
                                citation=Citation(
                                    url=ref_url,
                                    title=note.headword,
                                    kind="study_note",
                                    metadata={
                                        "verse": note.verse,
                                        "headword": note.headword,
                                        "inline_refs": note.inline_refs,
                                    },
                                ),
                                metadata={"source": "study_note"},
                            )
                        )
                        tr.kept(
                            source="study_note",
                            citation_url=ref_url,
                            reason=f"note for v.{note.verse}",
                        )
                        kept_count += 1
            step.note_kept(kept_count)

    # 2. CDN search + article fetch.
    with tr.step(
        "cdn_search", input_digest={"q_len": len(question), "limit": web_top_k}
    ) as step:
        kept_count = 0
        dropped_count = 0
        try:
            try:
                data = await cdn.search(
                    question,
                    filter_type="all",
                    language=language,
                    limit=web_top_k * 2,
                )
                items = _flatten_search(data, limit=web_top_k)
            except Exception as e:
                result.warnings.append(f"Search failed: {e}")
                tr.warn(f"cdn search failed: {e}", step="cdn_search")
                items = []
            step.note_hits(len(items))
            for item in items:
                url = _wol_url_from(item)
                if not url:
                    tr.dropped(source="cdn_search", reason="no_url")
                    dropped_count += 1
                    continue
                try:
                    html = await wol.fetch(url)
                except Exception as e:
                    result.warnings.append(f"Fetch {url} failed: {e}")
                    tr.dropped(
                        source="cdn_search",
                        reason=f"fetch_failed:{type(e).__name__}",
                        citation_url=url,
                    )
                    dropped_count += 1
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
                tr.kept(
                    source="cdn_search",
                    citation_url=url,
                    reason="article match",
                )
                kept_count += 1
        finally:
            if owned_cdn:
                await cdn.aclose()
            if owned_wol:
                await wol.aclose()
            step.note_kept(kept_count)
            step.note_dropped(dropped_count)

    # 3. Optional RAG.
    if rag_store is not None and hasattr(rag_store, "hybrid_search"):
        with tr.step("rag_hybrid_search", input_digest={"top_k": rag_top_k}) as step:
            kept_count = 0
            try:
                hits = rag_store.hybrid_search(question, top_k=rag_top_k)
            except Exception as e:
                result.warnings.append(f"RAG search failed: {e}")
                tr.warn(f"rag failed: {e}", step="rag_hybrid_search")
                hits = []
            step.note_hits(len(hits))
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
                tr.kept(
                    source="rag",
                    citation_url=hit.chunk.metadata.get("source_url", ""),
                    score=hit.score,
                    reason="rrf hit",
                )
                kept_count += 1
            step.note_kept(kept_count)

    for f in result.findings:
        stamp_finding_text(f)
    return result


def _iso_for(jw_or_iso: str) -> str:
    """Loose helper: turn a JW code like 'E' into ISO 'en', or pass through."""
    mapping = {"E": "en", "S": "es", "T": "pt"}
    return mapping.get(jw_or_iso.upper(), jw_or_iso.lower())
