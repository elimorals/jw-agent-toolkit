"""Heuristic JW-terminology evaluator.

Two scoring modes:
  * `score_terminology(answers, language)` — fraction of answers
    containing at least ONE term (binary per-answer, kept for back-compat).
  * `score_terminology_proportional(answers, language)` — average count
    of UNIQUE terms found per answer, normalized to [0, 1] by a soft cap.
    This reflects depth of vocabulary, not just presence.

Term sets cover 10 Tier 1 languages (es, en, pt, fr, de, it, ru, ja, ko, zh).
Terms come from the canonical JW vocabulary; you can extend any set by
appending to `TERMINOLOGY_SETS[lang]`.

Optionally, `score_terminology` accepts a `terms` override so callers can
inject a vocabulary mined from the Watch Tower topic index (see
`jw_finetune.data.jw_extractors.build_terminology_set_from_topic_index`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Curated minimal vocabulary per language. NOT exhaustive doctrine; just
# enough markers to distinguish JW voice from generic Christian.
TERMINOLOGY_SETS: dict[str, set[str]] = {
    "es": {
        "jehová",
        "reino",
        "publicador",
        "anciano",
        "atalaya",
        "testificación",
        "predicación",
        "soberanía",
        "ungidos",
        "salón del reino",
        "estudio bíblico",
        "memorial",
        "asamblea",
        "betel",
        "ministerio",
        "espíritu santo",
        "siglo i",
        "principio",
        "celosos",
        "edificantes",
    },
    "en": {
        "jehovah",
        "kingdom",
        "publisher",
        "elder",
        "watchtower",
        "witnessing",
        "preaching",
        "sovereignty",
        "anointed",
        "kingdom hall",
        "bible study",
        "memorial",
        "assembly",
        "bethel",
        "ministry",
        "holy spirit",
        "first century",
        "principle",
        "zealous",
        "upbuilding",
    },
    "pt": {
        "jeová",
        "reino",
        "publicador",
        "ancião",
        "atalaia",
        "testemunho",
        "pregação",
        "soberania",
        "ungidos",
        "salão do reino",
        "estudo bíblico",
        "celebração",
        "assembleia",
        "betel",
        "ministério",
        "espírito santo",
    },
    "fr": {
        "jéhovah",
        "royaume",
        "proclamateur",
        "ancien",
        "tour de garde",
        "prédication",
        "souveraineté",
        "oints",
        "salle du royaume",
        "étude biblique",
        "mémorial",
        "assemblée",
        "béthel",
        "ministère",
        "esprit saint",
    },
    "de": {
        "jehova",
        "königreich",
        "verkündiger",
        "ältester",
        "wachtturm",
        "verkündigung",
        "souveränität",
        "gesalbte",
        "königreichssaal",
        "bibelstudium",
        "gedenkmahl",
        "kongress",
        "bethel",
        "dienst",
        "heiliger geist",
    },
    "it": {
        "geova",
        "regno",
        "proclamatore",
        "anziano",
        "torre di guardia",
        "predicazione",
        "sovranità",
        "unti",
        "sala del regno",
        "studio biblico",
        "commemorazione",
        "assemblea",
        "betel",
        "ministero",
        "spirito santo",
    },
    "ru": {
        "иегова",
        "царство",
        "возвещатель",
        "старейшина",
        "сторожевая башня",
        "проповедь",
        "помазанник",
        "помазанные",
        "зал царства",
        "изучение библии",
        "вечеря",
        "конгресс",
        "вефиль",
        "служение",
        "святой дух",
    },
    "ja": {
        "エホバ",
        "王国",
        "伝道者",
        "長老",
        "ものみの塔",
        "宣教",
        "主権",
        "油そそがれた",
        "王国会館",
        "聖書研究",
        "記念式",
        "大会",
        "ベテル",
        "聖霊",
    },
    "ko": {
        "여호와",
        "왕국",
        "전도인",
        "장로",
        "파수대",
        "전도",
        "주권",
        "기름부음받은",
        "왕국회관",
        "성서연구",
        "기념식",
        "대회",
        "베델",
        "성령",
    },
    "zh": {
        "耶和华",
        "王国",
        "传道员",
        "长老",
        "守望台",
        "传道",
        "主权",
        "受膏者",
        "王国聚会所",
        "圣经研究",
        "纪念聚会",
        "大会",
        "伯特利",
        "圣灵",
    },
}


def _terms_for(language: str, override: set[str] | None) -> set[str]:
    if override is not None:
        return override
    return TERMINOLOGY_SETS.get(language[:2].lower(), set())


def score_terminology(
    answers: Iterable[str],
    *,
    language: str = "es",
    terms: set[str] | None = None,
) -> float:
    """Fraction of answers including >=1 JW-specific term."""
    answers_list = list(answers)
    if not answers_list:
        return 0.0
    use_terms = _terms_for(language, terms)
    if not use_terms:
        return 0.0
    hits = 0
    for a in answers_list:
        low = a.lower()
        if any(re.search(rf"\b{re.escape(t)}\b", low) for t in use_terms):
            hits += 1
    return hits / len(answers_list)


def score_terminology_proportional(
    answers: Iterable[str],
    *,
    language: str = "es",
    terms: set[str] | None = None,
    soft_cap: int = 4,
) -> float:
    """Average UNIQUE term count per answer, normalized by `soft_cap`.

    An answer using 4+ different JW terms scores 1.0; using 0 scores 0.0;
    in between scales linearly. This rewards depth, not just presence.
    """
    answers_list = list(answers)
    if not answers_list:
        return 0.0
    use_terms = _terms_for(language, terms)
    if not use_terms:
        return 0.0
    soft_cap = max(1, soft_cap)
    total = 0.0
    for a in answers_list:
        low = a.lower()
        unique_hits = sum(1 for t in use_terms if re.search(rf"\b{re.escape(t)}\b", low))
        total += min(unique_hits / soft_cap, 1.0)
    return total / len(answers_list)
