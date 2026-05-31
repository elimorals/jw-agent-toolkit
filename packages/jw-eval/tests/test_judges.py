from __future__ import annotations

from jw_eval.judges.embeddings import EmbeddingsJudge, FakeEmbedder


def test_embeddings_judge_identical_returns_one() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder())
    score = judge.cosine("hello world", "hello world")
    assert 0.999 <= score <= 1.0001


def test_embeddings_judge_disjoint_returns_low() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder())
    score = judge.cosine("hello", "completely different")
    assert score < 0.5


def test_embeddings_judge_classify_uses_thresholds() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.78, threshold_review_min=0.55)
    assert judge.classify(0.9) == "pass"
    assert judge.classify(0.7) == "review"
    assert judge.classify(0.3) == "fail"


def test_llm_judge_dispatches_to_callable() -> None:
    from jw_eval.judges.llm import LLMJudge

    calls: list[str] = []

    def stub_call(prompt: str) -> str:
        calls.append(prompt)
        return '{"verdict": "pass", "reason": "looks fine"}'

    judge = LLMJudge(caller=stub_call)
    verdict, reason = judge.judge(
        golden="The Trinity is not biblical.",
        candidate="Scripture rejects the Trinity.",
        keywords_any=["not biblical", "rejects"],
        keywords_none=["central doctrine"],
    )
    assert verdict == "pass"
    assert reason == "looks fine"
    assert "Respuesta dorada:" in calls[0] or "Golden:" in calls[0]


def test_llm_judge_handles_garbage_response() -> None:
    from jw_eval.judges.llm import LLMJudge

    judge = LLMJudge(caller=lambda _: "not even json")
    verdict, reason = judge.judge("a", "b", keywords_any=[], keywords_none=[])
    assert verdict == "error"
    assert "parse" in reason.lower()
