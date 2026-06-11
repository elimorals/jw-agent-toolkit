"""NLI factory tests — env-driven selection + adapter signature."""

from __future__ import annotations

import pytest

from jw_agents.meta.nli_factory import _NLIAdapter, build_nli_from_env


def test_default_env_returns_none() -> None:
    assert build_nli_from_env() is None


def test_env_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_META_NLI", "off")
    assert build_nli_from_env() is None


def test_adapter_normalizes_evaluate_entailment_signature() -> None:
    class FakeVerdict:
        verdict = "entails"
        score = 0.9

    class FakeProvider:
        name = "fake-nli"
        target = "cpu"

        def __init__(self) -> None:
            self.last_call: dict | None = None

        def is_available(self) -> bool:
            return True

        def evaluate(
            self, claim: str, premise: str, *, language: str = "en"
        ) -> FakeVerdict:
            self.last_call = {
                "claim": claim,
                "premise": premise,
                "language": language,
            }
            return FakeVerdict()

    fake = FakeProvider()
    adapter = _NLIAdapter(fake, language="es")
    out = adapter.evaluate_entailment(claim="X", premise="Y")
    assert out.verdict == "entails"
    assert fake.last_call == {
        "claim": "X",
        "premise": "Y",
        "language": "es",
    }
    assert adapter.name == "fake-nli"


def test_env_auto_with_unavailable_provider_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_META_NLI", "auto")

    class UnavailableProvider:
        name = "unavailable"
        target = "cpu"

        def is_available(self) -> bool:
            return False

        def evaluate(self, claim, premise, *, language="en"):  # noqa: D401, ARG002
            raise RuntimeError("should not be called")

    def _fake_factory():
        return UnavailableProvider()

    monkeypatch.setattr(
        "jw_core.fidelity.factory.get_default_nli_provider",
        _fake_factory,
    )
    assert build_nli_from_env() is None


def test_env_auto_with_available_provider_returns_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_META_NLI", "auto")

    class FakeVerdict:
        verdict = "neutral"
        score = 0.5

    class AvailableProvider:
        name = "available"
        target = "cpu"

        def is_available(self) -> bool:
            return True

        def evaluate(self, claim, premise, *, language="en") -> FakeVerdict:  # noqa: ARG002
            return FakeVerdict()

    def _fake_factory():
        return AvailableProvider()

    monkeypatch.setattr(
        "jw_core.fidelity.factory.get_default_nli_provider",
        _fake_factory,
    )
    adapter = build_nli_from_env(language="pt")
    assert adapter is not None
    verdict = adapter.evaluate_entailment(claim="C", premise="P")
    assert verdict.verdict == "neutral"
