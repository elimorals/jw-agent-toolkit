"""Filler-word detector tests."""

from __future__ import annotations

from jw_core.talk_lab.filler import count_fillers


def test_count_fillers_en() -> None:
    text = "um, like, you know, uh, this is, um, important."
    n = count_fillers(text, language="en")
    assert n == 5


def test_count_fillers_es() -> None:
    text = "Eh, pues, este, o sea, bueno, vale… continuamos."
    n = count_fillers(text, language="es")
    assert n == 6


def test_count_fillers_pt() -> None:
    text = "É, tipo assim, então, né, vamos lá."
    n = count_fillers(text, language="pt")
    assert n >= 4


def test_count_fillers_word_boundary() -> None:
    assert count_fillers("the umpire", language="en") == 0


def test_count_fillers_case_insensitive() -> None:
    assert count_fillers("UM, ok", language="en") == 1


def test_count_fillers_unknown_language_falls_back_to_en() -> None:
    n = count_fillers("um like", language="fr")
    assert n == 2


def test_count_fillers_empty_string() -> None:
    assert count_fillers("", language="es") == 0
