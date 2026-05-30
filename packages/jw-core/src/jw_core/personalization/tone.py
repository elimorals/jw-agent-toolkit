"""Tone adjustment helpers.

VISION.md: "Tono ajustable: respetuoso/formal vs casual para diferentes contextos".

We don't rewrite prose ourselves — we provide a SYSTEM prompt scaffold the
LLM (Claude/Ollama) can use to shape its output. The toolkit guarantees
the citations and structure; the LLM owns the tone.
"""

from __future__ import annotations

TONE_TEMPLATES: dict[str, dict[str, str]] = {
    "formal": {
        "en": "Use respectful, formal English. Address the reader as 'you'. Cite every claim.",
        "es": "Use un español formal y respetuoso. Trate al lector de 'usted'. Cite cada afirmación.",
        "pt": "Use português formal e respeitoso. Trate o leitor de 'você'. Cite cada afirmação.",
    },
    "casual": {
        "en": "Use friendly, casual English. Short sentences. Keep citations but make them flow.",
        "es": "Use un español cercano y casual. Frases cortas. Mantenga las citas integradas.",
        "pt": "Use português próximo e casual. Frases curtas. Mantenha as citações no texto.",
    },
    "easy_read": {
        "en": "Use plain English. Sentences under 15 words. Avoid jargon. One idea per sentence.",
        "es": "Use español sencillo. Frases de menos de 15 palabras. Sin tecnicismos.",
        "pt": "Use português simples. Frases com menos de 15 palavras. Sem jargão.",
    },
}


def adjust_tone(text: str, *, target_tone: str, language: str = "en") -> str:
    """Return a system-prompt suffix that the LLM uses to reshape `text`.

    The function itself does NOT rewrite — it returns a directive the LLM
    appends to its system prompt. Keeps responsibility clear: the LLM
    rephrases, the toolkit guarantees the source.
    """
    template = TONE_TEMPLATES.get(target_tone, TONE_TEMPLATES["formal"]).get(language, "")
    return (
        f"<<TONE_DIRECTIVE>>\n{template}\n"
        f"Rewrite the following while preserving every URL and reference verbatim:\n\n{text}"
    )
