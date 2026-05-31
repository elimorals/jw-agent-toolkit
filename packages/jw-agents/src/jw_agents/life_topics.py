"""life_topics agent — informative answers on sensitive personal topics.

This agent is DELIBERATELY different from research_topic and
conversation_assistant:

  - It serves a user asking *for themselves*, not researching for a class
    or preparing a witness conversation.
  - Every AgentResult includes a `disclaimer` Finding. The disclaimer is
    part of the agent's CONTRACT, not a doc-only note.
  - Topics marked `family=sensitive` ALSO carry an `elders_redirect`
    Finding pointing the user to local elders / family.
  - The agent NEVER fabricates Scripture; it only relays excerpts that
    appear verbatim in the matched articles.

If no published material matches, the result is empty of excerpts but
the disclaimer is still present. The agent never invents pastoral counsel.
"""

from __future__ import annotations

from typing import Any

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.wol import WOLClient
from jw_core.data.life_disclaimers import get_disclaimer, get_elders_redirect
from jw_core.data.life_topics import LifeTopic, resolve_topic
from jw_core.languages import get_language
from jw_core.parsers.article import parse_article

from jw_agents.base import AgentResult, Citation, Finding


async def life_topics(
    query: str,
    *,
    language: str = "en",
    top_articles: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 2,
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Surface published material on a life topic + mandatory disclaimer.

    Args:
        query: Free-form user input ("anxiety" / "ansiedad" / "ansiedade").
        language: ISO code ("en", "es", "pt"). Other ISOs fall back to English
            for disclaimer text but the topic registry still tries cross-lang.
        top_articles: how many CDN search hits to consider.
        fetch_top_k: of those, how many to actually fetch + parse.
        max_excerpts_per_article: paragraph cap per article.

    Returns:
        AgentResult with findings ordered: topic_index_entry -> cdn_search ->
        disclaimer -> elders_redirect.

        Empty results are still valid; the disclaimer is the floor.
    """
    result = AgentResult(query=query, agent_name="life_topics")
    result.metadata["language"] = language

    matched = resolve_topic(query, language=language)

    # Track which clients we own so we can close them cleanly.
    owned_topic = topic is None
    owned_cdn = cdn is None
    owned_wol = wol is None
    topic = topic if topic is not None else TopicIndexClient()
    cdn = cdn if cdn is not None else CDNClient()
    wol = wol if wol is not None else WOLClient()

    try:
        if matched is None:
            result.warnings.append(f"No matching life topic for query: {query!r}")
            _append_disclaimer(result, family="general", language=language)
            return result

        result.metadata["topic_id"] = matched.topic_id
        result.metadata["family"] = matched.family

        try:
            jw_lang = get_language(language).jw_code
        except KeyError:
            jw_lang = "E"

        await _surface_topic_index(
            result, matched, topic=topic, jw_lang=jw_lang, language=language
        )
        await _surface_cdn_articles(
            result,
            matched,
            cdn=cdn,
            wol=wol,
            jw_lang=jw_lang,
            top_articles=top_articles,
            fetch_top_k=fetch_top_k,
            max_excerpts_per_article=max_excerpts_per_article,
        )

        _append_disclaimer(result, family=matched.family, language=language)
        if matched.family == "sensitive":
            _append_elders_redirect(result, language=language)
        return result
    finally:
        if owned_topic:
            await topic.aclose()
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()


async def _surface_topic_index(
    result: AgentResult,
    matched: LifeTopic,
    *,
    topic: TopicIndexClient,
    jw_lang: str,
    language: str,
) -> None:
    for anchor in matched.topic_anchors:
        try:
            hits = await topic.search_subjects(anchor, language=jw_lang, limit=1)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Topic anchor {anchor!r} failed: {exc}")
            continue
        if not hits:
            continue
        docid = hits[0].get("docid") or ""
        if not docid:
            continue
        try:
            page = await topic.get_subject_page(docid, language=language)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Subject {anchor!r} fetch failed: {exc}")
            continue
        for sh in list(page.subheadings)[:3]:
            citations_text = "; ".join(getattr(c, "text", "") for c in sh.citations[:6])
            result.findings.append(
                Finding(
                    summary=f"{page.title} -> {sh.heading}",
                    excerpt=citations_text,
                    citation=Citation(
                        url=page.source_url,
                        title=f"{page.title}: {sh.heading}",
                        kind="topic_subheading",
                    ),
                    metadata={
                        "source": "topic_index_entry",
                        "anchor": anchor,
                        "topic_id": matched.topic_id,
                    },
                )
            )


async def _surface_cdn_articles(
    result: AgentResult,
    matched: LifeTopic,
    *,
    cdn: CDNClient,
    wol: WOLClient,
    jw_lang: str,
    top_articles: int,
    fetch_top_k: int,
    max_excerpts_per_article: int,
) -> None:
    try:
        data = await cdn.search(
            matched.search_query,
            filter_type="publications",
            language=jw_lang,
            limit=top_articles,
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"CDN search failed: {exc}")
        return

    items = _flatten(data, limit=top_articles)
    fetched = 0
    for item in items:
        if fetched >= fetch_top_k:
            break
        url = _wol_url(item)
        if not url:
            continue
        try:
            html = await wol.fetch(url)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Fetch failed for {url}: {exc}")
            continue
        article = parse_article(html)
        title = article.title or item.get("title", "")
        for i, paragraph in enumerate(article.paragraphs[:max_excerpts_per_article]):
            result.findings.append(
                Finding(
                    summary=f"Excerpt from {title!r}",
                    excerpt=paragraph,
                    citation=Citation(
                        url=url,
                        title=title,
                        kind="article",
                        metadata={"paragraph_index": i + 1},
                    ),
                    metadata={
                        "source": "cdn_search",
                        "topic_id": matched.topic_id,
                    },
                )
            )
        fetched += 1


def _append_disclaimer(result: AgentResult, *, family: str, language: str) -> None:
    text = get_disclaimer(family, language)
    result.findings.append(
        Finding(
            summary="Pastoral boundary",
            excerpt=text,
            citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
            metadata={"source": "disclaimer", "family": family},
        )
    )


def _append_elders_redirect(result: AgentResult, *, language: str) -> None:
    text = get_elders_redirect(language)
    result.findings.append(
        Finding(
            summary="Talk to your elders and family",
            excerpt=text,
            citation=Citation(
                url="",
                title="Elders redirect (1 Peter 5:1-3)",
                kind="elders_redirect",
            ),
            metadata={"source": "elders_redirect"},
        )
    )


def _flatten(data: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in data.get("results", []):
        if not isinstance(r, dict):
            continue
        if r.get("type") == "group":
            out.extend(x for x in r.get("results", []) if isinstance(x, dict))
        else:
            out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


def _wol_url(item: dict[str, Any]) -> str | None:
    links = item.get("links", {}) or {}
    return links.get("wol") or links.get("jw.org") or None
