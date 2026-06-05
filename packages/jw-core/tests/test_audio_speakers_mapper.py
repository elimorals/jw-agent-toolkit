"""SpeakerNameMapper: cosine similarity matching."""

from __future__ import annotations

import numpy as np

from jw_core.audio.speakers.mapper import SpeakerNameMapper
from jw_core.audio.speakers.voiceprint_store import Voiceprint, VoiceprintStore


def test_match_returns_closest_voiceprint(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    pablo_emb = np.array([1.0, 0.0, 0.0] + [0.0] * 189, dtype=np.float32)
    juan_emb = np.array([0.0, 1.0, 0.0] + [0.0] * 189, dtype=np.float32)
    store.save(Voiceprint(name="Pablo", embedding=pablo_emb, enrolled_at_iso="2026-06-05T10:00:00Z"))
    store.save(Voiceprint(name="Juan", embedding=juan_emb, enrolled_at_iso="2026-06-05T10:00:00Z"))

    mapper = SpeakerNameMapper(store=store, similarity_threshold=0.5)
    # Query close to pablo
    query = np.array([0.9, 0.1, 0.0] + [0.0] * 189, dtype=np.float32)
    name = mapper.identify(query)
    assert name == "Pablo"


def test_match_below_threshold_returns_none(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    pablo_emb = np.array([1.0, 0.0, 0.0] + [0.0] * 189, dtype=np.float32)
    store.save(Voiceprint(name="Pablo", embedding=pablo_emb, enrolled_at_iso="2026-06-05T10:00:00Z"))

    mapper = SpeakerNameMapper(store=store, similarity_threshold=0.99)
    query = np.array([0.0, 0.0, 1.0] + [0.0] * 189, dtype=np.float32)  # orthogonal
    assert mapper.identify(query) is None


def test_no_voiceprints_returns_none(tmp_path):
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    mapper = SpeakerNameMapper(store=store)
    query = np.random.randn(192).astype(np.float32)
    assert mapper.identify(query) is None


def test_zero_norm_query_does_not_crash(tmp_path):
    """Defensive: a zero-vector embedding should not raise."""
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    pablo_emb = np.array([1.0, 0.0, 0.0] + [0.0] * 189, dtype=np.float32)
    store.save(Voiceprint(name="Pablo", embedding=pablo_emb, enrolled_at_iso="2026-06-05T10:00:00Z"))
    mapper = SpeakerNameMapper(store=store, similarity_threshold=0.5)
    zero = np.zeros(192, dtype=np.float32)
    assert mapper.identify(zero) is None


def test_identify_with_short_embeddings(tmp_path):
    """Mapper works with any embedding dim — not hardcoded to 192."""
    store = VoiceprintStore(db_path=tmp_path / "vp.db")
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    store.save(Voiceprint(name="A", embedding=a, enrolled_at_iso="2026-06-05T10:00:00Z"))
    store.save(Voiceprint(name="B", embedding=b, enrolled_at_iso="2026-06-05T10:00:00Z"))
    mapper = SpeakerNameMapper(store=store, similarity_threshold=0.5)
    assert mapper.identify(np.array([0.95, 0.05], dtype=np.float32)) == "A"
    assert mapper.identify(np.array([0.05, 0.95], dtype=np.float32)) == "B"
