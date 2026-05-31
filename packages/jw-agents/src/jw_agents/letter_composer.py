"""letter_composer — scaffolds for letter / phone / cart witnessing.

Stateless. No network unless an optional TopicIndexClient is injected.
Produces a 4-section `AgentResult` (`opener · bridge · scripture · closing`)
plus optional 5th `topic_anchor` when a TopicIndexClient is provided.

Copyright stance: the prose in `metadata.data.letter_templates` is original
(written by the author of this package). Bible text is never copied — only
the canonical wol.jw.org URL is emitted via `Citation.url`. The LLM client
that consumes the scaffold decides what verse text (if any) to surface.

Territory hint: cosmetic only. Inserted verbatim into the opener prose.
Never used to filter content. Not stored.
"""

from __future__ import annotations

from typing import Literal

from jw_core.clients.topic_index import TopicIndexClient
from jw_core.data.cart_templates import get_cart_template
from jw_core.data.letter_templates import (
    AUDIENCES,
    LetterTemplate,
    resolve_topic_family,
)
from jw_core.data.letter_templates import get_template as get_letter_template
from jw_core.data.phone_templates import get_phone_template
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding

Kind = Literal["letter", "phone", "cart"]
KINDS: tuple[Kind, ...] = ("letter", "phone", "cart")

_SUPPORTED_LANGS = {"en", "es", "pt"}

_SCAFFOLD_URL = "https://www.jw.org/"


def _pick_template(kind: Kind, audience: str, topic_family: str) -> LetterTemplate:
    if kind == "letter":
        return get_letter_template(audience, topic_family)
    if kind == "phone":
        return get_phone_template(audience, topic_family)
    if kind == "cart":
        return get_cart_template(audience, topic_family)
    raise ValueError(f"unknown kind: {kind!r}")


def _localize(block: dict[str, str], language: str) -> str:
    return block.get(language) or block.get("en") or next(iter(block.values()), "")


def _scripture_finding(ref_text: str, language: str) -> Finding:
    ref = parse_reference(ref_text)
    if ref is None:
        return Finding(
            summary=f"Suggested scripture: {ref_text}",
            excerpt="",  # never copy bible text — copyright safety
            citation=Citation(
                url=f"https://wol.jw.org/{language}/wol/h/r1/lp-{language[0]}",
                title=ref_text,
                kind="verse",
            ),
            metadata={"source": "verse_text", "section": "scripture"},
        )
    return Finding(
        summary=f"Suggested scripture: {ref.display()}",
        excerpt="",  # copyright safety
        citation=Citation(
            url=ref.wol_url(lang=language),
            title=ref.display(),
            kind="verse",
        ),
        metadata={
            "source": "verse_text",
            "section": "scripture",
            "reference": ref.display(),
        },
    )


async def letter_composer(
    kind: Kind,
    *,
    language: str = "es",
    topic_or_question: str,
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
    topic: TopicIndexClient | None = None,
) -> AgentResult:
    """Compose a witnessing scaffold for letter / phone / cart.

    Returns 4 `Finding`s in order: opener, bridge, scripture, closing.
    Optional 5th: topic_anchor (only when `topic` is provided).
    """

    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind!r}. Allowed: {KINDS}")

    result = AgentResult(
        query=topic_or_question,
        agent_name="letter_composer",
    )

    # Resolve language (fallback en).
    lang = language.lower() if language else "en"
    if lang not in _SUPPORTED_LANGS:
        result.warnings.append(f"Unsupported language {language!r}; using English fallback.")
        lang = "en"

    # Resolve audience (fallback default).
    if audience not in AUDIENCES:
        result.warnings.append(f"Unknown audience {audience!r}; using 'default'. Available: {AUDIENCES}")
        eff_audience = "default"
    else:
        eff_audience = audience

    # Resolve topic family from the free-form text.
    topic_family = resolve_topic_family(topic_or_question, lang)

    template = _pick_template(kind, eff_audience, topic_family)

    # Build the four mandatory sections.
    opener_text = _localize(template.opener, lang)
    if territory_hint:
        # Cosmetic: prepend territory hint into opener prose.
        opener_text = f"({territory_hint.strip()}) {opener_text}"

    bridge_text = _localize(template.bridge, lang)
    closing_text = _localize(template.closing, lang)

    effective_jw_link = jw_link or template.suggested_jw_link

    result.findings.append(
        Finding(
            summary=opener_text,
            excerpt=opener_text,
            citation=Citation(url=_SCAFFOLD_URL, title="opener", kind="scaffold"),
            metadata={"source": "letter_template", "section": "opener"},
        )
    )
    result.findings.append(
        Finding(
            summary=bridge_text,
            excerpt=bridge_text,
            citation=Citation(url=_SCAFFOLD_URL, title="bridge", kind="scaffold"),
            metadata={"source": "letter_template", "section": "bridge"},
        )
    )
    result.findings.append(_scripture_finding(template.suggested_scripture, lang))
    result.findings.append(
        Finding(
            summary=closing_text,
            excerpt=closing_text,
            citation=Citation(
                url=effective_jw_link,
                title="closing",
                kind="scaffold",
            ),
            metadata={"source": "letter_template", "section": "closing"},
        )
    )

    # Optional 5th: topic anchor from the Publications Index.
    if topic is not None:
        try:
            hits = await topic.search_subjects(topic_or_question, language=lang.upper()[0], limit=1)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Topic Index search failed: {exc}")
            hits = []
        if hits:
            subj_url = hits[0].get("url") or _SCAFFOLD_URL
            title = hits[0].get("title") or topic_or_question
            result.findings.append(
                Finding(
                    summary=f"Topic anchor suggestion: {title}",
                    excerpt="",
                    citation=Citation(url=subj_url, title=title, kind="topic_subject"),
                    metadata={"source": "topic_index", "section": "topic_anchor"},
                )
            )

    # Global metadata (informational only — no PII persisted).
    result.metadata.update(
        {
            "kind": kind,
            "audience": eff_audience,
            "topic_family": topic_family,
            "language": lang,
            "word_count_target": template.word_count_target,
            "time_target_seconds": template.time_target_seconds,
            "territory_hint": territory_hint,
            "jw_link_suggested": effective_jw_link,
            "suggested_scripture": template.suggested_scripture,
        }
    )

    return result
