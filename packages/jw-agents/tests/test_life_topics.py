"""Tests for the life_topics agent — fully stubbed, zero network."""

from __future__ import annotations

from typing import Any

import pytest

from jw_agents.life_topics import life_topics


# --- Stubs ----------------------------------------------------------


class StubTopicIndex:
    def __init__(self, subjects: dict[str, Any] | None = None) -> None:
        self._subjects = subjects or {}
        self.searched: list[tuple[str, str]] = []

    async def search_subjects(
        self, anchor: str, *, language: str = "E", limit: int = 1
    ) -> list[dict[str, Any]]:
        self.searched.append((anchor, language))
        if anchor in self._subjects:
            return [
                {
                    "docid": f"doc-{anchor}",
                    "title": anchor,
                    "wol_url": f"https://wol.jw.org/{anchor}",
                    "score": 100,
                    "snippet": "",
                    "subtype": "subject",
                    "original_rank": 0,
                }
            ]
        return []

    async def get_subject_page(self, docid: str, *, language: str = "en"):
        anchor = docid.removeprefix("doc-")
        payload = self._subjects[anchor]

        class _Sub:
            heading = payload["heading"]
            citations = payload["citations"]
            is_top_level = True

        class _Page:
            title = anchor
            source_url = f"https://wol.jw.org/{anchor}"
            subheadings = [_Sub()]
            see_also: list[str] = []
            total_citations = len(payload["citations"])
            style = "default"

        return _Page()

    async def aclose(self) -> None: ...


class StubCDN:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = results or []
        self.calls: list[tuple[str, str, str]] = []

    async def search(
        self,
        query: str,
        *,
        filter_type: str = "all",
        language: str = "E",
        limit: int = 10,
    ) -> dict[str, Any]:
        self.calls.append((query, filter_type, language))
        return {"results": self._results[:limit]}

    async def aclose(self) -> None: ...


SAMPLE_ARTICLE_HTML = """
<html><head><title>How to Cope With Anxiety</title></head>
<body>
<article>
  <p id="p1" data-pid="1">The Bible acknowledges that we all face worry at times.</p>
  <p id="p2" data-pid="2">Jesus said: "Stop being anxious about your life." — Matthew 6:25.</p>
  <p id="p3" data-pid="3">Prayer is one of the strongest tools we have.</p>
</article>
</body></html>
"""


class StubWOL:
    def __init__(self, html: str = SAMPLE_ARTICLE_HTML) -> None:
        self._html = html
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> str:
        self.fetched.append(url)
        return self._html

    async def aclose(self) -> None: ...


class _Citation:
    def __init__(self, text: str, kind: str = "bible") -> None:
        self.text = text
        self.kind = kind


# --- Tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitive_topic_emits_disclaimer_and_redirect() -> None:
    topic = StubTopicIndex(
        subjects={
            "Anxiety": {
                "heading": "Anxiety — How to Cope",
                "citations": [_Citation("Philippians 4:6, 7"), _Citation("1 Peter 5:7")],
            }
        }
    )
    cdn = StubCDN(
        results=[
            {
                "title": "How to Cope With Anxiety",
                "links": {"wol": "https://wol.jw.org/articles/anxiety-1"},
            }
        ]
    )
    wol = StubWOL()

    result = await life_topics(
        "ansiedad", language="es", topic=topic, cdn=cdn, wol=wol
    )

    sources = [f.metadata.get("source") for f in result.findings]
    assert "topic_index_entry" in sources
    assert "cdn_search" in sources
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
    assert result.metadata["topic_id"] == "anxiety"
    assert result.metadata["family"] == "sensitive"
    assert result.metadata["language"] == "es"


@pytest.mark.asyncio
async def test_general_topic_does_not_emit_redirect() -> None:
    topic = StubTopicIndex(
        subjects={
            "Children": {
                "heading": "Raising Children",
                "citations": [_Citation("Ephesians 6:4")],
            }
        }
    )
    cdn = StubCDN(
        results=[
            {"title": "Family Help", "links": {"wol": "https://wol.jw.org/articles/family-1"}}
        ]
    )
    wol = StubWOL()

    result = await life_topics("parenting", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]

    assert "disclaimer" in sources
    assert "elders_redirect" not in sources
    assert result.metadata["family"] == "general"


@pytest.mark.asyncio
async def test_unknown_topic_emits_warning_and_generic_disclaimer_only() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN()
    wol = StubWOL()

    result = await life_topics("qwertyzzz", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]

    assert sources == ["disclaimer"]
    assert "elders_redirect" not in sources
    assert any("No matching life topic" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_cdn_error_does_not_kill_disclaimer() -> None:
    class BrokenCDN:
        async def search(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("network boom")

        async def aclose(self) -> None: ...

    topic = StubTopicIndex()
    wol = StubWOL()

    result = await life_topics(
        "anxiety", language="en", topic=topic, cdn=BrokenCDN(), wol=wol
    )
    sources = [f.metadata.get("source") for f in result.findings]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources  # still sensitive
    assert any("network boom" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_cdn_uses_publications_filter_and_topic_search_query() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    await life_topics("loneliness", language="en", topic=topic, cdn=cdn, wol=wol)
    assert cdn.calls, "CDN.search was not called"
    query, filt, lang = cdn.calls[0]
    assert filt == "publications"
    assert query == "loneliness friendship"
    assert lang == "E"


@pytest.mark.asyncio
async def test_excerpts_are_capped_per_article() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(
        results=[
            {"title": "Article", "links": {"wol": "https://wol.jw.org/x"}},
        ]
    )
    wol = StubWOL()
    result = await life_topics(
        "anxiety",
        language="en",
        topic=topic,
        cdn=cdn,
        wol=wol,
        max_excerpts_per_article=2,
    )
    excerpts = [f for f in result.findings if f.metadata.get("source") == "cdn_search"]
    assert len(excerpts) <= 2


@pytest.mark.asyncio
async def test_finding_order_disclaimer_before_redirect() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    result = await life_topics("grief", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]
    assert sources[-2:] == ["disclaimer", "elders_redirect"]


@pytest.mark.asyncio
async def test_no_bible_quotation_fabrication() -> None:
    """Excerpts must come from article HTML — never synthesized.

    We give the agent an HTML that does NOT contain Hebrews 4:13 and
    assert that no Finding text mentions it.
    """
    topic = StubTopicIndex()
    cdn = StubCDN(
        results=[{"title": "Article", "links": {"wol": "https://wol.jw.org/x"}}]
    )
    html_without_hebrews = (
        "<html><body><article><p data-pid='1'>Anxiety is common.</p></article></body></html>"
    )
    wol = StubWOL(html=html_without_hebrews)
    result = await life_topics("anxiety", language="en", topic=topic, cdn=cdn, wol=wol)
    for f in result.findings:
        assert "Hebrews 4:13" not in (f.excerpt or "")
        assert "Hebrews 4:13" not in f.summary


@pytest.mark.asyncio
async def test_language_fr_falls_back_to_english_disclaimer() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    result = await life_topics("anxiety", language="fr", topic=topic, cdn=cdn, wol=wol)
    disclaimer = next(f for f in result.findings if f.metadata.get("source") == "disclaimer")
    assert "Watchtower" in disclaimer.excerpt
