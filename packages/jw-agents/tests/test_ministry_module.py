"""Tests for the ministry module (Module 2): objections + revisits + lookups."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from jw_agents.presentation_builder import PROFILES, list_audiences, presentation_builder
from jw_agents.reverse_citation_lookup import _bigram_overlap, _normalize
from jw_agents.revisit_tracker import Revisit, RevisitStore, plan_next_visit
from jw_core.data.objections import CATALOG, find_objection, list_objections

# ── Objection catalog tests ──────────────────────────────────────────────


def test_catalog_contains_core_objections() -> None:
    keys = {o.key for o in CATALOG}
    for must in ("trinity", "hell", "soul_immortal", "cross", "blood", "contradictions"):
        assert must in keys, f"core objection {must!r} missing"


def test_find_objection_english_keywords() -> None:
    obj = find_objection("I don't get the Trinity teaching", language="en")
    assert obj is not None and obj.key == "trinity"


def test_find_objection_spanish_keywords() -> None:
    obj = find_objection("¿Cree usted en la trinidad?", language="es")
    assert obj is not None and obj.key == "trinity"


def test_find_objection_returns_none_on_miss() -> None:
    assert find_objection("favorite colour?", language="en") is None


def test_objection_label_falls_back_to_english() -> None:
    obj = next(o for o in CATALOG if o.key == "hell")
    assert obj.label("en").startswith("Doesn't")
    assert obj.label("zz") == obj.label("en")  # fallback


def test_list_objections_carries_anchors() -> None:
    items = list_objections("en")
    assert items
    for it in items:
        assert "label" in it
        assert "topic_anchors" in it and isinstance(it["topic_anchors"], list)


# ── Reverse citation lookup helpers ──────────────────────────────────────


def test_normalize_removes_punctuation() -> None:
    assert _normalize("Hello, world!") == "hello world"
    assert _normalize("¡Hola, mundo!") == "hola mundo"


def test_bigram_overlap_exact() -> None:
    a = "the joy of jehovah"
    b = "now the joy of jehovah is our stronghold"
    assert _bigram_overlap(a, b) == 1.0


def test_bigram_overlap_partial() -> None:
    a = "the joy of god"
    b = "the joy of jehovah is your strength"
    score = _bigram_overlap(a, b)
    assert 0 < score < 1


def test_bigram_overlap_zero_on_disjoint() -> None:
    assert _bigram_overlap("the joy", "completely different") == 0.0


# ── Revisit tracker tests ────────────────────────────────────────────────


def _tmp_store_path() -> Path:
    return Path(tempfile.mkdtemp()) / "ministry.db"


def test_revisit_store_upsert_get() -> None:
    path = _tmp_store_path()
    with RevisitStore(path) as store:
        store.upsert(
            Revisit(
                interest_id="alex",
                name_alias="Alex",
                language="en",
                last_topic="Trinity",
                notes="Asked about John 1:1",
                next_visit_iso="2026-07-01",
            )
        )
        retrieved = store.get("alex")
    assert retrieved is not None
    assert retrieved.name_alias == "Alex"
    assert retrieved.last_topic == "Trinity"
    assert retrieved.created_at_unix > 0


def test_revisit_store_updates_overwrite() -> None:
    path = _tmp_store_path()
    with RevisitStore(path) as store:
        store.upsert(Revisit(interest_id="x", name_alias="A", last_topic="Hell"))
        store.upsert(Revisit(interest_id="x", name_alias="A", last_topic="Trinity"))
        assert store.get("x").last_topic == "Trinity"


def test_revisit_due_filter() -> None:
    path = _tmp_store_path()
    with RevisitStore(path) as store:
        store.upsert(Revisit(interest_id="a", next_visit_iso="2026-06-15"))
        store.upsert(Revisit(interest_id="b", next_visit_iso="2026-08-01"))
        due = store.due(on_or_before="2026-06-30")
    ids = {r.interest_id for r in due}
    assert ids == {"a"}


def test_revisit_search() -> None:
    path = _tmp_store_path()
    with RevisitStore(path) as store:
        store.upsert(Revisit(interest_id="a", name_alias="Bob", notes="Loves John 3:16"))
        store.upsert(Revisit(interest_id="b", name_alias="Eve", notes="Asks about Genesis"))
        hits = store.search("John")
    assert len(hits) == 1 and hits[0].interest_id == "a"


def test_revisit_delete() -> None:
    path = _tmp_store_path()
    with RevisitStore(path) as store:
        store.upsert(Revisit(interest_id="a", name_alias="A"))
        assert store.delete("a") is True
        assert store.get("a") is None
        assert store.delete("a") is False


def test_plan_next_visit_localized() -> None:
    rev = Revisit(interest_id="x", last_topic="prayer", language="es", next_visit_iso="2026-07-01")
    plan = plan_next_visit(rev, language="es")
    assert "prayer" in plan["warm_up_question"]
    assert plan["intro"].startswith("Cuando regrese")


# ── Presentation builder (no network) ────────────────────────────────────


def test_presentation_builder_lists_audiences() -> None:
    items = list_audiences("en")
    keys = {a["key"] for a in items}
    assert {"catholic", "evangelical", "atheist", "young", "muslim", "struggling_grief"} <= keys


def test_presentation_builder_for_atheist_runs_offline() -> None:
    result = asyncio.run(presentation_builder("atheist", language="E"))
    assert result.metadata["audience"] == "atheist"
    assert result.metadata["common_ground"]
    assert result.findings, "Should always emit scripture anchors"


def test_presentation_builder_unknown_audience_warns() -> None:
    result = asyncio.run(presentation_builder("klingon", language="E"))
    assert result.warnings
    assert "Unknown audience" in result.warnings[0]


# ── Sanity: every CATALOG entry has at least 1 scripture anchor ──────────


def test_every_objection_has_anchor() -> None:
    for o in CATALOG:
        assert o.scripture_anchors, f"{o.key!r} missing scripture anchors"


def test_every_audience_profile_has_scriptures() -> None:
    for key, profile in PROFILES.items():
        assert profile.suggested_scriptures, f"{key!r} profile missing scriptures"
