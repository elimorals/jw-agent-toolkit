"""Heuristic stage tests (always-on, no network)."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.heuristics import (
    cites_jw_publication,
    has_minimum_substance,
)


@pytest.mark.parametrize(
    "answer",
    [
        "Según w23.04 p. 12, la respuesta es clara.",
        "Ver Atalaya w20 enero p. 4 párr. 6.",
        "https://wol.jw.org/es/wol/d/r4/lp-s/2024123",
        "Más información en https://wol.jw.org/en/wol/d/...",
        "Consultar bh capítulo 5 y g23 abril.",
        "El libro jy capítulo 17 lo explica.",
        "Como se muestra en sjj canción 27.",
    ],
)
def test_cites_jw_publication_positives(answer: str) -> None:
    assert cites_jw_publication(answer) is True


@pytest.mark.parametrize(
    "answer",
    [
        "Sin referencia clara.",
        "La Biblia dice que sí.",
        "Es una verdad bíblica importante.",
        "Ver el libro de Mateo capítulo 24.",
        "https://wikipedia.org/something",
        "",
        "   ",
    ],
)
def test_cites_jw_publication_negatives(answer: str) -> None:
    assert cites_jw_publication(answer) is False


def test_has_minimum_substance_passes_for_real_teaching() -> None:
    q = "¿Qué enseña la Biblia sobre el reino?"
    a = (
        "La Biblia enseña que el reino de Dios es un gobierno real con Cristo "
        "Jesús como rey, según Daniel 2:44 y Mateo 6:9-10."
    )
    assert has_minimum_substance(q, a) is True


@pytest.mark.parametrize(
    "a", ["Sí.", "No.", "Depende.", "Sí", "No", "Tal vez", "Puede ser"]
)
def test_has_minimum_substance_rejects_generic_answers(a: str) -> None:
    assert has_minimum_substance("¿Algo?", a) is False


def test_has_minimum_substance_rejects_too_short() -> None:
    assert (
        has_minimum_substance("¿Qué dice Juan 3:16?", "Es muy interesante.")
        is False
    )


def test_has_minimum_substance_rejects_question_echo() -> None:
    q = "¿Qué enseña la Biblia sobre el alma?"
    a = q + " Eso es."
    assert has_minimum_substance(q, a) is False


def test_has_minimum_substance_handles_none_safely() -> None:
    assert has_minimum_substance("?", "") is False
    assert has_minimum_substance("", "") is False


def test_has_minimum_substance_multilingual_passes() -> None:
    q_en = "What does the Bible teach about love?"
    a_en = (
        "The Bible teaches that love is the foremost quality of God's "
        "personality, as 1 John 4:8 explicitly declares: 'God is love.'"
    )
    assert has_minimum_substance(q_en, a_en) is True

    q_pt = "O que a Bíblia ensina sobre o reino?"
    a_pt = (
        "A Bíblia ensina que o reino de Deus é um governo real com Cristo "
        "Jesus como Rei, conforme Daniel 2:44 e Mateus 6:9-10."
    )
    assert has_minimum_substance(q_pt, a_pt) is True
