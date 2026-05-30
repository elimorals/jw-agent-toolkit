"""fact_checker agent — verify a claim only against official JW sources.

VISION.md #9: "Fact-checker contra fuentes JW oficiales únicamente
(rechazar todo lo que no esté en jw.org / wol.jw.org)".

Pipeline:
  1. Extract Bible refs from the claim.
  2. Hit the Watch Tower Publications Index (authoritative).
  3. Hit CDN search restricted to publications/bible/indexes.
  4. (Optionally) hit local RAG (which we trust if the user built it from
     official sources).
  5. Score the claim: SUPPORTED / DISPUTED / UNVERIFIABLE / REJECTED.

We never call external search APIs. If JW doesn't have something on it,
the verdict is UNVERIFIABLE (or REJECTED if we see a clear contradiction).
"""

from __future__ import annotations

from dataclasses import dataclass

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_all_references

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.research_topic import _flatten_search, _wol_url_from


# Phrases that, when found in published JW material, signal a contradiction
# of a hypothetical user claim. We don't try NLU here — we surface evidence
# and let the LLM judge.
_CONTRADICTION_HINTS = (
    "not biblical",
    "no es bíblico",
    "não é bíblico",
    "is unscriptural",
    "no es escritural",
    "não é escritural",
)


@dataclass
class FactCheckVerdict:
    verdict: str  # SUPPORTED | DISPUTED | UNVERIFIABLE | REJECTED
    confidence: float
    rationale: str
    supporting_urls: list[str]
    contradicting_urls: list[str]


_VERDICT_SUPPORTED = "SUPPORTED"
_VERDICT_DISPUTED = "DISPUTED"
_VERDICT_UNVERIFIABLE = "UNVERIFIABLE"
_VERDICT_REJECTED = "REJECTED"


