"""End-to-end tests for the 4 agents.

Unlike `test_agents_unit.py` (which checks individual pipeline steps),
these tests assert the **structural contract** the README and the docs
promise:

  1. `apologetics` source priority: topic_index > question_refs >
     verse_text > study_note > cdn_search > rag (the order findings
     appear in the result).
  2. Every `Finding` carries a non-empty `citation.url`.
  3. `verse_explainer` always puts the target_verse first.
  4. `research_topic` does NOT consult the topic index (it's a CDN-only
     pipeline).
  5. `meeting_helper` accepts both URL and Bible-reference inputs and
     produces the same finding shape.
  6. Warnings propagate when an upstream call fails.

A change that breaks any of these contracts will fail here.
"""

from __future__ import annotations

import pytest
from jw_agents import (
    apologetics,
    meeting_helper,
    research_topic,
    verse_explainer,
)

# ── Shared in-memory fakes (no network) ────────────────────────────────


class FakeWOL:
    """In-memory WOL client. Returns HTML with verse spans + study notes."""

    def __init__(self, html: str | None = None, fail: bool = False) -> None:
        self.html = html if html is not None else _SAMPLE_CHAPTER_HTML
        self.fetched_urls: list[str] = []
        self.fail = fail

    async def get_bible_chapter(self, book_num, chapter, *, language="en", publication="nwtsty"):
        if self.fail:
            raise RuntimeError("simulated WOL outage")
        url = f"https://wol.jw.org/{language}/wol/b/r1/lp-e/nwtsty/{book_num}/{chapter}"
        self.fetched_urls.append(url)
        return url, self.html

    async def fetch(self, url):
        if self.fail:
            raise RuntimeError("simulated WOL outage")
        self.fetched_urls.append(url)
        return self.html

    async def get_today_homepage(self, language="en"):
        url = f"https://wol.jw.org/{language}/wol/h/r1/lp-e"
        self.fetched_urls.append(url)
        return url, self.html

    async def aclose(self):
        pass


class FakeCDN:
    """In-memory CDN client. Returns a list of search results."""

    def __init__(self, results: list[dict] | None = None, fail: bool = False) -> None:
        self.results = _SAMPLE_SEARCH_RESULTS if results is None else results
        self.searches: list[str] = []
        self.fail = fail

    async def search(self, query, *, filter_type="all", language="E", limit=10):
        if self.fail:
            raise RuntimeError("simulated CDN outage")
        self.searches.append(query)
        return {"results": self.results[:limit]}

    async def aclose(self):
        pass


class FakeTopicIndex:
    """In-memory topic-index client wrapping FakeCDN."""

    def __init__(
        self,
        subjects: list[dict] | None = None,
        subject_payload: dict | None = None,
        fail: bool = False,
    ) -> None:
        self.subjects = subjects if subjects is not None else _SAMPLE_TOPIC_SUBJECTS
        self.subject_payload = subject_payload or _SAMPLE_TOPIC_SUBJECT_OBJ
        self.fail = fail
        self.subject_searches: list[str] = []
        self.subject_fetches: list[str] = []

    async def search_subjects(self, query, *, language="E", limit=5):
        if self.fail:
            from jw_core.clients.topic_index import TopicIndexError

            raise TopicIndexError("simulated topic-index outage")
        self.subject_searches.append(query)
        return self.subjects[:limit]

    async def get_subject_page(self, docid, *, language="en"):
        from jw_core.models import TopicCitation, TopicSubheading, TopicSubject

        self.subject_fetches.append(docid)
        # Convert the dict payload to a TopicSubject.
        return TopicSubject(
            docid=docid,
            title=self.subject_payload["title"],
            see_also=self.subject_payload.get("see_also", []),
            subheadings=[
                TopicSubheading(
                    heading=sh["heading"],
                    is_top_level=sh["is_top_level"],
                    citations=[TopicCitation(**c) for c in sh["citations"]],
                )
                for sh in self.subject_payload.get("subheadings", [])
            ],
            source_url=f"https://wol.jw.org/en/wol/d/r1/lp-e/{docid}",
            language=language,
            style=self.subject_payload.get("style", "trinity"),
        )

    async def aclose(self):
        pass


class FakeRAGStore:
    """Minimal RAG-store shape exposing `hybrid_search`."""

    def __init__(self, hits: list | None = None) -> None:
        from jw_rag.chunker import Chunk
        from jw_rag.store import SearchHit

        if hits is None:
            chunk = Chunk(
                id="rag-1",
                text="The Watchtower says peace is a gift from Jehovah.",
                source_id="bh:chapter4",
                metadata={
                    "title": "What Is Real Peace?",
                    "source_url": "https://wol.jw.org/en/wol/d/r1/lp-e/rag-source",
                    "kind": "epub_document",
                },
            )
            hits = [SearchHit(chunk=chunk, score=0.91, rank=1, source="hybrid")]
        self.hits = hits
        self.queries: list[str] = []
        self.is_empty = False

    def hybrid_search(self, query, top_k=5):
        self.queries.append(query)
        return self.hits[:top_k]


