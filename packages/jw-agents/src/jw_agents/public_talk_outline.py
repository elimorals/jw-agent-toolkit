"""public_talk_outline agent — outline a 10-30 min Bible discourse.

Given a theme verse or topic phrase, build a structured outline:

  - Theme statement
  - 3 main points (each with sub-points + supporting scriptures)
  - Suggested illustrations harvested from recent JW publications
  - Application + conclusion

The outline reuses topic_index (authoritative), research_topic, and the
RAG store when available. Nothing is invented — every supporting point
carries a citation.
"""

from __future__ import annotations

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_all_references

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.research_topic import _flatten_search, _wol_url_from

_LANG_KIND_MAP = {"E": "en", "S": "es", "T": "pt"}

_LOCAL_OUTLINE_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "intro": "Open with the theme scripture; raise a question your audience is asking.",
        "point": "Develop point {i}: state it briefly, read the scripture, illustrate, apply.",
        "conclusion": "Restate the theme, summarise the points, end with a call to action.",
    },
    "es": {
        "intro": "Abra con el texto temático; plantee la pregunta que su audiencia se hace.",
        "point": "Desarrolle el punto {i}: enúncielo, lea el texto, ilustre y aplique.",
        "conclusion": "Reformule el tema, repase los puntos y termine con un llamado a la acción.",
    },
    "pt": {
        "intro": "Abra com o texto-tema; levante a pergunta que sua audiência está fazendo.",
        "point": "Desenvolva o ponto {i}: enuncie, leia o texto, ilustre, aplique.",
        "conclusion": "Reafirme o tema, resuma os pontos e termine com um chamado à ação.",
    },
}


async def public_talk_outline(
    theme: str,
    *,
    language: str = "E",
    duration_minutes: int = 30,
    main_points: int = 3,
    illustration_top_k: int = 4,
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Build a discourse outline for `theme`.

    `theme` may be a phrase ("the unity of God's people") or a Bible
    reference ("Romanos 12:2"). When a reference is detected we use it
    as the theme scripture verbatim.
    """
    result = AgentResult(query=theme, agent_name="public_talk_outline")
    iso = _LANG_KIND_MAP.get(language.upper(), language.lower())
    templates = _LOCAL_OUTLINE_TEMPLATES.get(iso, _LOCAL_OUTLINE_TEMPLATES["en"])
    result.metadata.update(
        {
            "language": language,
            "duration_minutes": duration_minutes,
            "main_points": main_points,
            "outline_skeleton": {
                "intro": templates["intro"],
                "points": [templates["point"].format(i=i + 1) for i in range(main_points)],
                "conclusion": templates["conclusion"],
            },
        }
    )

    # If theme has a Bible reference, surface it.
    refs = parse_all_references(theme)
    if refs:
        ref = refs[0]
        result.findings.append(
            Finding(
                summary=f"Theme scripture: {ref.display()}",
                excerpt=ref.raw_match,
                citation=Citation(url=ref.wol_url(lang=iso), title=ref.display(), kind="verse"),
                metadata={"source": "question_refs"},
            )
        )

    owned_topic = topic is None
    owned_cdn = cdn is None
    owned_wol = wol is None
    topic = topic or TopicIndexClient(cdn=cdn, wol=wol)
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()

    try:
        # Topic Index — authoritative entry point.
        try:
            subjects = await topic.search_subjects(theme, language=language, limit=1)
        except Exception as e:
            result.warnings.append(f"Topic index lookup failed: {e}")
            subjects = []
        if subjects:
            top = subjects[0]
            docid = top.get("docid")
            if docid:
                try:
                    subject = await topic.get_subject_page(docid, language=iso)
                    for sh in subject.subheadings[:main_points]:
                        result.findings.append(
                            Finding(
                                summary=f"Main point candidate — {sh.heading}",
                                excerpt="; ".join(c.text for c in sh.citations[:6]),
                                citation=Citation(
                                    url=subject.source_url,
                                    title=f"{subject.title}: {sh.heading}",
                                    kind="topic_subheading",
                                ),
                                metadata={
                                    "source": "topic_index_entry",
                                    "bible_refs": [c.text for c in sh.citations if c.kind == "bible"],
                                    "publication_codes": [c.text for c in sh.citations if c.kind == "publication"],
                                },
                            )
                        )
                except Exception as e:
                    result.warnings.append(f"Subject fetch failed: {e}")

        # Recent-publications illustrations via CDN search.
        try:
            data = await cdn.search(theme, filter_type="publications", language=language, limit=illustration_top_k * 2)
            items = _flatten_search(data, limit=illustration_top_k)
        except Exception as e:
            result.warnings.append(f"Illustration search failed: {e}")
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
            paragraph = article.paragraphs[0] if article.paragraphs else item.get("snippet", "")
            result.findings.append(
                Finding(
                    summary=f"Illustration candidate: {article.title or item.get('title', '')}",
                    excerpt=paragraph[:400],
                    citation=Citation(url=url, title=article.title or item.get("title", ""), kind="article"),
                    metadata={"source": "cdn_search", "use": "illustration"},
                )
            )
    finally:
        if owned_topic:
            await topic.aclose()
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    return result
