from __future__ import annotations

from typing import Any

from jw_eval.layers.structural import evaluate_structural
from jw_eval.models import GoldenCase


class FakeFinding:
    def __init__(self, source: str, has_citation: bool = True, text: str = "demo") -> None:
        self._source = source
        self._has_citation = has_citation
        self._text = text

    @property
    def text(self) -> str:
        return self._text

    @property
    def metadata(self) -> dict[str, Any]:
        return {"source": self._source} if self._has_citation else {}


class FakeResult:
    def __init__(self, findings: list[FakeFinding]) -> None:
        self.findings = findings


def _agent_factory(result: FakeResult):
    def run(input_dict: dict[str, Any]) -> FakeResult:  # noqa: ARG001
        return result

    return run


def test_structural_passes_when_all_checks_met() -> None:
    case = GoldenCase(
        id="t1",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={
            "min_findings": 2,
            "sources_in_order": ["topic_index", "verse_text"],
            "must_have_source": "topic_index",
            "must_have_citation": True,
            "forbidden_keywords_in_findings": ["maybe"],
        },
    )
    result = FakeResult(
        findings=[
            FakeFinding("topic_index", True, "Real cite"),
            FakeFinding("verse_text", True, "Verse"),
        ]
    )
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "pass"


def test_structural_fails_on_missing_source() -> None:
    case = GoldenCase(
        id="t2",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"must_have_source": "topic_index"},
    )
    result = FakeResult(findings=[FakeFinding("rag")])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"
    assert any("topic_index" in reason for reason in r.reasons)


def test_structural_fails_on_forbidden_keyword() -> None:
    case = GoldenCase(
        id="t3",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"forbidden_keywords_in_findings": ["maybe"]},
    )
    result = FakeResult(findings=[FakeFinding("rag", True, "this is maybe wrong")])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"


def test_structural_fails_on_missing_citation() -> None:
    case = GoldenCase(
        id="t4",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"must_have_citation": True},
    )
    result = FakeResult(findings=[FakeFinding("rag", has_citation=False)])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"


def test_structural_errors_when_agent_raises() -> None:
    case = GoldenCase(id="t5", agent="apologetics", layer="l1", input={}, expected={})

    def broken(_: dict[str, Any]):
        raise RuntimeError("boom")

    r = evaluate_structural(case, broken)
    assert r.verdict == "error"
    assert any("boom" in reason for reason in r.reasons)
