"""Reasoner Pydantic models."""

from __future__ import annotations

import pytest

from jw_agents.reasoner.models import (
    Citation,
    ReasonerConfig,
    ReasoningStep,
    ReasoningTree,
)


def test_step_minimal() -> None:
    s = ReasoningStep(id="p1", kind="premise", statement="X is true.")
    assert s.depends_on == []
    assert s.nli_status == "skipped"
    assert s.citation is None


def test_step_with_citation_and_nli() -> None:
    c = Citation(
        text="Porque tanto amó Dios al mundo",
        wol_url="https://wol.jw.org/x",
        source_kind="verse",
    )
    s = ReasoningStep(
        id="p1",
        kind="premise",
        statement="John 3:16 declares God's love.",
        citation=c,
        nli_status="entails",
        nli_score=0.92,
    )
    assert s.citation.wol_url.startswith("https://")
    assert s.nli_status == "entails"


def test_step_rejects_out_of_range_nli_score() -> None:
    with pytest.raises(ValueError):
        ReasoningStep(
            id="x", kind="premise", statement="x", nli_score=1.5
        )


def test_tree_rejects_self_dep() -> None:
    with pytest.raises(ValueError):
        ReasoningTree(
            question_original="q",
            question_normalized="q",
            steps=[
                ReasoningStep(
                    id="p1",
                    kind="premise",
                    statement="x",
                    depends_on=["p1"],
                )
            ],
        )


def test_tree_rejects_missing_dep() -> None:
    with pytest.raises(ValueError):
        ReasoningTree(
            question_original="q",
            question_normalized="q",
            steps=[
                ReasoningStep(
                    id="i1",
                    kind="inference",
                    statement="x",
                    depends_on=["p99"],
                )
            ],
        )


def test_tree_accepts_valid_dag() -> None:
    tree = ReasoningTree(
        question_original="¿qué dice Juan 3:16?",
        question_normalized="¿qué dice Juan 3:16?",
        steps=[
            ReasoningStep(id="p1", kind="premise", statement="x"),
            ReasoningStep(
                id="c1",
                kind="conclusion",
                statement="y",
                depends_on=["p1"],
            ),
        ],
    )
    assert len(tree.steps) == 2
    assert tree.truncated is False


def test_reasoner_config_defaults() -> None:
    c = ReasonerConfig()
    assert c.language == "es"
    assert c.max_steps == 12
    assert c.nli_mode == "reject"
    assert c.reformulate_toxic is True


def test_reasoner_config_caps_max_steps() -> None:
    with pytest.raises(ValueError):
        ReasonerConfig(max_steps=100)
