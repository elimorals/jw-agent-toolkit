"""Bilingual disclaimer + elders-redirect text for the `life_topics` agent.

These strings are part of the agent's contract — every AgentResult of
`life_topics` includes at least the disclaimer. Sensitive topics also
include the elders redirect.

Pastoral boundary: the redirect intentionally does NOT name medical
professionals (therapists, doctors). The agent stays inside the
spiritual chain (family, elders). This is a design commitment, not an
oversight — see spec, section "Disclaimers and pastoral boundary".
"""

from __future__ import annotations

from typing import Literal

LifeTopicFamily = Literal["sensitive", "general"]


DISCLAIMERS: dict[tuple[str, str], str] = {
    ("general", "en"): (
        "This information is published material from the Watchtower. "
        "It is not personal counseling. For your specific situation, "
        "speak with your family and the elders of your congregation."
    ),
    ("general", "es"): (
        "Esta es información publicada por la Watchtower. No es consejería "
        "personal. Para tu situación específica, conversa con tu familia y con "
        "los ancianos de tu congregación."
    ),
    ("general", "pt"): (
        "Estas são informações publicadas pela Sociedade Torre de Vigia. "
        "Não é aconselhamento pessoal. Para a sua situação específica, "
        "converse com a sua família e com os anciãos da sua congregação."
    ),
}
# Sensitive topics share the same disclaimer prose; what changes is that
# the agent ALSO emits an elders_redirect Finding for them.
DISCLAIMERS[("sensitive", "en")] = DISCLAIMERS[("general", "en")]
DISCLAIMERS[("sensitive", "es")] = DISCLAIMERS[("general", "es")]
DISCLAIMERS[("sensitive", "pt")] = DISCLAIMERS[("general", "pt")]


ELDERS_REDIRECTS: dict[str, str] = {
    "en": (
        "If what you are going through is difficult, you are not alone. "
        "The elders of your congregation are willing to help (1 Peter 5:1-3) "
        "and your family can pray with you. This page is only published information."
    ),
    "es": (
        "Si lo que vives ahora es difícil, no estás solo. Los ancianos de "
        "tu congregación están dispuestos a ayudarte (1 Pedro 5:1-3) y "
        "tu familia puede orar contigo. Esta página es solo información publicada."
    ),
    "pt": (
        "Se o que você está vivendo agora é difícil, você não está só. "
        "Os anciãos da sua congregação estão dispostos a ajudar (1 Pedro 5:1-3) "
        "e a sua família pode orar com você. Esta página é apenas informação publicada."
    ),
}


def get_disclaimer(family: LifeTopicFamily | str, language: str) -> str:
    """Lookup the disclaimer for (family, language), falling back to (general, en)."""
    key = (family if family in {"general", "sensitive"} else "general", language)
    if key in DISCLAIMERS:
        return DISCLAIMERS[key]
    return (
        DISCLAIMERS[(key[0], "en")]
        if (key[0], "en") in DISCLAIMERS
        else DISCLAIMERS[("general", "en")]
    )


def get_elders_redirect(language: str) -> str:
    """Return the elders-redirect text, falling back to English on unknown lang."""
    return ELDERS_REDIRECTS.get(language, ELDERS_REDIRECTS["en"])
