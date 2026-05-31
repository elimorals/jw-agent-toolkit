"""Grammar fragment that constrains citation URLs to https://wol.jw.org/.

Kept separate so the regex and the GBNF rule stay in lock-step. Both
fall back to a single Python-level regex (`CITATION_URL_REGEX`).
"""

from __future__ import annotations

import re

# Single source of truth — re-exported from schemas for backward compat.
CITATION_URL_REGEX = r"^https://wol\.jw\.org/[a-z]{2,3}/.+"


def citation_url_grammar() -> str:
    """Return the GBNF fragment that defines the `citation-url` rule.

    Rule shape (informal):
        citation-url ::= "\\"" "https://wol.jw.org/" lang "/" rest "\\""
        lang         ::= [a-z] [a-z] [a-z]?
        rest         ::= [-A-Za-z0-9_/.%]+
    """

    return (
        'citation-url ::= "\\"" "https://wol.jw.org/" lang "/" rest "\\""\n'
        "lang ::= [a-z] [a-z] [a-z]?\n"
        "rest ::= [-A-Za-z0-9_/.%]+\n"
    )


def inject_citation_url_rule(rules: dict[str, str]) -> None:
    """Add the citation-url rule + helpers to a rules dict in-place.

    Idempotent: calling twice leaves the dict unchanged.
    """

    if "citation-url" in rules:
        return
    rules["citation-url"] = '"\\"" "https://wol.jw.org/" lang "/" rest "\\""'
    rules.setdefault("lang", "[a-z] [a-z] [a-z]?")
    rules.setdefault("rest", "[-A-Za-z0-9_/.%]+")


def validates_against_citation_grammar(quoted_url: str) -> bool:
    """Test helper: simulate the GBNF rule by validating against the regex.

    `quoted_url` is the string the GBNF rule would actually emit — i.e.
    surrounded by JSON double quotes. We strip them and apply the regex.
    """

    if not (quoted_url.startswith('"') and quoted_url.endswith('"')):
        return False
    inner = quoted_url[1:-1]
    return re.match(CITATION_URL_REGEX, inner) is not None
