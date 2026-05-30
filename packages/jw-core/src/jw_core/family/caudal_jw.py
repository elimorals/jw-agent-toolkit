"""'Caudal jw' / 'Caleb and Sophia' catalog of children's content.

VISION.md Module 5 / Gap 11: ship resources for the `Caleb and Sophia`
series (a.k.a. `Caudal jw` in some communities — the children's video
series and matching activity sheets).

The series is hosted under the `BJF` (Become Jehovah's Friend) category
on JW Broadcasting. Each episode pairs with a worksheet and a story.

This catalog is the bridge between the curated lesson topics and the
JW Broadcasting client (Module 3): for each lesson we know the video
key, the worksheet URL pattern, and the age band.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaudalResource:
    key: str
    title: dict[str, str]
    topic: str
    age_band: str = "younger"  # younger / middle
    bjf_video_key: str = ""  # naturalKey of the Caleb-and-Sophia video
    activity_url: dict[str, str] = field(default_factory=dict)
    scripture_anchors: tuple[str, ...] = ()


# Hand-curated, public-information catalog. Update when JW publishes
# new lessons.
CAUDAL_LESSONS: list[CaudalResource] = [
    CaudalResource(
        key="obey_parents",
        title={
            "en": "Obey Your Parents",
            "es": "Obedece a tus padres",
            "pt": "Obedeça aos pais",
        },
        topic="obedience",
        bjf_video_key="ljf_E_001",
        activity_url={
            "en": "https://www.jw.org/en/library/children/become-jehovahs-friend/activities/obey-your-parents/",
            "es": "https://www.jw.org/es/biblioteca/ninos/se-amigo-de-jehova/actividades/obedece-a-tus-padres/",
        },
        scripture_anchors=("Ephesians 6:1", "Colossians 3:20"),
    ),
    CaudalResource(
        key="tell_truth",
        title={
            "en": "Always Tell the Truth",
            "es": "Di siempre la verdad",
            "pt": "Sempre fale a verdade",
        },
        topic="truth",
        bjf_video_key="ljf_E_002",
        activity_url={
            "en": "https://www.jw.org/en/library/children/become-jehovahs-friend/activities/always-tell-the-truth/",
            "es": "https://www.jw.org/es/biblioteca/ninos/se-amigo-de-jehova/actividades/di-siempre-la-verdad/",
        },
        scripture_anchors=("Ephesians 4:25", "Proverbs 12:22"),
    ),
    CaudalResource(
        key="be_kind",
        title={"en": "Be Kind", "es": "Sé amable", "pt": "Seja gentil"},
        topic="kindness",
        bjf_video_key="ljf_E_005",
        scripture_anchors=("Ephesians 4:32",),
    ),
    CaudalResource(
        key="share",
        title={"en": "Share With Others", "es": "Comparte con los demás", "pt": "Compartilhe com os outros"},
        topic="generosity",
        bjf_video_key="ljf_E_006",
        scripture_anchors=("Hebrews 13:16",),
    ),
    CaudalResource(
        key="dont_be_jealous",
        title={"en": "Don't Be Jealous", "es": "No tengas envidia", "pt": "Não fique com inveja"},
        topic="contentment",
        bjf_video_key="ljf_E_011",
        scripture_anchors=("Galatians 5:26",),
    ),
    CaudalResource(
        key="forgive",
        title={"en": "Forgive Others", "es": "Perdona a los demás", "pt": "Perdoe os outros"},
        topic="forgiveness",
        bjf_video_key="ljf_E_007",
        scripture_anchors=("Colossians 3:13",),
    ),
    CaudalResource(
        key="pray_to_jehovah",
        title={"en": "Pray to Jehovah", "es": "Ora a Jehová", "pt": "Ore a Jeová"},
        topic="prayer",
        bjf_video_key="ljf_E_009",
        scripture_anchors=("Philippians 4:6", "1 Thessalonians 5:17"),
    ),
    CaudalResource(
        key="respect_meetings",
        title={
            "en": "Behave at the Meetings",
            "es": "Compórtate bien en las reuniones",
            "pt": "Comporte-se nas reuniões",
        },
        topic="meetings",
        bjf_video_key="ljf_E_004",
        scripture_anchors=("Hebrews 10:24-25",),
    ),
    CaudalResource(
        key="be_patient",
        title={"en": "Be Patient", "es": "Sé paciente", "pt": "Seja paciente"},
        topic="patience",
        bjf_video_key="ljf_E_016",
        scripture_anchors=("James 1:19",),
    ),
    CaudalResource(
        key="help_others",
        title={
            "en": "Help Others — Joash and Jehoiada",
            "es": "Ayuda a otros — Joás y Joiada",
            "pt": "Ajude os outros — Joás e Joiada",
        },
        topic="service",
        bjf_video_key="ljf_E_022",
        age_band="middle",
        scripture_anchors=("Galatians 6:2",),
    ),
]


def list_caudal_lessons(language: str = "en", *, age_band: str | None = None) -> list[dict[str, object]]:
    items = []
    for c in CAUDAL_LESSONS:
        if age_band and c.age_band != age_band:
            continue
        items.append(
            {
                "key": c.key,
                "title": c.title.get(language, c.title["en"]),
                "topic": c.topic,
                "age_band": c.age_band,
                "bjf_video_key": c.bjf_video_key,
                "activity_url": c.activity_url.get(language, c.activity_url.get("en", "")),
                "scripture_anchors": list(c.scripture_anchors),
            }
        )
    return items


def pick_caudal_by_topic(topic: str, language: str = "en") -> dict[str, object] | None:
    for c in CAUDAL_LESSONS:
        if c.topic.lower() == topic.lower():
            return list_caudal_lessons(language=language)[CAUDAL_LESSONS.index(c)]
    return None
