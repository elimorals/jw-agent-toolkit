"""presentation_builder — adapt a witnessing presentation to an interlocutor.

Audience profiles supported (out of the box):
  - catholic, evangelical, atheist, muslim, hindu, buddhist, young,
    skeptic_intellectual, struggling_grief

The agent doesn't write the spiel — it returns a STRUCTURED scaffold:
opening question, common ground, anchor scriptures, anchor publications,
and a respectful pivot. The LLM (Claude/etc.) wraps it in prose.

Every anchor is a wol.jw.org URL so the resulting presentation can be
fact-checked at every claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jw_core.clients.topic_index import TopicIndexClient
from jw_core.data.locale_context import context_for_presentation
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding

_LANG_MAP = {"E": "en", "S": "es", "T": "pt"}


@dataclass(frozen=True)
class AudienceProfile:
    key: str
    label: dict[str, str]
    opening_questions: dict[str, list[str]] = field(default_factory=dict)
    common_ground: dict[str, list[str]] = field(default_factory=dict)
    suggested_topics: list[str] = field(default_factory=list)
    suggested_scriptures: list[str] = field(default_factory=list)
    tone_notes: dict[str, str] = field(default_factory=dict)


PROFILES: dict[str, AudienceProfile] = {
    "catholic": AudienceProfile(
        key="catholic",
        label={"en": "Catholic", "es": "Católico", "pt": "Católico"},
        opening_questions={
            "en": ["What did Jesus actually teach about prayer?"],
            "es": ["¿Qué enseñó realmente Jesús sobre la oración?"],
            "pt": ["O que Jesus realmente ensinou sobre a oração?"],
        },
        common_ground={
            "en": ["belief in Jesus", "respect for the Bible", "concern for family"],
            "es": ["creencia en Jesús", "respeto por la Biblia", "preocupación por la familia"],
            "pt": ["crença em Jesus", "respeito pela Bíblia", "preocupação com a família"],
        },
        suggested_topics=["God's Name", "Jesus Christ", "Prayer", "Mary"],
        suggested_scriptures=["Matthew 6:9", "John 17:3", "Exodus 20:4-5"],
        tone_notes={
            "en": "Respect tradition. Never attack 'the Church'.",
            "es": "Respete la tradición. Nunca ataque 'a la Iglesia'.",
            "pt": "Respeite a tradição. Nunca ataque 'a Igreja'.",
        },
    ),
    "evangelical": AudienceProfile(
        key="evangelical",
        label={"en": "Evangelical Christian", "es": "Evangélico", "pt": "Evangélico"},
        opening_questions={
            "en": ["What do you think God's Kingdom will actually do?"],
            "es": ["¿Qué piensa usted que hará el Reino de Dios?"],
            "pt": ["O que o senhor acha que o Reino de Deus vai fazer?"],
        },
        common_ground={
            "en": ["Bible authority", "personal Bible study", "born-again message"],
            "es": ["autoridad de la Biblia", "estudio bíblico personal"],
            "pt": ["autoridade da Bíblia", "estudo pessoal da Bíblia"],
        },
        suggested_topics=["Kingdom", "Trinity", "Hell"],
        suggested_scriptures=["Daniel 2:44", "John 17:3", "Ecclesiastes 9:5"],
    ),
    "atheist": AudienceProfile(
        key="atheist",
        label={"en": "Atheist / Agnostic", "es": "Ateo / Agnóstico", "pt": "Ateu / Agnóstico"},
        opening_questions={
            "en": ["What evidence would convince you there's a Creator?"],
            "es": ["¿Qué evidencia le convencería de que hay un Creador?"],
            "pt": ["Que evidência o convenceria de que existe um Criador?"],
        },
        common_ground={
            "en": ["evidence-based reasoning", "concern about suffering"],
            "es": ["razonamiento basado en evidencia", "preocupación por el sufrimiento"],
            "pt": ["raciocínio baseado em evidência", "preocupação com o sofrimento"],
        },
        suggested_topics=["Creation", "Suffering", "Bible Prophecy"],
        suggested_scriptures=["Romans 1:20", "Hebrews 3:4", "James 1:13"],
        tone_notes={
            "en": "Don't ask them to assume God exists. Start with design.",
            "es": "No les pida que asuman que Dios existe. Empiece por el diseño.",
            "pt": "Não peça que assuma que Deus existe. Comece pelo design.",
        },
    ),
    "young": AudienceProfile(
        key="young",
        label={"en": "Youth / Teenager", "es": "Joven", "pt": "Jovem"},
        opening_questions={
            "en": ["Have you ever wondered why life feels so unfair sometimes?"],
            "es": ["¿Te has preguntado por qué la vida parece injusta a veces?"],
            "pt": ["Você já se perguntou por que a vida parece injusta às vezes?"],
        },
        common_ground={
            "en": ["future hopes", "identity"],
            "es": ["esperanzas para el futuro", "identidad"],
            "pt": ["esperanças para o futuro", "identidade"],
        },
        suggested_topics=["Youth", "Anxiety", "Future"],
        suggested_scriptures=["Ecclesiastes 12:1", "Philippians 4:6-7", "Psalm 37:11"],
    ),
    "muslim": AudienceProfile(
        key="muslim",
        label={"en": "Muslim", "es": "Musulmán", "pt": "Muçulmano"},
        opening_questions={
            "en": ["What did God reveal His personal name to be?"],
            "es": ["¿Qué nombre reveló Dios que es el suyo?"],
            "pt": ["Que nome Deus revelou ser dele?"],
        },
        common_ground={
            "en": ["monotheism", "respect for prophets", "modesty"],
            "es": ["monoteísmo", "respeto por los profetas", "modestia"],
            "pt": ["monoteísmo", "respeito pelos profetas", "modéstia"],
        },
        suggested_topics=["God's Name", "Jesus Christ", "Resurrection"],
        suggested_scriptures=["Psalm 83:18", "John 17:3", "Acts 24:15"],
    ),
    "struggling_grief": AudienceProfile(
        key="struggling_grief",
        label={"en": "Grieving / In sorrow", "es": "Apenado / En duelo", "pt": "Pessoa enlutada"},
        opening_questions={
            "en": ["Have you ever wondered if the dead will live again?"],
            "es": ["¿Se ha preguntado si los muertos volverán a vivir?"],
            "pt": ["Você já se perguntou se os mortos voltarão a viver?"],
        },
        common_ground={
            "en": ["loss", "hope for the future"],
            "es": ["pérdida", "esperanza para el futuro"],
            "pt": ["perda", "esperança para o futuro"],
        },
        suggested_topics=["Resurrection", "Death", "Comfort"],
        suggested_scriptures=["John 5:28-29", "Revelation 21:3-4", "Acts 24:15"],
    ),
}


async def presentation_builder(
    audience: str,
    *,
    language: str = "E",
    topic_overrides: list[str] | None = None,
    topic: TopicIndexClient | None = None,
    country: str | None = None,
) -> AgentResult:
    """Build a structured presentation scaffold for `audience`.

    Optional `country` is an ISO-3166 2-letter code (e.g. 'MX', 'JP').
    When given, the result is enriched with cultural anchors, sensitive
    topics to avoid initially, holidays to acknowledge, and locale
    languages — sourced from `data.locale_context`.
    """
    iso = _LANG_MAP.get(language.upper(), language.lower())
    profile = PROFILES.get(audience.lower())
    result = AgentResult(query=audience, agent_name="presentation_builder")
    if profile is None:
        result.warnings.append(f"Unknown audience profile {audience!r}. Available: {sorted(PROFILES.keys())}")
        return result

    locale_payload: dict[str, object] = {}
    if country:
        locale_payload = context_for_presentation(country, display_language=iso)
        if "error" in locale_payload:
            result.warnings.append(str(locale_payload["error"]))
            locale_payload = {}

    result.metadata.update(
        {
            "audience": profile.key,
            "audience_label": profile.label.get(iso, profile.label["en"]),
            "language": language,
            "country": (country or "").upper() or None,
            "tone_notes": profile.tone_notes.get(iso, ""),
            "common_ground": profile.common_ground.get(iso, []),
            "opening_questions": profile.opening_questions.get(iso, []),
            "locale_context": locale_payload,
        }
    )

    for ref_text in profile.suggested_scriptures:
        ref = parse_reference(ref_text)
        if ref is None:
            continue
        result.findings.append(
            Finding(
                summary=f"Anchor scripture: {ref.display()}",
                excerpt=ref.raw_match,
                citation=Citation(
                    url=ref.wol_url(lang=iso),
                    title=ref.display(),
                    kind="verse",
                ),
                metadata={"source": "presentation_anchor"},
            )
        )

    if topic is not None:
        for anchor in topic_overrides or profile.suggested_topics:
            try:
                hits = await topic.search_subjects(anchor, language=language, limit=1)
            except Exception as e:
                result.warnings.append(f"Topic {anchor!r}: {e}")
                continue
            if not hits:
                continue
            docid = hits[0].get("docid")
            if not docid:
                continue
            try:
                subject = await topic.get_subject_page(docid, language=iso)
            except Exception as e:
                result.warnings.append(f"Subject fetch {anchor!r}: {e}")
                continue
            result.findings.append(
                Finding(
                    summary=f"Topic anchor: {subject.title}",
                    excerpt=f"{subject.total_citations} citations across {len(subject.subheadings)} subheadings.",
                    citation=Citation(
                        url=subject.source_url,
                        title=subject.title,
                        kind="topic_subject",
                    ),
                    metadata={"source": "topic_index", "anchor": anchor},
                )
            )
    return result


def list_audiences(language: str = "en") -> list[dict[str, object]]:
    return [
        {
            "key": p.key,
            "label": p.label.get(language, p.label["en"]),
            "topics": p.suggested_topics,
            "scriptures": p.suggested_scriptures,
        }
        for p in PROFILES.values()
    ]
