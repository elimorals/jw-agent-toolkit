"""When content drifts AND an NLIProvider is wired, the validator re-runs NLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from jw_agents.base import Citation
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)


@dataclass
class _NLIVerdict:
    """Mirror of Fase 39's NLIVerdict shape — duck-typed by the validator."""

    label: str
    score: float


class FakeNLIProvider:
    """Returns a pre-canned verdict regardless of input."""

    def __init__(self, label: str, score: float) -> None:
        self.label = label
        self.score = score
        self.calls: list[tuple[str, str]] = []

    async def evaluate_entailment(self, claim: str, premise: str) -> Any:
        self.calls.append((claim, premise))
        return _NLIVerdict(label=self.label, score=self.score)


class FakeFetcher:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(final_url=url, status=200, body=self._body)


async def test_nli_rerun_attached_on_changed_when_provider_present() -> None:
    """Hash mismatch + NLI provider → verdict.nli_rerun populated."""

    original_text = "Jesús es el Hijo de Dios"
    new_text = "Jesús es Dios mismo"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
            "nli_claim": "Jesus is the Son of God",
            "nli_verdict": "entails",
        },
    )
    provider = FakeNLIProvider(label="neutral", score=0.42)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert verdict.nli_rerun["changed"] is True
    assert verdict.nli_rerun["from"] == "entails"
    assert verdict.nli_rerun["to"] == "neutral"
    assert verdict.nli_rerun["score"] == pytest.approx(0.42)
    assert len(provider.calls) == 1


async def test_nli_rerun_changed_false_when_label_matches() -> None:
    """If NLI still says 'entails' even though content changed, mark unchanged verdict."""

    original_text = "x"
    new_text = "y"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )
    provider = FakeNLIProvider(label="entails", score=0.91)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert verdict.nli_rerun["changed"] is False
    assert verdict.nli_rerun["to"] == "entails"


async def test_nli_rerun_skipped_when_no_claim_in_metadata() -> None:
    """Without a baseline claim, we can't re-run NLI — nli_rerun stays None."""

    original_text = "x"
    new_text = "y"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
        },
    )
    provider = FakeNLIProvider(label="entails", score=1.0)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is None
    assert provider.calls == []


async def test_nli_rerun_never_runs_when_status_is_match() -> None:
    """No drift → no NLI re-run."""

    text = "stable text"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(text),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )
    provider = FakeNLIProvider(label="contradicts", score=0.99)
    validator = ProvenanceValidator(fetcher=FakeFetcher(text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "match"
    assert verdict.nli_rerun is None
    assert provider.calls == []


async def test_nli_rerun_error_captured_when_provider_raises() -> None:
    """A misbehaving provider must not crash the whole validator."""

    new_text = "different"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256("original"),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )

    class _BoomProvider:
        async def evaluate_entailment(self, claim: str, premise: str) -> Any:
            raise RuntimeError("boom")

    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=_BoomProvider())
    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert "boom" in verdict.nli_rerun.get("error", "")
