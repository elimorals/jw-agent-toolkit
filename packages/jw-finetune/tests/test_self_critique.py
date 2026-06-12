"""Tests for SL-CAI self_critique pipeline (F80 Phase 0).

Covers the supervised half of Constitutional AI: regex tier first, then LLM
revise on hard-principle hits. The module already existed pre-F80; these
tests pin the behavior so subsequent interpretability phases can build on
a stable contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jw_eval.principles import DetectionRules, Principle
from jw_finetune.data.formats import QAPair
from jw_finetune.synth.critique import (
    CritiqueResult,
    batch_critique,
    self_critique,
)
from jw_finetune.synth.provider import LLMRequest, LLMResponse


@dataclass
class FakeProvider:
    """Deterministic provider for tests. Records calls, returns canned text."""

    name: str = "fake"
    model: str = "fake-1"
    canned: str = ""
    raises: Exception | None = None
    calls: list[LLMRequest] = field(default_factory=list)

    def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        if self.raises is not None:
            raise self.raises
        return LLMResponse(
            text=self.canned,
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 1, "output_tokens": 1},
        )


def _principle_no_apocrypha(applies_to: list[str] | None = None) -> Principle:
    """Hard principle: forbid bringing apocrypha as canon."""
    return Principle(
        id="PF-test-no-apocrypha",
        severity="hard",
        rationale="No presentar libros apócrifos como canónicos JW.",
        applies_to=applies_to or [],
        detect=DetectionRules(forbidden_phrases=["el libro de tobías enseña"]),
    )


def _principle_soft_cite_first() -> Principle:
    return Principle(
        id="PF-test-soft-cite",
        severity="soft",
        rationale="Citar antes de parafrasear cuando hay duda.",
        detect=DetectionRules(forbidden_phrases=["creo recordar que"]),
    )


def _pair(answer: str, language: str = "es") -> QAPair:
    return QAPair(
        question="¿Qué enseña la Biblia sobre la oración?",
        answer=answer,
        source_chunk_id="chunk-001",
        language=language,
    )


# ---------------------------------------------------------------------------
# Behavior matrix
# ---------------------------------------------------------------------------


def test_no_applicable_principles_returns_unchanged() -> None:
    """When agent filter excludes every principle, skip LLM and return as-is."""
    p = _principle_no_apocrypha(applies_to=["other_agent_only"])
    provider = FakeProvider(canned="should-not-be-called")
    result = self_critique(
        _pair("Mateo 6:9 nos enseña a orar al Padre."),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert isinstance(result, CritiqueResult)
    assert result.changed is False
    assert result.violated_principle_ids == []
    assert provider.calls == [], "LLM must not be called when no principle applies"


def test_no_violation_returns_unchanged() -> None:
    """Clean answer + applicable principle → no LLM call, no change."""
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    provider = FakeProvider(canned="should-not-be-called")
    result = self_critique(
        _pair("Mateo 6:9 nos enseña a orar al Padre."),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is False
    assert provider.calls == [], "no violation → no LLM call (regex tier short-circuits)"


def test_hard_violation_calls_llm_and_revises() -> None:
    """Hard violation → LLM revise → revised text replaces answer."""
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    revised = "Mateo 6:9 enseña que oremos al Padre celestial."
    provider = FakeProvider(canned=revised)
    result = self_critique(
        _pair("El libro de Tobías enseña que la oración cura. Mateo 6:9."),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is True
    assert result.revised.answer == revised
    assert "PF-test-no-apocrypha" in result.violated_principle_ids
    assert len(provider.calls) == 1


def test_revised_pair_has_sl_cai_metadata_flags() -> None:
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    provider = FakeProvider(canned="answer revisada")
    result = self_critique(
        _pair("El libro de Tobías enseña X."),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    md = result.revised.metadata
    assert md["sl_cai_revised"] == "true"
    assert "PF-test-no-apocrypha" in md["sl_cai_principles"]


def test_preserve_original_stashes_original_answer_in_metadata() -> None:
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    original = "El libro de Tobías enseña X."
    provider = FakeProvider(canned="respuesta limpia")
    result = self_critique(
        _pair(original),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
        preserve_original=True,
    )
    assert result.revised.metadata["original_answer"] == original
    assert result.original_answer == original


def test_llm_provider_failure_keeps_original_pair() -> None:
    """Provider raising → graceful fallback to original, no crash."""
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    provider = FakeProvider(raises=RuntimeError("transient"))
    original_text = "El libro de Tobías enseña X."
    result = self_critique(
        _pair(original_text),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is False
    assert result.revised.answer == original_text
    assert "PF-test-no-apocrypha" in result.violated_principle_ids


def test_empty_llm_response_keeps_original() -> None:
    """LLM returns empty → treat as no-change (rather than blanking the answer)."""
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    provider = FakeProvider(canned="   ")
    original_text = "El libro de Tobías enseña X."
    result = self_critique(
        _pair(original_text),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is False
    assert result.revised.answer == original_text


def test_llm_returns_same_answer_marked_unchanged() -> None:
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    original = "El libro de Tobías enseña X."
    provider = FakeProvider(canned=original)
    result = self_critique(
        _pair(original),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is False


def test_english_pair_uses_english_prompt() -> None:
    p = Principle(
        id="PF-en-test",
        severity="hard",
        rationale="Do not present apocrypha as canon.",
        applies_to=["doctrinal_reasoner"],
        detect=DetectionRules(forbidden_phrases=["the book of tobit teaches"]),
    )
    provider = FakeProvider(canned="Matthew 6:9 teaches us to pray.")
    result = self_critique(
        _pair("The book of Tobit teaches that prayer heals.", language="en"),
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert result.changed is True
    assert len(provider.calls) == 1
    # English path uses English system prompt
    assert "doctrinal fidelity" in provider.calls[0].system.lower()


def test_batch_critique_counts_only_changed() -> None:
    p = _principle_no_apocrypha(applies_to=["doctrinal_reasoner"])
    provider = FakeProvider(canned="revisado")
    pairs = [
        _pair("Mateo 6:9 enseña a orar."),  # clean
        _pair("El libro de Tobías enseña X."),  # dirty
        _pair("Juan 17:3 habla del conocimiento de Dios."),  # clean
        _pair("Otra cosa, el libro de Tobías enseña Y."),  # dirty
    ]
    revised, changed = batch_critique(
        pairs,
        principles=[p],
        llm_provider=provider,
        agent="doctrinal_reasoner",
    )
    assert len(revised) == 4
    assert changed == 2
    assert len(provider.calls) == 2  # only the dirty ones hit the LLM
