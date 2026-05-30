"""research_topic agent — multi-step topic research with verified citations.

Input:  a topic phrase, e.g. "the day of Jehovah", "el día del Señor".
Steps:
  1. CDN search (filter='all') → top N results across publications.
  2. Pull article HTML for the top K results.
  3. Extract paragraphs + scripture references from each.
  4. Build Findings sorted by source relevance.

Output: AgentResult with findings ready for an LLM to synthesize into prose
with citations.
"""

from __future__ import annotations

from typing import Any

from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article

from jw_agents.base import AgentResult, Citation, Finding


async def research_topic(
    topic: str,
    *,
    language: str = "E",
    top_n: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 3,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Search jw.org for a topic and harvest excerpts from top articles."""
    result = AgentResult(query=topic, agent_name="research_topic")
    result.metadata["language"] = language

    owned_cdn = False
    owned_wol = False
    if cdn is None:
        cdn = CDNClient()
        owned_cdn = True
    if wol is None:
        wol = WOLClient()
        owned_wol = True

    try:
        data = await cdn.search(
            topic, filter_type="all", language=language, limit=top_n
        )
    except Exception as e:
        result.warnings.append(f"CDN search failed: {e}")
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()
        return result

    items = _flatten_search(data, limit=top_n)
    result.metadata["search_hits"] = len(items)
    if not items:
        result.warnings.append("No search results.")
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()
        return result

    # Fetch the top K articles.
    fetched = 0
    for item in items:
        if fetched >= fetch_top_k:
            break
        url = _wol_url_from(item)
        if not url:
            continue
        try:
            html = await wol.fetch(url)
        except Exception as e:
            result.warnings.append(f"Fetch failed for {url}: {e}")
            continue
        article = parse_article(html)
        title = article.title or item.get("title", "")
        for i, p in enumerate(article.paragraphs[:max_excerpts_per_article]):
            result.findings.append(Finding(
                summary=f"Excerpt from “{title}”",
                excerpt=p,
                citation=Citation(
                    url=url,
                    title=title,
                    kind="article",
                    metadata={"paragraph_index": i + 1},
                ),
            ))
        fetched += 1

    if owned_cdn:
        await cdn.aclose()
    if owned_wol:
        await wol.aclose()
    return result


def _flatten_search(data: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for r in data.get("results", []):
        if isinstance(r, dict) and r.get("type") == "group":
            flat.extend(x for x in r.get("results", []) if isinstance(x, dict))
        elif isinstance(r, dict):
            flat.append(r)
        if len(flat) >= limit:
            break
    return flat[:limit]


def _wol_url_from(entry: dict[str, Any]) -> str | None:
    links = entry.get("links", {}) or {}
    return links.get("wol") or links.get("jw.org") or None