async def fact_checker(
    claim: str,
    *,
    language: str = "E",
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    web_top_k: int = 4,
    rag_store: object | None = None,
    require_published: bool = True,
) -> AgentResult:
    """Fact-check `claim` against JW-official sources only.

    Args:
        claim: the assertion to verify.
        language: JW code.
        require_published: when True, the verdict requires at least one
            citation from `jw.org`/`wol.jw.org`. RAG-only support is
            downgraded to DISPUTED.
    """
    result = AgentResult(query=claim, agent_name="fact_checker")
    result.metadata["language"] = language

    supporting: list[str] = []
    contradicting: list[str] = []

    owned_topic = topic is None
    owned_cdn = cdn is None
    owned_wol = wol is None
    topic = topic or TopicIndexClient(cdn=cdn, wol=wol)
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()

    try:
        # 1. Explicit Bible refs
        for ref in parse_all_references(claim):
            url = ref.wol_url(lang=language.lower())
            result.findings.append(
                Finding(
                    summary=f"Claim cites {ref.display()}",
                    excerpt=ref.raw_match,
                    citation=Citation(url=url, title=ref.display(), kind="verse"),
                    metadata={"source": "question_refs"},
                )
            )
            supporting.append(url)

        # 2. Topic index
        try:
            subjects = await topic.search_subjects(claim, language=language, limit=1)
        except Exception as e:
            result.warnings.append(f"Topic search failed: {e}")
            subjects = []
        for s in subjects[:1]:
            docid = s.get("docid")
            if not docid:
                continue
            try:
                subject = await topic.get_subject_page(docid, language=language.lower())
            except Exception as e:
                result.warnings.append(f"Subject fetch failed: {e}")
                continue
            supporting.append(subject.source_url)
            result.findings.append(
                Finding(
                    summary=f"Topic index hit: {subject.title}",
                    excerpt=f"{subject.total_citations} citations across {len(subject.subheadings)} subheadings.",
                    citation=Citation(url=subject.source_url, title=subject.title, kind="topic_subject"),
                    metadata={"source": "topic_index"},
                )
            )

        # 3. CDN search
        try:
            data = await cdn.search(claim, filter_type="all", language=language, limit=web_top_k * 2)
            items = _flatten_search(data, limit=web_top_k)
        except Exception as e:
            result.warnings.append(f"CDN search failed: {e}")
            items = []
        for item in items:
            url = _wol_url_from(item)
            if not url:
                continue
            try:
                html = await wol.fetch(url)
            except Exception as e:
                result.warnings.append(f"Could not fetch {url}: {e}")
                continue
            article = parse_article(html)
            full_text = " ".join(article.paragraphs).lower()
            is_contradiction = any(h in full_text for h in _CONTRADICTION_HINTS)
            target_list = contradicting if is_contradiction else supporting
            target_list.append(url)
            result.findings.append(
                Finding(
                    summary=f"{'Contradiction' if is_contradiction else 'Match'}: {article.title or item.get('title', '')}",
                    excerpt=article.paragraphs[0] if article.paragraphs else "",
                    citation=Citation(url=url, title=article.title, kind="article"),
                    metadata={"source": "cdn_search", "is_contradiction": is_contradiction},
                )
            )

        # 4. RAG (optional)
        if rag_store is not None and hasattr(rag_store, "hybrid_search"):
            try:
                hits = rag_store.hybrid_search(claim, top_k=3)
            except Exception as e:
                result.warnings.append(f"RAG search failed: {e}")
                hits = []
            for hit in hits:
                url = hit.chunk.metadata.get("source_url", "")
                if url and url.startswith("http"):
                    supporting.append(url)
                result.findings.append(
                    Finding(
                        summary="RAG hit",
                        excerpt=hit.chunk.text,
                        citation=Citation(url=url, title=hit.chunk.metadata.get("title", ""), kind="rag_chunk"),
                        metadata={"source": "rag", "rrf_score": hit.score},
                    )
                )

    finally:
        if owned_topic:
            await topic.aclose()
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    verdict = _judge(supporting, contradicting, require_published=require_published)
    result.metadata["verdict"] = verdict.verdict
    result.metadata["confidence"] = verdict.confidence
    result.metadata["rationale"] = verdict.rationale
    result.metadata["supporting_urls"] = supporting
    result.metadata["contradicting_urls"] = contradicting
    return result


def _judge(
    supporting: list[str],
    contradicting: list[str],
    *,
    require_published: bool,
) -> FactCheckVerdict:
    if contradicting and not supporting:
        return FactCheckVerdict(
            verdict=_VERDICT_REJECTED,
            confidence=min(1.0, 0.5 + 0.1 * len(contradicting)),
            rationale="Found contradictions and no supporting sources.",
            supporting_urls=supporting,
            contradicting_urls=contradicting,
        )
    if contradicting and supporting:
        return FactCheckVerdict(
            verdict=_VERDICT_DISPUTED,
            confidence=0.5,
            rationale="Mixed signals — at least one source contradicts and others align.",
            supporting_urls=supporting,
            contradicting_urls=contradicting,
        )
    if supporting:
        official = [u for u in supporting if u.startswith("http") and ("jw.org" in u or "wol.jw.org" in u)]
        if require_published and not official:
            return FactCheckVerdict(
                verdict=_VERDICT_DISPUTED,
                confidence=0.4,
                rationale="Supporting evidence found only in RAG / non-published sources.",
                supporting_urls=supporting,
                contradicting_urls=contradicting,
            )
        return FactCheckVerdict(
            verdict=_VERDICT_SUPPORTED,
            confidence=min(1.0, 0.5 + 0.15 * len(official or supporting)),
            rationale="Multiple official JW sources align with the claim.",
            supporting_urls=supporting,
            contradicting_urls=contradicting,
        )
    return FactCheckVerdict(
        verdict=_VERDICT_UNVERIFIABLE,
        confidence=0.0,
        rationale="No JW-official sources found for this claim. Treat as unverifiable.",
        supporting_urls=supporting,
        contradicting_urls=contradicting,
    )
