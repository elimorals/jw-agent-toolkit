"""Unit tests for jw-agents — pure structural tests; no real network.

We test the structure (AgentResult shape, citation propagation, warnings on
bad input) and rely on a FakeWOLClient for any agent that needs to fetch.
"""

from dataclasses import dataclass

import pytest

from jw_agents import (
    AgentResult,
    Citation,
    Finding,
    meeting_helper,
    research_topic,
    verse_explainer,
)


# ── Test doubles ────────────────────────────────────────────────────────

class FakeWOL:
    """Minimal in-memory WOL client returning canned HTML."""

    def __init__(self, html: str = "") -> None:
        self.html = html or _SAMPLE_HTML
        self.fetched_urls: list[str] = []

    async def get_bible_chapter(self, book_num, chapter, *, language="en", publication="nwtsty"):
        url = f"https://wol.jw.org/{language}/wol/b/r1/lp-{language[0]}/nwtsty/{book_num}/{chapter}"
        self.fetched_urls.append(url)
        return url, self.html

    async def fetch(self, url: str) -> str:
        self.fetched_urls.append(url)
        return self.html

    async def get_today_homepage(self, language="en"):
        url = f"https://wol.jw.org/{language}/wol/h/r1/lp-{language[0]}"
        self.fetched_urls.append(url)
        return url, self.html

    async def aclose(self) -> None:
        pass


class FakeCDN:
    """Minimal in-memory CDN client returning canned search results."""

    def __init__(self, results: list[dict] | None = None) -> None:
        # `or` would replace an empty list with the default; we want []  honored.
        self.results = _SAMPLE_SEARCH_RESULTS if results is None else results
        self.searches: list[str] = []

    async def search(self, query, *, filter_type="all", language="E", limit=10):
        self.searches.append(query)
        return {"results": self.results[:limit]}

    async def aclose(self) -> None:
        pass


_SAMPLE_HTML = """
<html><body>
<article id="article">
<h1>Sample Article Title</h1>
<p id="p1" data-pid="1">
  <span class="v" id="v43-3-1-1">1 First verse with some content. It speaks of love.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample/1/0">+</a>
  </span>
  <span class="v" id="v43-3-2-1">2 Second verse with more content. Peace is a gift.</span>
</p>
<p id="p2" data-pid="2">
  <span class="v" id="v43-3-3-1">3 The Son of God spoke of love.</span>
  <span class="v" id="v43-3-16-1">16 For God so loved the world.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample/16/0">+</a>
  </span>
</p>
<div class="studyNoteGroup">
  <li class="item studyNote">
    <strong>love:</strong> A note about love in this chapter.
    <a class="b" href="/en/wol/bc/r1/lp-e/sample/2/0">1 John 4:8</a>
  </li>
</div>
</article>
</body></html>
"""

_SAMPLE_SEARCH_RESULTS = [{
    "type": "item",
    "title": "What the Bible Says About Love",
    "snippet": "Love is the greatest virtue.",
    "links": {"wol": "https://wol.jw.org/en/wol/d/r1/lp-e/example-1"},
}, {
    "type": "item",
    "title": "Peace and Security",
    "snippet": "True peace comes from God.",
    "links": {"wol": "https://wol.jw.org/en/wol/d/r1/lp-e/example-2"},
}]


# ── Base dataclasses ────────────────────────────────────────────────────

def test_agent_result_to_dict_structure() -> None:
    r = AgentResult(
        query="x", agent_name="test",
        findings=[Finding(
            summary="s", excerpt="e",
            citation=Citation(url="http://x", title="t", kind="article"),
        )],
        warnings=["w1"],
    )
    d = r.to_dict()
    assert d["query"] == "x"
    assert d["agent_name"] == "test"
    assert d["warnings"] == ["w1"]
    assert d["findings"][0]["citation"]["url"] == "http://x"


# ── verse_explainer ─────────────────────────────────────────────────────

