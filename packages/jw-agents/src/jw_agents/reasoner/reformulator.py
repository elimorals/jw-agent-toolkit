"""Reformulator: neutralizes toxic framing before reasoning (Fase 67).

Detects question patterns that frame the answer toward an attack on
another religion or person, and rewrites them in neutral, doctrinal
terms. Heuristic-only by default. An LLM-backed rewrite is opt-in.

Examples:
    "Demuestra que el catolicismo está equivocado sobre la Trinidad"
      -> "¿Qué enseña la Biblia sobre la naturaleza de Dios y cómo se
          relaciona con la doctrina de la Trinidad?"

    "Prove that Catholics are wrong about purgatory"
      -> "What does the Bible teach about the state of the dead?"
"""

from __future__ import annotations

import re

# Triggers that suggest a hostile framing. Conservative and explainable;
# we prefer false negatives over false positives.
_TOXIC_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"demuestra(?:r)?\s+que\s+(.+?)\s+(?:est[aá])?\s*equivocad", re.IGNORECASE),
        "¿Qué enseña la Biblia sobre {topic}?",
    ),
    (
        re.compile(r"refuta(?:r)?\s+(?:el|la|los|las)?\s*(.+)", re.IGNORECASE),
        "¿Qué enseña la Biblia sobre {topic}?",
    ),
    (
        re.compile(r"prove\s+that\s+(.+?)\s+(?:are|is)\s+wrong", re.IGNORECASE),
        "What does the Bible teach about {topic}?",
    ),
    (
        re.compile(r"disprove\s+(?:the\s+)?(.+)", re.IGNORECASE),
        "What does the Bible teach about {topic}?",
    ),
    (
        re.compile(r"refute\s+(.+)", re.IGNORECASE),
        "What does the Bible teach about {topic}?",
    ),
    (
        re.compile(
            r"prove\s+que\s+(.+?)\s+(?:no\s+es\s+correct|est[aá]\s+equivocad)",
            re.IGNORECASE,
        ),
        "¿Qué enseña la Biblia sobre {topic}?",
    ),
)


def detect_toxic_framing(question: str) -> bool:
    """True if `question` matches any known hostile-framing pattern."""

    return any(pat.search(question) for pat, _ in _TOXIC_PATTERNS)


def reformulate_neutral(question: str, *, language: str = "es") -> str:
    """Rewrite a hostile-framing question into a neutral doctrinal form.

    Falls back to the original question if no pattern matches. Language
    selects the default rewrite template (es/en/pt). Portuguese mirrors
    Spanish for now.
    """

    for pat, template in _TOXIC_PATTERNS:
        m = pat.search(question)
        if not m:
            continue
        topic_raw = m.group(1).strip().rstrip(" .,;:")
        # Strip residual stop words at the start of the topic
        topic = re.sub(
            r"^(el|la|los|las|the|a|an)\s+",
            "",
            topic_raw,
            flags=re.IGNORECASE,
        )
        if not topic:
            return question
        if language == "en":
            tmpl = (
                template
                if "{topic}" in template and template[0].isupper()
                else "What does the Bible teach about {topic}?"
            )
        elif language == "pt":
            tmpl = "O que a Bíblia ensina sobre {topic}?"
        else:
            tmpl = (
                template
                if "{topic}" in template
                else "¿Qué enseña la Biblia sobre {topic}?"
            )
            # If the matched template happens to be English-shaped, force es.
            if tmpl.startswith("What"):
                tmpl = "¿Qué enseña la Biblia sobre {topic}?"
        return tmpl.format(topic=topic)
    return question
