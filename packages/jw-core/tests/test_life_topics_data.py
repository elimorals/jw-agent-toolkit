"""Tests for jw_core.data.life_topics — registry + alias resolution."""

from __future__ import annotations

import pytest

from jw_core.data.life_topics import REGISTRY, LifeTopic, resolve_topic


def test_registry_has_expected_topics() -> None:
    ids = {t.topic_id for t in REGISTRY}
    assert {
        "anxiety",
        "grief",
        "marriage_conflict",
        "depression_signs",
        "addictions",
        "doubts_in_faith",
        "parenting",
        "loneliness",
        "conflict_with_brother",
    } <= ids


def test_every_topic_has_three_languages() -> None:
    for t in REGISTRY:
        assert {"en", "es", "pt"} <= set(t.labels.keys()), f"{t.topic_id} missing labels"
        assert {"en", "es", "pt"} <= set(t.aliases.keys()), f"{t.topic_id} missing aliases"


def test_family_is_sensitive_or_general() -> None:
    for t in REGISTRY:
        assert t.family in {"sensitive", "general"}


def test_sensitive_set_matches_spec() -> None:
    sensitive = {t.topic_id for t in REGISTRY if t.family == "sensitive"}
    assert sensitive == {
        "anxiety",
        "grief",
        "marriage_conflict",
        "depression_signs",
        "addictions",
        "doubts_in_faith",
    }


def test_resolve_topic_by_canonical_label_es() -> None:
    topic = resolve_topic("Ansiedad", language="es")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_by_alias_en() -> None:
    topic = resolve_topic("worry", language="en")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_accent_insensitive_pt() -> None:
    topic = resolve_topic("solidao", language="pt")
    assert topic is not None
    assert topic.topic_id == "loneliness"


def test_resolve_topic_cross_language_fallback() -> None:
    # User typed Spanish word but said language=en — still resolves.
    topic = resolve_topic("ansiedad", language="en")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_unknown_returns_none() -> None:
    assert resolve_topic("qwertypotato", language="en") is None


def test_each_topic_has_at_least_one_anchor_and_query() -> None:
    for t in REGISTRY:
        assert t.topic_anchors, f"{t.topic_id} has no topic_anchors"
        assert t.search_query, f"{t.topic_id} has empty search_query"


def test_life_topic_dataclass_is_frozen() -> None:
    t = REGISTRY[0]
    with pytest.raises(Exception):  # FrozenInstanceError
        t.topic_id = "x"  # type: ignore[misc]
