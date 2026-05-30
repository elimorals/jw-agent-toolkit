"""reverse_citation_lookup — answer 'where is this quote from?'

The flow:
  1. Normalise the quote (remove punctuation, lowercase).
  2. Run a CDN search restricted to publications.
  3. For each candidate URL, fetch and check that the (normalised) text
     actually contains the (normalised) quote.
  4. Return matches with confidence + publication metadata.

This is the inverse of `research_topic` — you HAVE the snippet, you need
the source.
"""

from __future__ import annotations

import re

from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.research_topic import _flatten_search, _wol_url_from

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _bigram_overlap(needle: str, haystack: str) -> float:
    needle_tokens = needle.split()
    if len(needle_tokens) < 2:
        return 1.0 if needle in haystack else 0.0
    needle_bigrams = {tuple(needle_tokens[i : i + 2]) for i in range(len(needle_tokens) - 1)}
    hay_tokens = haystack.split()
    if not hay_tokens:
        return 0.0
    hay_bigrams = {tuple(hay_tokens[i : i + 2]) for i in range(len(hay_tokens) - 1)}
    overlap = needle_bigrams & hay_bigrams
    if not needle_bigrams:
        return 0.0
    return len(overlap) / len(needle_bigrams)


async def reverse_citation_lookup(
    quote: str,
    *,
    language: str = "E",
    top_n: int = 8,
    min_confidence: float = 0.4,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Find the JW publication that contains `quote`.

    Args:
        quote: Verbatim or near-verbatim text. Works best with 8-30 words.
        language: JW code ('E', 'S', 'T').
        top_n: How many CDN hits to evaluate.
        min_confidence: 0.0-1.0 bigram overlap threshold to keep a match.
    """
    result = AgentResult(query=quote, agent_name="reverse_citation_lookup")
    needle = _normalize(quote)
    if not needle:
        result.warnings.append("Empty quote after normalisation.")
        return result

    owned_cdn = cdn is None
    owned_wol = wol is None
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()

    try:
        # Use the longest meaningful phrase as the search query so the
        # CDN has something to work with.
        query = " ".join(needle.split()[:10])
        try:
            data = await cdn.search(query, filter_type="publications", language=language, limit=top_n * 2)
        except Exception as e:
            result.warnings.append(f"CDN search failed: {e}")
            return result

        items = _flatten_search(data, limit=top_n)
        evaluated = 0
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
            haystack = _normalize(" ".join(article.paragraphs))
            confidence = _bigram_overlap(needle, haystack)
            evaluated += 1
            if confidence < min_confidence:
                continue
            best_para = _best_paragraph(article.paragraphs, needle)
            result.findings.append(
                Finding(
                    summary=f"Match (confidence {confidence:.2f}): {article.title or item.get('title', '')}",
                    excerpt=best_para,
                    citation=Citation(
                        url=url,
                        title=article.title or item.get("title", ""),
                        kind="article",
                        metadata={"confidence": confidence},
                    ),
                    metadata={"source": "reverse_citation", "confidence": confidence},
                )
            )
        result.metadata["evaluated"] = evaluated
    finally:
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    return result


def _best_paragraph(paragraphs: list[str], needle: str) -> str:
    """Pick the paragraph with the highest bigram overlap."""
    best_score = 0.0
    best_para = paragraphs[0] if paragraphs else ""
    for p in paragraphs:
        score = _bigram_overlap(needle, _normalize(p))
        if score > best_score:
            best_score = score
            best_para = p
    return best_para
