"""Regression tests over golden sparring conversation fixtures.

Each .jsonl line is a complete scenario:
  {
    "persona": "<key>",
    "language": "es",
    "turns": [
      {"user": "...",
       "expected_reply_contains": "...",   # optional
       "expected_needs_followup": true,     # optional
       "expected_citation_quality": "weak"  # optional, asserts feedback
      },
      ...
    ]
  }

The replies come from `FakeSparLLM` (deterministic), so the assertions
stay stable across runs. These fixtures are documentation of the
intended behavior; when we change the fake or the canned responses,
the diff in the fixture surfaces in the test result.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from jw_agents.spar.feedback import score_session
from jw_agents.spar.session import (
    clear_sessions,
    close_session,
    get_session,
    start_session,
    take_turn,
)
from jw_agents.spar.simulator import FakeSparLLM

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "conversations"


def _scenarios() -> list[dict]:
    out: list[dict] = []
    for path in sorted(_FIXTURES_DIR.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_sessions()
    yield
    clear_sessions()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    _scenarios(),
    ids=lambda s: f"{s['persona']}_{s['language']}",
)
async def test_golden_conversation_runs_clean(scenario: dict) -> None:
    """Each turn must complete + assertions on reply / feedback hold."""

    llm = FakeSparLLM()
    s = start_session(
        persona_key=scenario["persona"], language=scenario["language"]
    )
    citation_qualities: list[str] = []
    for turn_spec in scenario["turns"]:
        response = await take_turn(
            session_id=s.session_id,
            user_text=turn_spec["user"],
            llm=llm,
        )
        if "expected_reply_contains" in turn_spec:
            substr = turn_spec["expected_reply_contains"]
            assert (
                substr.lower() in response.reply.lower()
            ), f"expected {substr!r} in reply, got {response.reply!r}"
        if "expected_needs_followup" in turn_spec:
            assert (
                response.needs_followup
                == turn_spec["expected_needs_followup"]
            )

    session = get_session(s.session_id)
    close_session(session_id=s.session_id)
    score_session(session)

    for turn_spec, fb in zip(
        scenario["turns"], session.feedback, strict=False
    ):
        if "expected_citation_quality" in turn_spec:
            assert (
                fb.citation_quality == turn_spec["expected_citation_quality"]
            ), (
                f"expected citation_quality "
                f"{turn_spec['expected_citation_quality']!r}, "
                f"got {fb.citation_quality!r}"
            )
        citation_qualities.append(fb.citation_quality)

    # Every scenario should produce a non-empty score_summary
    assert session.score_summary is not None
    assert session.score_summary["turns"] == len(scenario["turns"])


def test_at_least_three_golden_scenarios_present() -> None:
    assert len(_scenarios()) >= 3
