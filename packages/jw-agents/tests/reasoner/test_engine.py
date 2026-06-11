"""End-to-end doctrinal_reasoner tests (Fase 67)."""

from __future__ import annotations

import json

import pytest

from jw_agents.reasoner.engine import doctrinal_reasoner
from jw_agents.reasoner.models import Citation, ReasonerConfig, ReasoningStep


class FakeLLM:
    name = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


class FakeVerdict:
    def __init__(self, verdict: str, score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    name = "fake-nli"

    def __init__(self, verdict: str = "entails") -> None:
        self._verdict = verdict

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:  # noqa: ARG002
        return FakeVerdict(self._verdict)


async def _dispatcher(step: ReasoningStep) -> Citation | None:
    return Citation(
        text="amó tanto al mundo",
        wol_url="https://wol.jw.org/x",
        source_kind="verse",
    )


_PLAN_JSON = json.dumps(
    {
        "steps": [
            {
                "id": "p1",
                "kind": "premise",
                "statement": "John 3:16 declares God's love is universal.",
                "depends_on": [],
                "rationale": "establish foundational text",
            },
            {
                "id": "c1",
                "kind": "conclusion",
                "statement": "Therefore God's love motivates action.",
                "depends_on": ["p1"],
                "rationale": "build on premise",
            },
        ]
    }
)


@pytest.mark.asyncio
async def test_doctrinal_reasoner_happy_path() -> None:
    tree = await doctrinal_reasoner(
        question="¿qué enseña Juan 3:16?",
        llm=FakeLLM(_PLAN_JSON),
        config=ReasonerConfig(language="es"),
        nli=FakeNLI("entails"),
        tool_dispatcher=_dispatcher,
    )
    assert len(tree.steps) == 2
    assert tree.truncated is False
    assert tree.summary_prose
    assert "Premisas" in tree.summary_prose or "Premises" in tree.summary_prose


@pytest.mark.asyncio
async def test_doctrinal_reasoner_reformulates_toxic() -> None:
    """A hostile-framing question is normalized before planning."""
    tree = await doctrinal_reasoner(
        question="Demuestra que el catolicismo está equivocado sobre la Trinidad",
        llm=FakeLLM(_PLAN_JSON),
        config=ReasonerConfig(language="es", reformulate_toxic=True),
        nli=None,
        tool_dispatcher=_dispatcher,
    )
    assert tree.question_normalized.startswith("¿Qué enseña la Biblia")
    assert tree.question_original != tree.question_normalized


@pytest.mark.asyncio
async def test_doctrinal_reasoner_reject_truncates_on_contradicts() -> None:
    tree = await doctrinal_reasoner(
        question="x",
        llm=FakeLLM(_PLAN_JSON),
        config=ReasonerConfig(language="es", nli_mode="reject"),
        nli=FakeNLI("contradicts"),
        tool_dispatcher=_dispatcher,
    )
    assert tree.truncated is True
    assert len(tree.steps) == 1


@pytest.mark.asyncio
async def test_doctrinal_reasoner_summary_disabled() -> None:
    tree = await doctrinal_reasoner(
        question="x",
        llm=FakeLLM(_PLAN_JSON),
        config=ReasonerConfig(
            language="es", include_summary_prose=False
        ),
        nli=None,
        tool_dispatcher=_dispatcher,
    )
    assert tree.summary_prose == ""


@pytest.mark.asyncio
async def test_doctrinal_reasoner_truncated_summary_has_note() -> None:
    tree = await doctrinal_reasoner(
        question="x",
        llm=FakeLLM(_PLAN_JSON),
        config=ReasonerConfig(language="es", nli_mode="reject"),
        nli=FakeNLI("contradicts"),
        tool_dispatcher=_dispatcher,
    )
    assert tree.truncated is True
    assert "truncó" in tree.summary_prose or "truncated" in tree.summary_prose
