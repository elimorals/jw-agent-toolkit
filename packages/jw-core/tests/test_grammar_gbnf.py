"""Tests for jw_core.grammar.gbnf — low-level builders."""

from __future__ import annotations

import re

import pytest

from jw_core.grammar.gbnf import (
    agent_result_grammar,
    bible_ref_grammar,
    escape_gbnf_string,
    json_object_grammar,
)


def test_escape_gbnf_string_basic() -> None:
    assert escape_gbnf_string('hello "world"') == r'hello \"world\"'
    assert escape_gbnf_string("back\\slash") == r"back\\slash"


def test_json_object_grammar_round_trip_shape() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    grammar = json_object_grammar(schema)
    assert "root" in grammar
    # The field names appear inside escaped GBNF terminals (\"name\" / \"age\").
    assert r"\"name\"" in grammar
    assert r"\"age\"" in grammar


def test_bible_ref_grammar_contains_expected_alternatives() -> None:
    grammar = bible_ref_grammar()
    # Spot-check a handful of books in EN/ES/PT to verify the alternation
    # covers the languages we exercise in agents.
    assert "Genesis" in grammar
    assert "Génesis" in grammar
    assert "Gênesis" in grammar
    assert re.search(r"[0-9]+", grammar) is not None  # chapter/verse digits


def test_agent_result_grammar_includes_citation_url_rule() -> None:
    grammar = agent_result_grammar()
    assert "citation-url" in grammar
    assert "wol.jw.org" in grammar
    assert "root" in grammar


def test_json_object_grammar_rejects_non_object_schema() -> None:
    with pytest.raises(ValueError):
        json_object_grammar({"type": "string"})
