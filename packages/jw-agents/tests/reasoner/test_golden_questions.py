"""Regression tests against the golden 10 doctrinal questions (Fase 67).

Each scenario runs the reasoner with a FakeLLM that returns a canned
plan tailored to the question id. We assert structural properties: the
tree carries at least `min_steps`, the kinds match the expected set,
and the reformulator does NOT trigger (none of the goldens are toxic).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_agents.reasoner.engine import doctrinal_reasoner
from jw_agents.reasoner.models import ReasonerConfig

_GOLDEN = (
    Path(__file__).parent / "fixtures" / "golden.jsonl"
)


def _scenarios() -> list[dict]:
    out: list[dict] = []
    for line in _GOLDEN.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _plan_for(scenario: dict) -> str:
    """Build a canned planner response with `min_steps` steps using the
    expected kinds."""
    kinds = list(scenario["expected_kinds"])
    target = max(scenario["min_steps"], len(kinds))
    steps: list[dict] = []
    for i in range(target):
        kind = kinds[i] if i < len(kinds) else "premise"
        steps.append(
            {
                "id": f"s{i + 1}",
                "kind": kind,
                "statement": f"Paso {i + 1} para {scenario['id']}",
                "depends_on": [steps[i - 1]["id"]] if i > 0 else [],
                "rationale": "scripted",
            }
        )
    return json.dumps({"steps": steps})


class _CannedLLM:
    name = "canned"

    def __init__(self, text: str) -> None:
        self._text = text

    async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
        return self._text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario", _scenarios(), ids=lambda s: s["id"]
)
async def test_golden_question_runs_clean(scenario: dict) -> None:
    llm = _CannedLLM(_plan_for(scenario))
    cfg = ReasonerConfig(
        language=scenario["language"],
        max_steps=12,
        nli_mode="off",
        include_summary_prose=True,
    )
    tree = await doctrinal_reasoner(
        question=scenario["question"], llm=llm, config=cfg, nli=None
    )
    # Reformulator does NOT trigger on goldens
    assert tree.question_normalized == scenario["question"]
    assert len(tree.steps) >= scenario["min_steps"]
    actual_kinds = {s.kind for s in tree.steps}
    for kind in scenario["expected_kinds"]:
        assert kind in actual_kinds, (
            f"{scenario['id']}: expected kind {kind!r} missing; got {actual_kinds}"
        )
    assert tree.summary_prose


def test_at_least_ten_golden_scenarios() -> None:
    assert len(_scenarios()) >= 10
