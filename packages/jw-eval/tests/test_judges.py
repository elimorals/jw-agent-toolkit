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
