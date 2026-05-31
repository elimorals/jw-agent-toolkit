"""Procedural templates for `study_conductor` anticipation questions.

Templates are intentionally simple: the agent picks a template per
paragraph and substitutes `n` (paragraph number) and optionally `ref`
(a scripture reference). NO LLM is involved.

CRISIS_KEYWORDS scans user notes locally and surfaces a warning if a
match is found — the agent never blocks the save; it just adds a hint
in the AgentResult.warnings.
"""

from __future__ import annotations

from typing import Any

ANTICIPATION_TEMPLATES: dict[str, dict[str, str]] = {
    "es": {
        "fact": "¿Qué punto principal enseña el párrafo {n}?",
        "application": "¿Cómo aplicaría usted personalmente lo del párrafo {n}?",
        "scripture": "Lea {ref}. ¿Cómo apoya esto la idea del párrafo {n}?",
        "feeling": "¿Cómo se siente respecto a lo que dice el párrafo {n}?",
    },
    "en": {
        "fact": "What main point does paragraph {n} teach?",
        "application": "How would you personally apply paragraph {n}?",
        "scripture": "Read {ref}. How does it support the idea in paragraph {n}?",
        "feeling": "How do you feel about what paragraph {n} says?",
    },
    "pt": {
        "fact": "Qual é o ponto principal do parágrafo {n}?",
        "application": "Como você aplicaria pessoalmente o parágrafo {n}?",
        "scripture": "Leia {ref}. Como isso apoia a ideia do parágrafo {n}?",
        "feeling": "Como você se sente sobre o que o parágrafo {n} diz?",
    },
}

CRISIS_KEYWORDS: dict[str, list[str]] = {
    "es": ["suicidio", "abuso", "violencia", "me quiero morir", "autolesión"],
    "en": ["suicide", "abuse", "violence", "want to die", "self-harm"],
    "pt": ["suicídio", "abuso", "violência", "quero morrer", "automutilação"],
}


def render_template(language: str, kind: str, **kwargs: Any) -> str:
    """Render an anticipation template; fall back to English if `language` unknown."""

    lang_templates = ANTICIPATION_TEMPLATES.get(language) or ANTICIPATION_TEMPLATES["en"]
    template = lang_templates[kind]  # raises KeyError if `kind` unknown — by design
    return template.format(**kwargs)


def scan_for_crisis(text: str, *, language: str) -> list[str]:
    """Return crisis keywords found in `text`. Empty list when none."""

    if not text:
        return []
    haystack = text.lower()
    needles = CRISIS_KEYWORDS.get(language) or CRISIS_KEYWORDS["en"]
    return [kw for kw in needles if kw in haystack]
