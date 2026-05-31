"""Catalog of common objections raised during conversations.

Each entry pairs a normalized objection key with:
  - localized labels (en/es/pt)
  - keywords for fuzzy matching
  - a list of anchor topics (used to call into the Watch Tower Publications
    Index — the AUTHORITATIVE source)
  - a list of anchor Bible references that always apply

The catalog is data — it intentionally does NOT carry prose responses.
Prose is composed by the `apologetics` agent (or your LLM) from the
authoritative anchors. This keeps doctrine current as JW updates its
material; we never hard-code answers that would rot.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Objection:
    key: str
    labels: dict[str, str]
    keywords: dict[str, list[str]]
    topic_anchors: list[str] = field(default_factory=list)
    scripture_anchors: list[str] = field(default_factory=list)
    category: str = "doctrine"

    def label(self, language: str = "en") -> str:
        return self.labels.get(language, self.labels.get("en", self.key))


CATALOG: list[Objection] = [
    Objection(
        key="trinity",
        labels={
            "en": "Why don't you believe in the Trinity?",
            "es": "¿Por qué no creen en la Trinidad?",
            "pt": "Por que vocês não acreditam na Trindade?",
        },
        keywords={
            "en": ["trinity", "three persons", "godhead", "triune", "jesus is god"],
            "es": ["trinidad", "tres personas", "deidad", "jesús es dios"],
            "pt": ["trindade", "três pessoas", "deidade", "jesus é deus"],
        },
        topic_anchors=["Trinity", "Jesus Christ", "Holy Spirit"],
        scripture_anchors=["John 17:3", "1 Corinthians 8:6", "Deuteronomy 6:4"],
    ),
    Objection(
        key="hell",
        labels={
            "en": "Doesn't the Bible teach an eternal hellfire?",
            "es": "¿No enseña la Biblia un infierno de fuego eterno?",
            "pt": "A Bíblia não ensina um inferno de fogo eterno?",
        },
        keywords={
            "en": ["hell", "eternal torment", "lake of fire", "burn forever"],
            "es": ["infierno", "fuego eterno", "tormento", "lago de fuego"],
            "pt": ["inferno", "fogo eterno", "tormento", "lago de fogo"],
        },
        topic_anchors=["Hell", "Soul", "Death"],
        scripture_anchors=["Ecclesiastes 9:5", "Romans 6:23", "Ezekiel 18:4"],
    ),
    Objection(
        key="soul_immortal",
        labels={
            "en": "Doesn't the soul live on after death?",
            "es": "¿No es inmortal el alma humana?",
            "pt": "A alma humana não é imortal?",
        },
        keywords={
            "en": ["immortal soul", "soul lives", "after death", "spirit returns"],
            "es": ["alma inmortal", "vida después", "espíritu vuelve"],
            "pt": ["alma imortal", "vida após", "espírito retorna"],
        },
        topic_anchors=["Soul", "Death", "Resurrection"],
        scripture_anchors=["Genesis 2:7", "Ezekiel 18:4", "Ecclesiastes 9:5"],
    ),
    Objection(
        key="cross",
        labels={
            "en": "Why don't you use the cross as a symbol?",
            "es": "¿Por qué no usan la cruz como símbolo?",
            "pt": "Por que vocês não usam a cruz como símbolo?",
        },
        keywords={
            "en": ["cross", "crucifix", "christ died on a cross"],
            "es": ["cruz", "crucifijo", "murió en una cruz"],
            "pt": ["cruz", "crucifixo", "morreu numa cruz"],
        },
        topic_anchors=["Cross"],
        scripture_anchors=["Acts 5:30", "Galatians 3:13", "1 Peter 2:24"],
    ),
    Objection(
        key="blood",
        labels={
            "en": "Why do you refuse blood transfusions?",
            "es": "¿Por qué rechazan las transfusiones de sangre?",
            "pt": "Por que vocês recusam transfusões de sangue?",
        },
        keywords={
            "en": ["blood transfusion", "blood", "refuse blood"],
            "es": ["transfusión", "sangre", "rechazan sangre"],
            "pt": ["transfusão", "sangue", "recusam sangue"],
        },
        topic_anchors=["Blood"],
        scripture_anchors=["Acts 15:28-29", "Genesis 9:4", "Leviticus 17:11"],
    ),
    Objection(
        key="contradictions",
        labels={
            "en": "Doesn't the Bible contradict itself?",
            "es": "¿La Biblia no se contradice?",
            "pt": "A Bíblia não se contradiz?",
        },
        keywords={
            "en": ["contradiction", "contradicts", "bible errors", "discrepancy"],
            "es": ["contradicción", "se contradice", "errores", "discrepancia"],
            "pt": ["contradição", "contradiz", "erros", "discrepância"],
        },
        topic_anchors=["Bible", "Apparent Contradictions"],
        scripture_anchors=["2 Timothy 3:16", "John 17:17"],
        category="bible_reliability",
    ),
    Objection(
        key="why_suffering",
        labels={
            "en": "If God exists, why is there so much suffering?",
            "es": "Si Dios existe, ¿por qué hay tanto sufrimiento?",
            "pt": "Se Deus existe, por que há tanto sofrimento?",
        },
        keywords={
            "en": ["why suffering", "evil exist", "if god is good", "pain"],
            "es": ["sufrimiento", "maldad", "dolor", "por qué dios"],
            "pt": ["sofrimento", "maldade", "dor", "por que deus"],
        },
        topic_anchors=["Suffering", "Sovereignty", "Issue Raised"],
        scripture_anchors=["Job 1:9-11", "James 1:13", "Romans 5:12"],
        category="philosophical",
    ),
    Objection(
        key="last_days",
        labels={
            "en": "Isn't it arrogant to say we live in the 'last days'?",
            "es": "¿No es presuntuoso decir que vivimos en los 'últimos días'?",
            "pt": "Não é arrogância dizer que vivemos nos 'últimos dias'?",
        },
        keywords={
            "en": ["last days", "end of the world", "armageddon"],
            "es": ["últimos días", "fin del mundo", "armagedón"],
            "pt": ["últimos dias", "fim do mundo", "armagedom"],
        },
        topic_anchors=["Last Days", "Sign of the Last Days"],
        scripture_anchors=["Matthew 24:3-14", "2 Timothy 3:1-5", "Luke 21:10-11"],
    ),
    Objection(
        key="kingdom_1914",
        labels={
            "en": "Why do Jehovah's Witnesses talk about the year 1914?",
            "es": "¿Por qué los Testigos hablan del año 1914?",
            "pt": "Por que as Testemunhas falam do ano 1914?",
        },
        keywords={
            "en": ["1914", "kingdom established", "seven times"],
            "es": ["1914", "reino establecido", "siete tiempos"],
            "pt": ["1914", "reino estabelecido", "sete tempos"],
        },
        topic_anchors=["1914", "Kingdom"],
        scripture_anchors=["Daniel 4:16", "Luke 21:24", "Matthew 24:7"],
    ),
]


def find_objection(text: str, *, language: str = "en") -> Objection | None:
    """Best-effort fuzzy match of `text` against the catalog.

    Lowercases and substring-matches against each entry's keywords for
    the requested language; falls back to English keywords.
    """
    lowered = text.lower()
    best: tuple[int, Objection] | None = None
    for entry in CATALOG:
        score = _score(entry, lowered, language)
        if score == 0:
            continue
        if best is None or score > best[0]:
            best = (score, entry)
    return best[1] if best else None


def _score(entry: Objection, text: str, language: str) -> int:
    keywords = entry.keywords.get(language, entry.keywords.get("en", []))
    score = 0
    for kw in keywords:
        if kw.lower() in text:
            # Longer keywords are more specific; weight them higher.
            score += max(1, len(kw.split()))
    return score


def list_objections(language: str = "en") -> list[dict[str, object]]:
    return [
        {
            "key": e.key,
            "label": e.label(language),
            "category": e.category,
            "topic_anchors": e.topic_anchors,
            "scripture_anchors": e.scripture_anchors,
        }
        for e in CATALOG
    ]
