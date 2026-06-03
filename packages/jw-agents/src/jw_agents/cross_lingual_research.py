"""cross_lingual_research agent (F54.7) — query in lang A, search corpus in lang B.

Killer multilingual feature for JW research: the user asks a question in
their own language (Spanish, Quechua, Kinyarwanda…) but the richest article
corpus lives in the dominant publication language for that topic (usually
English). This agent bridges that gap:

  1. Translate query A → B via NLLB-200 (preserving Bible refs).
  2. Run the existing `research_topic` agent on the corpus in B.
  3. Translate each finding's excerpt back to A, preserving refs.

Bible refs survive both translation hops because of `translate_preserving_
references()` — the model never sees the book/chapter/verse, just opaque
`<<REF:i>>` tokens. Numeric hallucination is structurally impossible.
"""

from __future__ import annotations

from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.translation import translate_preserving_references
from jw_core.translation_providers import TranslationProvider, get_translation_provider

from jw_agents.base import AgentResult, Finding
from jw_agents.research_topic import research_topic
from jw_agents.tracing import AgentTracer, get_active_tracer


async def cross_lingual_research(
    topic: str,
    *,
    user_language: str = "es",
    corpus_language: str = "E",
    corpus_language_iso: str = "en",
    top_n: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 3,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    translator: TranslationProvider | None = None,
    trace: AgentTracer | None = None,
) -> AgentResult:
    """Translate query, search corpus in `corpus_language`, translate back.

    Args:
        topic: User query in `user_language`.
        user_language: ISO-639-1 ("es"). For NLLB translation routing.
        corpus_language: MEPS code passed to `research_topic` ("E" for English).
        corpus_language_iso: ISO equivalent of `corpus_language` for NLLB
            ("en"). The two diverge because jw.org uses MEPS but NLLB uses ISO.
        translator: optional injected provider (test seam). Defaults to the
            best available via `get_translation_provider()`.

    Returns:
        An `AgentResult` where findings.excerpts are in `user_language`
        (translated back), preserving Bible refs in `user_language` naming.
    """
    tr = trace if trace is not None else get_active_tracer()
    if translator is None:
        translator = get_translation_provider(source=user_language, target=corpus_language_iso)

    # 1. Translate query into corpus language.
    with tr.step(
        "translate_query",
        input_digest={"from": user_language, "to": corpus_language_iso, "len": len(topic)},
    ) as step:
        translated_query = translate_preserving_references(
            topic,
            source=user_language,
            target=corpus_language_iso,
            provider=translator,
        )
        step.note_hits(1)

    # 2. Run the existing research agent on the translated query.
    inner = await research_topic(
        translated_query,
        language=corpus_language,
        top_n=top_n,
        fetch_top_k=fetch_top_k,
        max_excerpts_per_article=max_excerpts_per_article,
        cdn=cdn,
        wol=wol,
        trace=tr,
    )

    # 3. Translate summaries + excerpts back to user_language, preserving refs.
    out = AgentResult(query=topic, agent_name="cross_lingual_research")
    out.metadata = {
        **inner.metadata,
        "user_language": user_language,
        "corpus_language": corpus_language,
        "corpus_language_iso": corpus_language_iso,
        "translator": translator.name,
        "translated_query": translated_query,
    }
    out.warnings = list(inner.warnings)
    with tr.step("translate_findings", input_digest={"n": len(inner.findings)}) as step:
        for finding in inner.findings:
            translated_summary = translate_preserving_references(
                finding.summary,
                source=corpus_language_iso,
                target=user_language,
                provider=translator,
            )
            translated_excerpt = (
                translate_preserving_references(
                    finding.excerpt,
                    source=corpus_language_iso,
                    target=user_language,
                    provider=translator,
                )
                if finding.excerpt
                else ""
            )
            out.findings.append(
                Finding(
                    summary=translated_summary,
                    citation=finding.citation,
                    excerpt=translated_excerpt,
                    metadata=dict(finding.metadata),
                )
            )
        step.note_kept(len(out.findings))

    return out
