"""Tests for the personalization module (Module 12)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from jw_core.personalization import (
    TONE_TEMPLATES,
    MemoryEntry,
    SessionMemory,
    UserProfile,
    UserProfileStore,
    adjust_tone,
    easy_read,
    high_contrast_palette,
)


def _tmp_db() -> Path:
    return Path(tempfile.mkdtemp()) / "p.db"


# ── Profile ─────────────────────────────────────────────────────────────


def test_profile_default_minor_logic() -> None:
    p = UserProfile(assignments=["youth"])
    assert p.is_minor


def test_profile_store_roundtrip() -> None:
    path = _tmp_db()
    with UserProfileStore(path) as s:
        s.upsert(UserProfile(user_id="alex", language="es", assignments=["pioneer"], tone="casual"))
        loaded = s.get("alex")
    assert loaded.language == "es"
    assert loaded.tone == "casual"
    assert loaded.assignments == ["pioneer"]


def test_profile_store_returns_default_for_unknown() -> None:
    path = _tmp_db()
    with UserProfileStore(path) as s:
        p = s.get("missing")
    assert p.user_id == "missing"
    assert p.language == "en"


# ── Memory ──────────────────────────────────────────────────────────────


def test_memory_append_and_recent_ordering() -> None:
    path = _tmp_db()
    with SessionMemory(path) as mem:
        mem.add(MemoryEntry(user_id="alex", kind="topic", text="Trinity"))
        mem.add(MemoryEntry(user_id="alex", kind="verse_ref", text="John 1:1"))
        recent = mem.recent("alex", limit=10)
    assert recent[0].text == "John 1:1"  # most recent first
    assert recent[1].text == "Trinity"


def test_memory_kind_filter() -> None:
    path = _tmp_db()
    with SessionMemory(path) as mem:
        mem.add(MemoryEntry(user_id="alex", kind="topic", text="A"))
        mem.add(MemoryEntry(user_id="alex", kind="open_question", text="Q?"))
        only_q = mem.recent("alex", kinds=["open_question"])
    assert len(only_q) == 1
    assert only_q[0].kind == "open_question"


def test_memory_clear_per_user() -> None:
    path = _tmp_db()
    with SessionMemory(path) as mem:
        mem.add(MemoryEntry(user_id="a", kind="topic", text="x"))
        mem.add(MemoryEntry(user_id="b", kind="topic", text="y"))
        mem.clear("a")
        assert mem.recent("a") == []
        assert len(mem.recent("b")) == 1


# ── Tone ────────────────────────────────────────────────────────────────


def test_tone_templates_localized() -> None:
    for tone in ("formal", "casual", "easy_read"):
        for lang in ("en", "es", "pt"):
            assert TONE_TEMPLATES[tone][lang]


def test_adjust_tone_keeps_original_text() -> None:
    out = adjust_tone("hello", target_tone="casual", language="es")
    assert "<<TONE_DIRECTIVE>>" in out
    assert "hello" in out


# ── Accessibility ──────────────────────────────────────────────────────


def test_easy_read_shortens_long_sentences() -> None:
    # Need >21 words to trigger chunking.
    text = (
        "This is a very long sentence that goes on and on for many words to test "
        "the chunking behaviour of the easy read helper across multiple breakpoints."
    )
    out = easy_read(text, language="en")
    assert out.count(".") >= 2


def test_easy_read_swaps_complex_words_es() -> None:
    text = "Sin embargo, debemos demostrar amor."
    out = easy_read(text, language="es")
    assert "mostrar" in out
    assert "pero" in out
    assert "Sin embargo" not in out


def test_palette_has_six_keys() -> None:
    p = high_contrast_palette("dark")
    assert set(p.keys()) == {"background", "foreground", "accent", "muted", "danger", "success"}


def test_palette_unknown_falls_back_to_dark() -> None:
    p = high_contrast_palette("klingon")
    assert p["background"] == "#000000"