async def test_verse_explainer_resolves_and_fetches() -> None:
    wol = FakeWOL()
    # Use English so the sample HTML's verse anchors (v43-3-*) match (es WOL
    # would 404 in production; FakeWOL ignores language but the parser still
    # tags verses with the requested ISO).
    result = await verse_explainer("John 3:16", language="en", wol=wol)
    assert result.agent_name == "verse_explainer"
    assert result.metadata["book_num"] == 43
    assert result.metadata["chapter"] == 3
    assert result.metadata["verse_start"] == 16
    assert len(result.findings) > 0
    # Phase 3 upgrade: target_verse finding for v16.
    target = [f for f in result.findings if f.metadata.get("kind") == "target_verse"]
    assert target
    assert "loved the world" in target[0].excerpt
    # Cross-ref markers from inside the verse spans.
    crossrefs = [f for f in result.findings if f.metadata.get("kind") == "cross_ref"]
    assert len(crossrefs) >= 1


async def test_verse_explainer_no_ref_returns_warning() -> None:
    result = await verse_explainer("hello world", wol=FakeWOL())
    assert result.warnings
    assert not result.findings


# ── research_topic ──────────────────────────────────────────────────────

async def test_research_topic_aggregates_excerpts() -> None:
    result = await research_topic(
        "love", language="E",
        cdn=FakeCDN(), wol=FakeWOL(),
        top_n=5, fetch_top_k=2, max_excerpts_per_article=2,
    )
    assert result.agent_name == "research_topic"
    assert result.metadata["search_hits"] == 2
    # 2 articles × 2 excerpts = 4 findings.
    assert len(result.findings) == 4
    for f in result.findings:
        assert f.citation.url.startswith("https://wol.jw.org")


async def test_research_topic_handles_empty_results() -> None:
    result = await research_topic(
        "nothing", cdn=FakeCDN(results=[]), wol=FakeWOL(),
    )
    assert result.warnings
    assert not result.findings


# ── meeting_helper ──────────────────────────────────────────────────────

async def test_meeting_helper_with_url_input() -> None:
    result = await meeting_helper(
        "https://wol.jw.org/en/wol/d/r1/lp-e/example",
        wol=FakeWOL(),
    )
    assert result.agent_name == "meeting_helper"
    assert "title" in result.metadata
    assert len(result.findings) > 0
    assert "prep_prompts" in result.metadata


async def test_meeting_helper_with_reference_input() -> None:
    wol = FakeWOL()
    result = await meeting_helper("Juan 3:16", language="es", wol=wol)
    assert result.metadata.get("resolved_reference") == "John 3:16"
    assert len(wol.fetched_urls) == 1


async def test_meeting_helper_invalid_input_warns() -> None:
    result = await meeting_helper("nonsense", wol=FakeWOL())
    assert result.warnings


# ── apologetics ─────────────────────────────────────────────────────────

async def test_apologetics_combines_refs_and_search() -> None:
    from jw_agents.apologetics import apologetics
    result = await apologetics(
        "What does Juan 3:16 say about love?",
        language="E",
        cdn=FakeCDN(), wol=FakeWOL(),
        web_top_k=2,
    )
    sources = {f.metadata.get("source") for f in result.findings}
    assert "question_refs" in sources   # Bible ref in question detected
    assert "cdn_search" in sources      # search articles included


async def test_apologetics_with_rag_store() -> None:
    from jw_agents.apologetics import apologetics
    from jw_rag import Chunk, FakeEmbedder, VectorStore
    from pathlib import Path

    store = VectorStore(Path("/tmp/nonexistent"), FakeEmbedder(dim=32))
    store.add([Chunk(
        id="c1",
        text="The greatest commandment is love",
        source_id="local-1",
        metadata={"title": "On Love", "source_url": "https://wol.jw.org/example",
                  "kind": "article"},
    )])
    result = await apologetics(
        "What is the greatest commandment?",
        cdn=FakeCDN(), wol=FakeWOL(),
        rag_store=store, rag_top_k=3,
    )
    rag_findings = [f for f in result.findings if f.metadata.get("source") == "rag"]
    assert len(rag_findings) >= 1
    assert "rrf_score" in rag_findings[0].metadata
