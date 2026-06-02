"""End-to-end judge tests using FakeLLMProvider + FakeNLIProvider."""

from __future__ import annotations

import pytest
from jw_finetune.synth.judge.judge import Judge, score_qa_pair
from jw_finetune.synth.judge.models import QAScore
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides
from jw_finetune.synth.provider import LLMRequest, LLMResponse


class FakeLLMProvider:
    name = "fake"
    model = "fake-judge"

    def __init__(self, text: str = "3") -> None:
        self._text = text
        self.calls: list[LLMRequest] = []

    def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        return LLMResponse(
            text=self._text,
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 10, "output_tokens": 1},
        )


class FakeVerdict:
    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self._v = verdict
        self._s = score

    def evaluate_entailment(
        self, *, claim: str, premise: str
    ) -> FakeVerdict:  # noqa: ARG002
        return FakeVerdict(self._v, self._s)


def test_score_qa_pair_heuristics_only_passes_loose() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer=(
            "Como explica w23.04 página 12, el reino de Dios es un gobierno real "
            "con Cristo Jesús como rey, fundado en Daniel 2:44 y Mateo 6:9-10."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    assert isinstance(score, QAScore)
    assert score.kept is True
    assert score.cites_jw_publication is True
    assert score.has_minimum_substance is True
    assert score.overall == pytest.approx(7.0)


def test_score_qa_pair_no_citation_passes_loose_above_cutoff() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer=(
            "El reino de Dios es un gobierno real fundado por Jehová, "
            "pero no menciono ninguna publicación específica."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    assert score.cites_jw_publication is False
    assert score.has_minimum_substance is True
    assert score.overall == pytest.approx(5.5)
    assert score.kept is True


def test_score_qa_pair_no_citation_rejected_strict() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer="El reino de Dios es un gobierno real fundado por Jehová.",
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=None,
    )
    assert score.kept is False
    assert any(r.code == "overall_below_threshold" for r in score.reasons)


def test_score_qa_pair_generic_answer_rejected() -> None:
    score = score_qa_pair(
        question="¿Qué dice Juan 3:16?",
        answer="Sí.",
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    assert score.has_minimum_substance is False
    assert score.kept is False
    assert any(r.code == "insufficient_substance" for r in score.reasons)


def test_score_qa_pair_uses_llm_when_provided() -> None:
    llm = FakeLLMProvider(text="3")
    score = score_qa_pair(
        question="¿Qué enseña w23 sobre el amor?",
        answer=(
            "Según w23.06 p. 5, el amor es la cualidad principal de Dios "
            "y la Biblia lo confirma."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=llm,
        nli_provider=None,
    )
    assert score.pedagogical_quality == 3
    assert score.overall == 10.0
    assert score.kept is True
    assert len(llm.calls) == 1


def test_score_qa_pair_llm_garbage_response_neutral() -> None:
    llm = FakeLLMProvider(text="banana")
    score = score_qa_pair(
        question="?",
        answer=(
            "Según w23.06 p. 5, el amor es la cualidad principal de Dios "
            "y la Biblia lo confirma."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=llm,
        nli_provider=None,
    )
    assert score.pedagogical_quality is None
    assert score.overall == pytest.approx(7.0)


def test_score_qa_pair_nli_contradicts_penalizes() -> None:
    nli = FakeNLI(verdict="contradicts", score=0.92)
    score = score_qa_pair(
        question="?",
        answer=(
            "La Atalaya dice: “Jehová es un solo Dios.” Esto no es "
            "consistente con la doctrina de los tres dioses, w23.06."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    assert score.nli_verdict == "contradicts"
    assert score.kept is False
    assert any(r.code == "nli_contradicts" for r in score.reasons)


def test_score_qa_pair_nli_entails_strict_pass() -> None:
    nli = FakeNLI(verdict="entails", score=0.95)
    score = score_qa_pair(
        question="?",
        answer=(
            "El texto dice: “Jehová es uno solo.” Esto se enseña "
            "claramente en w23.06 p. 4 párr. 5."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    assert score.kept is True
    assert score.nli_verdict == "entails"


def test_score_qa_pair_strict_require_nli_entails_blocks_neutral() -> None:
    nli = FakeNLI(verdict="neutral", score=0.5)
    score = score_qa_pair(
        question="?",
        answer=(
            "El texto dice: “Jehová es uno solo.” Esto se enseña "
            "claramente en w23.06 p. 4 párr. 5."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    assert score.nli_verdict == "neutral"
    assert score.kept is False
    assert any(r.code == "nli_neutral_low" for r in score.reasons)


def test_score_qa_pair_off_mode_returns_kept_true() -> None:
    score = score_qa_pair(
        question="?",
        answer="Sí.",
        language="es",
        mode=JudgeMode.OFF,
        llm_provider=None,
        nli_provider=None,
    )
    assert score.kept is True
    assert score.reasons == []


def test_judge_class_carries_state() -> None:
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=FakeLLMProvider(text="2"),
        nli_provider=None,
    )
    s = judge.score(
        question="?",
        answer=(
            "Como muestra w23.06, el amor es central. "
            "La Biblia es clara en 1 Juan 4:8."
        ),
        language="es",
    )
    assert s.pedagogical_quality == 2
    assert s.kept is True


def test_judge_class_dump_for_metadata() -> None:
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    s = judge.score(
        question="?",
        answer=(
            "Como muestra w23.06, el amor es central. "
            "La Biblia es clara en 1 Juan 4:8."
        ),
        language="es",
    )
    dumped = s.model_dump(exclude_none=True)
    assert dumped["kept"] is True
    assert dumped["cites_jw_publication"] is True
    assert "nli_score" not in dumped
