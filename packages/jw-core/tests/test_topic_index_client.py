"""Unit tests for jw_core.clients.topic_index — no network, pure logic."""

from jw_core.clients.topic_index import _rerank_by_title_match

SAMPLE_RAW = [
    {"title": "Hermas", "wol_url": "x", "docid": "111", "original_rank": 0, "score": 0.0},
    {"title": "Minor Reformed Church", "wol_url": "y", "docid": "222", "original_rank": 1, "score": 0.0},
    {"title": "Trinity", "wol_url": "z", "docid": "333", "original_rank": 2, "score": 0.0},
    {"title": "Trinity in History", "wol_url": "w", "docid": "444", "original_rank": 3, "score": 0.0},
    {"title": "Unrelated topic", "wol_url": "v", "docid": "555", "original_rank": 4, "score": 0.0},
]


def test_rerank_exact_title_match_wins() -> None:
    ranked = _rerank_by_title_match(list(SAMPLE_RAW), "Trinity")
    assert ranked[0]["title"] == "Trinity"
    assert ranked[0]["score"] == 100.0


def test_rerank_startswith_beats_no_match() -> None:
    ranked = _rerank_by_title_match(list(SAMPLE_RAW), "Trinity")
    # 'Trinity in History' starts with 'trinity' → score 80
    second = ranked[1]
    assert second["title"] == "Trinity in History"
    assert second["score"] == 80.0


def test_rerank_falls_back_to_original_rank_on_ties() -> None:
    """If no title matches the query at all, all scores are 0 and original
    rank breaks ties."""
    ranked = _rerank_by_title_match(list(SAMPLE_RAW), "Quantum")
    assert all(r["score"] == 0.0 for r in ranked)
    assert ranked[0]["title"] == "Hermas"  # original rank 0
    assert ranked[-1]["title"] == "Unrelated topic"  # original rank 4


def test_rerank_case_insensitive() -> None:
    ranked = _rerank_by_title_match(list(SAMPLE_RAW), "TRINITY")
    assert ranked[0]["title"] == "Trinity"


def test_rerank_word_boundary_match() -> None:
    """'God' should match 'Word of God' (whole-word) but not 'Goddess'."""
    sample = [
        {"title": "Goddess", "wol_url": "a", "docid": "1", "original_rank": 0, "score": 0.0},
        {"title": "Word of God", "wol_url": "b", "docid": "2", "original_rank": 1, "score": 0.0},
        {"title": "Idolatry", "wol_url": "c", "docid": "3", "original_rank": 2, "score": 0.0},
    ]
    ranked = _rerank_by_title_match(sample, "God")
    assert ranked[0]["title"] == "Word of God"
    assert ranked[0]["score"] == 60.0  # whole-word match
    # 'Goddess' contains 'god' as substring but not as word → score 40
    goddess = next(r for r in ranked if r["title"] == "Goddess")
    assert goddess["score"] == 40.0
