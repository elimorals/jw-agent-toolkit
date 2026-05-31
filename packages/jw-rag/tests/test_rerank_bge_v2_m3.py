from __future__ import annotations

import importlib.util

import pytest
from jw_rag.rerank_providers.bge_v2_m3 import BGERerankerV2M3Provider


def test_is_available_false_when_sentence_transformers_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None if name == "sentence_transformers" else importlib.util.find_spec(name),
    )
    assert BGERerankerV2M3Provider().is_available() is False


def test_name_and_target() -> None:
    p = BGERerankerV2M3Provider()
    assert p.name == "bge-v2-m3"


@pytest.mark.rerank_local
def test_real_rerank_returns_one_score_per_candidate() -> None:
    p = BGERerankerV2M3Provider()
    if not p.is_available():
        pytest.skip("sentence-transformers not installed")
    scores = p.rerank("trinidad", ["el trino", "una manzana", "doctrina cristiana"])
    assert len(scores) == 3
    assert all(isinstance(s, float) for s in scores)
