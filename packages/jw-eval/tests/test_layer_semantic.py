from __future__ import annotations

from typing import Any

from jw_eval.judges.embeddings import EmbeddingsJudge, FakeEmbedder
from jw_eval.layers.semantic import evaluate_semantic
from jw_eval.models import GoldenCase


def _stub_agent(text: str):
    class _F:
        def __init__(self, t: str) -> None:
            self.text = t
            self.metadata = {"source": "rag"}

    class _R:
        findings = [_F(text)]

    def run(_: dict[str, Any]) -> _R:
        return _R()

    return run


def test_semantic_pass_high_similarity() -> None:
    case = GoldenCase(
        id="l3_pass",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "The Trinity is not a Bible teaching.",
            "expected_keywords_any": ["not"],
            "expected_keywords_none": ["central doctrine"],
        },
    )
    agent = _stub_agent("The Trinity is not a Bible teaching, Scripture rejects it.")
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.5, threshold_review_min=0.3)
    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=None)
    assert r.verdict == "pass"
    assert r.score is not None and r.score >= 0.5


def test_semantic_fail_forbidden_keyword_present() -> None:
    case = GoldenCase(
        id="l3_kw_fail",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "X",
            "expected_keywords_any": [],
            "expected_keywords_none": ["central doctrine"],
        },
    )
    agent = _stub_agent("It is the central doctrine of the faith.")
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.0, threshold_review_min=0.0)
    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=None)
    assert r.verdict == "fail"


def test_semantic_escalates_when_borderline() -> None:
    case = GoldenCase(
        id="l3_borderline",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "answer",
            "expected_keywords_any": [],
            "expected_keywords_none": [],
        },
    )
    agent = _stub_agent("totally different words")

    # Force borderline score region
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.99, threshold_review_min=0.0)

    calls: list[str] = []

    class StubLLM:
        def judge(self, golden: str, candidate: str, keywords_any: list[str], keywords_none: list[str]) -> tuple[str, str]:
            calls.append(candidate)
            return "pass", "escalated and approved"

    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=StubLLM())
    assert r.verdict == "pass"
    assert calls, "LLM judge should have been called"