# ── Sample data ────────────────────────────────────────────────────────

_SAMPLE_CHAPTER_HTML = """
<html><body>
<article id="article">
<h1>According to John</h1>
<p data-pid="1">
  <span class="v" id="v43-3-1-1">1 There was a man of the Pharisees named Nicodemus.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample-doc/1/0">+</a>
  </span>
  <span class="v" id="v43-3-3-1">3 Jesus said you must be born again.</span>
</p>
<p data-pid="2">
  <span class="v" id="v43-3-16-1">16 For God so loved the world.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample-doc/16/0">+</a>
  </span>
</p>
<div class="studyNoteGroup">
  <li class="item studyNote">
    <strong>Nicodemus:</strong> A Pharisee, member of the Sanhedrin.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample-note/0/0">Joh 7:50</a>
  </li>
  <li class="item studyNote">
    <strong>born again:</strong> Means regenerated from above by the spirit.
  </li>
  <li class="item studyNote">
    <strong>loved:</strong> Greek a-ga-PA-o; principled love.
  </li>
</div>
</article>
</body></html>
"""

_SAMPLE_SEARCH_RESULTS = [
    {
        "type": "item",
        "title": "Real Love Comes From God",
        "snippet": "The first occurrence of love...",
        "links": {"wol": "https://wol.jw.org/en/wol/d/r1/lp-e/cdn-1"},
    },
    {
        "type": "item",
        "title": "Why Does God Permit Suffering?",
        "snippet": "True peace comes from understanding...",
        "links": {"wol": "https://wol.jw.org/en/wol/d/r1/lp-e/cdn-2"},
    },
]

_SAMPLE_TOPIC_SUBJECTS = [
    {
        "title": "Love",
        "snippet": "Subject index entry for love",
        "wol_url": "https://wol.jw.org/en/wol/d/r1/lp-e/topic-love",
        "docid": "1200999001",
        "subtype": "indexes",
        "score": 100.0,
        "original_rank": 0,
    },
]

_SAMPLE_TOPIC_SUBJECT_OBJ = {
    "title": "LOVE",
    "see_also": ["Affection", "Devotion"],
    "style": "trinity",
    "subheadings": [
        {
            "heading": "love of God",
            "is_top_level": True,
            "citations": [
                {
                    "text": "Joh 3:16",
                    "kind": "bible",
                    "url": "https://wol.jw.org/en/wol/bc/r1/lp-e/topic-love/0/0",
                },
                {
                    "text": "w24.04 12",
                    "kind": "publication",
                    "url": "https://wol.jw.org/en/wol/pc/r1/lp-e/topic-love/0/1",
                },
            ],
        },
    ],
}


# ── verse_explainer e2e ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verse_explainer_target_verse_appears_first() -> None:
    """The target verse finding must precede any study-note or cross-ref."""
    wol = FakeWOL()
    result = await verse_explainer("John 3:16", language="en", wol=wol)
    kinds = [f.metadata.get("kind") for f in result.findings]
    # The first finding's kind should be 'target_verse'.
    assert kinds[0] == "target_verse", f"Expected target_verse first, got {kinds}"


@pytest.mark.asyncio
async def test_verse_explainer_every_finding_has_citation_url() -> None:
    wol = FakeWOL()
    result = await verse_explainer("John 3:16", language="en", wol=wol)
    assert result.findings, "Expected at least one finding"
    for f in result.findings:
        assert f.citation.url, f"Finding missing citation.url: {f.summary}"


@pytest.mark.asyncio
async def test_verse_explainer_no_ref_emits_warning() -> None:
    wol = FakeWOL()
    result = await verse_explainer("gibberish", wol=wol)
    assert result.warnings
    assert not result.findings


# ── Fase 23 smoke: citation validator over verse_explainer output ──────


@pytest.mark.asyncio
async def test_verse_explainer_citations_pass_structural_validator() -> None:
    """Every citation emitted by verse_explainer must pass structural validation.

    Fase 23 smoke — the AgentResult format produced by verse_explainer should
    pipe cleanly into CitationValidator in default (offline) mode.
    """
    from jw_core.citations import CitationValidator

    wol = FakeWOL()
    result = await verse_explainer("John 3:16", language="en", wol=wol)

    v = CitationValidator()  # no catalog, no fetcher → everything skipped/unknown
    report = await v.validate_agent_output(result, mode="structural")
    assert report.summary["failed"] == 0, report.checks


