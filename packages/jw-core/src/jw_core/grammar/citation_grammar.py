"""Placeholder — filled in Task 4."""

from __future__ import annotations


def citation_url_grammar() -> str:  # pragma: no cover - replaced in Task 4
    return ""


def inject_citation_url_rule(rules: dict[str, str]) -> None:  # pragma: no cover
    rules.setdefault("citation-url", '"\\"" "https://wol.jw.org/" [a-z]+ "/" [-A-Za-z0-9_/.%]+ "\\""')
