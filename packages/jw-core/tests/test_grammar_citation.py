"""Tests for jw_core.grammar.citation_grammar — URL anchoring."""

from __future__ import annotations

import re

from jw_core.grammar.citation_grammar import (
    CITATION_URL_REGEX,
    citation_url_grammar,
    inject_citation_url_rule,
    validates_against_citation_grammar,
)


def test_citation_url_grammar_text_contains_wol_host() -> None:
    grammar = citation_url_grammar()
    assert "wol.jw.org" in grammar
    assert "citation-url" in grammar


def test_validates_accepts_wol_url() -> None:
    assert validates_against_citation_grammar('"https://wol.jw.org/es/wol/d/r4/lp-s/2024/01/01"') is True
    assert validates_against_citation_grammar('"https://wol.jw.org/en/wol/b/r1/lp-e/nwt/E/2024/43/3"') is True


def test_validates_rejects_non_wol() -> None:
    assert validates_against_citation_grammar('"https://example.com/whatever"') is False
    assert validates_against_citation_grammar('"http://wol.jw.org/es/x"') is False
    assert validates_against_citation_grammar('"https://wol.jw.org/"') is False


def test_inject_citation_url_rule_is_idempotent() -> None:
    rules: dict[str, str] = {}
    inject_citation_url_rule(rules)
    inject_citation_url_rule(rules)
    # Inserted exactly once.
    keys = list(rules.keys())
    assert keys.count("citation-url") == 1


def test_regex_matches_three_letter_lang_codes() -> None:
    # JW languages include three-letter codes like 'ase' (American Sign Language).
    assert re.match(CITATION_URL_REGEX, "https://wol.jw.org/ase/wol/d/r80/lp-asl/2024001") is not None