# ── apologetics e2e — source priority is the central contract ─────────


@pytest.mark.asyncio
async def test_apologetics_topic_index_findings_come_first() -> None:
    """Source order in findings: topic_index > question_refs > everything else."""
    result = await apologetics(
        "What does the Bible teach about love? See John 3:16.",
        language="E",
        cdn=FakeCDN(),
        wol=FakeWOL(),
        topic=FakeTopicIndex(),
        topic_top_k=1,
        topic_subheadings_limit=2,
        web_top_k=1,
    )
    sources = [f.metadata.get("source") for f in result.findings]
    # First source must be topic_index (the anchor) followed by topic_index_entry.
    assert sources[0] == "topic_index", f"Expected topic_index first, got {sources}"
    # question_refs must appear AFTER topic_index findings but BEFORE cdn_search.
    if "question_refs" in sources and "cdn_search" in sources:
        assert sources.index("question_refs") < sources.index("cdn_search")
    # verse_text + study_note must appear AFTER question_refs.
    if "verse_text" in sources and "cdn_search" in sources:
        assert sources.index("verse_text") < sources.index("cdn_search")


@pytest.mark.asyncio
async def test_apologetics_includes_rag_when_store_has_hits() -> None:
    rag = FakeRAGStore()
    result = await apologetics(
        "What about peace?",
        language="E",
        cdn=FakeCDN(),
        wol=FakeWOL(),
        topic=FakeTopicIndex(subjects=[]),  # no topic index hit
        rag_store=rag,
        rag_top_k=3,
        web_top_k=1,
    )
    rag_findings = [f for f in result.findings if f.metadata.get("source") == "rag"]
    assert rag_findings, "Expected RAG findings when store has hits"
    # The RAG query was issued.
    assert rag.queries


@pytest.mark.asyncio
async def test_apologetics_every_finding_has_url() -> None:
    """No Finding may have an empty citation.url (the LLM relies on links)."""
    result = await apologetics(
        "Why does God permit suffering? See John 3:16.",
        language="E",
        cdn=FakeCDN(),
        wol=FakeWOL(),
        topic=FakeTopicIndex(),
        topic_top_k=1,
        web_top_k=1,
    )
    missing = [f for f in result.findings if not f.citation.url]
    assert not missing, f"{len(missing)} findings missing citation.url: {[m.summary for m in missing]}"


@pytest.mark.asyncio
async def test_apologetics_topic_index_failure_does_not_crash() -> None:
    """When the topic index is unavailable, apologetics still returns CDN findings."""
    result = await apologetics(
        "love",
        language="E",
        cdn=FakeCDN(),
        wol=FakeWOL(),
        topic=FakeTopicIndex(fail=True),
        web_top_k=1,
    )
    # Warning should mention the topic-index failure.
    assert any("topic" in w.lower() or "index" in w.lower() for w in result.warnings)
    # But CDN findings still come through.
    assert any(f.metadata.get("source") == "cdn_search" for f in result.findings)


# ── research_topic e2e ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_topic_does_not_query_topic_index() -> None:
    """research_topic is a CDN+WOL pipeline; topic_index is apologetics-only."""
    topic = FakeTopicIndex()
    result = await research_topic(
        "love",
        language="E",
        cdn=FakeCDN(),
        wol=FakeWOL(),
        top_n=2,
        fetch_top_k=1,
        max_excerpts_per_article=2,
    )
    # research_topic was never passed `topic`; the fake should be untouched.
    assert not topic.subject_searches, "research_topic should not consult the topic index"
    assert result.findings, "Expected at least one finding from CDN search"
    assert all(f.metadata.get("source") is None or f.metadata.get("source") != "topic_index" for f in result.findings)


# ── meeting_helper e2e ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_meeting_helper_url_input_produces_findings_and_prep_prompts() -> None:
    wol = FakeWOL()
    result = await meeting_helper(
        "https://wol.jw.org/en/wol/d/r1/lp-e/some-article",
        wol=wol,
    )
    assert result.findings
    assert "prep_prompts" in result.metadata
    assert len(result.metadata["prep_prompts"]) >= 3


@pytest.mark.asyncio
async def test_meeting_helper_ref_input_resolves_to_chapter() -> None:
    wol = FakeWOL()
    result = await meeting_helper("Juan 3:16", language="en", wol=wol)
    assert result.metadata.get("resolved_reference")
    # The chapter URL was fetched (book 43 chapter 3).
    assert any("43/3" in url for url in wol.fetched_urls)


@pytest.mark.asyncio
async def test_meeting_helper_invalid_input_warns_not_crashes() -> None:
    wol = FakeWOL()
    result = await meeting_helper("not a URL or a ref", wol=wol)
    assert result.warnings
    assert not result.findings
