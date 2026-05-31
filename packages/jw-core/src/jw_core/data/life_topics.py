"""Vocabulario controlado de temas de vida para el agente `life_topics`.

Tres familias de datos puros, sin red ni LLM:

  LifeTopic           dataclass frozen
  REGISTRY            list[LifeTopic] — 9 temas iniciales
  resolve_topic(...)  alias-aware lookup en es/en/pt + fallback cross-lang

Esta tabla es deliberadamente conservadora. Cada tema añadido debe
considerarse caso por caso — los temas marcados `family='sensitive'`
disparan automáticamente el redirect a ancianos en el agente, así que
añadir uno "general" cuando debería ser sensible es un riesgo pastoral.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Literal

LifeTopicFamily = Literal["sensitive", "general"]


@dataclass(frozen=True)
class LifeTopic:
    topic_id: str
    family: LifeTopicFamily
    labels: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, list[str]] = field(default_factory=dict)
    topic_anchors: list[str] = field(default_factory=list)
    search_query: str = ""


def _strip(s: str) -> str:
    """Lowercase + strip accents, for fuzzy matching."""
    nf = unicodedata.normalize("NFD", s)
    return "".join(c for c in nf if unicodedata.category(c) != "Mn").lower().strip()


REGISTRY: list[LifeTopic] = [
    LifeTopic(
        topic_id="anxiety",
        family="sensitive",
        labels={"en": "Anxiety", "es": "Ansiedad", "pt": "Ansiedade"},
        aliases={
            "en": ["anxiety", "worry", "stress", "fear", "anxious"],
            "es": ["ansiedad", "preocupacion", "estres", "miedo", "nervios"],
            "pt": ["ansiedade", "preocupacao", "estresse", "medo"],
        },
        topic_anchors=["Anxiety", "Worry"],
        search_query="anxiety overcome",
    ),
    LifeTopic(
        topic_id="grief",
        family="sensitive",
        labels={"en": "Grief", "es": "Duelo", "pt": "Luto"},
        aliases={
            "en": ["grief", "loss", "death of a loved one", "mourning", "bereavement"],
            "es": ["duelo", "perdida", "muerte de un ser querido", "luto"],
            "pt": ["luto", "perda", "morte de um ente querido"],
        },
        topic_anchors=["Death", "Resurrection", "Comfort"],
        search_query="death of a loved one comfort",
    ),
    LifeTopic(
        topic_id="marriage_conflict",
        family="sensitive",
        labels={
            "en": "Marriage conflict",
            "es": "Conflicto matrimonial",
            "pt": "Conflito conjugal",
        },
        aliases={
            "en": ["marriage conflict", "arguing with spouse", "marriage problem"],
            "es": ["conflicto matrimonial", "problemas de pareja", "discusiones con conyuge"],
            "pt": ["conflito conjugal", "problemas no casamento"],
        },
        topic_anchors=["Marriage", "Husband", "Wife"],
        search_query="marriage problems peace",
    ),
    LifeTopic(
        topic_id="depression_signs",
        family="sensitive",
        labels={"en": "Depression", "es": "Depresión", "pt": "Depressão"},
        aliases={
            "en": ["depression", "sadness", "hopelessness", "down"],
            "es": ["depresion", "tristeza profunda", "desesperanza"],
            "pt": ["depressao", "tristeza profunda", "desesperanca"],
        },
        topic_anchors=["Depression", "Discouragement"],
        search_query="depression discouragement encouragement",
    ),
    LifeTopic(
        topic_id="addictions",
        family="sensitive",
        labels={"en": "Addictions", "es": "Adicciones", "pt": "Vícios"},
        aliases={
            "en": ["addiction", "addictions", "habit", "smoking", "alcohol", "drugs"],
            "es": ["adicciones", "adiccion", "vicio", "tabaco", "alcohol", "drogas"],
            "pt": ["vicios", "vicio", "habito", "fumo", "alcool", "drogas"],
        },
        topic_anchors=["Habits", "Self-Control"],
        search_query="overcoming bad habits",
    ),
    LifeTopic(
        topic_id="doubts_in_faith",
        family="sensitive",
        labels={
            "en": "Doubts in faith",
            "es": "Dudas en la fe",
            "pt": "Dúvidas na fé",
        },
        aliases={
            "en": ["doubt", "doubts", "doubting", "weak faith", "lost faith"],
            "es": ["dudas", "dudo", "fe debil", "perdi la fe"],
            "pt": ["duvidas", "duvido", "fe fraca", "perdi a fe"],
        },
        topic_anchors=["Faith", "Trust in God"],
        search_query="strengthen your faith",
    ),
    LifeTopic(
        topic_id="parenting",
        family="general",
        labels={
            "en": "Parenting",
            "es": "Crianza de los hijos",
            "pt": "Criação dos filhos",
        },
        aliases={
            "en": ["parenting", "raising children", "discipline kids", "teen"],
            "es": ["crianza", "educar a los hijos", "disciplina", "adolescentes"],
            "pt": ["criacao", "educar os filhos", "disciplina", "adolescentes"],
        },
        topic_anchors=["Children", "Family"],
        search_query="raising children family",
    ),
    LifeTopic(
        topic_id="loneliness",
        family="general",
        labels={"en": "Loneliness", "es": "Soledad", "pt": "Solidão"},
        aliases={
            "en": ["loneliness", "lonely", "alone", "isolation"],
            "es": ["soledad", "solo", "sola", "aislamiento"],
            "pt": ["solidao", "sozinho", "isolamento"],
        },
        topic_anchors=["Friendship", "Loneliness"],
        search_query="loneliness friendship",
    ),
    LifeTopic(
        topic_id="conflict_with_brother",
        family="general",
        labels={
            "en": "Conflict with a brother",
            "es": "Conflicto con un hermano",
            "pt": "Conflito com um irmão",
        },
        aliases={
            "en": ["conflict with a brother", "argument with brother", "offended by brother"],
            "es": ["conflicto con un hermano", "ofensa de un hermano", "discusion con hermano"],
            "pt": ["conflito com um irmao", "ofensa de um irmao"],
        },
        topic_anchors=["Forgiveness", "Peace"],
        search_query="forgive a brother reconcile",
    ),
]


def resolve_topic(query: str, language: str = "en") -> LifeTopic | None:
    """Map a free-form `query` to a canonical LifeTopic, alias-aware.

    Order:
      1. Match against `aliases[language]` (accent-insensitive, lowercased).
      2. Match against `labels[language]`.
      3. Cross-language fallback: try every alias list.

    Returns `None` if nothing matches — the agent then emits a generic
    disclaimer and no redirect (we don't know whether the topic is
    sensitive, so we don't presume).
    """
    normalized = _strip(query)
    if not normalized:
        return None

    for topic in REGISTRY:
        for alias in topic.aliases.get(language, []):
            if _strip(alias) == normalized:
                return topic
        label = topic.labels.get(language, "")
        if label and _strip(label) == normalized:
            return topic

    # Cross-language fallback.
    for topic in REGISTRY:
        for lang_aliases in topic.aliases.values():
            for alias in lang_aliases:
                if _strip(alias) == normalized:
                    return topic
        for label in topic.labels.values():
            if _strip(label) == normalized:
                return topic

    return None
