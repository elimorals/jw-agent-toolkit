"""Reformulator tests (Fase 67)."""

from __future__ import annotations

import pytest

from jw_agents.reasoner.reformulator import (
    detect_toxic_framing,
    reformulate_neutral,
)


@pytest.mark.parametrize(
    "q",
    [
        "Demuestra que el catolicismo está equivocado sobre la Trinidad",
        "Refuta la doctrina del purgatorio",
        "Prove that Catholics are wrong about purgatory",
        "Disprove the idea of an immortal soul",
        "Refute the Trinity",
    ],
)
def test_detect_toxic_framing_positives(q: str) -> None:
    assert detect_toxic_framing(q) is True


@pytest.mark.parametrize(
    "q",
    [
        "¿Qué enseña la Biblia sobre el alma?",
        "What does the Bible teach about the resurrection?",
        "Juan 3:16 vs Juan 14:28: ¿cómo se reconcilian?",
    ],
)
def test_detect_toxic_framing_negatives(q: str) -> None:
    assert detect_toxic_framing(q) is False


def test_reformulate_neutral_es() -> None:
    q = "Demuestra que el catolicismo está equivocado sobre la Trinidad"
    out = reformulate_neutral(q, language="es")
    assert out.startswith("¿Qué enseña la Biblia")
    assert "catolicismo" in out or "Trinidad" in out


def test_reformulate_neutral_en() -> None:
    q = "Prove that Catholics are wrong about purgatory"
    out = reformulate_neutral(q, language="en")
    assert out.startswith("What does the Bible teach")
    assert "Catholics" in out


def test_reformulate_neutral_pt() -> None:
    q = "Refuta la doctrina del purgatorio"
    out = reformulate_neutral(q, language="pt")
    assert out.startswith("O que a Bíblia ensina")


def test_reformulate_returns_original_when_neutral() -> None:
    q = "¿Qué enseña la Biblia sobre el alma?"
    out = reformulate_neutral(q, language="es")
    assert out == q
