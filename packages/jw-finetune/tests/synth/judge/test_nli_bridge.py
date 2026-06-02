"""Tests for the NLI bridge — claim/premise extraction + provider plumbing."""

from __future__ import annotations

from typing import Any

from jw_finetune.synth.judge.nli_bridge import (
    extract_premise_from_answer,
    run_nli_check,
)


class FakeVerdict:
    def __init__(self, verdict: str, score: float) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLIProvider:
    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self._verdict = verdict
        self._score = score
        self.calls: list[tuple[str, str]] = []

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:
        self.calls.append((claim, premise))
        return FakeVerdict(self._verdict, self._score)


def test_extract_premise_from_typographic_quotes() -> None:
    answer = (
        'La Atalaya dice: "Dios amó tanto al mundo que dio a su Hijo." '
        "Esto enseña amor."
    )
    premise = extract_premise_from_answer(answer)
    assert premise == "Dios amó tanto al mundo que dio a su Hijo."


def test_extract_premise_from_guillemets() -> None:
    answer = "El texto declara: «Jehová es uno solo.» y por eso..."
    premise = extract_premise_from_answer(answer)
    assert premise == "Jehová es uno solo."


def test_extract_premise_returns_none_when_no_quote() -> None:
    assert extract_premise_from_answer("No hay nada citado aquí.") is None


def test_extract_premise_strips_outer_whitespace() -> None:
    answer = '   "  hello world  again now  "   '
    assert extract_premise_from_answer(answer) == "hello world  again now"


def test_run_nli_check_returns_verdict_and_score() -> None:
    provider = FakeNLIProvider(verdict="entails", score=0.88)
    answer = 'Dice: "amó tanto al mundo." Por eso entendemos el amor.'
    result = run_nli_check(answer=answer, nli_provider=provider)
    assert result is not None
    verdict, score = result
    assert verdict == "entails"
    assert score == 0.88
    assert provider.calls, "NLI provider should have been called"


def test_run_nli_check_returns_none_without_premise() -> None:
    provider = FakeNLIProvider()
    result = run_nli_check(answer="No quote here", nli_provider=provider)
    assert result is None
    assert provider.calls == []


def test_run_nli_check_returns_none_when_provider_is_none() -> None:
    result = run_nli_check(answer='He said: "anything to test."', nli_provider=None)
    assert result is None


def test_run_nli_check_swallows_provider_exceptions() -> None:
    class BoomProvider:
        def evaluate_entailment(self, **_: Any) -> Any:
            raise RuntimeError("model not loaded")

    result = run_nli_check(
        answer='He said: "anything more here."', nli_provider=BoomProvider()
    )
    assert result is None
